"""Deterministic feasibility scoring. Pure functions: no I/O, no LLM calls.

Missing or invalid inputs make the affected component unavailable instead of
guessing. The weighted score is renormalised over the available components, and
data_completeness records how much of the full weight was actually backed by data.
When completeness falls below MIN_COMPLETENESS the verdict is forced to MAYBE.
"""

from __future__ import annotations

import math

from app.schemas import (
    IMPORT_YEARS,
    BreakEven,
    CategoryRecord,
    CompetitionBreakdown,
    CostBreakdown,
    FeasibilityBreakdown,
    CapexRange,
    FeasibilityReport,
    MachineCostRange,
    MarketBreakdown,
    TrendLabel,
    Verdict,
    WhatIfOverrides,
)

from app.guidance import ADVISORS, next_steps_for, supplier_links, usd_to_jod  # noqa: E402

WEIGHTS = {"market": 0.35, "cost": 0.30, "feasibility": 0.20, "competition": 0.15}
VOLUME_SHARE, TREND_SHARE = 0.6, 0.4
MANUFACTURE_THRESHOLD = 6.0
MAYBE_THRESHOLD = 4.0
MIN_COMPLETENESS = 0.8  # e.g. losing the whole cost (0.30) or market (0.35) component forces MAYBE

# Cost gate: if making it locally costs more than importing (margin < 0), the product can't be a
# MANUFACTURE however good the market is. Applied after the weighted score; weights and the
# 6.0 / 4.0 thresholds are unchanged.
COST_GATE_MAYBE_BELOW = 0.0  # margin < 0     -> verdict at most MAYBE, score capped at 5.9
COST_GATE_MAYBE_SCORE_CAP = 5.9
COST_GATE_DONT_BELOW = -0.25  # margin < -0.25 -> verdict DONT, score capped at 3.9
COST_GATE_DONT_SCORE_CAP = 3.9
_VERDICT_RANK = {"DONT": 0, "MAYBE": 1, "MANUFACTURE": 2}

# Flags (information for the user; they never change the score).
HIGH_CAPEX_USD = 250_000  # machine_cost_usd_max at or above this -> "high_capital_requirement"
HIGH_CAPITAL_FLAG = "high_capital_requirement"

FIRST_YEAR, LATEST_YEAR = IMPORT_YEARS[0], IMPORT_YEARS[-1]


# --- primitives ---------------------------------------------------------------

def clamp(x: float, lo: float = 0.0, hi: float = 10.0) -> float:
    if math.isnan(x):
        raise ValueError("clamp() received NaN")
    return max(lo, min(hi, x))


def round1(x: float) -> float:
    """Round half up to one decimal (Python's round() uses banker's rounding)."""
    return math.floor(x * 10 + 0.5) / 10


def volume_score(latest_import_usd: float) -> float:
    return clamp(10 * math.log10(1 + latest_import_usd / 1e6) / math.log10(101))


def cagr(first: float, last: float, years: int = LATEST_YEAR - FIRST_YEAR) -> float | None:
    if first <= 0 or last < 0 or years <= 0:
        return None
    return (last / first) ** (1 / years) - 1


def trend_score(growth: float) -> float:
    return clamp(5 + growth * 50)


def landed_cost(import_price_per_kg: float, customs_pct: float) -> float:
    """Landed import cost per kg. Import values are CIF (cost, insurance, freight), so freight is
    already inside import_price_per_kg; only customs is added. shipping_pct is information only."""
    return import_price_per_kg * (1 + customs_pct)


def margin(landed: float, local_cost_per_kg: float) -> float | None:
    if landed <= 0:
        return None
    return (landed - local_cost_per_kg) / landed


def cost_score(m: float) -> float:
    return clamp(5 + m * 25)


def break_even(capex_min: float | None, capex_max: float | None, import_weight_kg: float | None,
               landed: float | None, local: float | None) -> BreakEven | None:
    """Tonnes to sell at import-parity price before the equipment is paid back (indicative; equipment only,
    no buildings or working capital). None unless every input exists and local production is cheaper."""
    if None in (capex_min, capex_max, import_weight_kg, landed, local) or import_weight_kg <= 0 or landed <= local:
        return None
    capex_mid = (capex_min + capex_max) / 2
    unit_saving = landed - local
    kg = capex_mid / unit_saving
    return BreakEven(
        capex_mid_usd=round(capex_mid, 2), unit_saving_usd_per_kg=round(unit_saving, 4),
        break_even_tons=round(kg / 1000, 1), share_of_2024_imports=round(kg / import_weight_kg, 4),
    )


def feasibility_score(machinery: float, raw_material: float, skills: float) -> float:
    return clamp((machinery + raw_material + skills) / 15 * 10)


def competition_score(local_factories: int, saturation: int) -> float:
    return clamp(10 * (1 - min(1, local_factories / saturation)))


TREND_THRESHOLD = 0.03  # +/-3% CAGR separates growing / stable / declining (display label only)


def trend_label(growth: float | None) -> TrendLabel | None:
    if growth is None:
        return None
    if growth > TREND_THRESHOLD:
        return "growing"
    if growth < -TREND_THRESHOLD:
        return "declining"
    return "stable"


def split_list(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(";") if part.strip()]


def verdict_for(score: float) -> Verdict:
    if score >= MANUFACTURE_THRESHOLD:
        return "MANUFACTURE"
    if score >= MAYBE_THRESHOLD:
        return "MAYBE"
    return "DONT"


# --- input validation -----------------------------------------------------------

def _valid(value, lo: float, hi: float, *, lo_inclusive: bool = True) -> bool:
    if value is None or isinstance(value, bool):
        return False
    try:
        v = float(value)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(v) or v > hi:
        return False
    return v >= lo if lo_inclusive else v > lo


# --- report -------------------------------------------------------------------

def compute_report(record: CategoryRecord, overrides: WhatIfOverrides | None = None) -> FeasibilityReport:
    applied = overrides.model_dump(exclude_none=True) if overrides else {}
    v = {
        "import_price_per_kg_usd": record.import_price_per_kg_usd,
        "shipping_pct": record.shipping_pct,
        "customs_pct": record.customs_pct,
        "local_cost_per_kg_est_usd": record.local_cost_per_kg_est_usd,
        "local_factories": record.local_factories,
        **applied,
    }
    imports = dict(record.imports_usd)
    notes: list[str] = []
    missing: list[str] = []

    def check(name: str, value, lo: float, hi: float, *, lo_inclusive: bool = True) -> bool:
        if value is None:
            missing.append(name)
            return False
        if not _valid(value, lo, hi, lo_inclusive=lo_inclusive):
            missing.append(name)
            notes.append(f"{name} has an invalid value and was ignored")
            return False
        return True

    available: dict[str, float] = {}  # component -> fraction of its weight backed by data

    # Market
    first, latest = imports.get(FIRST_YEAR), imports.get(LATEST_YEAR)
    vol = trend = growth = market = None
    if check(f"imports_{LATEST_YEAR}_usd", latest, 0, 1e12):
        vol = volume_score(latest)
        if check(f"imports_{FIRST_YEAR}_usd", first, 0, 1e12):
            growth = cagr(first, latest)
            if growth is None:
                notes.append(f"growth trend unavailable: imports_{FIRST_YEAR}_usd is zero")
            else:
                trend = trend_score(growth)
        if trend is not None:
            market = VOLUME_SHARE * vol + TREND_SHARE * trend
            available["market"] = 1.0
        else:
            market = vol
            available["market"] = VOLUME_SHARE
            notes.append("market score uses import volume only; growth trend could not be computed")
    else:
        notes.append(f"market score unavailable: imports_{LATEST_YEAR}_usd is missing")

    # Cost
    price, ship, customs, local = (
        v["import_price_per_kg_usd"], v["shipping_pct"], v["customs_pct"], v["local_cost_per_kg_est_usd"],
    )
    landed = m = cost = None
    ok = [
        check("import_price_per_kg_usd", price, 0, 1e6, lo_inclusive=False),
        check("customs_pct", customs, 0, 2),
        check("local_cost_per_kg_est_usd", local, 0, 1e6, lo_inclusive=False),
    ]
    if all(ok):
        landed = landed_cost(price, customs)
        m = margin(landed, local)
        if m is not None:
            cost = cost_score(m)
            available["cost"] = 1.0
    if cost is None:
        notes.append("cost score unavailable: import price, customs or local cost data is missing")
    # shipping_pct is information only (freight is already in the CIF import price): an invalid
    # value is dropped from the report but never affects the score or completeness.
    if ship is not None and not _valid(ship, 0, 2):
        notes.append("shipping_pct has an invalid value and was ignored (information only)")
        ship = None
    if "shipping_pct" in applied:
        notes.append("shipping_pct is information only: freight is already included in the CIF import price, "
                     "so changing it does not change the score")

    # Manufacturing feasibility
    mach, raw, skills = record.machinery_availability, record.raw_material_local, record.skills_availability
    feas = None
    ok = [
        check("machinery_availability", mach, 0, 5),
        check("raw_material_local", raw, 0, 5),
        check("skills_availability", skills, 0, 5),
    ]
    if all(ok):
        feas = feasibility_score(mach, raw, skills)
        available["feasibility"] = 1.0
    else:
        notes.append("feasibility score unavailable: machinery, raw material or skills rating is missing")

    # Competition
    factories, saturation = v["local_factories"], record.factories_saturation
    comp = None
    ok = [
        check("local_factories", factories, 0, 100_000),
        check("factories_saturation", saturation, 1, 100_000),
    ]
    if all(ok):
        comp = competition_score(factories, saturation)
        available["competition"] = 1.0
    else:
        notes.append("competition score unavailable: factory count or saturation level is missing")

    # Weighted total, renormalised over available components
    components = {"market": market, "cost": cost, "feasibility": feas, "competition": comp}
    used = {k: s for k, s in components.items() if s is not None}
    completeness = sum(WEIGHTS[k] * available[k] for k in used)
    score: float | None = None
    if used:
        raw_score = sum(WEIGHTS[k] * s for k, s in used.items()) / sum(WEIGHTS[k] for k in used)
        score = round1(clamp(raw_score))

    forced = score is None or completeness < MIN_COMPLETENESS - 1e-9
    if forced:
        verdict: Verdict = "MAYBE"
        notes.append(
            f"verdict set to MAYBE because data completeness ({completeness:.0%}) is below {MIN_COMPLETENESS:.0%}"
        )
    else:
        verdict = verdict_for(score)

    # Cost gate. When completeness also forces MAYBE, the lower verdict wins.
    capped_by = None
    if m is not None and score is not None and m < COST_GATE_MAYBE_BELOW:
        if m < COST_GATE_DONT_BELOW:
            cap_score, cap_verdict, limit = COST_GATE_DONT_SCORE_CAP, "DONT", "the verdict is DONT"
        else:
            cap_score, cap_verdict, limit = COST_GATE_MAYBE_SCORE_CAP, "MAYBE", "the verdict can be at most MAYBE"
        new_score = min(score, cap_score)
        new_verdict = min(verdict, cap_verdict, key=_VERDICT_RANK.__getitem__)
        if (new_score, new_verdict) != (score, verdict):
            capped_by = "cost_gate"
            notes.append(
                f"verdict limited by the cost gate: producing locally ({local:g} USD/kg) costs more than importing "
                f"({landed:.3g} USD/kg landed), so {limit} (score capped at {cap_score})"
            )
        else:
            notes.append(f"producing locally ({local:g} USD/kg) costs more than importing ({landed:.3g} USD/kg "
                         f"landed); {limit}")
        score, verdict = new_score, new_verdict

    flags: list[str] = []
    capex_max = record.machine_cost_usd_max
    if capex_max is not None and _valid(capex_max, 0, 1e12) and capex_max >= HIGH_CAPEX_USD:
        flags.append(HIGH_CAPITAL_FLAG)
        notes.append(f"high capital requirement: equipment alone is listed at up to {capex_max:,.0f} USD "
                     f"(equipment only, partial: ex-works supplier listing prices, excluding shipping, customs, "
                     f"installation, moulds and buildings)")

    if record.data_status == "TODO_REAL_DATA":
        notes.append("based on placeholder data (TODO_REAL_DATA), not verified trade statistics")

    def r(x, nd=3):
        return None if x is None else round(x, nd)

    return FeasibilityReport(
        category_id=record.category_id,
        name_en=record.name_en,
        name_ar=record.name_ar,
        hs6=record.hs6,
        data_status=record.data_status,
        is_placeholder_data=record.data_status == "TODO_REAL_DATA",
        score=score,
        verdict=verdict,
        verdict_forced_maybe=forced,
        verdict_capped_by=capped_by,
        flags=flags,
        data_completeness=round(completeness, 2),
        missing_fields=list(dict.fromkeys(missing)),
        weights=dict(WEIGHTS),
        market=MarketBreakdown(
            score=r(market, 2), volume_score=r(vol, 2), trend_score=r(trend, 2),
            cagr=r(growth, 4), latest_import_usd=latest, latest_import_jod=usd_to_jod(latest),
        ),
        cost=CostBreakdown(
            score=r(cost, 2), import_price_per_kg_usd=price, shipping_pct=ship, customs_pct=customs,
            landed_cost_per_kg_usd=r(landed, 3), local_cost_per_kg_est_usd=local, margin=r(m, 4),
            raw_material_price_usd_per_kg=record.raw_material_price_usd_per_kg,
            material_kg_per_kg_product=record.material_kg_per_kg_product,
            conversion_cost_per_kg_usd=record.conversion_cost_per_kg_usd,
        ),
        feasibility=FeasibilityBreakdown(
            score=r(feas, 2), machinery_availability=mach, raw_material_local=raw, skills_availability=skills,
        ),
        competition=CompetitionBreakdown(score=r(comp, 2), local_factories=factories, factories_saturation=saturation),
        imports_usd=imports,
        overrides_applied={k: float(val) for k, val in applied.items()},
        notes=notes,
        trend_label=trend_label(growth),
        machinery=split_list(record.machinery),
        raw_materials=split_list(record.raw_materials),
        risk_notes=record.risk_notes,
        competition_note=record.competition_note,
        source_notes=record.source_notes,
        sources=[u for u in (record.source_url, record.tariff_source_url, *record.machine_source_urls) if u],
        estimated_fields=list(record.estimated_fields),
        machine_cost_range_jod=(
            None if record.machine_cost_jod_min is None and record.machine_cost_jod_max is None
            else MachineCostRange(min=record.machine_cost_jod_min, max=record.machine_cost_jod_max)
        ),
        capex_usd_range=(
            None if record.machine_cost_usd_min is None and record.machine_cost_usd_max is None
            else CapexRange(min=record.machine_cost_usd_min, max=record.machine_cost_usd_max)
        ),
        machine_source=record.machine_source,
        import_weight_kg_2024=record.import_weight_kg_2024,
        # Uses the what-if values (landed and local), so sliders move it too.
        break_even=break_even(record.machine_cost_usd_min, record.machine_cost_usd_max, record.import_weight_kg_2024,
                              landed, local if cost is not None else None),
        # Static guidance (app/guidance.py): never computed by the LLM.
        next_steps=next_steps_for(verdict),
        advisors=list(ADVISORS),
        suppliers=supplier_links(split_list(record.machinery), split_list(record.raw_materials)),
    )
