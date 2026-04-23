from __future__ import annotations

import re

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.token_encryption import decrypt_token
from app.db.models.category import Category
from app.db.models.user import User
from app.db.schemas.task import TaskAutoFillResponse

_GITHUB_ISSUE_RE = re.compile(r"^https://github\.com/([^/]+)/([^/]+)/issues/(\d+)$")
# GitHub API base URL is hardcoded — never derived from user input (OWASP A10)
_GITHUB_API_BASE = "https://api.github.com"

# ---------------------------------------------------------------------------
# GitHub Project board status → teamtakt internal status
# Mapping is case-insensitive; unknown values fall back to "todo".
# ---------------------------------------------------------------------------
_GITHUB_STATUS_TO_TASK_STATUS: dict[str, str] = {
    "backlog": "todo",
    "sprint backlog": "todo",
    "in progress": "running",
    "in review": "running",
    "done": "done",
}


def map_github_status_to_task_status(github_status: str) -> str:
    """Map a GitHub Project board column name to a teamtakt TaskStatus value.

    Unknown/unrecognised column names default to ``"todo"``.
    """
    return _GITHUB_STATUS_TO_TASK_STATUS.get(github_status.strip().lower(), "todo")


class GitHubTokenRevokedError(Exception):
    """Raised when the stored GitHub token is invalid or revoked (HTTP 401)."""


async def resolve_github_token(user: User) -> str | None:
    """Return the best available GitHub token for *user*.

    Tries the user's linked token first; falls back to the shared env token.
    Returns ``None`` when no token is configured at all.
    """
    if user.github_access_token_enc:
        enc_key = settings.GITHUB_TOKEN_ENCRYPTION_KEY
        if enc_key and user.github_token_iv:
            return decrypt_token(
                user.github_access_token_enc, user.github_token_iv, enc_key
            )
        # Dev/local fallback — token stored plain when no key configured
        if not user.github_token_iv:
            return user.github_access_token_enc
    return settings.GITHUB_TOKEN


async def fetch_github_issue(
    url: str,
    github_token: str | None = None,
    user: User | None = None,
    db: AsyncSession | None = None,
) -> dict:
    """Fetch a GitHub Issue by URL via the GitHub REST API.

    If *user* is provided, attempts to use the user's linked token first,
    falling back to *github_token* then to the shared ``GITHUB_TOKEN`` env var.

    Raises ``ValueError`` for invalid URLs or non-2xx API responses.
    Raises ``GitHubTokenRevokedError`` if the stored user token is revoked,
    after clearing it from the database (caller must inform the user to re-link).
    """
    m = _GITHUB_ISSUE_RE.match(url.strip())
    if not m:
        raise ValueError("Invalid GitHub issue URL")
    owner, repo, number = m.group(1), m.group(2), m.group(3)

    api_url = f"{_GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{number}"

    # Resolve token: user-linked > explicit argument > shared env token
    resolved_token = github_token
    if user is not None:
        try:
            user_token = await resolve_github_token(user)
        except Exception:
            user_token = None
        if user_token:
            resolved_token = user_token

    headers = {"Accept": "application/vnd.github.v3+json"}
    if resolved_token:
        headers["Authorization"] = f"Bearer {resolved_token}"

    async with httpx.AsyncClient() as client:
        resp = await client.get(api_url, headers=headers)

    if resp.status_code == 401 and user is not None and user.github_access_token_enc:
        # The user's stored token is invalid or revoked — clear it
        if db is not None:
            user.github_access_token_enc = None
            user.github_token_iv = None
            user.github_login = None
            await db.commit()
        raise GitHubTokenRevokedError(
            "Your GitHub token has been revoked. Please re-link your GitHub account."
        )

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

    # Resolve github_status and derive teamtakt status
    github_status: str | None = None
    if github_field_map and "Status" in github_field_map:
        field_key = github_field_map["Status"]
        raw = issue.get(field_key)
        if isinstance(raw, str) and raw:
            github_status = raw
    derived_status = (
        map_github_status_to_task_status(github_status) if github_status else "todo"
    )

    return TaskAutoFillResponse(
        title=title,
        description=description,
        category_id=category_id,
        insight=insight,
        github_status=github_status,
        status=derived_status,
    )
