# TODO: implement in follow-up GitHub issue
# GitHub Issue auto-fill for Task creation — see issue filed after #11.
# The functions below are stubs that signal "not yet implemented".
# The /tasks/autofill endpoint returns HTTP 501 until this is complete.

from __future__ import annotations

from app.db.schemas.task import TaskAutoFillResponse  # re-exported for callers


async def fetch_github_issue(url: str, github_token: str | None = None) -> dict:
    """Fetch a GitHub Issue by URL via the GitHub REST API.

    Not yet implemented. Raises NotImplementedError until the follow-up issue
    is resolved.
    """
    raise NotImplementedError("GitHub auto-fill not yet implemented")


async def map_to_task_fields(
    issue: dict,
    project_item: dict | None,
    field_map: dict,
) -> TaskAutoFillResponse:
    """Map raw GitHub Issue + Project item fields to TaskAutoFillResponse.

    Not yet implemented. Raises NotImplementedError until the follow-up issue
    is resolved.
    """
    raise NotImplementedError("GitHub auto-fill not yet implemented")
