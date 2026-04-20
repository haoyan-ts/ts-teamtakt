from __future__ import annotations

import re

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.category import Category
from app.db.schemas.task import TaskAutoFillResponse

_GITHUB_ISSUE_RE = re.compile(r"^https://github\.com/([^/]+)/([^/]+)/issues/(\d+)$")


async def fetch_github_issue(url: str, github_token: str | None = None) -> dict:
    """Fetch a GitHub Issue by URL via the GitHub REST API.

    Raises ValueError for invalid URLs or non-2xx API responses.
    """
    m = _GITHUB_ISSUE_RE.match(url.strip())
    if not m:
        raise ValueError("Invalid GitHub issue URL")
    owner, repo, number = m.group(1), m.group(2), m.group(3)

    api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{number}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    async with httpx.AsyncClient() as client:
        resp = await client.get(api_url, headers=headers)

    if resp.status_code != 200:
        raise ValueError(f"GitHub API error: {resp.status_code}")

    return resp.json()


async def map_to_task_fields(
    issue: dict,
    db: AsyncSession,
    github_field_map: dict | None = None,
) -> TaskAutoFillResponse:
    """Map a raw GitHub Issue dict to TaskAutoFillResponse.

    Matches first label name (case-insensitive) against active categories.
    If github_field_map contains an "Insight" key, the corresponding custom
    field value from the issue is used to populate insight (capped at 500 chars).
    """
    title: str | None = issue.get("title")
    description: str | None = issue.get("body")
    label_names = [lbl["name"].lower() for lbl in issue.get("labels", [])]

    category_id = None
    if label_names:
        result = await db.execute(select(Category).where(Category.is_active.is_(True)))
        categories = result.scalars().all()
        for cat in categories:
            if cat.name.lower() in label_names:
                category_id = cat.id
                break

    # Resolve insight from github_field_map if configured
    insight: str | None = None
    if github_field_map and "Insight" in github_field_map:
        field_key = github_field_map["Insight"]
        raw = issue.get(field_key)
        if isinstance(raw, str) and raw:
            insight = raw[:500]

    return TaskAutoFillResponse(
        title=title,
        description=description,
        category_id=category_id,
        insight=insight,
    )
