"""Additive guidance features: JOD import value, next steps, advisors, supplier links, budget check, methodology."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.data_store import load_categories
from app.explanation import llm_facts
from app.factory import create_app
from app.guidance import ADVISORS, NEXT_STEPS, SUPPLIER_CAPTION_AR, SUPPLIER_CAPTION_EN, USD_TO_JOD
from app.schemas import BudgetResponse, ErrorResponse, MethodologyResponse
from app.scoring import WEIGHTS, compute_report
from tests.conftest import TEST_CSV, FakeLLM, test_settings

REAL_CSV = Path(__file__).resolve().parent.parent / "data" / "categories.csv"
STORE = load_categories(TEST_CSV)


@pytest.fixture(scope="module")
def real_client():
    return TestClient(create_app(test_settings(categories_csv=REAL_CSV), llm=FakeLLM()))


# --- a. latest_import_jod ------------------------------------------------------------------------

def test_latest_import_jod_is_usd_times_peg():
    for record in STORE.list():
        m = compute_report(record).market
        assert m.latest_import_jod == pytest.approx(m.latest_import_usd * 0.709, abs=0.01)
    assert USD_TO_JOD == 0.709


# --- c. next steps -------------------------------------------------------------------------------

def test_next_steps_follow_the_verdict_in_both_languages():
    seen = set()
    for record in STORE.list():
        rep = compute_report(record)
        assert rep.next_steps.en == NEXT_STEPS[rep.verdict]["en"]
        assert rep.next_steps.ar == NEXT_STEPS[rep.verdict]["ar"]
        seen.add(rep.verdict)
    assert {"MANUFACTURE", "DONT"} <= seen
    for verdict, steps in NEXT_STEPS.items():
        assert len(steps["en"]) == len(steps["ar"]) >= 3, verdict
        assert all(any("؀" <= ch <= "ۿ" for ch in s) for s in steps["ar"])


# --- d. advisors ---------------------------------------------------------------------------------

def test_advisors_are_official_https_sites_without_phones():
    rep = compute_report(STORE.list()[0])
    assert rep.advisors == ADVISORS and len(ADVISORS) >= 4
    for a in ADVISORS:
        assert a.url.startswith("https://") and a.name_en and a.name_ar and a.offer_en and a.offer_ar
        text = " ".join([a.name_en, a.name_ar, a.offer_en, a.offer_ar])
        assert not re.search(r"\+?\d[\d\s-]{6,}", text), a.name_en  # no phone numbers
    assert {"https://www.jedco.gov.jo", "https://www.jci.org.jo", "https://www.mit.gov.jo",
            "https://www.ccd.gov.jo"} <= {a.url for a in ADVISORS}


# --- e. supplier links ---------------------------------------------------------------------------

def test_supplier_links_cover_every_item_with_search_urls_and_caption():
    for record in STORE.list():
        rep = compute_report(record)
        s = rep.suppliers
        assert s.caption_en == "Search links, not supplier recommendations. Verify suppliers yourself."
        assert s.caption_en == SUPPLIER_CAPTION_EN and s.caption_ar == SUPPLIER_CAPTION_AR
        assert [i.item for i in s.items] == rep.machinery + rep.raw_materials
        assert [i.kind for i in s.items] == ["machinery"] * len(rep.machinery) + ["raw_material"] * len(rep.raw_materials)
        for item in s.items:
            for link in item.links:
                assert link.url.startswith("https://www.made-in-china.com/multi-search/")
                assert item.item.split()[0].lower() in link.url.lower()  # built from the item name
        assert s.local_directory.url.startswith("https://jci.org.jo/")


def test_supplier_link_encodes_the_item():
    from app.guidance import supplier_links

    links = supplier_links(["CNC/hydraulic tube bender"], []).items[0].links
    assert links[0].url == "https://www.made-in-china.com/multi-search/CNC%2Fhydraulic+tube+bender/F1/1.html"


def test_new_fields_are_not_sent_to_the_explanation_model():
    facts = llm_facts(compute_report(STORE.list()[0]))
    for name in ("next_steps", "advisors", "suppliers"):
        assert name not in facts["report"]
    assert "latest_import_jod" not in facts["report"]["market"]


# --- b. /api/budget ------------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("budget", "status", "gap"),
    [(400_000, "covered", 0.0), (354_500, "covered", 0.0), (100_000, "partial", 254_500.0),
     (35_450, "partial", 319_050.0), (1_000, "short", 353_500.0)],
)
def test_budget_status_and_gap(real_client, budget, status, gap):
    # tomato_paste: capex 50,000-500,000 USD -> 35,450-354,500 JOD
    r = real_client.post("/api/budget", json={"category_id": "tomato_paste", "budget_jod": budget})
    assert r.status_code == 200, r.text
    body = BudgetResponse.model_validate(r.json())
    assert body.status == status and body.gap_jod == gap
    assert (body.capex_jod_range.min, body.capex_jod_range.max) == (35_450.0, 354_500.0)
    assert "Equipment only" in body.caption_en and "excluding shipping, customs, installation" in body.caption_en
    assert "المعدات فقط" in body.caption_ar
    assert body.request_id == r.headers["X-Request-ID"]


@pytest.mark.parametrize(
    ("payload", "status", "code"),
    [({"category_id": "spaceships", "budget_jod": 10}, 404, "unknown_category"),
     ({"category_id": "tomato_paste", "budget_jod": -1}, 422, "validation_error"),
     ({"category_id": "tomato_paste"}, 422, "validation_error"),
     ({"category_id": "tomato_paste", "budget_jod": 1, "extra": 1}, 422, "validation_error")],
)
def test_budget_errors(real_client, payload, status, code):
    r = real_client.post("/api/budget", json=payload)
    assert r.status_code == status and ErrorResponse.model_validate(r.json()).error.code == code


def test_budget_without_capex_is_422(client):
    # The frozen test fixture has no equipment cost columns filled in.
    r = client.post("/api/budget", json={"category_id": "led_lamps", "budget_jod": 1000})
    assert r.status_code == 422 and r.json()["error"]["code"] == "capex_unavailable"


# --- f. /api/methodology -------------------------------------------------------------------------

def test_methodology_en_ar_with_weights_cost_gate_and_covid_note(client):
    r = client.get("/api/methodology")
    assert r.status_code == 200
    body = MethodologyResponse.model_validate(r.json())
    assert body.weights == WEIGHTS and body.min_completeness == 0.8
    assert body.cost_gate == {"maybe_below_margin": 0.0, "maybe_score_cap": 5.9,
                              "dont_below_margin": -0.25, "dont_score_cap": 3.9}
    en = " ".join(s.body for s in body.sections["en"])
    ar = " ".join(s.body for s in body.sections["ar"])
    assert len(body.sections["en"]) == len(body.sections["ar"]) >= 5
    for text in (en, ar):
        assert "35" in text and "30" in text and "20" in text and "15" in text and "5.9" in text and "3.9" in text
    assert "COVID" in en and "2020" in en and "كورونا" in ar and "2020" in ar
    assert "UN Comtrade" in en and "WITS" in en
