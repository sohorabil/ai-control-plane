"""Unit tests for app.rate_limit's threshold logic, against a fake Redis
client instead of a live one — keeps this test fast and dependency-free for
CI, while still proving the actual fixed-window counting logic is correct
(off-by-one at the limit boundary is the easiest bug to introduce here).
"""

import pytest
from fastapi import HTTPException

import app.rate_limit as rate_limit


class _FakeRedis:
    def __init__(self):
        self._counts = {}

    def incr(self, key):
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key]

    def expire(self, key, seconds):
        pass  # not needed for this test's assertions


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(rate_limit, "redis_client", fake)
    return fake


def test_requests_under_limit_are_allowed():
    for _ in range(rate_limit.LIMIT):
        rate_limit.check_rate_limit("test-app")  # should not raise


def test_request_over_limit_is_blocked():
    for _ in range(rate_limit.LIMIT):
        rate_limit.check_rate_limit("test-app")

    with pytest.raises(HTTPException) as exc_info:
        rate_limit.check_rate_limit("test-app")
    assert exc_info.value.status_code == 429


def test_different_apps_have_independent_limits():
    for _ in range(rate_limit.LIMIT):
        rate_limit.check_rate_limit("app-a")

    rate_limit.check_rate_limit("app-b")  # should not raise, separate counter
