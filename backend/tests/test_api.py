from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.data_store import load_categories
from app.factory import create_app
from app.schemas import CategoriesResponse, ErrorResponse, HealthResponse, WhatIfResponse
from tests.conftest import TEST_CSV


# --- health ---------------------------------------------------------------

def test_health_schema_and_degraded_without_llm(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = HealthResponse.model_validate(r.json())
    assert body.status == "degraded"
    assert body.llm_configured is False
    assert body.demo_mode is False
    assert body.categories_loaded == 5
    assert any("TODO_REAL_DATA" in w for w in body.data_warnings)
    assert body.request_id == r.headers["X-Request-ID"]


def test_health_ok_in_demo_mode(make_settings):
    r = TestClient(create_app(make_settings(demo_mode=True))).get("/api/health")
    assert r.json()["status"] == "ok"
    assert r.json()["demo_mode"] is True


def test_health_ok_with_key_and_key_never_exposed(make_settings):
    secret = "sk-ant-test-SECRET-123"
    settings = make_settings(openai_api_key=secret)
    assert secret not in repr(settings)
    r = TestClient(create_app(settings)).get("/api/health")
    assert r.json()["status"] == "ok"
    assert r.json()["llm_configured"] is True
    assert secret not in r.text


# --- categories -----------------------------------------------------------

def test_categories_match_csv(client):
    r = client.get("/api/categories")
    assert r.status_code == 200
    body = CategoriesResponse.model_validate(r.json())
    assert [c.category_id for c in body.categories] == load_categories(TEST_CSV).ids
    for c in body.categories:
        assert c.is_placeholder_data == (c.data_status == "TODO_REAL_DATA")


def test_categories_include_arabic_names(client):
    cats = client.get("/api/categories").json()["categories"]
    assert all(any("؀" <= ch <= "ۿ" for ch in c["name_ar"]) for c in cats)


# --- cross-cutting --------------------------------------------------------

def test_request_ids_are_unique(client):
    ids = {client.get("/api/health").headers["X-Request-ID"] for _ in range(5)}
    assert len(ids) == 5


def test_unknown_route_uses_error_schema(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404
    body = ErrorResponse.model_validate(r.json())
    assert body.error.code == "not_found"
    assert body.error.request_id == r.headers["X-Request-ID"]


def test_wrong_method_uses_error_schema(client):
    r = client.post("/api/categories")
    assert r.status_code == 405
    assert ErrorResponse.model_validate(r.json()).error.code == "method_not_allowed"


@pytest.mark.parametrize(("origin", "allowed"), [("http://localhost:5173", True), ("https://evil.example", False)])
def test_cors_respects_configured_origins(make_settings, origin, allowed):
    app = create_app(make_settings(cors_origins=["http://localhost:5173"]))
    r = TestClient(app).options(
        "/api/health", headers={"Origin": origin, "Access-Control-Request-Method": "GET"}
    )
    assert (r.headers.get("access-control-allow-origin") == origin) is allowed


def test_cors_wildcard(make_settings):
    app = create_app(make_settings(cors_origins=["*"]))
    r = TestClient(app).get("/api/health", headers={"Origin": "https://anything.example"})
    assert r.headers["access-control-allow-origin"] == "*"


# --- what-if --------------------------------------------------------------

def test_whatif_without_overrides_equals_baseline(client):
    r = client.post("/api/whatif", json={"category_id": "plastic_kitchenware"})
    assert r.status_code == 200
    body = WhatIfResponse.model_validate(r.json())
    assert body.baseline == body.scenario
    assert body.score_delta == 0
    assert body.request_id == r.headers["X-Request-ID"]


def test_whatif_applies_overrides(client):
    r = client.post("/api/whatif", json={
        "category_id": "glass_containers",
        "overrides": {"customs_pct": 0.5, "local_factories": 0},
    })
    assert r.status_code == 200
    body = WhatIfResponse.model_validate(r.json())
    assert body.scenario.cost.customs_pct == 0.5
    assert body.scenario.overrides_applied == {"customs_pct": 0.5, "local_factories": 0.0}
    assert body.score_delta > 0
    assert body.score_delta == round(body.scenario.score - body.baseline.score, 1)


def test_whatif_unknown_category(client):
    r = client.post("/api/whatif", json={"category_id": "spaceships"})
    assert r.status_code == 404
    assert ErrorResponse.model_validate(r.json()).error.code == "unknown_category"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"category_id": ""},
        {"category_id": "plastic_kitchenware", "overrides": {"customs_pct": 5}},
        {"category_id": "plastic_kitchenware", "overrides": {"local_cost_per_kg_est_usd": 0}},
        {"category_id": "plastic_kitchenware", "overrides": {"score": 10}},
        {"category_id": "plastic_kitchenware", "extra": True},
    ],
)
def test_whatif_rejects_invalid_requests(client, payload):
    r = client.post("/api/whatif", json=payload)
    assert r.status_code == 422
    body = ErrorResponse.model_validate(r.json())
    assert body.error.code == "validation_error" and body.error.details


def test_whatif_rejects_non_json(client):
    r = client.post("/api/whatif", content=b"not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 422


def test_app_refuses_to_start_on_invalid_csv(make_settings, csv_frame, write_csv):
    from app.data_store import DataValidationError

    bad = write_csv(csv_frame.iloc[:2])
    with pytest.raises(DataValidationError):
        create_app(make_settings(categories_csv=bad))


def test_whatif_shipping_override_does_not_change_score(client):
    r = client.post("/api/whatif", json={"category_id": "plastic_kitchenware", "overrides": {"shipping_pct": 1.5}})
    body = WhatIfResponse.model_validate(r.json())
    assert body.score_delta == 0 and body.scenario.cost.shipping_pct == 1.5
    assert any("information only" in n for n in body.scenario.notes)


def test_whatif_crosses_cost_gate_via_api(client):
    # led_lamps fixture: landed 17.5 x 1.05 = 18.375, local 18 -> MANUFACTURE.
    r = client.post("/api/whatif", json={"category_id": "led_lamps", "overrides": {"local_cost_per_kg_est_usd": 19}})
    body = WhatIfResponse.model_validate(r.json())
    assert body.baseline.verdict == "MANUFACTURE" and body.baseline.verdict_capped_by is None
    assert body.scenario.verdict == "MAYBE" and body.scenario.score == 5.9
    assert body.scenario.verdict_capped_by == "cost_gate"
