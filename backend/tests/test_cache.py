"""Optional SQLite cache: hit, miss, TTL, fail-open, no images stored, /api/searches/top, DB_ENABLED=false."""

from __future__ import annotations

import base64
import io
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.cache import AnalysisCache, cache_key, normalize_text
from app.factory import create_app
from app.llm import LLMUnavailable
from app.schemas import AnalyzeResponse, TopSearchesResponse
from tests.conftest import FakeLLM, norm_output


class Clock:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self):
        return self.now


def make(make_settings, tmp_path, llm=None, **settings):
    settings.setdefault("db_enabled", True)
    settings.setdefault("db_path", tmp_path / "cache.db")
    llm = llm or FakeLLM()
    app = create_app(make_settings(**settings), llm=llm)
    clock = Clock()
    if app.state.cache is not None:
        app.state.cache.clock = clock
    return TestClient(app), llm, clock


def post(client, text="plastic lunch box", **kw):
    r = client.post("/api/analyze", data={"text": text, "language": kw.pop("language", "en")}, **kw)
    assert r.status_code == 200, r.text
    return r


def png_bytes(color=(10, 200, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (48, 48), color).save(buf, format="PNG")
    return buf.getvalue()


# --- miss / hit / normalisation --------------------------------------------------------------

def test_miss_then_hit_skips_the_llm(make_settings, tmp_path):
    client, llm, _ = make(make_settings, tmp_path)
    first = post(client)
    assert first.json()["cache"] == "miss" and llm.ops() == ["normalize", "explain"]
    second = post(client, text="  PLASTIC   lunch BOX ")  # normalised text: same key
    body = AnalyzeResponse.model_validate(second.json())
    assert body.cache == "hit" and llm.ops() == ["normalize", "explain"]  # no new LLM call
    assert body.request_id == second.headers["X-Request-ID"] != first.json()["request_id"]
    assert body.report == AnalyzeResponse.model_validate(first.json()).report
    assert body.explanation == AnalyzeResponse.model_validate(first.json()).explanation
    assert body.timings_ms.normalize is None and body.timings_ms.explain is None


def test_language_is_part_of_the_key(make_settings, tmp_path):
    client, llm, _ = make(make_settings, tmp_path)
    post(client, language="en")
    assert post(client, language="ar").json()["cache"] == "miss"
    assert llm.ops().count("normalize") == 2


def test_key_normalisation():
    assert normalize_text("  Plastic\tLUNCH  box ") == "plastic lunch box"
    assert cache_key("a", None, "en") != cache_key("a", None, "ar") != cache_key("a", "f" * 64, "ar")


# --- TTL ------------------------------------------------------------------------------------------

def test_ttl_expiry(make_settings, tmp_path):
    client, llm, clock = make(make_settings, tmp_path, cache_ttl_hours=24)
    post(client)
    clock.now += 24 * 3600 - 1
    assert post(client).json()["cache"] == "hit"
    clock.now += 2  # now older than 24 h
    assert post(client).json()["cache"] == "miss"
    assert llm.ops().count("normalize") == 2


# --- what is never cached -------------------------------------------------------------------------

@pytest.mark.parametrize(
    "norm",
    [norm_output(confidence=0.4), norm_output("unsupported", 0.9), norm_output("plastic_kitchenware", 0.9, physical=False)],
    ids=["needs_confirmation", "unsupported", "not_physical"],
)
def test_needs_confirmation_and_unsupported_are_not_cached(make_settings, tmp_path, norm):
    client, llm, _ = make(make_settings, tmp_path, llm=FakeLLM(normalize=norm))
    assert post(client).json()["cache"] == "miss"
    assert post(client).json()["cache"] == "miss"
    assert llm.ops().count("normalize") == 2


def test_errors_are_not_cached(make_settings, tmp_path):
    llm = FakeLLM(normalize=LLMUnavailable("down"))
    client, _, _ = make(make_settings, tmp_path, llm=llm)
    for _ in range(2):
        r = client.post("/api/analyze", data={"text": "spaceship engine"})
        assert r.status_code == 503 and "cache" not in r.json()
    assert llm.ops() == ["normalize", "normalize"]


def test_demo_mode_never_uses_the_cache(make_settings, tmp_path):
    client, _, _ = make(make_settings, tmp_path, demo_mode=True)
    assert client.app.state.cache is None
    assert "cache" not in post(client).json()
    assert not (tmp_path / "cache.db").exists()
    assert client.get("/api/searches/top").status_code == 404


# --- DB_ENABLED=false -----------------------------------------------------------------------------

def test_disabled_changes_nothing(make_settings, tmp_path):
    client, llm, _ = make(make_settings, tmp_path, db_enabled=False)
    body = post(client).json()
    assert "cache" not in body and client.app.state.cache is None
    post(client)
    assert llm.ops().count("normalize") == 2  # every request goes to the LLM, as before
    assert not (tmp_path / "cache.db").exists()
    assert client.get("/api/searches/top").status_code == 404  # the endpoint doesn't exist


# --- fail-open ------------------------------------------------------------------------------------

def test_corrupt_database_fails_open(make_settings, tmp_path, caplog):
    path = tmp_path / "cache.db"
    path.write_bytes(b"this is not a sqlite database" * 100)
    client, llm, _ = make(make_settings, tmp_path, db_path=path)
    with caplog.at_level("WARNING", logger="sannaha.cache"):
        r1, r2 = post(client), post(client)
    assert r1.json()["status"] == r2.json()["status"] == "complete"
    assert r1.json()["cache"] == r2.json()["cache"] == "miss"
    assert llm.ops().count("normalize") == 2
    assert any("ignored" in m for m in caplog.messages)
    assert client.get("/api/searches/top").json()["searches"] == []


def test_locked_database_fails_open(make_settings, tmp_path, caplog):
    path = tmp_path / "cache.db"
    client, llm, _ = make(make_settings, tmp_path, db_path=path)
    post(client)  # creates the database
    locker = sqlite3.connect(path)
    locker.execute("BEGIN EXCLUSIVE")
    try:
        with caplog.at_level("WARNING", logger="sannaha.cache"):
            r = post(client)
        assert r.json()["status"] == "complete" and r.json()["cache"] == "miss"
        assert any("ignored" in m for m in caplog.messages)
    finally:
        locker.rollback()
        locker.close()
    assert post(client).json()["cache"] == "hit"  # works again once the lock is gone


def test_unwritable_location_fails_open(make_settings, tmp_path):
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("x")
    client, llm, _ = make(make_settings, tmp_path, db_path=blocker / "cache.db")
    assert post(client).json()["status"] == "complete"


def test_cache_methods_never_raise(tmp_path):
    bad = AnalysisCache(tmp_path / "x.db", 3600)
    (tmp_path / "x.db").write_bytes(b"garbage" * 50)
    assert bad.get("k") is None and bad.top_searches(5) == []
    bad.put("k", {"a": 1})
    bad.record_search("c", None, "n", "n")


# --- images ---------------------------------------------------------------------------------------

def test_no_image_bytes_are_stored(make_settings, tmp_path):
    path = tmp_path / "cache.db"
    client, llm, _ = make(make_settings, tmp_path, db_path=path)
    raw = png_bytes()
    files = {"image": ("photo.png", raw, "image/png")}
    assert client.post("/api/analyze", files=files, data={"language": "en"}).json()["cache"] == "miss"
    assert client.post("/api/analyze", files={"image": ("again.png", raw, "image/png")},
                       data={"language": "en"}).json()["cache"] == "hit"
    sanitised = base64.b64decode(llm.calls[0][1].base64_data)  # the JPEG the LLM received
    blob = path.read_bytes()
    for needle in (raw, sanitised, base64.b64encode(raw), base64.b64encode(sanitised), raw[:64], sanitised[:64]):
        assert needle not in blob
    conn = sqlite3.connect(path)
    cols = {r[1] for t in ("analyze_cache", "searches") for r in conn.execute(f"PRAGMA table_info({t})")}
    conn.close()
    assert cols == {"key", "created_at", "response_json", "category_id", "hs6_guess", "name_en", "name_ar",
                    "count", "last_seen"}
    # a different image is a different key
    other = client.post("/api/analyze", files={"image": ("o.png", png_bytes((200, 0, 0)), "image/png")},
                        data={"language": "en"})
    assert other.json()["cache"] == "miss"


# --- /api/searches/top ----------------------------------------------------------------------------

def test_top_searches_counts_hits_and_misses_without_personal_data(make_settings, tmp_path):
    lunch = FakeLLM()
    client, _, clock = make(make_settings, tmp_path, llm=lunch)
    for _ in range(3):
        post(client, text="plastic lunch box")  # 1 miss + 2 hits
    client.app.state.pipeline.llm = FakeLLM(normalize=norm_output("led_lamps", 0.95, name_en="LED bulb"))
    post(client, text="led bulb")
    client.app.state.pipeline.llm = FakeLLM(normalize=norm_output(confidence=0.3))
    post(client, text="something vague")  # needs_confirmation: not counted
    r = client.get("/api/searches/top", params={"limit": 10})
    body = TopSearchesResponse.model_validate(r.json())
    assert [(s.category_id, s.count) for s in body.searches] == [("plastic_kitchenware", 3), ("led_lamps", 1)]
    assert body.searches[0].name_ar and body.searches[0].hs6_guess is None
    text = r.text
    assert "testclient" not in text and "127.0.0.1" not in text and "something vague" not in text
    assert client.get("/api/searches/top", params={"limit": 1}).json()["searches"][0]["count"] == 3
    for bad in (0, 51, "x"):
        assert client.get("/api/searches/top", params={"limit": bad}).status_code == 422


def test_market_preview_is_cached_and_counted_by_hs6(make_settings, tmp_path):
    from app.comtrade import TradeSeries
    from app.schemas import NormalizationLLMOutput

    trade = TradeSeries(hs6="854143", imports_usd={2020: 10e6, 2021: 11e6, 2022: 12e6, 2023: 13e6, 2024: 14e6},
                        import_weight_kg_2024=2e6)

    class Comtrade:
        calls = 0

        def fetch(self, hs6):
            Comtrade.calls += 1
            return trade

    solar = NormalizationLLMOutput(is_physical_product=True, product_name_en="Solar panel", product_name_ar="لوح شمسي",
                                   description="A PV module.", category_id="unsupported", confidence=0.95,
                                   alternatives=[], hs6_guess="854143")
    app = create_app(make_settings(db_enabled=True, db_path=tmp_path / "c.db"), llm=FakeLLM(normalize=solar),
                     comtrade=Comtrade())
    client = TestClient(app)
    assert post(client, text="solar panel").json()["status"] == "market_preview"
    second = post(client, text="solar panel").json()
    assert second["status"] == "market_preview" and second["cache"] == "hit" and Comtrade.calls == 1
    top = client.get("/api/searches/top").json()["searches"]
    assert top == [{"category_id": None, "hs6_guess": "854143", "name_en": "Solar panel", "name_ar": "لوح شمسي",
                    "count": 2}]
