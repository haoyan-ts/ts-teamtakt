"""
In-memory OAuth state / nonce store.

Holds PKCE code_verifier and optional user_id keyed by the random ``state``
parameter exchanged with Microsoft during the auth code flow.

Entries expire after TTL_MINUTES; expiry is checked lazily on every
``consume_state`` call (no background thread required for single-process).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TypedDict

TTL_MINUTES = 10

_store: dict[str, _Entry] = {}


class _Entry(TypedDict):
    code_verifier: str
    user_id: str | None
    created_at: datetime


def store_state(
    state: str,
    code_verifier: str,
    user_id: str | None = None,
) -> None:
    """Persist a new state entry."""
    _store[state] = _Entry(
        code_verifier=code_verifier,
        user_id=user_id,
        created_at=datetime.now(UTC),
    )


def consume_state(state: str) -> _Entry | None:
    """
    Remove and return the entry for *state*.

    Returns ``None`` if the state is unknown or has expired.
    """
    entry = _store.pop(state, None)
    if entry is None:
        return None
    age = datetime.now(UTC) - entry["created_at"]
    if age > timedelta(minutes=TTL_MINUTES):
        return None
    return entry
