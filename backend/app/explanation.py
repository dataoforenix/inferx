"""Explanation helpers: the facts handed to the LLM, the grounding guard, and a
deterministic template explanation used whenever the LLM one can't be trusted.

Grounding guard: every number in the LLM's explanation must match (after rounding to the
precision it was written with) a number from the report or the key figures, a year in the
data, or a small count (0-10). Anything else is treated as a fabricated statistic.
"""

from __future__ import annotations

import math
import re
from typing import Any, Iterable

from app.scoring import HIGH_CAPITAL_FLAG
from app.schemas import (
    BREAK_EVEN_DESCRIPTION, IMPORT_YEARS, Explanation, ExplanationLLMOutput, FeasibilityReport, Language,
)

SMALL_COUNTS = set(range(0, 11)) | {100}
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫٬", "01234567890123456789.,")
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")
_THOUSANDS_RE = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?")


def _r(x: float | None, nd: int = 1) -> float | None:
    return None if x is None else round(x, nd)


def _pct(x: float | None) -> float | None:
    return None if x is None else round(x * 100, 1)


def key_figures(report: FeasibilityReport) -> dict[str, Any]:
    """Human-friendly versions of report numbers, so the LLM never has to do arithmetic."""
    imports_m = {str(y): _r(v / 1e6) if v is not None else None for y, v in report.imports_usd.items()}
    latest = report.market.latest_import_usd
    return {
        "product_category": report.name_en,
        "score_out_of_10": report.score,
        "verdict": report.verdict,
        "verdict_forced_maybe": report.verdict_forced_maybe,
        "verdict_capped_by": report.verdict_capped_by,
        "is_placeholder_data": report.is_placeholder_data,
        "data_completeness_pct": round(report.data_completeness * 100),
        "latest_year": IMPORT_YEARS[-1],
        "latest_imports_usd_millions": _r(latest / 1e6) if latest is not None else None,
        "imports_by_year_usd_millions": imports_m,
        "import_growth_per_year_pct": _pct(report.market.cagr),
        "import_price_per_kg_usd_cif": _r(report.cost.import_price_per_kg_usd, 2),
        "customs_pct": _pct(report.cost.customs_pct),
        "landed_cost_per_kg_usd": _r(report.cost.landed_cost_per_kg_usd, 2),
        "landed_cost_formula": "CIF import price x (1 + customs); freight is already inside the CIF price",
        "shipping_pct_info_only": _pct(report.cost.shipping_pct),
        "local_cost_per_kg_usd": _r(report.cost.local_cost_per_kg_est_usd, 2),
        "cost_advantage_pct": _pct(report.cost.margin),
        "machinery_availability_out_of_5": report.feasibility.machinery_availability,
        "raw_material_local_out_of_5": report.feasibility.raw_material_local,
        "skills_availability_out_of_5": report.feasibility.skills_availability,
        "local_factories": report.competition.local_factories,
        "factories_saturation": report.competition.factories_saturation,
        "component_scores_out_of_10": {
            "market": _r(report.market.score),
            "cost": _r(report.cost.score),
            "feasibility": _r(report.feasibility.score),
            "competition": _r(report.competition.score),
        },
        "import_trend": report.trend_label,
        "machinery": report.machinery,
        "raw_materials": report.raw_materials,
        "machine_cost_range_jod": (
            report.machine_cost_range_jod.model_dump() if report.machine_cost_range_jod else None
        ),
        "capex_usd_range": (
            {**report.capex_usd_range.model_dump(), "scope": CAPEX_SCOPE} if report.capex_usd_range else None
        ),
        "flags": report.flags,
        "break_even": _break_even_figures(report),
        "estimated_fields": report.estimated_fields,
    }


def _break_even_figures(report: FeasibilityReport) -> dict[str, Any] | None:
    be = report.break_even
    if be is None:
        return None
    return {
        "equipment_cost_mid_usd": round(be.capex_mid_usd),
        "saving_per_kg_usd": _r(be.unit_saving_usd_per_kg, 2),
        "break_even_tons": _tons(be.break_even_tons),
        "share_of_latest_year_imports_pct": _pct(be.share_of_2024_imports),
        "scope": BREAK_EVEN_DESCRIPTION,
    }


def _tons(x: float) -> float:
    """Whole tonnes from 10 t up ("1,458"), one decimal below ("3.4")."""
    return float(round(x)) if x >= 10 else round(x, 1)


CAPEX_SCOPE = ("equipment only, partial: ex-works supplier listing prices, excluding shipping, customs, "
               "installation, moulds and buildings")


# Free-text CSV fields whose numbers the LLM may legitimately quote ("8.3%", "1.6 million").
FREE_TEXT_FIELDS = ("risk_notes", "competition_note", "source_notes", "machine_source", "machinery", "raw_materials")

# Long free text goes to the model once, in its own <data_notes> block, and is removed from the
# report copy (source_notes alone is ~1000 characters per category in the real data).
DATA_NOTE_FIELDS = ("source_notes", "risk_notes", "competition_note", "machine_source", "sources")
# Already in key_figures, so not repeated in the report copy either.
REPORT_FIELDS_IN_KEY_FIGURES = ("machinery", "raw_materials")
# Static guidance for the UI (links, steps, bodies): not report data, so never sent to the explanation model.
REPORT_FIELDS_NOT_FOR_LLM = ("next_steps", "advisors", "suppliers")


_LLM_REPORT_EXCLUDE = {
    **dict.fromkeys((*DATA_NOTE_FIELDS, *REPORT_FIELDS_IN_KEY_FIGURES, *REPORT_FIELDS_NOT_FOR_LLM), True),
    "market": {"latest_import_jod": True},  # derived JOD value: the model explains the USD figures
}


def llm_facts(report: FeasibilityReport) -> dict[str, Any]:
    """What the explanation model sees: key figures, the report (without long text) and the data notes."""
    return {
        "key_figures": key_figures(report),
        "report": report.model_dump(mode="json", exclude=_LLM_REPORT_EXCLUDE),
        "data_notes": {name: getattr(report, name) for name in DATA_NOTE_FIELDS if getattr(report, name)},
    }


# --- grounding guard ------------------------------------------------------------

def _walk_numbers(obj: Any) -> Iterable[float]:
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)):
        if math.isfinite(obj):
            yield abs(float(obj))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_numbers(k)
            yield from _walk_numbers(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _walk_numbers(v)
    elif isinstance(obj, str) and obj.isdigit():
        yield float(obj)  # e.g. the HS code


def allowed_numbers(report: FeasibilityReport) -> set[float]:
    allowed = set(_walk_numbers(llm_facts(report)))
    for name in FREE_TEXT_FIELDS:
        value = getattr(report, name)
        for text in value if isinstance(value, list) else [value]:
            allowed |= {v for _, v, _ in extract_numbers(text)}
    allowed.add(float(report.hs6))
    allowed |= {float(y) for y in IMPORT_YEARS}
    allowed |= {float(n) for n in SMALL_COUNTS}
    return allowed


def extract_numbers(text: str) -> list[tuple[str, float, int]]:
    """Return (token, value, decimals) for every number written in the text (Arabic digits included)."""
    found = []
    for token in _NUMBER_RE.findall(text.translate(_ARABIC_DIGITS)):
        if _THOUSANDS_RE.fullmatch(token):
            parts = [token.replace(",", "")]
        else:
            parts = token.split(",")  # "2020,2024" or a list; not a decimal comma
        for part in parts:
            if not part:
                continue
            decimals = len(part.split(".")[1]) if "." in part else 0
            try:
                found.append((part, float(part), decimals))
            except ValueError:
                continue
    return found


def is_grounded(value: float, decimals: int, allowed: set[float]) -> bool:
    tolerance = 0.5 * 10 ** (-decimals) + 1e-9  # "7.5" may stand for 7.46; "41" for 41.4
    return any(abs(value - a) <= tolerance for a in allowed)


def grounding_issues(output: ExplanationLLMOutput, report: FeasibilityReport) -> list[str]:
    allowed = allowed_numbers(report)
    texts = [output.summary, *output.reasons_for, *output.concerns, *output.next_steps, *output.caveats]
    issues = []
    for text in texts:
        for token, value, decimals in extract_numbers(text):
            if not is_grounded(value, decimals, allowed):
                issues.append(token)
    return list(dict.fromkeys(issues))


# --- deterministic fallback ----------------------------------------------------

_T = {
    "en": {
        "verdict": {
            "MANUFACTURE": "local manufacturing looks worth exploring",
            "MAYBE": "local manufacturing is possible but needs more checking",
            "DONT": "local manufacturing does not look attractive right now",
        },
        "summary": "{name} scored {score} out of 10, so {verdict}.",
        "summary_none": "There is not enough data to score {name}, so the result is uncertain.",
        "forced": " The data is incomplete, so the verdict was set to MAYBE.",
        "cost_gate": " The verdict was limited because producing locally ({local} USD/kg) costs more than importing ({landed} USD/kg including customs).",
        "break_even": " Indicative break-even: selling about {tons} tonnes ({share}% of {year} imports) at the import-parity price would pay back about {capex} USD of equipment (equipment only; excludes buildings and working capital).",
        "strong": {
            "market": "Imports are sizeable: about {imports} million USD in {year}, changing by {growth}% per year.",
            "cost": "Imports cost about {landed} USD/kg including customs (freight is already in the import price), against an estimated local cost of {local} USD/kg.",
            "feasibility": "Local capability is reasonable: machinery {m}/5, raw materials {r}/5, skills {s}/5.",
            "competition": "Competition is limited: {f} local factories against a saturation level of {sat}.",
        },
        "weak": {
            "market": "The import market is modest: about {imports} million USD in {year}, changing by {growth}% per year.",
            "cost": "The estimated local cost ({local} USD/kg) leaves little advantage against an import cost of {landed} USD/kg including customs (freight is already in the import price).",
            "feasibility": "Local capability is limited: machinery {m}/5, raw materials {r}/5, skills {s}/5.",
            "competition": "Competition is strong: {f} local factories against a saturation level of {sat}.",
        },
        "pad_for": [
            "The score is built from four transparent factors you can test in the what-if tool.",
            "Producing locally can shorten delivery times compared with importing.",
            "Local production can reduce exposure to shipping disruptions.",
        ],
        "pad_against": [
            "Cost figures are estimates and must be checked against real supplier quotes.",
            "Trade data may not capture informal or re-exported trade.",
            "Setting up a factory needs capital, licences and time before the first sale.",
        ],
        "next_steps": [
            "Get written quotes from machinery and raw-material suppliers.",
            "Talk to local wholesalers and retailers to confirm demand and target prices.",
            "Check licensing, standards and incentives with the Jordan Investment Commission and the Chamber of Industry.",
        ],
        "caveat_placeholder": "The figures are illustrative placeholders, not real Jordanian trade statistics.",
        "caveat_forced": "Some data is missing, so the result is less reliable.",
        "caveat_estimates": "The figures for these items are estimates, not measured values: {fields}.",
        "high_capex": "High capital requirement: the equipment alone is listed at {capex_min} to {capex_max} USD, and this is only part of the investment (ex-works supplier listing prices, excluding shipping, customs, installation, moulds and buildings).",
        "caveat_general": "This is a quick screening estimate, not a business plan or financial advice.",
    },
    "ar": {
        "verdict": {
            "MANUFACTURE": "التصنيع المحلي يبدو فكرة تستحق الدراسة",
            "MAYBE": "التصنيع المحلي ممكن لكنه يحتاج إلى مزيد من التحقق",
            "DONT": "التصنيع المحلي لا يبدو مجدياً في الوقت الحالي",
        },
        "summary": "حصل منتج {name} على {score} من 10، لذلك {verdict}.",
        "summary_none": "لا تتوفر بيانات كافية لتقييم {name}، لذلك النتيجة غير مؤكدة.",
        "forced": " البيانات غير مكتملة، لذلك تم تعيين النتيجة إلى «ربما».",
        "cost_gate": " تم تقييد النتيجة لأن الإنتاج المحلي ({local} دولار للكيلوغرام) أغلى من الاستيراد ({landed} دولار للكيلوغرام شاملة الجمارك).",
        "break_even": " نقطة التعادل (تقديرية): بيع حوالي {tons} طن ({share}% من واردات {year}) بسعر يعادل سعر المستورد يسترد حوالي {capex} دولار من ثمن المعدات (المعدات فقط، بدون المباني ورأس المال العامل).",
        "strong": {
            "market": "حجم الاستيراد جيد: حوالي {imports} مليون دولار في {year}، بتغير سنوي قدره {growth}%.",
            "cost": "تبلغ تكلفة المستورد حوالي {landed} دولار للكيلوغرام شاملة الجمارك (الشحن مشمول أصلاً في سعر الاستيراد)، مقابل تكلفة محلية تقديرية {local} دولار للكيلوغرام.",
            "feasibility": "القدرات المحلية معقولة: الآلات {m}/5، المواد الخام {r}/5، المهارات {s}/5.",
            "competition": "المنافسة محدودة: {f} مصانع محلية مقابل حد تشبع قدره {sat}.",
        },
        "weak": {
            "market": "سوق الاستيراد محدود: حوالي {imports} مليون دولار في {year}، بتغير سنوي قدره {growth}%.",
            "cost": "التكلفة المحلية التقديرية ({local} دولار للكيلوغرام) لا تترك ميزة كبيرة مقابل تكلفة المستورد {landed} دولار للكيلوغرام شاملة الجمارك (الشحن مشمول أصلاً في سعر الاستيراد).",
            "feasibility": "القدرات المحلية محدودة: الآلات {m}/5، المواد الخام {r}/5، المهارات {s}/5.",
            "competition": "المنافسة قوية: {f} مصانع محلية مقابل حد تشبع قدره {sat}.",
        },
        "pad_for": [
            "التقييم مبني على أربعة عوامل واضحة يمكنك تجربتها في أداة «ماذا لو».",
            "الإنتاج المحلي قد يقلل مدة التوريد مقارنة بالاستيراد.",
            "الإنتاج المحلي قد يقلل التأثر باضطرابات الشحن.",
        ],
        "pad_against": [
            "أرقام التكلفة تقديرية ويجب التحقق منها بعروض أسعار حقيقية من الموردين.",
            "بيانات التجارة قد لا تشمل التجارة غير الرسمية أو إعادة التصدير.",
            "إنشاء مصنع يحتاج إلى رأس مال وتراخيص ووقت قبل أول عملية بيع.",
        ],
        "next_steps": [
            "اطلب عروض أسعار مكتوبة من موردي الآلات والمواد الخام.",
            "تحدث مع تجار الجملة والتجزئة المحليين لتأكيد الطلب والأسعار المستهدفة.",
            "تحقق من التراخيص والمواصفات والحوافز لدى هيئة الاستثمار وغرفة صناعة الأردن.",
        ],
        "caveat_placeholder": "الأرقام توضيحية مؤقتة وليست إحصاءات تجارة أردنية حقيقية.",
        "caveat_forced": "بعض البيانات ناقصة، لذلك النتيجة أقل موثوقية.",
        "caveat_estimates": "أرقام هذه البنود تقديرية وليست قيماً مقاسة: {fields}.",
        "high_capex": "رأس المال المطلوب مرتفع: سعر المعدات وحدها بين {capex_min} و{capex_max} دولار، وهذا جزء من الاستثمار فقط (أسعار الموردين المعلنة من المصنع، بدون الشحن والجمارك والتركيب والقوالب والمباني).",
        "caveat_general": "هذا تقدير أولي سريع وليس خطة عمل أو نصيحة مالية.",
    },
}

# Plain names for CSV columns, used when listing estimated fields. Unknown names are shown as-is.
FIELD_LABELS: dict[str, dict[str, str]] = {
    "en": {
        **{f"imports_{y}_usd": f"imports in {y}" for y in IMPORT_YEARS},
        "import_weight_kg_2024": "import weight", "import_price_per_kg_usd": "import price per kg",
        "shipping_pct": "shipping cost", "customs_pct": "customs duty",
        "local_cost_per_kg_est_usd": "local production cost", "machinery_availability": "machinery availability",
        "raw_material_local": "local raw materials", "skills_availability": "skills availability",
        "local_factories": "number of local factories", "factories_saturation": "market saturation level",
        "machine_cost_jod_min": "machine cost", "machine_cost_jod_max": "machine cost",
    },
    "ar": {
        **{f"imports_{y}_usd": f"واردات {y}" for y in IMPORT_YEARS},
        "import_weight_kg_2024": "وزن الواردات", "import_price_per_kg_usd": "سعر الاستيراد للكيلوغرام",
        "shipping_pct": "تكلفة الشحن", "customs_pct": "الرسوم الجمركية",
        "local_cost_per_kg_est_usd": "تكلفة الإنتاج المحلي", "machinery_availability": "توفر الآلات",
        "raw_material_local": "المواد الخام المحلية", "skills_availability": "توفر المهارات",
        "local_factories": "عدد المصانع المحلية", "factories_saturation": "حد تشبع السوق",
        "machine_cost_jod_min": "تكلفة الآلات", "machine_cost_jod_max": "تكلفة الآلات",
    },
}


def _money(x: float | None) -> str:
    return "?" if x is None else f"{x:,.0f}"


def _fmt(x: float | None, nd: int = 1) -> str:
    if x is None:
        return "?"
    value = round(x, nd)
    return str(int(value)) if value == int(value) else str(value)


def fallback_explanation(report: FeasibilityReport, language: Language) -> Explanation:
    t = _T[language]
    k = key_figures(report)
    name = report.name_ar if language == "ar" else report.name_en
    values = {
        "imports": _fmt(k["latest_imports_usd_millions"]), "year": k["latest_year"],
        "growth": _fmt(k["import_growth_per_year_pct"]),
        "landed": _fmt(k["landed_cost_per_kg_usd"], 2), "local": _fmt(k["local_cost_per_kg_usd"], 2),
        "m": _fmt(k["machinery_availability_out_of_5"]), "r": _fmt(k["raw_material_local_out_of_5"]),
        "s": _fmt(k["skills_availability_out_of_5"]),
        "f": _fmt(k["local_factories"]), "sat": _fmt(k["factories_saturation"]),
    }

    if report.score is None:
        summary = t["summary_none"].format(name=name)
    else:
        summary = t["summary"].format(name=name, score=_fmt(report.score), verdict=t["verdict"][report.verdict])
    if report.verdict_forced_maybe:
        summary += t["forced"]
    if report.verdict_capped_by == "cost_gate":
        summary += t["cost_gate"].format(**values)
    be = k["break_even"]
    if be is not None:
        summary += t["break_even"].format(
            tons=_money(be["break_even_tons"]) if be["break_even_tons"] >= 10 else _fmt(be["break_even_tons"]),
            share=_fmt(be["share_of_latest_year_imports_pct"]), year=k["latest_year"],
            capex=_money(be["equipment_cost_mid_usd"]),
        )

    components = {
        "market": report.market.score, "cost": report.cost.score,
        "feasibility": report.feasibility.score, "competition": report.competition.score,
    }
    # Trend-less market text would print "?" for growth; only use templates whose inputs exist.
    usable = {
        "market": report.market.cagr is not None,
        "cost": report.cost.score is not None,
        "feasibility": report.feasibility.score is not None,
        "competition": report.competition.score is not None,
    }
    scored = sorted(((s, c) for c, s in components.items() if s is not None and usable[c]), reverse=True)
    reasons = [t["strong"][c].format(**values) for s, c in scored if s >= 5]
    concerns = [t["weak"][c].format(**values) for s, c in reversed(scored) if s < 5]
    reasons = (reasons + t["pad_for"])[:3]
    # The data team's own risk note is more specific than any generic sentence: it goes first.
    risk = [report.risk_notes] if report.risk_notes else []
    if HIGH_CAPITAL_FLAG in report.flags and report.capex_usd_range:
        capex = report.capex_usd_range
        risk.append(t["high_capex"].format(capex_min=_money(capex.min), capex_max=_money(capex.max)))
    concerns = (risk + concerns + t["pad_against"])[:3]

    caveats = []
    if report.is_placeholder_data:
        caveats.append(t["caveat_placeholder"])
    if report.estimated_fields:
        separator = "، " if language == "ar" else ", "
        names = dict.fromkeys(FIELD_LABELS[language].get(f, f) for f in report.estimated_fields)  # dedupe, keep order
        caveats.append(t["caveat_estimates"].format(fields=separator.join(names)))
    if report.verdict_forced_maybe or report.missing_fields:
        caveats.append(t["caveat_forced"])
    caveats.append(t["caveat_general"])

    return Explanation(
        language=language, summary=summary, reasons_for=reasons, concerns=concerns,
        next_steps=list(t["next_steps"]), caveats=caveats,
    )
