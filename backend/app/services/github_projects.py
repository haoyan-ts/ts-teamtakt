from __future__ import annotations

import httpx
from fastapi import HTTPException, status

from app.db.schemas.project import GitHubAvailableProjectItem

# GitHub GraphQL endpoint — hardcoded, never derived from user input (OWASP A10)
_GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"

# Viewer personal projects + first page of org projects in one query.
# NOTE: Org project pagination (>100 projects per org) is not implemented;
# this returns only the first 100 projects per org (known limitation).
_PROJECTS_QUERY = """
query($cursor: String) {
  viewer {
    projectsV2(first: 100, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        id
        number
        title
        url
        owner {
          ... on User { login }
          ... on Organization { login }
        }
      }
    }
    organizations(first: 100) {
      nodes {
        projectsV2(first: 100) {
          nodes {
            id
            number
            title
            url
            owner {
              ... on Organization { login }
            }
          }
        }
      }
    }
  }
}
"""


async def fetch_available_github_projects(
    github_token: str,
) -> list[GitHubAvailableProjectItem]:
    """Return all GitHub Projects V2 accessible to the user identified by *github_token*.

    Paginates through the viewer's personal projects. Org projects are fetched
    for the first page only (first 100 per org).

    Raises ``HTTPException(403)`` if the token is invalid or revoked.
    Raises ``HTTPException(502)`` if GitHub returns unexpected GraphQL errors.
    """
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Content-Type": "application/json",
    }

    seen: set[str] = set()
    results: list[GitHubAvailableProjectItem] = []
    cursor: str | None = None

    async with httpx.AsyncClient(timeout=15.0) as client:
        while True:
            payload: dict = {"query": _PROJECTS_QUERY, "variables": {"cursor": cursor}}
            response = await client.post(
                _GITHUB_GRAPHQL_URL, json=payload, headers=headers
            )

            if response.status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="GitHub token is invalid or revoked. Please re-link your GitHub account.",
                )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"GitHub API returned unexpected status {response.status_code}",
                )

            data = response.json()

            if "errors" in data:
                error_msg = "; ".join(
                    e.get("message", "unknown") for e in data["errors"]
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"GitHub GraphQL error: {error_msg}",
                )

            viewer = data["data"]["viewer"]

            # Collect personal projects from this page
            for node in viewer["projectsV2"]["nodes"]:
                node_id: str = node["id"]
                if node_id not in seen:
                    seen.add(node_id)
                    results.append(
                        GitHubAvailableProjectItem(
                            node_id=node_id,
                            number=node["number"],
                            title=node["title"],
                            owner_login=node["owner"]["login"],
                            url=node["url"],
                        )
                    )

            # Collect org projects (first page only — no further pagination)
            if cursor is None:
                for org in viewer["organizations"]["nodes"]:
                    for node in org["projectsV2"]["nodes"]:
                        node_id = node["id"]
                        if node_id not in seen:
                            seen.add(node_id)
                            results.append(
                                GitHubAvailableProjectItem(
                                    node_id=node_id,
                                    number=node["number"],
                                    title=node["title"],
                                    owner_login=node["owner"]["login"],
                                    url=node["url"],
                                )
                            )

            page_info = viewer["projectsV2"]["pageInfo"]
            if not page_info["hasNextPage"]:
                break
            cursor = page_info["endCursor"]

    return results
