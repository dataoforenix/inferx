from __future__ import annotations

from fastapi.testclient import TestClient

from app.factory import create_app
from app.rate_limit import RateLimiter
from app.schemas import ErrorResponse
from tests.conftest import FakeLLM


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_limiter_allows_up_to_limit_then_blocks_with_retry_after():
    clock = Clock()
    limiter = RateLimiter(3, clock=clock)
    assert [limiter.check("ip")[0] for _ in range(3)] == [True, True, True]
    allowed, retry_after = limiter.check("ip")
    assert not allowed and retry_after == 60
    clock.now += 45
    assert limiter.check("ip") == (False, 15)


def test_window_slides():
    clock = Clock()
    limiter = RateLimiter(2, clock=clock)
    limiter.check("ip")
    clock.now += 30
    limiter.check("ip")
    clock.now += 31  # first hit is now older than 60 s
    assert limiter.check("ip")[0] is True
    assert limiter.check("ip")[0] is False


def test_clients_are_independent_and_zero_disables():
    limiter = RateLimiter(1, clock=Clock())
    assert limiter.check("a")[0] and limiter.check("b")[0] and not limiter.check("a")[0]
    off = RateLimiter(0)
    assert not off.enabled and all(off.check("a")[0] for _ in range(100))


def test_api_returns_429_with_standard_body(make_settings):
    c = TestClient(create_app(make_settings(rate_limit_per_minute=2), llm=FakeLLM()))
    assert c.post("/api/analyze", data={"text": "cup"}).status_code == 200
    assert c.post("/api/analyze/confirm", json={"category_id": "led_lamps"}).status_code == 200  # shared budget
    r = c.post("/api/analyze", data={"text": "cup"})
    assert r.status_code == 429
    body = ErrorResponse.model_validate(r.json())
    assert body.error.code == "rate_limited" and body.error.request_id == r.headers["X-Request-ID"]
    assert 1 <= int(r.headers["Retry-After"]) <= 60


def test_other_endpoints_are_not_limited(make_settings):
    c = TestClient(create_app(make_settings(rate_limit_per_minute=1), llm=FakeLLM()))
    for _ in range(5):
        assert c.get("/api/health").status_code == 200
        assert c.get("/api/categories").status_code == 200
        assert c.post("/api/whatif", json={"category_id": "led_lamps"}).status_code == 200


def test_disabled_by_default_in_tests(llm_client):
    assert all(llm_client.post("/api/analyze", data={"text": "cup"}).status_code == 200 for _ in range(40))


def test_setting_default_and_override(monkeypatch):
    from app.config import load_settings

    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "")
    assert load_settings().rate_limit_per_minute == 30
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "0")
    assert load_settings().rate_limit_per_minute == 0
