"""Unit tests for app.auth — pure logic only, no real database.

authenticate_app()/create_app() need a live Postgres connection (app.db
imports pgvector at module load time), so those two aren't unit-tested here;
they're covered by the real end-to-end checks each part already runs
against the actual running gateway. What's tested here is the logic that
doesn't need a database at all: hashing, and the allow-list check.
"""

import pytest
from fastapi import HTTPException

from app.auth import hash_key, check_provider_allowed


def test_hash_key_is_deterministic():
    assert hash_key("my-secret-key") == hash_key("my-secret-key")


def test_hash_key_differs_for_different_input():
    assert hash_key("key-one") != hash_key("key-two")


def test_hash_key_never_returns_the_raw_key():
    raw = "super-secret-app-key"
    assert hash_key(raw) != raw


class _FakeApp:
    def __init__(self, app_id, role, allowed_providers):
        self.app_id = app_id
        self.role = role
        self.allowed_providers = allowed_providers


def test_check_provider_allowed_passes_for_allowed_provider():
    app = _FakeApp("support-app", "support", ["mock", "vertex"])
    check_provider_allowed(app, "vertex")  # should not raise


def test_check_provider_allowed_blocks_disallowed_provider():
    app = _FakeApp("support-app", "support", ["mock", "vertex"])
    with pytest.raises(HTTPException) as exc_info:
        check_provider_allowed(app, "bedrock")
    assert exc_info.value.status_code == 403
    assert "support-app" in exc_info.value.detail
