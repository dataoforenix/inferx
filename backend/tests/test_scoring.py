from __future__ import annotations

import math
import random

import pytest
from pydantic import ValidationError

from app.data_store import load_categories
from app.schemas import CategoryRecord, WhatIfOverrides
from app.scoring import (
    MIN_COMPLETENESS,
    cagr,
    clamp,
    competition_score,
    compute_report,
    cost_score,
    feasibility_score,
    landed_cost,
    margin,
    round1,
    trend_score,
    verdict_for,
    volume_score,
)
from tests.conftest import TEST_CSV


def make_record(**changes) -> CategoryRecord:
    """A simple record whose score is easy to compute by hand (see test_full_report_hand_calculated)."""
    imports = {2020: 10e6, 2021: 10e6, 2022: 10e6, 2023: 10e6, 2024: 10e6}
    imports.update(changes.pop("imports", {}))
    base = dict(
        category_id="test_cat", name_en="Test", name_ar="اختبار", description_en="test",
        keywords_en=[], keywords_ar=[], hs6="123456", imports_usd=imports,
        import_weight_kg_2024=1e6, import_price_per_kg_usd=10.0, shipping_pct=0.0, customs_pct=0.0,
        local_cost_per_kg_est_usd=10.0, machinery_availability=3.0, raw_material_local=3.0,
        skills_availability=3.0, local_factories=5, factories_saturation=10,
        machinery="", raw_materials="", data_status="ESTIMATE", source_notes="",
    )
    base.update(changes)
    return CategoryRecord(**base)


# --- formulas -----------------------------------------------------------------

@pytest.mark.parametrize(
    ("imports", "expected"),
    [(0, 0.0), (9e6, 10 / math.log10(101)), (100e6, 10.0), (5e9, 10.0)],
)
def test_volume_score(imports, expected):
    assert volume_score(imports) == pytest.approx(expected)


def test_cagr():
    assert cagr(100, 200) == pytest.approx(2 ** 0.25 - 1)
    assert cagr(100, 100) == 0
    assert cagr(100, 0) == -1
    assert cagr(0, 100) is None


@pytest.mark.parametrize(("growth", "expected"), [(0, 5), (0.05, 7.5), (0.1, 10), (0.5, 10), (-0.1, 0), (-1, 0)])
def test_trend_score_and_clamping(growth, expected):
    assert trend_score(growth) == pytest.approx(expected)


def test_landed_cost_is_cif_plus_customs():
    # CIF already contains freight: landed = price x (1 + customs), shipping is not added.
    assert landed_cost(10, 0.2) == pytest.approx(12.0)
    assert landed_cost(4.404, 0.25) == pytest.approx(5.505)


@pytest.mark.parametrize(("m", "expected"), [(0, 5), (0.1, 7.5), (0.2, 10), (0.9, 10), (-0.2, 0), (-5, 0)])
def test_cost_score_and_clamping(m, expected):
    assert cost_score(m) == pytest.approx(expected)


def test_margin():
    assert margin(10, 8) == pytest.approx(0.2)
    assert margin(10, 12) == pytest.approx(-0.2)
    assert margin(0, 1) is None


def test_feasibility_score():
    assert feasibility_score(5, 5, 5) == 10
    assert feasibility_score(3, 3, 3) == pytest.approx(6)
    assert feasibility_score(0, 0, 0) == 0


def test_competition_score():
    assert competition_score(0, 10) == 10
    assert competition_score(5, 10) == pytest.approx(5)
    assert competition_score(10, 10) == 0
    assert competition_score(30, 10) == 0


@pytest.mark.parametrize(
    ("score", "verdict"),
    [(10, "MANUFACTURE"), (6.0, "MANUFACTURE"), (5.9, "MAYBE"), (4.0, "MAYBE"), (3.9, "DONT"), (0, "DONT")],
)
def test_verdict_thresholds(score, verdict):
    assert verdict_for(score) == verdict


@pytest.mark.parametrize(("x", "expected"), [(5.95, 6.0), (5.94, 5.9), (2.25, 2.3), (0.05, 0.1), (7.0, 7.0)])
def test_round1_is_half_up(x, expected):
    assert round1(x) == expected


def test_clamp_rejects_nan():
    assert clamp(-3) == 0 and clamp(42) == 10 and clamp(float("inf")) == 10
    with pytest.raises(ValueError):
        clamp(float("nan"))


# --- full report ----------------------------------------------------------------

def test_full_report_hand_calculated():
    rep = compute_report(make_record())
    vol = 10 * math.log10(11) / math.log10(101)
    market = 0.6 * vol + 0.4 * 5
    expected = 0.35 * market + 0.30 * 5 + 0.20 * 6 + 0.15 * 5
    assert rep.market.score == pytest.approx(market, abs=0.01)
    assert rep.cost.score == 5 and rep.cost.margin == 0 and rep.cost.landed_cost_per_kg_usd == 10
    assert rep.feasibility.score == 6 and rep.competition.score == 5
    assert rep.score == round1(expected) == 5.2  # 0.35*5.118 + 1.5 + 1.2 + 0.75 = 5.241
    assert rep.verdict == "MAYBE"
    assert rep.data_completeness == 1.0 and not rep.verdict_forced_maybe and rep.missing_fields == []


def test_weights_sum_to_one():
    assert sum(compute_report(make_record()).weights.values()) == pytest.approx(1.0)


def test_manufacture_and_dont_verdicts():
    good = compute_report(make_record(local_cost_per_kg_est_usd=5.0, local_factories=0,
                                      imports={2024: 200e6}, machinery_availability=5.0))
    bad = compute_report(make_record(local_cost_per_kg_est_usd=20.0, local_factories=50,
                                     imports={2024: 1e6}, machinery_availability=0.0))
    assert good.verdict == "MANUFACTURE" and good.score >= 6
    assert bad.verdict == "DONT" and bad.score < 4


def test_placeholder_data_is_flagged():
    rep = compute_report(make_record(data_status="TODO_REAL_DATA"))
    assert rep.is_placeholder_data
    assert any("TODO_REAL_DATA" in n for n in rep.notes)


def test_real_csv_categories_all_score():
    for record in load_categories(TEST_CSV).list():
        rep = compute_report(record)
        assert rep.score is not None and 0 <= rep.score <= 10
        assert rep.verdict == verdict_for(rep.score)


# --- missing / invalid data ---------------------------------------------------

def test_missing_first_year_uses_volume_only():
    rep = compute_report(make_record(imports={2020: None}))
    assert rep.market.trend_score is None and rep.market.cagr is None
    assert rep.market.score == rep.market.volume_score
    assert rep.data_completeness == pytest.approx(1 - 0.35 * 0.4)
    assert not rep.verdict_forced_maybe
    assert "imports_2020_usd" in rep.missing_fields


def test_zero_first_year_disables_trend():
    rep = compute_report(make_record(imports={2020: 0.0}))
    assert rep.market.trend_score is None
    assert any("zero" in n for n in rep.notes)


def test_missing_latest_imports_forces_maybe():
    rep = compute_report(make_record(imports={2024: None}, local_cost_per_kg_est_usd=1.0, local_factories=0,
                                     machinery_availability=5.0, raw_material_local=5.0, skills_availability=5.0))
    assert rep.market.score is None
    assert rep.data_completeness == pytest.approx(0.65)
    assert rep.score >= 6  # the available components look great...
    assert rep.verdict == "MAYBE" and rep.verdict_forced_maybe  # ...but completeness is too low to trust it


def test_missing_cost_forces_maybe():
    rep = compute_report(make_record(local_cost_per_kg_est_usd=None))
    assert rep.cost.score is None and rep.data_completeness == pytest.approx(0.70)
    assert rep.verdict == "MAYBE" and rep.verdict_forced_maybe


def test_missing_feasibility_at_threshold_is_not_forced():
    rep = compute_report(make_record(skills_availability=None))
    assert rep.data_completeness == pytest.approx(MIN_COMPLETENESS)
    assert not rep.verdict_forced_maybe


def test_all_missing():
    rep = compute_report(make_record(
        imports={y: None for y in range(2020, 2025)}, import_price_per_kg_usd=None, local_factories=None,
        machinery_availability=None,
    ))
    assert rep.score is None and rep.verdict == "MAYBE" and rep.verdict_forced_maybe
    assert rep.data_completeness == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"import_price_per_kg_usd": float("nan")},
        {"import_price_per_kg_usd": 0.0},
        {"customs_pct": float("inf")},
        {"machinery_availability": 9.0},
        {"imports": {2024: float("nan")}},
        {"imports": {2020: -5.0}},
        {"factories_saturation": 0},
    ],
)
def test_invalid_inputs_are_ignored_not_propagated(changes):
    rep = compute_report(make_record(**changes))
    assert rep.score is not None and math.isfinite(rep.score) and 0 <= rep.score <= 10
    assert rep.data_completeness < 1
    assert any("invalid value" in n for n in rep.notes)


def test_random_inputs_never_produce_nan():
    rng = random.Random(1234)
    weird = [None, float("nan"), float("inf"), -1.0, 0.0, 1e-12, 1e15]

    def pick(lo, hi):
        return rng.choice(weird) if rng.random() < 0.3 else rng.uniform(lo, hi)

    for _ in range(500):
        rec = make_record(
            imports={y: pick(0, 1e9) for y in range(2020, 2025)},
            import_price_per_kg_usd=pick(0, 100), shipping_pct=pick(0, 1), customs_pct=pick(0, 1),
            local_cost_per_kg_est_usd=pick(0, 100), machinery_availability=pick(0, 5),
            raw_material_local=pick(0, 5), skills_availability=pick(0, 5),
            local_factories=rng.choice([None, 0, 3, 50, 10_000]), factories_saturation=rng.choice([None, 1, 20]),
        )
        rep = compute_report(rec)
        assert rep.score is None or (math.isfinite(rep.score) and 0 <= rep.score <= 10)
        assert rep.verdict in {"MANUFACTURE", "MAYBE", "DONT"}
        assert 0 <= rep.data_completeness <= 1
        rep.model_dump_json()  # must serialise (no NaN/inf in JSON)


# --- what-if overrides ---------------------------------------------------------

def test_overrides_are_applied_and_reported():
    rec = make_record()
    rep = compute_report(rec, WhatIfOverrides(customs_pct=0.3, local_factories=0))
    assert rep.cost.customs_pct == 0.3 and rep.competition.local_factories == 0
    assert rep.overrides_applied == {"customs_pct": 0.3, "local_factories": 0.0}
    assert rec.customs_pct == 0.0  # record untouched


def test_empty_overrides_match_baseline():
    rec = make_record()
    assert compute_report(rec, WhatIfOverrides()) == compute_report(rec)


def test_override_can_fill_missing_value():
    rec = make_record(local_cost_per_kg_est_usd=None)
    rep = compute_report(rec, WhatIfOverrides(local_cost_per_kg_est_usd=8.0))
    assert rep.cost.score is not None and rep.data_completeness == 1.0 and not rep.verdict_forced_maybe


def _scores(field, values):
    # Base chosen so no component starts saturated at 0 or 10.
    rec = make_record(local_cost_per_kg_est_usd=11.0, customs_pct=0.05)
    return [compute_report(rec, WhatIfOverrides(**{field: v})).score for v in values]


@pytest.mark.parametrize(
    ("field", "values", "direction"),
    [
        ("customs_pct", [0, 0.05, 0.1, 0.2, 0.5, 1, 2], "up"),
        ("import_price_per_kg_usd", [1, 5, 9, 10, 11, 12, 20, 100], "up"),
        ("local_cost_per_kg_est_usd", [1, 5, 9, 10, 11, 12, 20, 100], "down"),
        ("local_factories", [0, 1, 3, 5, 8, 10, 20, 1000], "down"),
    ],
)
def test_overrides_are_monotonic(field, values, direction):
    scores = _scores(field, values)
    pairs = list(zip(scores, scores[1:]))
    if direction == "up":
        assert all(a <= b for a, b in pairs), scores
    else:
        assert all(a >= b for a, b in pairs), scores
    assert scores[0] != scores[-1]  # the override actually moves the score


@pytest.mark.parametrize(
    "bad",
    [
        {"customs_pct": -0.1}, {"customs_pct": 2.5}, {"shipping_pct": 3}, {"local_cost_per_kg_est_usd": 0},
        {"import_price_per_kg_usd": -1}, {"local_factories": -1}, {"local_factories": 2.5},
        {"customs_pct": float("nan")}, {"unknown_field": 1},
    ],
)
def test_override_validation(bad):
    with pytest.raises(ValidationError):
        WhatIfOverrides(**bad)


# --- category context on the report (final CSV schema) ------------------------------

@pytest.mark.parametrize(
    ("first", "last", "label"),
    [(10e6, 14e6, "growing"), (10e6, 10.5e6, "stable"), (10e6, 8e6, "declining"), (0.0, 10e6, None)],
)
def test_trend_label(first, last, label):
    assert compute_report(make_record(imports={2020: first, 2024: last})).trend_label == label


def test_trend_label_thresholds():
    from app.scoring import trend_label
    assert trend_label(0.03) == "stable" and trend_label(0.0301) == "growing"
    assert trend_label(-0.03) == "stable" and trend_label(-0.0301) == "declining"


def test_report_exposes_csv_context():
    rep = compute_report(make_record(
        machinery="Injection moulding machine; moulds ;", raw_materials="PP resin;",
        risk_notes="Resin prices are volatile.", competition_note="Two large importers.",
        source_notes="UN Comtrade 2024", source_url="https://a.example", tariff_source_url="",
        estimated_fields=["local_cost_per_kg_est_usd"], machine_cost_jod_min=15000.0, machine_cost_jod_max=None,
    ))
    assert rep.machinery == ["Injection moulding machine", "moulds"] and rep.raw_materials == ["PP resin"]
    assert rep.risk_notes == "Resin prices are volatile." and rep.competition_note == "Two large importers."
    assert rep.source_notes == "UN Comtrade 2024" and rep.sources == ["https://a.example"]
    assert rep.estimated_fields == ["local_cost_per_kg_est_usd"]
    assert rep.machine_cost_range_jod.min == 15000 and rep.machine_cost_range_jod.max is None


def test_report_context_defaults():
    rep = compute_report(make_record())
    assert rep.machine_cost_range_jod is None and rep.sources == [] and rep.estimated_fields == []
    assert rep.trend_label == "stable"


def test_context_fields_do_not_change_the_score():
    plain = compute_report(make_record())
    rich = compute_report(make_record(risk_notes="x", estimated_fields=["shipping_pct"], machine_cost_jod_min=1.0))
    assert (plain.score, plain.verdict, plain.data_completeness) == (rich.score, rich.verdict, rich.data_completeness)


def test_report_exposes_cost_build_capex_and_machine_sources():
    rep = compute_report(make_record(
        raw_material_price_usd_per_kg=1.49, material_kg_per_kg_product=1.15, conversion_cost_per_kg_usd=2.0,
        machine_cost_usd_min=9200.0, machine_cost_usd_max=30800.0, machine_source="Supplier listings",
        source_url="https://a.example", machine_source_urls=["https://m1.example", "https://m2.example"],
    ))
    assert (rep.cost.raw_material_price_usd_per_kg, rep.cost.material_kg_per_kg_product,
            rep.cost.conversion_cost_per_kg_usd) == (1.49, 1.15, 2.0)
    assert rep.capex_usd_range.min == 9200 and rep.capex_usd_range.max == 30800
    assert rep.machine_source == "Supplier listings"
    assert rep.sources == ["https://a.example", "https://m1.example", "https://m2.example"]


def test_capex_range_absent_without_usd_costs():
    rep = compute_report(make_record())
    assert rep.capex_usd_range is None and rep.machine_source == "" and rep.cost.conversion_cost_per_kg_usd is None


def test_capex_description_says_equipment_only():
    from app.schemas import FeasibilityReport

    text = FeasibilityReport.model_fields["capex_usd_range"].description
    for phrase in ("Equipment only", "supplier listing prices ex-works", "excluding shipping, customs, installation",
                   "moulds and buildings"):
        assert phrase in text


# --- landed cost = CIF x (1 + customs); shipping is information only ----------------------

def test_landed_cost_hand_computed_in_report():
    rep = compute_report(make_record(shipping_pct=0.5, customs_pct=0.2, import_price_per_kg_usd=10.0,
                                     local_cost_per_kg_est_usd=10.0))
    assert rep.cost.landed_cost_per_kg_usd == 12.0  # 10 x 1.2, the 50% shipping is NOT added
    assert rep.cost.margin == pytest.approx(0.1667, abs=1e-4)  # (12 - 10) / 12
    assert rep.cost.score == pytest.approx(9.17, abs=0.01)  # 5 + 0.1667 x 25
    assert rep.cost.shipping_pct == 0.5  # still reported


@pytest.mark.parametrize("shipping", [0.0, 0.08, 0.5, 2.0, None])
def test_shipping_never_changes_the_score(shipping):
    base = compute_report(make_record(shipping_pct=0.0))
    rep = compute_report(make_record(shipping_pct=shipping))
    assert (rep.score, rep.verdict, rep.cost.score, rep.data_completeness) == (
        base.score, base.verdict, base.cost.score, base.data_completeness)


def test_missing_or_invalid_shipping_keeps_cost_and_completeness():
    for shipping in (None, -0.5, float("nan")):
        rep = compute_report(make_record(shipping_pct=shipping))
        assert rep.cost.score is not None and rep.data_completeness == 1.0
        assert "shipping_pct" not in rep.missing_fields
    invalid = compute_report(make_record(shipping_pct=-0.5))
    assert invalid.cost.shipping_pct is None
    assert any("shipping_pct has an invalid value" in n and "information only" in n for n in invalid.notes)


def test_shipping_override_is_informational():
    rec = make_record(local_cost_per_kg_est_usd=11.0, customs_pct=0.05)
    base = compute_report(rec)
    for value in (0, 0.1, 1, 2):
        rep = compute_report(rec, WhatIfOverrides(shipping_pct=value))
        assert rep.score == base.score and rep.cost.shipping_pct == value
        assert any("shipping_pct is information only" in n for n in rep.notes)
    assert not any("shipping_pct is information only" in n for n in base.notes)


# --- cost gate ----------------------------------------------------------------------------

def gate_record(local: float, **changes) -> "CategoryRecord":
    """price 10, customs 0 -> landed 10, so margin = (10 - local) / 10. Every other component is strong:
    market 0.6x10 + 0.4x5 = 8.0, feasibility 10, competition 10 -> score = 6.3 + 0.3 x cost."""
    base = dict(imports={y: 200e6 for y in range(2020, 2025)}, import_price_per_kg_usd=10.0, customs_pct=0.0,
                local_cost_per_kg_est_usd=local, machinery_availability=5.0, raw_material_local=5.0,
                skills_availability=5.0, local_factories=0)
    base.update(changes)
    return make_record(**base)


@pytest.mark.parametrize(
    ("local", "margin", "raw_score", "score", "verdict", "capped"),
    [
        (8.0, 0.20, 9.3, 9.3, "MANUFACTURE", None),      # cost 10    -> 6.3 + 3.0
        (10.0, 0.0, 7.8, 7.8, "MANUFACTURE", None),      # cost 5     -> 6.3 + 1.5 (margin 0 is not < 0)
        (10.1, -0.01, 7.7, 5.9, "MAYBE", "cost_gate"),   # cost 4.75  -> 7.725 -> capped at 5.9
        (11.0, -0.10, 7.1, 5.9, "MAYBE", "cost_gate"),   # cost 2.5   -> 7.05  -> capped at 5.9
        (12.5, -0.25, 6.3, 5.9, "MAYBE", "cost_gate"),   # cost 0     -> -0.25 is not < -0.25: MAYBE tier
        (13.0, -0.30, 6.3, 3.9, "DONT", "cost_gate"),    # cost 0     -> DONT, capped at 3.9
    ],
)
def test_cost_gate_margins(local, margin, raw_score, score, verdict, capped):
    rep = compute_report(gate_record(local))
    assert rep.cost.margin == pytest.approx(margin, abs=1e-9)
    assert rep.score == score and rep.verdict == verdict and rep.verdict_capped_by == capped
    if capped:
        note = next(n for n in rep.notes if "cost gate" in n)
        assert f"({local:g} USD/kg)" in note and "(10 USD/kg landed)" in note
    # Without the gate this is what the weighted formula gives (weights / thresholds unchanged).
    assert verdict_for(raw_score) == ("MANUFACTURE" if raw_score >= 6 else "MAYBE")


def test_gate_does_not_raise_a_low_score_or_verdict():
    # Already MAYBE below 5.9: the gate changes nothing, so it is not reported as the cap.
    # margin -0.05 -> cost 3.75; 0.35x8 + 0.3x3.75 + 0.2x0 + 0.15x10 = 5.425 -> 5.4 MAYBE (below the 5.9 cap)
    rep = compute_report(gate_record(10.5, machinery_availability=0.0, raw_material_local=0.0,
                                     skills_availability=0.0))
    assert rep.cost.margin < 0 and rep.verdict == "MAYBE" and rep.score == 5.4
    assert rep.verdict_capped_by is None
    assert any("costs more than importing" in n for n in rep.notes)


@pytest.mark.parametrize(
    ("local", "verdict"), [(8.0, "MAYBE"), (11.0, "MAYBE"), (13.0, "DONT")],
)
def test_gate_with_forced_maybe_lower_verdict_wins(local, verdict):
    rep = compute_report(gate_record(local, imports={2024: None}))  # market missing -> completeness 0.65
    assert rep.verdict_forced_maybe and rep.data_completeness == pytest.approx(0.65)
    assert rep.verdict == verdict


def test_whatif_crosses_the_gate():
    rec = gate_record(8.0)
    assert compute_report(rec).verdict == "MANUFACTURE"
    up = compute_report(rec, WhatIfOverrides(local_cost_per_kg_est_usd=11.0))
    assert (up.verdict, up.score, up.verdict_capped_by) == ("MAYBE", 5.9, "cost_gate")
    way_up = compute_report(rec, WhatIfOverrides(local_cost_per_kg_est_usd=13.0))
    assert (way_up.verdict, way_up.score) == ("DONT", 3.9)
    # Customs protection can move a category back across the gate.
    back = compute_report(gate_record(11.0), WhatIfOverrides(customs_pct=0.2))  # landed 12 > local 11
    assert back.verdict == "MANUFACTURE" and back.verdict_capped_by is None


def test_gate_keeps_monotonicity_in_local_cost():
    scores = [compute_report(gate_record(c)).score for c in (5, 8, 9.9, 10, 10.1, 11, 12.5, 13, 20)]
    assert all(a >= b for a, b in zip(scores, scores[1:])), scores


# --- high capital requirement flag -----------------------------------------------------------

@pytest.mark.parametrize(
    ("capex_max", "flagged"), [(None, False), (55_000.0, False), (249_999.0, False), (250_000.0, True), (500_000.0, True)],
)
def test_high_capital_flag(capex_max, flagged):
    rep = compute_report(make_record(machine_cost_usd_min=50_000.0 if capex_max else None, machine_cost_usd_max=capex_max))
    assert (rep.flags == ["high_capital_requirement"]) is flagged
    assert any("high capital requirement" in n and "equipment only" in n for n in rep.notes) is flagged


def test_capex_flag_never_changes_the_score():
    plain = compute_report(make_record())
    flagged = compute_report(make_record(machine_cost_usd_min=50_000.0, machine_cost_usd_max=900_000.0))
    assert flagged.flags and (flagged.score, flagged.verdict, flagged.data_completeness) == (
        plain.score, plain.verdict, plain.data_completeness)


# --- break-even ------------------------------------------------------------------

def test_break_even_hand_calculated():
    # landed 10 x 1.2 = 12, local 10 -> saving 2 USD/kg; capex mid 30,000 -> 15,000 kg = 15 t = 1.5% of 1,000 t
    rep = compute_report(make_record(customs_pct=0.2, machine_cost_usd_min=20_000.0, machine_cost_usd_max=40_000.0))
    be = rep.break_even
    assert be.capex_mid_usd == 30_000 and be.unit_saving_usd_per_kg == 2.0
    assert be.break_even_tons == 15.0 and be.share_of_2024_imports == pytest.approx(0.015)
    assert rep.import_weight_kg_2024 == 1e6


@pytest.mark.parametrize("changes", [
    {"machine_cost_usd_min": None, "machine_cost_usd_max": None},  # no capex range
    {"machine_cost_usd_min": None},  # only half of the range
    {"import_weight_kg_2024": None},
    {"customs_pct": 0.0},  # landed == local: no saving
    {"local_cost_per_kg_est_usd": 13.0},  # local dearer than import
    {"local_cost_per_kg_est_usd": None},  # no cost data
])
def test_break_even_is_null_without_inputs_or_saving(changes):
    base = {"customs_pct": 0.2, "machine_cost_usd_min": 20_000.0, "machine_cost_usd_max": 40_000.0}
    assert compute_report(make_record(**{**base, **changes})).break_even is None


def test_break_even_follows_whatif_overrides():
    record = make_record(customs_pct=0.2, machine_cost_usd_min=20_000.0, machine_cost_usd_max=40_000.0)
    cheaper = compute_report(record, WhatIfOverrides(local_cost_per_kg_est_usd=8.0)).break_even  # saving 4
    assert cheaper.break_even_tons == 7.5
    assert compute_report(record, WhatIfOverrides(customs_pct=0.0)).break_even is None  # saving gone
    assert compute_report(record, WhatIfOverrides(customs_pct=0.0, import_price_per_kg_usd=12.5)).break_even \
        .unit_saving_usd_per_kg == 2.5
    assert compute_report(record, WhatIfOverrides(shipping_pct=0.5)).break_even == compute_report(record).break_even


def test_break_even_never_changes_the_score():
    plain = make_record(customs_pct=0.2)
    with_capex = make_record(customs_pct=0.2, machine_cost_usd_min=20_000.0, machine_cost_usd_max=40_000.0)
    a, b = compute_report(plain), compute_report(with_capex)
    assert (a.score, a.verdict, a.data_completeness) == (b.score, b.verdict, b.data_completeness)
