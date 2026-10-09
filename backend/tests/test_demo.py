from __future__ import annotations

import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.data_store import load_categories
from app.demo import PLACEHOLDER, DemoCache, image_fingerprint, keyword_in
from app.explanation import fallback_explanation, key_figures
from app.image_utils import prepare_image
from app.llm import LLMUnavailable
from app.factory import create_app
from app.pipeline import DEMO_WARNING, LIVE_FALLBACK_WARNING
from app.schemas import AnalyzeResponse, ErrorResponse, HealthResponse
from app.scoring import compute_report
from tests.conftest import TEST_CSV, TEST_DEMO_CACHE, FakeLLM

STORE = load_categories(TEST_CSV)


def ok(r) -> AnalyzeResponse:
    assert r.status_code == 200, r.text
    return AnalyzeResponse.model_validate(r.json())


def entry(id_, category_id, keywords, confidence=0.9, explanations=None, image_sha256=None):
    return {
        "id": id_, "generated_by": "pipeline", "generated_at": "2026-10-09T00:00:00+00:00", "model": "test",
        "example_input": {"text": keywords[0]}, "match_keywords": keywords, "image_sha256": image_sha256,
        "normalization": {
            "is_physical_product": True, "product_name_en": "Thing", "product_name_ar": "شيء",
            "description": "A thing.", "category_id": category_id, "confidence": confidence, "alternatives": [],
        },
        "explanations": explanations or {"en": None, "ar": None},
    }


@pytest.fixture
def cache_dir(tmp_path):
    def _make(*entries, extra_files=None):
        for e in entries:
            (tmp_path / f"{e['id']}.json").write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")
        for name, content in (extra_files or {}).items():
            (tmp_path / name).write_text(content, encoding="utf-8")
        return tmp_path

    return _make


# --- cache loading / matching ------------------------------------------------------

def test_shipped_cache_loads_and_is_marked_placeholder():
    cache = DemoCache.load(TEST_DEMO_CACHE, STORE.ids)
    assert len(cache.entries) == 7
    assert all(e.generated_by == PLACEHOLDER for e in cache.entries)
    assert all(e.explanations.get("en") is None for e in cache.entries)  # placeholders never fake AI text
    assert any("placeholders" in w for w in cache.warnings)
    covered = {e.normalization.category_id for e in cache.entries}
    assert set(STORE.ids) <= covered and "unsupported" in covered


def test_bad_files_are_skipped_with_warnings(cache_dir):
    d = cache_dir(entry("good", "led_lamps", ["led"]), entry("alien", "spaceships", ["ufo"]),
                  extra_files={"broken.json": "{nope"})
    cache = DemoCache.load(d, STORE.ids)
    assert [e.id for e in cache.entries] == ["good"]
    assert len(cache.warnings) == 2


def test_missing_cache_dir_is_empty(tmp_path):
    assert DemoCache.load(tmp_path / "missing", STORE.ids).entries == []


@pytest.mark.parametrize(
    ("keyword", "text", "expected"),
    [
        ("app", "wrapping paper", False),
        ("led", "sealed glass jar", False),
        ("led", "LED bulb 9W", True),
        ("t-shirt", "white T-shirt", True),
        ("مرطبان", "المرطبان الزجاجي", True),
    ],
)
def test_keyword_matching(keyword, text, expected):
    assert keyword_in(keyword, text) is expected


def test_longest_keyword_wins():
    cache = DemoCache.load(TEST_DEMO_CACHE, STORE.ids)
    assert cache.match(None, "a disposable paper cup").id == "paper_cup_uncertain"
    assert cache.match(None, "nothing relevant here") is None


def test_image_fingerprint_match(cache_dir):
    buf = io.BytesIO()
    Image.new("RGB", (20, 20), (9, 9, 9)).save(buf, format="PNG")
    prepared = prepare_image(buf.getvalue(), "image/png", 8 * 1024 * 1024)
    cache = DemoCache.load(cache_dir(entry("pic", "led_lamps", ["zzz"], image_sha256=image_fingerprint(prepared))),
                           STORE.ids)
    assert cache.match(prepared, None).id == "pic"


# --- DEMO_MODE end to end ----------------------------------------------------------

@pytest.fixture
def demo_client(make_settings):
    live = FakeLLM()
    c = TestClient(create_app(make_settings(demo_mode=True), llm=live))
    c.live = live
    return c


def test_demo_health(demo_client):
    body = HealthResponse.model_validate(demo_client.get("/api/health").json())
    assert body.status == "ok" and body.demo_mode
    assert body.demo_cache_entries == 7 and body.demo_cache_placeholder_entries == 7


def test_demo_complete_uses_live_scores_and_template(demo_client):
    body = ok(demo_client.post("/api/analyze", data={"text": "plastic lunch box", "language": "ar"}))
    assert body.status == "complete" and body.source == "demo_cache"
    assert body.report == compute_report(STORE.get("plastic_kitchenware"))
    assert body.explanation_source == "fallback"
    assert body.explanation == fallback_explanation(body.report, "ar")
    assert DEMO_WARNING in body.warnings
    assert demo_client.live.calls == []  # demo mode never touches the live LLM


def test_demo_needs_confirmation_then_confirm(demo_client):
    body = ok(demo_client.post("/api/analyze", data={"text": "Disposable paper cup"}))
    assert body.status == "needs_confirmation"
    assert [c.category_id for c in body.candidates] == ["plastic_kitchenware", "toilet_tissue"]
    confirmed = ok(demo_client.post("/api/analyze/confirm", json={"category_id": "plastic_kitchenware"}))
    assert confirmed.status == "complete" and confirmed.source == "demo_cache"
    assert demo_client.live.calls == []


def test_demo_unsupported(demo_client):
    assert ok(demo_client.post("/api/analyze", data={"text": "تطبيق توصيل"})).status == "unsupported"


def test_demo_no_match_lists_examples(demo_client):
    r = demo_client.post("/api/analyze", data={"text": "spaceship engine"})
    assert r.status_code == 404
    body = ErrorResponse.model_validate(r.json())
    assert body.error.code == "demo_no_match" and "Plastic lunch box" in body.error.message


def test_demo_replays_recorded_grounded_explanation(make_settings, cache_dir):
    k = key_figures(compute_report(STORE.get("led_lamps")))
    recorded = {"summary": f"Scored {k['score_out_of_10']} out of 10.", "reasons_for": ["a", "b", "c"],
                "concerns": ["d", "e", "f"], "next_steps": ["g", "h", "i"], "caveats": []}
    d = cache_dir(entry("bulb", "led_lamps", ["bulb"], explanations={"en": recorded, "ar": None}))
    c = TestClient(create_app(make_settings(demo_mode=True, demo_cache_dir=d)))
    en = ok(c.post("/api/analyze", data={"text": "bulb", "language": "en"}))
    assert en.explanation_source == "llm" and en.explanation.summary == recorded["summary"]
    ar = ok(c.post("/api/analyze", data={"text": "bulb", "language": "ar"}))
    assert ar.explanation_source == "fallback"  # no recorded Arabic explanation


def test_demo_rejects_ungrounded_recorded_explanation(make_settings, cache_dir):
    bad = {"summary": "Imports will hit 999 million.", "reasons_for": ["a", "b", "c"],
           "concerns": ["d", "e", "f"], "next_steps": ["g", "h", "i"], "caveats": []}
    d = cache_dir(entry("bulb", "led_lamps", ["bulb"], explanations={"en": bad}))
    c = TestClient(create_app(make_settings(demo_mode=True, demo_cache_dir=d)))
    body = ok(c.post("/api/analyze", data={"text": "bulb"}))
    assert body.explanation_source == "fallback" and "999" not in body.explanation.model_dump_json()  # not the whole body: request_id hex may contain 999


# --- live mode: LLM down -> matching cached example, else clear error ---------------

def test_live_outage_serves_matching_demo_example(make_settings):
    live = FakeLLM(normalize=LLMUnavailable("down"))
    c = TestClient(create_app(make_settings(), llm=live))
    body = ok(c.post("/api/analyze", data={"text": "white cotton t-shirt"}))
    assert body.source == "demo_cache" and body.status == "complete"
    assert body.report.category_id == "cotton_tshirts"
    assert LIVE_FALLBACK_WARNING in body.warnings
    assert live.ops() == ["normalize"]  # the explanation came from the cache/template, not the dead LLM


def test_live_outage_without_match_is_503(make_settings):
    c = TestClient(create_app(make_settings(), llm=FakeLLM(normalize=LLMUnavailable("down"))))
    r = c.post("/api/analyze", data={"text": "spaceship engine"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "llm_unavailable"


# --- unexpected errors ----------------------------------------------------------------

def test_unhandled_error_returns_clean_500(make_settings):
    c = TestClient(create_app(make_settings(), llm=FakeLLM(normalize=RuntimeError("secret internals"))),
                   raise_server_exceptions=False)
    r = c.post("/api/analyze", data={"text": "cup"})
    assert r.status_code == 500
    body = ErrorResponse.model_validate(r.json())
    assert body.error.code == "internal_error" and "secret" not in r.text
    assert body.error.request_id == r.headers["X-Request-ID"]


# --- data/demo_inputs.json (inputs for the recorder and the live tests) ------------------

def test_demo_inputs_file_parses():
    """Structure only: the categories themselves are checked against the real CSV in test_real_data.py."""
    from app.demo import load_demo_inputs

    inputs = load_demo_inputs()
    assert len({i.id for i in inputs}) == len(inputs) >= 3
    unsupported = [i for i in inputs if i.expected_category_id == "unsupported"]
    assert any(i.placeholder.is_physical_product is not True for i in unsupported)  # e.g. software
    assert any(i.placeholder.is_physical_product is True for i in unsupported)  # out-of-catalogue product
    assert any(i.placeholder.alternatives and i.placeholder.confidence < 0.7 for i in inputs)  # ambiguous

def test_demo_input_mismatches_are_listed():
    from app.demo import DemoInput, demo_input_mismatches

    good = DemoInput(id="a", text="cup", match_keywords=["cup"], expected_category_id="led_lamps",
                     placeholder={"name_en": "x", "name_ar": "x", "description": "x", "confidence": 0.9})
    bad = good.model_copy(update={"id": "b", "expected_category_id": "plastic_buckets"})
    alt = good.model_copy(update={"id": "c", "placeholder": good.placeholder.model_copy(
        update={"alternatives": [{"category_id": "paper_cups", "confidence": 0.2}]})})
    unsupported = good.model_copy(update={"id": "d", "expected_category_id": "unsupported"})
    assert demo_input_mismatches([good, bad, alt, unsupported], STORE.ids) == [
        "b: unknown category plastic_buckets", "c: unknown category paper_cups"]
