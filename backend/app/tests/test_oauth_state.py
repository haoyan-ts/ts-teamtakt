"""
Unit tests for app/core/oauth_state.py.

Covers:
- Happy path: store then consume returns the entry
- Missing state returns None
- Expired entry (> TTL_MINUTES) returns None
- Consume is single-use (second call returns None)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from app.core import oauth_state
from app.core.oauth_state import TTL_MINUTES, consume_state, store_state


@pytest.fixture(autouse=True)
def _clear_store():
    """Isolate each test by resetting the module-level store."""
    oauth_state._store.clear()
    yield
    oauth_state._store.clear()


# ---------------------------------------------------------------------------
# 1. Happy path
# ---------------------------------------------------------------------------
def test_store_and_consume_returns_entry():
    store_state("state-abc", code_verifier="verifier-xyz")
    entry = consume_state("state-abc")
    assert entry is not None
    assert entry["code_verifier"] == "verifier-xyz"
    assert entry["user_id"] is None


def test_store_with_user_id():
    store_state("state-uid", code_verifier="verifier-123", user_id="user-42")
    entry = consume_state("state-uid")
    assert entry is not None
    assert entry["user_id"] == "user-42"


# ---------------------------------------------------------------------------
# 2. Missing state
# ---------------------------------------------------------------------------
def test_consume_missing_state_returns_none():
    result = consume_state("nonexistent-state")
    assert result is None


# ---------------------------------------------------------------------------
# 3. Expired entry
# ---------------------------------------------------------------------------
def test_consume_expired_state_returns_none():
    store_state("state-old", code_verifier="verifier-old")
    # Simulate time having advanced past TTL
    future = datetime.now(UTC) + timedelta(minutes=TTL_MINUTES + 1)
    with patch("app.core.oauth_state.datetime") as mock_dt:
        mock_dt.now.return_value = future
        result = consume_state("state-old")
    assert result is None


# ---------------------------------------------------------------------------
# 4. Consume is single-use
# ---------------------------------------------------------------------------
def test_consume_removes_entry():
    store_state("state-once", code_verifier="verifier-once")
    first = consume_state("state-once")
    second = consume_state("state-once")
    assert first is not None
    assert second is None


# ---------------------------------------------------------------------------
# 5. Exactly at TTL boundary (not yet expired)
# ---------------------------------------------------------------------------
def test_consume_at_ttl_boundary_is_valid():
    base_time = datetime.now(UTC)
    at_boundary = base_time + timedelta(minutes=TTL_MINUTES)
    with patch("app.core.oauth_state.datetime") as mock_dt:
        mock_dt.now.return_value = base_time
        store_state("state-boundary", code_verifier="verifier-boundary")
        mock_dt.now.return_value = at_boundary
        result = consume_state("state-boundary")
    assert result is not None
