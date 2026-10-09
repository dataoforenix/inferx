"""Checks against the REAL data in data/ (the only offline test file that reads it).

The rest of the suite uses frozen fixtures so it can't be broken by a data change. These tests
pin down what the installed data produces, so a data update that changes a verdict is noticed.
Expected scores came from an independent calculation (corrected landed cost, cost gate).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.data_store import inspect_categories, load_categories
from app.demo import DemoCache, demo_input_mismatches, load_demo_inputs
from app.market_preview import MARKET_PREVIEW_ID
from app.scoring import compute_report

DATA = Path(__file__).resolve().parent.parent / "data"
CSV = DATA / "categories.csv"

EXPECTED = {
    # category_id: (verdict, score, margin)  margin = (CIF x (1 + customs) - local) / landed
    "metal_chair": ("MANUFACTURE", 7.0, 0.3255),
    "warehouse_racks": ("MANUFACTURE", 7.2, 0.3503),
    "plastic_tableware": ("MANUFACTURE", 6.2, 0.1367),
    "ceiling_fan": ("MAYBE", 5.2, -0.0360),
    "frozen_fries": ("MANUFACTURE", 8.6, 0.1227),
    "tomato_paste": ("DONT", 3.9, -1.7870),  # cost gate: weighted score 4.7, margin < -0.25
}


@pytest.fixture(scope="module")
def store():
    return load_categories(CSV)


@pytest.fixture(scope="module")
def reports(store):
    return {r.category_id: compute_report(r) for r in store.list()}


def test_loads_with_zero_errors_and_zero_warnings():
    result = inspect_categories(CSV, detailed=True)
    assert result.errors == [] and result.warnings == []


def test_all_six_categories_present(store):
    assert sorted(store.ids) == sorted(EXPECTED)


def test_no_placeholder_rows(store):
    assert all(r.data_status != "TODO_REAL_DATA" for r in store.list())


@pytest.mark.parametrize("category_id", sorted(EXPECTED))
def test_verdict_score_margin(reports, category_id):
    verdict, score, margin = EXPECTED[category_id]
    rep = reports[category_id]
    assert rep.data_completeness == 1.0 and not rep.verdict_forced_maybe
    assert rep.verdict == verdict
    assert rep.score == pytest.approx(score, abs=0.1)
    assert rep.cost.margin == pytest.approx(margin, abs=1e-4)


def test_cost_gate_only_on_tomato_paste(reports):
    assert {cid for cid, r in reports.items() if r.verdict_capped_by} == {"tomato_paste"}
    assert reports["tomato_paste"].verdict_capped_by == "cost_gate"


def test_high_capital_flags(reports):
    flagged = {cid for cid, r in reports.items() if "high_capital_requirement" in r.flags}
    assert flagged == {"frozen_fries", "tomato_paste"}  # machine_cost_usd_max 420,000 and 500,000


BREAK_EVEN = {
    # category_id: (break_even_tons, share_of_2024_imports)  capex mid / (landed - local); None = no cost advantage
    "metal_chair": (11.2, 0.022),
    "warehouse_racks": (68.1, 0.0108),
    "plastic_tableware": (87.8, 0.0224),
    "frozen_fries": (1457.7, 0.0177),
    "ceiling_fan": None,
    "tomato_paste": None,
}


@pytest.mark.parametrize("category_id", sorted(BREAK_EVEN))
def test_break_even(reports, category_id):
    be = reports[category_id].break_even
    if BREAK_EVEN[category_id] is None:
        assert be is None
    else:
        tons, share = BREAK_EVEN[category_id]
        assert be.break_even_tons == pytest.approx(tons, abs=0.1)
        assert be.share_of_2024_imports == pytest.approx(share, abs=1e-4)


def test_break_even_reacts_to_whatif_endpoint():
    from fastapi.testclient import TestClient

    from app.factory import create_app
    from tests.conftest import FakeLLM, test_settings

    client = TestClient(create_app(test_settings(categories_csv=CSV, demo_cache_dir=DATA / "demo_cache"), llm=FakeLLM()))
    body = client.post("/api/whatif", json={"category_id": "tomato_paste",
                                            "overrides": {"local_cost_per_kg_est_usd": 1.0}}).json()
    assert body["baseline"]["break_even"] is None
    assert body["scenario"]["break_even"]["break_even_tons"] == pytest.approx(275_000 / 0.4388 / 1000, abs=0.1)
    fries = client.post("/api/whatif", json={"category_id": "frozen_fries", "overrides": {"customs_pct": 0}}).json()
    assert fries["baseline"]["break_even"] is not None and fries["scenario"]["break_even"] is None


def test_demo_needs_both_extremes(reports):
    verdicts = [r.verdict for r in reports.values()]
    assert "DONT" in verdicts and "MANUFACTURE" in verdicts


def test_reports_carry_sources_and_capex(reports):
    for rep in reports.values():
        assert len(rep.sources) >= 3  # trade data, tariff and at least one equipment listing
        assert rep.capex_usd_range is not None and rep.machine_source
        assert rep.cost.raw_material_price_usd_per_kg is not None


def test_demo_inputs_match_real_categories(store):
    assert demo_input_mismatches(load_demo_inputs(), store.ids) == []


def test_demo_inputs_cover_every_category_in_both_languages(store):
    inputs = load_demo_inputs()
    for cid in store.ids:
        texts = [i.text for i in inputs if i.expected_category_id == cid and not i.placeholder.alternatives]
        assert any(t.isascii() for t in texts) and any(not t.isascii() for t in texts), cid


BACKEND = DATA.parent
DOCS = [BACKEND / "README.md", BACKEND / "docs" / "api_contract.md", DATA / "sources.md"]
EXAMPLES = sorted((BACKEND / "docs" / "examples").glob("*.json"))
# Ids of categories that no longer exist: the old placeholder data, the frozen test fixture, and the list
# the docs used before the real data arrived.
RETIRED_IDS = {"plastic_kitchenware", "glass_containers", "toilet_tissue", "led_lamps", "cotton_tshirts"}
for _csv in (DATA / "categories.placeholder.csv", BACKEND / "tests" / "fixtures" / "categories_test.csv"):
    if _csv.exists():
        RETIRED_IDS |= {line.split(",", 1)[0] for line in _csv.read_text(encoding="utf-8").splitlines()[1:] if line}
CATEGORY_ID_IN_TEXT = re.compile(r'"(?:expected_)?category_id"\s*:\s*"([^"]*)"')


def _json_category_ids(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in ("category_id", "expected_category_id") and isinstance(value, str):
                yield value
            else:
                yield from _json_category_ids(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _json_category_ids(value)


@pytest.mark.parametrize("path", DOCS + EXAMPLES, ids=lambda p: p.name)
def test_docs_mention_only_real_category_ids(store, path):
    valid = {*store.ids, "unsupported", MARKET_PREVIEW_ID}  # market_preview: report id of a preview
    text = path.read_text(encoding="utf-8")
    ids = set(CATEGORY_ID_IN_TEXT.findall(text))
    if path.suffix == ".json":
        ids |= set(_json_category_ids(json.loads(text)))
    assert ids <= valid, f"{path.name}: unknown category_id {sorted(ids - valid)}"
    retired = sorted(i for i in RETIRED_IDS - valid if re.search(rf"\b{re.escape(i)}\b", text))
    assert not retired, f"{path.name} still mentions retired category ids {retired}"


def test_demo_cache_matches_demo_inputs(store):
    cache = DemoCache.load(DATA / "demo_cache", store.ids)
    assert cache.warnings == [] or all("placeholders" in w for w in cache.warnings)  # nothing ignored
    inputs = load_demo_inputs()
    assert {e.id for e in cache.entries} == {i.id for i in inputs}
    for item in inputs:
        entry = cache.match(None, item.text)
        assert entry is not None and entry.id == item.id
        assert entry.normalization.category_id == item.expected_category_id
