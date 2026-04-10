"""
Export endpoints for daily records and task entries.

Member:  GET /export/my-records?start_date=&end_date=&format=csv|xlsx
Leader:  GET /export/team/{team_id}?start_date=&end_date=&format=csv|xlsx
Admin:   GET /export/bulk?format=csv|xlsx

CSV: flat rows (one per task entry, record fields repeated).
XLSX member/leader: Sheet 1 = records, Sheet 2 = task entries.
XLSX bulk: one sheet per table.

Exports only data the requester is permitted to see.
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import date

import openpyxl
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.engine import get_db
from app.db.models.absence import Absence
from app.db.models.category import BlockerType, Category, CategorySubType
from app.db.models.daily_record import DailyRecord
from app.db.models.project import Project
from app.db.models.task_entry import TaskEntry
from app.db.models.team import Team, TeamMembership
from app.db.models.user import User

router = APIRouter(prefix="/export", tags=["export"])

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _team_member_ids(team_id: uuid.UUID, db: AsyncSession) -> list[uuid.UUID]:
    """Return the user_ids of all current (left_at=NULL) team members."""
    r = await db.execute(
        select(TeamMembership.user_id).where(
            TeamMembership.team_id == team_id,
            TeamMembership.left_at.is_(None),
        )
    )
    return list(r.scalars().all())


async def _fetch_records_with_tasks(
    user_ids: list[uuid.UUID],
    start_date: date | None,
    end_date: date | None,
    db: AsyncSession,
) -> tuple[list[DailyRecord], list[TaskEntry]]:
    """Fetch DailyRecords and their TaskEntries for the given users and range."""
    q = select(DailyRecord).where(DailyRecord.user_id.in_(user_ids))
    if start_date:
        q = q.where(DailyRecord.record_date >= start_date)
    if end_date:
        q = q.where(DailyRecord.record_date <= end_date)
    q = q.order_by(DailyRecord.user_id, DailyRecord.record_date)
    r = await db.execute(q)
    records = list(r.scalars().all())

    record_ids = [rec.id for rec in records]
    task_rows: list[TaskEntry] = []
    if record_ids:
        rt = await db.execute(
            select(TaskEntry)
            .where(TaskEntry.daily_record_id.in_(record_ids))
            .order_by(TaskEntry.daily_record_id, TaskEntry.sort_order)
        )
        task_rows = list(rt.scalars().all())

    return records, task_rows


async def _build_lookup_maps(db: AsyncSession) -> dict:
    """
    Return dicts: user_map, category_map, subtype_map, project_map, blocker_type_map.
    All keyed by UUID → display string.
    """
    users = (await db.execute(select(User))).scalars().all()
    cats = (await db.execute(select(Category))).scalars().all()
    subtypes = (await db.execute(select(CategorySubType))).scalars().all()
    projs = (await db.execute(select(Project))).scalars().all()
    blocker_types = (await db.execute(select(BlockerType))).scalars().all()

    return {
        "users": {u.id: u.display_name for u in users},
        "categories": {c.id: c.name for c in cats},
        "subtypes": {s.id: s.name for s in subtypes},
        "projects": {p.id: p.name for p in projs},
        "blocker_types": {bt.id: bt.name for bt in blocker_types},
    }


# ---------------------------------------------------------------------------
# CSV / XLSX builders
# ---------------------------------------------------------------------------

_RECORD_HEADERS = [
    "record_id",
    "user",
    "record_date",
    "day_load",
    "day_note",
]
_TASK_HEADERS = [
    "task_id",
    "record_id",
    "category",
    "sub_type",
    "project",
    "task_description",
    "effort",
    "status",
    "blocker_type",
    "blocker_text",
    "carried_from_id",
    "sort_order",
]


def _record_row(rec: DailyRecord, maps: dict, *, include_private: bool = True) -> list:
    return [
        str(rec.id),
        maps["users"].get(rec.user_id, str(rec.user_id)),
        str(rec.record_date),
        rec.day_load if include_private else "",
        rec.day_note or "",
    ]


def _task_row(task: TaskEntry, maps: dict, *, include_private: bool = True) -> list:
    return [
        str(task.id),
        str(task.daily_record_id),
        maps["categories"].get(task.category_id, str(task.category_id)),
        maps["subtypes"].get(task.sub_type_id, "") if task.sub_type_id else "",
        maps["projects"].get(task.project_id, str(task.project_id)),
        task.task_description,
        task.effort,
        task.status,
        (
            maps["blocker_types"].get(task.blocker_type_id, "")
            if task.blocker_type_id
            else ""
        ),
        (task.blocker_text or "") if include_private else "",
        str(task.carried_from_id) if task.carried_from_id else "",
        task.sort_order,
    ]


def _build_csv_flat(
    records: list[DailyRecord],
    tasks: list[TaskEntry],
    maps: dict,
    *,
    include_private: bool = True,
) -> bytes:
    """One row per task entry; record fields repeated. Records with no tasks get one row."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["task_id", "record_id"] + _RECORD_HEADERS + _TASK_HEADERS[2:])

    tasks_by_record: dict[uuid.UUID, list[TaskEntry]] = {}
    for t in tasks:
        tasks_by_record.setdefault(t.daily_record_id, []).append(t)

    for rec in records:
        rec_row = _record_row(rec, maps, include_private=include_private)
        rec_tasks = tasks_by_record.get(rec.id, [])
        if not rec_tasks:
            writer.writerow(
                ["", str(rec.id)] + rec_row + [""] * (len(_TASK_HEADERS) - 2)
            )
        else:
            for task in rec_tasks:
                task_part = _task_row(task, maps, include_private=include_private)[
                    2:
                ]  # skip task_id, record_id
                writer.writerow([str(task.id), str(rec.id)] + rec_row + task_part)

    return buf.getvalue().encode("utf-8-sig")  # BOM for Excel compatibility


def _build_xlsx_two_sheet(
    records: list[DailyRecord],
    tasks: list[TaskEntry],
    maps: dict,
    *,
    include_private: bool = True,
) -> bytes:
    """Sheet 1 = records, Sheet 2 = task entries."""
    wb = openpyxl.Workbook()
    ws_rec = wb.active
    assert ws_rec is not None
    ws_rec.title = "Records"
    ws_rec.append(_RECORD_HEADERS)
    for rec in records:
        ws_rec.append(_record_row(rec, maps, include_private=include_private))

    ws_task = wb.create_sheet("TaskEntries")
    ws_task.append(_TASK_HEADERS)
    for task in tasks:
        ws_task.append(_task_row(task, maps, include_private=include_private))

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _streaming_response(
    content: bytes, format: str, filename: str
) -> StreamingResponse:
    if format == "csv":
        media_type = "text/csv"
        disposition = f'attachment; filename="{filename}.csv"'
    else:
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        disposition = f'attachment; filename="{filename}.xlsx"'
    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": disposition},
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/my-records")
async def export_my_records(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export the current user's own daily records + task entries."""
    records, tasks = await _fetch_records_with_tasks(
        [current_user.id], start_date, end_date, db
    )
    maps = await _build_lookup_maps(db)

    if format == "csv":
        content = _build_csv_flat(records, tasks, maps, include_private=True)
    else:
        content = _build_xlsx_two_sheet(records, tasks, maps, include_private=True)

    return _streaming_response(content, format, "my-records")


@router.get("/team/{team_id}")
async def export_team_records(
    team_id: uuid.UUID,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Export all team members' records (leaders and admins; private fields included).
    """
    if not (current_user.is_leader or current_user.is_admin):
        raise HTTPException(status_code=403, detail="Leaders and admins only.")

    # Leaders may only export their own team (or granted teams)
    if not current_user.is_admin:
        r = await db.execute(
            select(TeamMembership).where(
                TeamMembership.user_id == current_user.id,
                TeamMembership.team_id == team_id,
                TeamMembership.left_at.is_(None),
            )
        )
        if r.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=403,
                detail="You are not a leader of this team.",
            )

    member_ids = await _team_member_ids(team_id, db)
    if not member_ids:
        raise HTTPException(status_code=404, detail="Team not found or has no members.")

    records, tasks = await _fetch_records_with_tasks(
        member_ids, start_date, end_date, db
    )
    maps = await _build_lookup_maps(db)

    if format == "csv":
        content = _build_csv_flat(records, tasks, maps, include_private=True)
    else:
        content = _build_xlsx_two_sheet(records, tasks, maps, include_private=True)

    return _streaming_response(content, format, f"team-{team_id}-records")


@router.get("/bulk")
async def export_bulk(
    format: str = Query("xlsx", pattern="^(csv|xlsx)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Admin-only: export all tables for backup/migration.
    XLSX: one sheet per table.
    CSV: flat combined file (records + tasks).
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admins only.")

    users = list((await db.execute(select(User))).scalars().all())
    teams = list((await db.execute(select(Team))).scalars().all())
    records = list((await db.execute(select(DailyRecord))).scalars().all())
    tasks = list((await db.execute(select(TaskEntry))).scalars().all())
    absences = list((await db.execute(select(Absence))).scalars().all())
    categories = list((await db.execute(select(Category))).scalars().all())
    projects = list((await db.execute(select(Project))).scalars().all())
    bl_types = list((await db.execute(select(BlockerType))).scalars().all())

    if format == "csv":
        # Bulk CSV: just export records+tasks flat
        maps = await _build_lookup_maps(db)
        content = _build_csv_flat(records, tasks, maps, include_private=True)
        return _streaming_response(content, "csv", "bulk-export")

    # XLSX with one sheet per table
    wb = openpyxl.Workbook()

    def _sheet(title: str, headers: list[str], rows):
        ws = wb.create_sheet(title)
        ws.append(headers)
        for row in rows:
            ws.append(row)

    # Users sheet
    _sheet(
        "Users",
        [
            "id",
            "email",
            "display_name",
            "is_leader",
            "is_admin",
            "preferred_locale",
            "created_at",
        ],
        [
            [
                str(u.id),
                u.email,
                u.display_name,
                u.is_leader,
                u.is_admin,
                u.preferred_locale,
                str(u.created_at),
            ]
            for u in users
        ],
    )
    # Teams sheet
    _sheet(
        "Teams",
        ["id", "name", "created_at"],
        [[str(t.id), t.name, str(t.created_at)] for t in teams],
    )
    # Records sheet
    _sheet(
        "DailyRecords",
        ["id", "user_id", "record_date", "day_load", "day_note", "created_at"],
        [
            [
                str(r.id),
                str(r.user_id),
                str(r.record_date),
                r.day_load,
                r.day_note or "",
                str(r.created_at),
            ]
            for r in records
        ],
    )
    # Tasks sheet
    _sheet(
        "TaskEntries",
        [
            "id",
            "daily_record_id",
            "category_id",
            "sub_type_id",
            "project_id",
            "task_description",
            "effort",
            "status",
            "blocker_type_id",
            "blocker_text",
            "carried_from_id",
            "sort_order",
        ],
        [
            [
                str(t.id),
                str(t.daily_record_id),
                str(t.category_id),
                str(t.sub_type_id) if t.sub_type_id else "",
                str(t.project_id),
                t.task_description,
                t.effort,
                t.status,
                str(t.blocker_type_id) if t.blocker_type_id else "",
                t.blocker_text or "",
                str(t.carried_from_id) if t.carried_from_id else "",
                t.sort_order,
            ]
            for t in tasks
        ],
    )
    # Absences sheet
    _sheet(
        "Absences",
        ["id", "user_id", "record_date", "absence_type", "note"],
        [
            [
                str(a.id),
                str(a.user_id),
                str(a.record_date),
                a.absence_type,
                a.note or "",
            ]
            for a in absences
        ],
    )
    # Categories sheet
    _sheet(
        "Categories",
        ["id", "name", "is_active"],
        [[str(c.id), c.name, c.is_active] for c in categories],
    )
    # Projects sheet
    _sheet(
        "Projects",
        ["id", "name", "scope", "team_id", "is_active", "created_at"],
        [
            [
                str(p.id),
                p.name,
                p.scope,
                str(p.team_id) if p.team_id else "",
                p.is_active,
                str(p.created_at),
            ]
            for p in projects
        ],
    )
    # BlockerTypes sheet
    _sheet(
        "BlockerTypes",
        ["id", "name", "is_active"],
        [[str(bt.id), bt.name, bt.is_active] for bt in bl_types],
    )

    # Remove the default empty sheet
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]

    buf = io.BytesIO()
    wb.save(buf)
    return _streaming_response(buf.getvalue(), "xlsx", "bulk-export")
