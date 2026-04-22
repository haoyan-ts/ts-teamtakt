"""
Microsoft Graph API Teams channel publish service.

Posts weekly report summaries to a team's MS Teams channel from
the member's own MS365 account via delegated ChannelMessage.Send permission.

Token refresh flow follows the same pattern as graph_mail.py.
Private fields (day_load, blocker free-text) must be stripped before
calling build_teams_message — apply visibility.py filtering at the call site.
"""

from __future__ import annotations

import logging

import httpx

from app.services.graph_auth import refresh_graph_token as _refresh

logger = logging.getLogger(__name__)

_GRAPH_POST_URL = (
    "https://graph.microsoft.com/v1.0/teams/{teams_team_id}"
    "/channels/{teams_channel_id}/messages"
)

_TEAMS_SCOPE = "https://graph.microsoft.com/ChannelMessage.Send offline_access"


async def refresh_graph_token(refresh_token: str) -> tuple[str, str]:
    """
    Exchange a refresh token for a new access + refresh token pair.
    Returns (access_token, new_refresh_token).
    Raises RuntimeError on failure.
    """
    return await _refresh(refresh_token, _TEAMS_SCOPE)


async def post_channel_message(
    *,
    access_token: str,
    teams_team_id: str,
    teams_channel_id: str,
    html_body: str,
) -> None:
    """
    Post an HTML message to a Teams channel via Graph API.
    Raises RuntimeError on failure.
    """
    url = _GRAPH_POST_URL.format(
        teams_team_id=teams_team_id,
        teams_channel_id=teams_channel_id,
    )
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={"body": {"contentType": "html", "content": html_body}},
        )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Graph Teams post failed [{resp.status_code}]: {resp.text}")


def build_teams_message(
    *,
    member_name: str,
    week_start: str,
    week_end: str,
    effort_summary: dict[str, int],
    report_url: str,
) -> str:
    """
    Build an HTML message body for Teams channel posting.

    Only receives pre-filtered data — private fields (day_load, blocker free-text)
    must be stripped by the caller before passing effort_summary.

    Args:
        member_name: Display name of the team member.
        week_start: ISO date string (YYYY-MM-DD) for Monday.
        week_end: ISO date string (YYYY-MM-DD) for Sunday.
        effort_summary: Category-name → effort mapping (already filtered).
        report_url: Deep link to the full weekly report in the app.
    """
    effort_rows = "".join(
        f"<tr><td>{cat}</td><td>{pts}</td></tr>"
        for cat, pts in sorted(effort_summary.items(), key=lambda x: -x[1])
    )
    effort_table = (
        f"<table><thead><tr><th>Category</th><th>Effort (pts)</th></tr></thead>"
        f"<tbody>{effort_rows}</tbody></table>"
        if effort_rows
        else "<p>No effort data recorded.</p>"
    )

    return (
        f"<h3>週報 — {member_name}</h3>"
        f"<p><strong>Week:</strong> {week_start} – {week_end}</p>"
        f"<h4>Effort Summary</h4>"
        f"{effort_table}"
        f'<p><a href="{report_url}">View full report</a></p>'
    )
