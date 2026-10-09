from __future__ import annotations

import pytest

from app.data_store import load_categories
from app.explanation import extract_numbers, fallback_explanation, grounding_issues, key_figures, llm_facts
from app.schemas import ExplanationLLMOutput, WhatIfOverrides
from app.scoring import compute_report
from tests.conftest import TEST_CSV

RECORDS = load_categories(TEST_CSV).list()
PLASTIC = next(r for r in RECORDS if r.category_id == "plastic_kitchenware")


def explanation(*sentences: str) -> ExplanationLLMOutput:
    return ExplanationLLMOutput(
        summary=" ".join(sentences), reasons_for=["fine", "fine", "fine"], concerns=["fine", "fine", "fine"],
        next_steps=["fine", "fine", "fine"], caveats=[],
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("score 7.9 of 10", [7.9, 10]),
        ("٧٫٩ من ١٠", [7.9, 10]),
        ("۲۴ million", [24]),
        ("24,000,000 USD", [24_000_000]),
        ("in 2020,2024", [2020, 2024]),
        ("41.36%", [41.36]),
        ("no numbers", []),
    ],
)
def test_extract_numbers(text, expected):
    assert [v for _, v, _ in extract_numbers(text)] == expected


def test_grounded_numbers_pass():
    report = compute_report(PLASTIC)
    k = key_figures(report)
    out = explanation(
        f"Score {report.score} out of 10, verdict MANUFACTURE.",
        f"Imports were about {k['latest_imports_usd_millions']} million USD in 2024 (24,000,000 USD).",
        f"Imports grew about {k['import_growth_per_year_pct']}% a year, roughly 7% per year.",
        # landed = CIF 2.5 x (1 + 0.20) = 3.0; margin (3.0 - 1.9) / 3.0 = 36.7%
        "Landed cost is 3.0 USD/kg versus a local cost of 1.9 USD/kg, an advantage of about 37%.",
        "There are 25 local factories; saturation is at 60. HS code 392410.",
        "حصل المنتج على ٧٫٩ من ١٠",
    )
    assert grounding_issues(out, report) == []


@pytest.mark.parametrize(
    "fabricated",
    [
        "Imports will reach 999 million USD by 2030.",
        "Demand grows 45% a year.",
        "The market has 12.5 million customers.",
        "The cost advantage is 43%.",  # report says 36.7%
        "Score is 8.4 out of 10.",  # report says 7.9
    ],
)
def test_fabricated_numbers_are_caught(fabricated):
    assert grounding_issues(explanation(fabricated), compute_report(PLASTIC)) != []


def test_whatif_numbers_are_grounded_against_the_scenario_report():
    scenario = compute_report(PLASTIC, WhatIfOverrides(customs_pct=0.35))
    assert grounding_issues(explanation("Customs at 35% changes the landed cost."), scenario) == []
    assert grounding_issues(explanation("Customs at 35% changes the landed cost."), compute_report(PLASTIC)) != []


@pytest.mark.parametrize("record", RECORDS, ids=lambda r: r.category_id)
@pytest.mark.parametrize("language", ["en", "ar"])
def test_fallback_explanation_is_grounded_and_complete(record, language):
    report = compute_report(record)
    fb = fallback_explanation(report, language)
    assert fb.language == language
    assert len(fb.reasons_for) == len(fb.concerns) == len(fb.next_steps) == 3
    assert "?" not in fb.summary + "".join(fb.reasons_for + fb.concerns)
    as_llm = ExplanationLLMOutput(**fb.model_dump(exclude={"language"}))
    assert grounding_issues(as_llm, report) == []
    if report.is_placeholder_data:
        assert fb.caveats[0] in {"The figures are illustrative placeholders, not real Jordanian trade statistics.",
                                 "الأرقام توضيحية مؤقتة وليست إحصاءات تجارة أردنية حقيقية."}


def test_fallback_handles_missing_data():
    record = PLASTIC.model_copy(update={"imports_usd": {**PLASTIC.imports_usd, 2020: None},
                                        "local_cost_per_kg_est_usd": None})
    report = compute_report(record)
    fb = fallback_explanation(report, "en")
    assert report.verdict_forced_maybe and "incomplete" in fb.summary
    assert "?" not in " ".join(fb.reasons_for + fb.concerns)
    assert grounding_issues(ExplanationLLMOutput(**fb.model_dump(exclude={"language"})), report) == []


# --- free-text notes, estimates, risk notes ------------------------------------------

RICH = PLASTIC.model_copy(update={
    "risk_notes": "Resin prices rose 8.3% in 2024 and about 1.6 million USD of stock is held by importers.",
    "competition_note": "3 large importers dominate.",
    "estimated_fields": ["local_cost_per_kg_est_usd", "shipping_pct"],
    "machine_cost_jod_min": 15000.0, "machine_cost_jod_max": 40000.0,
})


def test_numbers_quoted_from_risk_notes_are_grounded():
    report = compute_report(RICH)
    assert grounding_issues(explanation("Resin prices rose 8.3%, and 1.6 million USD of stock is held."), report) == []
    assert grounding_issues(explanation("Machines cost 15,000 to 40,000 JOD."), report) == []


def test_numbers_from_nowhere_still_fail_with_notes_present():
    report = compute_report(RICH)
    assert grounding_issues(explanation("Resin prices rose 9.7%."), report) == ["9.7"]


def test_llm_facts_include_new_fields_once():
    # Numbers and short lists live in key_figures; long text lives in data_notes (step 5 of the real-data work).
    facts = llm_facts(compute_report(RICH))
    k, notes = facts["key_figures"], facts["data_notes"]
    for name in ("import_trend", "machinery", "raw_materials", "machine_cost_range_jod", "estimated_fields"):
        assert name in k
    for name in ("risk_notes", "competition_note"):
        assert name in notes and name not in k and name not in facts["report"]
    assert k["estimated_fields"] == ["local_cost_per_kg_est_usd", "shipping_pct"]
    assert k["machine_cost_range_jod"] == {"min": 15000.0, "max": 40000.0}


@pytest.mark.parametrize(("language", "word"), [("en", "estimates"), ("ar", "تقديرية")])
def test_fallback_mentions_estimated_fields(language, word):
    fb = fallback_explanation(compute_report(RICH), language)
    estimate_caveats = [c for c in fb.caveats if word in c]
    assert len(estimate_caveats) == 1
    assert ("local production cost" if language == "en" else "تكلفة الإنتاج المحلي") in estimate_caveats[0]


def test_fallback_without_estimated_fields_has_no_estimate_caveat():
    assert not any("estimates, not measured" in c for c in fallback_explanation(compute_report(PLASTIC), "en").caveats)


@pytest.mark.parametrize("language", ["en", "ar"])
def test_fallback_uses_risk_notes_as_first_concern(language):
    report = compute_report(RICH)
    fb = fallback_explanation(report, language)
    assert fb.concerns[0] == RICH.risk_notes and len(fb.concerns) == 3
    assert grounding_issues(ExplanationLLMOutput(**fb.model_dump(exclude={"language"})), report) == []


# --- landed cost wording ---------------------------------------------------------------

def test_key_figures_mark_shipping_as_information_only():
    k = key_figures(compute_report(PLASTIC))
    assert "shipping_pct" not in k and k["shipping_pct_info_only"] == 8.0
    assert k["landed_cost_per_kg_usd"] == 3.0 and "freight is already inside the CIF price" in k["landed_cost_formula"]


@pytest.mark.parametrize(("language", "phrase"), [("en", "freight is already in the import price"),
                                                   ("ar", "الشحن مشمول أصلاً في سعر الاستيراد")])
def test_fallback_cost_sentence_says_freight_is_in_cif(language, phrase):
    fb = fallback_explanation(compute_report(PLASTIC), language)
    assert any(phrase in s for s in fb.reasons_for + fb.concerns)
    assert not any("after shipping" in s or "بعد الشحن" in s for s in fb.reasons_for + fb.concerns)


# --- cost gate wording ---------------------------------------------------------------------

@pytest.mark.parametrize(("language", "phrase"), [("en", "The verdict was limited because producing locally"),
                                                   ("ar", "تم تقييد النتيجة لأن الإنتاج المحلي")])
def test_fallback_explains_cost_gate_with_figures(language, phrase):
    gated = PLASTIC.model_copy(update={"local_cost_per_kg_est_usd": 4.2})  # landed 3.0 -> margin -0.4 -> DONT
    report = compute_report(gated)
    assert report.verdict_capped_by == "cost_gate" and report.verdict == "DONT"
    fb = fallback_explanation(report, language)
    assert phrase in fb.summary and "4.2" in fb.summary and "3" in fb.summary
    assert grounding_issues(ExplanationLLMOutput(**fb.model_dump(exclude={"language"})), report) == []
    assert key_figures(report)["verdict_capped_by"] == "cost_gate"


def test_fallback_without_gate_has_no_gate_sentence():
    assert "limited because" not in fallback_explanation(compute_report(PLASTIC), "en").summary


# --- capex -------------------------------------------------------------------------------------

BIG_CAPEX = PLASTIC.model_copy(update={"machine_cost_usd_min": 45_000.0, "machine_cost_usd_max": 420_000.0,
                                       "risk_notes": "Cold chain needed."})


def test_key_figures_include_capex_with_scope():
    k = key_figures(compute_report(BIG_CAPEX))
    assert k["capex_usd_range"]["min"] == 45_000 and k["capex_usd_range"]["max"] == 420_000
    assert "equipment only, partial" in k["capex_usd_range"]["scope"]
    assert k["flags"] == ["high_capital_requirement"]


def test_capex_numbers_are_grounded():
    report = compute_report(BIG_CAPEX)
    assert grounding_issues(explanation("Equipment alone is listed at 45,000 to 420,000 USD."), report) == []
    assert grounding_issues(explanation("Equipment costs 600,000 USD."), report) == ["600000"]


@pytest.mark.parametrize(("language", "phrases"), [
    ("en", ["High capital requirement", "45,000 to 420,000 USD", "only part of the investment", "ex-works"]),
    ("ar", ["رأس المال المطلوب مرتفع", "45,000", "420,000", "جزء من الاستثمار فقط"]),
])
def test_fallback_lists_high_capex_as_concern(language, phrases):
    report = compute_report(BIG_CAPEX)
    fb = fallback_explanation(report, language)
    assert fb.concerns[0] == "Cold chain needed." and len(fb.concerns) == 3  # risk note first, capex second
    for phrase in phrases:
        assert phrase in fb.concerns[1]
    assert grounding_issues(ExplanationLLMOutput(**fb.model_dump(exclude={"language"})), report) == []


def test_no_capex_concern_without_flag():
    small = PLASTIC.model_copy(update={"machine_cost_usd_min": 9_200.0, "machine_cost_usd_max": 30_800.0})
    assert not any("High capital requirement" in c for c in fallback_explanation(compute_report(small), "en").concerns)


# --- long free text from the real data (step 5) ----------------------------------------------

REAL_NOTES = PLASTIC.model_copy(update={
    "source_notes": (
        "Imports & weight: UN Comtrade (Jordan=400, partner World, flow M, CIF USD), pulled 2026-10-09. "
        "Customs: WITS/TRAINS MFN simple average 2023. Freight: China->Aqaba 40ft USD 7575 (Goodhope Freight, "
        "Sep 2026 quotes 7,300-7,850); payload 6500 kg per container is an estimate. Raw material: WITS: Jordan "
        "imports 730630 welded steel tube 2023 = 4,766.65k USD / 3,199,080 kg. FX: 1 JOD = 1.4104 USD (CBJ peg 0.709)."
    ),
    "risk_notes": "أنابيب الحديد مستوردة جزئياً؛ السوق صغير (2.2 مليون دولار سنة 2024)",
    "machine_source": "Made-in-China supplier listings, Oct 2026: Tube bender USD 4,000-4,200 to 8,000-24,800",
})


@pytest.mark.parametrize(
    "sentence",
    [
        "Freight from China to Aqaba is about 7575 USD per 40ft container, with a payload of 6500 kg.",
        "Freight quotes ranged from 7,300 to 7,850 USD.",
        "Welded steel tube imports were 3,199,080 kg (4,766.65 thousand USD).",
        "السوق صغير: 2.2 مليون دولار",
        "A tube bender costs 4,000-4,200 USD, larger ones up to 24,800 USD.",
        "The exchange rate is 0.709 JOD per USD.",
    ],
)
def test_numbers_from_real_free_text_are_grounded(sentence):
    assert grounding_issues(explanation(sentence), compute_report(REAL_NOTES)) == []


@pytest.mark.parametrize("sentence", ["Freight is 9100 USD per container.", "The payload is 7200 kg."])
def test_invented_numbers_still_fail_with_long_notes(sentence):
    assert grounding_issues(explanation(sentence), compute_report(REAL_NOTES)) != []


# --- break-even ----------------------------------------------------------------------------------

# landed 3.0, local 1.9 (fixture) -> saving 1.1 USD/kg; capex mid 20,000 -> 18.2 t
BREAK_EVEN = PLASTIC.model_copy(update={"machine_cost_usd_min": 10_000.0, "machine_cost_usd_max": 30_000.0})


def test_key_figures_include_break_even_with_scope():
    report = compute_report(BREAK_EVEN)
    k = key_figures(report)["break_even"]
    assert report.break_even.break_even_tons == 18.2 and k["break_even_tons"] == 18  # whole tonnes from 10 t up
    assert k["share_of_latest_year_imports_pct"] == 0.2
    assert k["equipment_cost_mid_usd"] == 20_000 and "excludes buildings and working capital" in k["scope"]
    assert key_figures(compute_report(PLASTIC))["break_even"] is None


@pytest.mark.parametrize(("language", "phrase"), [("en", "Indicative break-even"), ("ar", "نقطة التعادل (تقديرية)")])
def test_fallback_mentions_break_even_once_and_is_grounded(language, phrase):
    report = compute_report(BREAK_EVEN)
    fb = fallback_explanation(report, language)
    assert fb.summary.count(phrase) == 1 and "20,000" in fb.summary
    assert grounding_issues(ExplanationLLMOutput(**fb.model_dump(exclude={"language"})), report) == []
    assert phrase not in fallback_explanation(compute_report(PLASTIC), language).summary


def test_break_even_numbers_are_grounded():
    report = compute_report(BREAK_EVEN)
    be = report.break_even
    tons, share = f"{be.break_even_tons:g}", f"{be.share_of_2024_imports * 100:.1f}"
    assert grounding_issues(explanation(f"Break-even is about {tons} tonnes, {share}% of imports."), report) == []
    assert grounding_issues(explanation("Break-even is about 917 tonnes."), report) == ["917"]
