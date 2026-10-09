"""UN Comtrade client and the market preview. HTTP is always mocked (urlopen is patched) and time is fake."""

from __future__ import annotations

import io
import json
import socket
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

import app.comtrade as comtrade_module
from app.comtrade import ComtradeClient, TradeSeries
from app.factory import create_app
from app.schemas import NormalizationLLMOutput
from tests.conftest import FakeLLM, norm_output, test_settings

VALUES = {2020: 10e6, 2021: 11e6, 2022: 12e6, 2023: 13e6, 2024: 14_641_000.0}  # +10%/year


def row(year, value=None, weight=None, **extra):
    return {"period": year, "reporterCode": 400, "partnerCode": 0, "flowCode": "M", "cmdCode": "854143",
            "primaryValue": VALUES[year] if value is None else value,
            "netWgt": 2_000_000.0 if weight is None else weight, **extra}


class FakeTime:
    """Fake clock + sleep: tests never really wait. Each HTTP request takes `request_seconds`."""

    def __init__(self, request_seconds=0.7):
        self.now = 0.0
        self.request_seconds = request_seconds
        self.sleeps: list[float] = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(round(seconds, 3))
        self.now += seconds


class FakeHTTP:
    """Replaces urllib's urlopen. `respond(year)` returns a JSON-able body or an exception to raise."""

    def __init__(self, time_, respond=lambda year: {"data": [row(year)]}):
        self.time = time_
        self.respond = respond
        self.urls: list[str] = []
        self.timeouts: list[float] = []
        self.started: list[float] = []

    def __call__(self, request, timeout):
        url = request.full_url
        self.urls.append(url)
        self.timeouts.append(round(timeout, 3))
        self.started.append(round(self.time.now, 3))
        self.time.now += self.time.request_seconds
        result = self.respond(self.year(url))
        if isinstance(result, BaseException):
            raise result
        return io.BytesIO(json.dumps(result).encode("utf-8"))

    @staticmethod
    def year(url):
        return int(parse_qs(urlparse(url).query)["period"][0])

    def years(self):
        return [self.year(u) for u in self.urls]


def rate_limited(seconds=3):
    message = f"Rate limit is exceeded. Try again in {seconds} seconds."
    body = io.BytesIO(json.dumps({"statusCode": 429, "message": message}).encode())
    return HTTPError("u", 429, "Too Many Requests", {}, body)


@pytest.fixture
def fake_time():
    return FakeTime()


@pytest.fixture
def http(monkeypatch, fake_time):
    fake = FakeHTTP(fake_time)
    monkeypatch.setattr(comtrade_module, "urlopen", fake)
    return fake


@pytest.fixture
def make_client(fake_time):
    def _make(**kw):
        return ComtradeClient(clock=fake_time.clock, sleep=fake_time.sleep, **kw)
    return _make


# --- client -------------------------------------------------------------------------------

def test_success_reads_every_year_latest_first(http, make_client):
    series = make_client(total_timeout=30).fetch("854143")
    assert series.imports_usd == VALUES and series.import_weight_kg_2024 == 2_000_000.0 and series.complete
    assert http.years() == [2024, 2020, 2021, 2022, 2023]  # the score needs 2024 and 2020 only
    for year, url in zip(http.years(), http.urls):
        assert url.startswith("https://comtradeapi.un.org/public/v1/preview/C/A/HS?")
        q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
        assert q == {"reporterCode": "400", "partnerCode": "0", "flowCode": "M", "period": str(year),
                     "cmdCode": "854143"}


def test_requests_are_paced_and_share_the_10_second_budget(http, make_client):
    # 0.7 s per request, 2.5 s between starts: 2024, 2020, 2021, 2022 fit in 10 s; 2023 does not.
    series = make_client().fetch("854143")
    assert http.started == [0.0, 2.5, 5.0, 7.5]
    assert http.timeouts == [10.0, 7.5, 5.0, 2.5]
    assert series.imports_usd[2023] is None and not series.complete
    assert series.imports_usd[2020] == VALUES[2020] and series.imports_usd[2024] == VALUES[2024]


def test_pacing_is_shared_between_fetches(http, make_client):
    client = make_client(total_timeout=30)
    client.fetch("854143")
    before = len(http.started)
    client.fetch("940171")
    assert http.started[before] - http.started[before - 1] == pytest.approx(2.5)


def test_rate_limit_waits_as_told_and_retries_once(http, make_client):
    calls = {"n": 0}

    def respond(year):
        if year == 2020 and calls["n"] == 0:
            calls["n"] += 1
            return rate_limited(3)
        return {"data": [row(year)]}

    http.respond = respond
    series = make_client(total_timeout=30).fetch("854143")
    assert series.imports_usd[2020] == VALUES[2020]
    assert http.years()[:3] == [2024, 2020, 2020]
    # waited the 3 s the server asked for, counted from the 429 answer (the request itself took 0.7 s)
    assert http.started[2] - http.started[1] == pytest.approx(3.7)


def test_rate_limit_on_latest_year_twice_returns_none(http, make_client):
    http.respond = lambda year: rate_limited(1) if year == 2024 else {"data": [row(year)]}
    assert make_client(total_timeout=30).fetch("854143") is None


def test_breakdown_rows_are_skipped(http, make_client):
    http.respond = lambda y: {"data": [row(y, value=1.0, motCode=2100), row(y, customsCode="C00", motCode=0)]}
    assert make_client().fetch("854143").imports_usd[2024] == VALUES[2024]


@pytest.mark.parametrize("body", [{"data": []}, {"data": None}, {}, {"error": "x"}, [], "nonsense"])
def test_empty_data_returns_none(http, make_client, body):
    http.respond = lambda year: body
    assert make_client().fetch("854143") is None
    assert http.years() == [2024]  # stops at once: the latest year is required


def test_missing_earlier_year_is_kept_as_none(http, make_client):
    http.respond = lambda year: {"data": [] if year == 2020 else [row(year)]}
    series = make_client(total_timeout=30).fetch("854143")
    assert series.imports_usd[2020] is None and series.imports_usd[2024] == VALUES[2024]


@pytest.mark.parametrize("error", [
    socket.timeout("timed out"), TimeoutError(), ConnectionResetError(), OSError("dns"),
    HTTPError("u", 500, "err", {}, None),
])
def test_network_errors_on_latest_year_return_none(http, make_client, error):
    http.respond = lambda year: error if year == 2024 else {"data": [row(year)]}
    assert make_client().fetch("854143") is None


def test_network_error_on_earlier_year_leaves_a_gap(http, make_client):
    http.respond = lambda year: TimeoutError() if year == 2022 else {"data": [row(year)]}
    series = make_client(total_timeout=30).fetch("854143")
    assert series.imports_usd[2022] is None and series.imports_usd[2023] == VALUES[2023]


def test_unexpected_exception_never_raises(http, make_client):
    http.respond = lambda year: RuntimeError("boom")
    assert make_client().fetch("854143") is None


def test_bad_json_returns_none(monkeypatch, make_client):
    monkeypatch.setattr(comtrade_module, "urlopen", lambda request, timeout: io.BytesIO(b"<html>busy</html>"))
    assert make_client().fetch("854143") is None


def test_slow_latest_year_times_out(http, make_client):
    http.respond = lambda year: socket.timeout("timed out")  # urlopen gave up after the remaining budget
    assert make_client().fetch("854143") is None
    assert http.timeouts[0] == 10.0


def test_cache_hit_makes_no_request(http, make_client, fake_time):
    client = make_client(total_timeout=30)
    first = client.fetch("854143")
    fake_time.now += 23 * 3600
    assert client.fetch("854143") is first and len(http.urls) == 5
    fake_time.now += 2 * 3600  # after 24 h the entry expires
    client.fetch("854143")
    assert len(http.urls) == 10


def test_failures_are_not_cached(http, make_client):
    client = make_client()
    http.respond = lambda year: TimeoutError()
    assert client.fetch("854143") is None
    http.respond = lambda year: {"data": [row(year)]}
    assert client.fetch("854143") is not None


@pytest.mark.parametrize("hs6", ["85414", "8541430", "abcdef", "", None])
def test_invalid_hs6_makes_no_request(http, make_client, hs6):
    assert make_client().fetch(hs6) is None and http.urls == []


# --- normaliser output ------------------------------------------------------------------------

@pytest.mark.parametrize(("raw", "expected"), [("854143", "854143"), (" 8541.43 ", "854143"), ("85414", None),
                                               ("8541430", None), ("abc", None), (None, None), (854143, None)])
def test_hs6_guess_is_six_digits_or_none(raw, expected):
    out = norm_output("unsupported").model_dump()
    assert NormalizationLLMOutput.model_validate({**out, "hs6_guess": raw}).hs6_guess == expected


def test_hs6_guess_is_optional_for_old_cache_entries():
    out = norm_output().model_dump(exclude={"hs6_guess"})
    assert NormalizationLLMOutput.model_validate(out).hs6_guess is None


def test_normalization_schema_asks_for_hs6_guess():
    from app.schemas import NormalizationLLMOutput
    from app.llm import NORMALIZE_SYSTEM
    schema = NormalizationLLMOutput.model_json_schema()
    assert "hs6_guess" in schema["properties"]  # optional nullable field: present in properties, not required
    assert "hs6_guess" in NORMALIZE_SYSTEM


# --- pipeline -------------------------------------------------------------------------------

SOLAR = norm_output("unsupported", 0.95, physical=True, name_en="Solar panel", name_ar="لوح طاقة شمسية",
                    description="A photovoltaic panel.").model_copy(update={"hs6_guess": "854143"})


class SpyComtrade:
    def __init__(self, result):
        self.result = result
        self.calls: list[str] = []

    def fetch(self, hs6):
        self.calls.append(hs6)
        return self.result


def preview_client(normalize=SOLAR, comtrade=None, **settings):
    llm = FakeLLM(normalize=normalize)
    app = create_app(test_settings(**settings), llm=llm, comtrade=comtrade)
    return TestClient(app), llm


@pytest.mark.parametrize("language", ["en", "ar"])
def test_market_preview_success(http, make_client, language):
    client, llm = preview_client(comtrade=make_client(total_timeout=30))
    body = client.post("/api/analyze", data={"text": "rooftop solar panel", "language": language}).json()
    assert body["status"] == "market_preview" and body["source"] == "live"
    assert body["product"]["hs6_guess"] == "854143" and body["product"]["category_id"] is None
    rep = body["report"]
    assert rep["flags"] == ["market_preview_only"] and rep["hs6"] == "854143"
    assert rep["verdict"] == "MAYBE" and rep["verdict_forced_maybe"] and rep["data_completeness"] == 0.35
    assert rep["cost"]["score"] is None and rep["feasibility"]["score"] is None and rep["competition"]["score"] is None
    for field in ("import_price_per_kg_usd", "local_cost_per_kg_est_usd", "machinery_availability", "local_factories"):
        assert field in rep["missing_fields"]
    assert rep["imports_usd"]["2024"] == VALUES[2024] and rep["import_weight_kg_2024"] == 2_000_000.0
    assert rep["market"]["cagr"] == pytest.approx(0.1, abs=1e-4)
    assert any("market preview only" in n for n in rep["notes"])
    assert body["explanation_source"] == "template" and body["explanation"]["language"] == language
    assert "854143" in body["explanation"]["summary"]
    assert any("854143" in w for w in body["warnings"])
    assert llm.ops() == ["normalize"]  # no explanation call
    assert body["timings_ms"]["market_data"] is not None


def test_market_preview_template_texts():
    from app.market_preview import preview_explanation, preview_report

    trade = TradeSeries("854143", dict(VALUES), 2_000_000.0)
    report = preview_report(trade, "Solar panel", "لوح طاقة شمسية")
    en, ar = preview_explanation(report, "en"), preview_explanation(report, "ar")
    assert "preliminary market scan" in en.summary and "14.6 million USD" in en.summary
    assert "مسح أولي للسوق" in ar.summary and "لوح طاقة شمسية" in ar.summary
    for fb in (en, ar):
        assert len(fb.reasons_for) == len(fb.concerns) == len(fb.next_steps) == 3
    assert "10% per year" in en.reasons_for[1] and "2,000 tonnes" in en.reasons_for[2]
    assert any("import price per kg" in c for c in en.concerns)  # says what data is needed to decide


def test_market_preview_with_partial_years():
    from app.market_preview import preview_explanation, preview_report

    trade = TradeSeries("854143", {**VALUES, 2020: None, 2023: None}, None)
    report = preview_report(trade, "Solar panel", "لوح طاقة شمسية")
    assert report.market.cagr is None and report.market.score is not None  # volume only
    fb = preview_explanation(report, "en")
    assert len(fb.reasons_for) == 3 and not any("per year" in r for r in fb.reasons_for)


def test_comtrade_failure_falls_back_to_unsupported_with_warning():
    spy = SpyComtrade(None)
    client, _ = preview_client(comtrade=spy)
    body = client.post("/api/analyze", data={"text": "rooftop solar panel"}).json()
    assert spy.calls == ["854143"]
    assert body["status"] == "unsupported" and body["report"] is None
    assert any("could not be loaded" in w for w in body["warnings"])


def test_comtrade_timeout_falls_back_to_unsupported(http, make_client):
    http.respond = lambda year: socket.timeout("timed out")
    client, _ = preview_client(comtrade=make_client())
    assert client.post("/api/analyze", data={"text": "rooftop solar panel"}).json()["status"] == "unsupported"


@pytest.mark.parametrize("norm", [
    SOLAR.model_copy(update={"hs6_guess": None}),  # no guess
    SOLAR.model_copy(update={"is_physical_product": False}),  # software, service
])
def test_no_preview_without_physical_product_and_hs6(norm):
    spy = SpyComtrade(object())
    client, _ = preview_client(normalize=norm, comtrade=spy)
    body = client.post("/api/analyze", data={"text": "x"}).json()
    assert body["status"] == "unsupported" and spy.calls == []
    assert not any("could not be loaded" in w for w in body["warnings"])


def test_demo_mode_skips_comtrade(tmp_path):
    entry = {
        "id": "solar", "generated_by": "PLACEHOLDER_HANDWRITTEN", "example_input": {"text": "solar panel"},
        "match_keywords": ["solar panel"], "explanations": {"en": None, "ar": None},
        "normalization": SOLAR.model_dump(),
    }
    (tmp_path / "solar.json").write_text(json.dumps(entry), encoding="utf-8")
    spy = SpyComtrade(object())
    client, _ = preview_client(comtrade=spy, demo_mode=True, demo_cache_dir=tmp_path)
    body = client.post("/api/analyze", data={"text": "solar panel"}).json()
    assert body["status"] == "unsupported" and body["source"] == "demo_cache" and spy.calls == []


def test_demo_mode_never_creates_a_comtrade_client():
    app = create_app(test_settings(demo_mode=True, market_preview=True))
    assert app.state.pipeline.comtrade is None
    live = create_app(test_settings(market_preview=True))
    assert isinstance(live.state.pipeline.comtrade, ComtradeClient)
    assert create_app(test_settings(market_preview=False)).state.pipeline.comtrade is None
