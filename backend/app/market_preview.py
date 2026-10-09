"""Market preview: a preliminary scan for a physical product that fits none of the categories.

Only Jordan's imports for the AI-guessed HS6 code (UN Comtrade) are known, so the record built here has
every other value empty. compute_report then marks cost, feasibility and competition as missing and the
completeness rule forces MAYBE. The explanation is a fixed template (no LLM call).
"""

from __future__ import annotations

from app.comtrade import BASE_URL, TradeSeries
from app.explanation import _fmt, key_figures
from app.schemas import CategoryRecord, Explanation, FeasibilityReport, Language
from app.scoring import compute_report

MARKET_PREVIEW_ID = "market_preview"  # report.category_id; not a real category (no /confirm or /whatif)
MARKET_PREVIEW_FLAG = "market_preview_only"


def preview_record(trade: TradeSeries, name_en: str, name_ar: str) -> CategoryRecord:
    return CategoryRecord(
        category_id=MARKET_PREVIEW_ID, name_en=name_en, name_ar=name_ar,
        description_en=f"Market preview for HS {trade.hs6} (code guessed by the AI)",
        keywords_en=[], keywords_ar=[], hs6=trade.hs6,
        imports_usd=dict(trade.imports_usd), import_weight_kg_2024=trade.import_weight_kg_2024,
        import_price_per_kg_usd=None, shipping_pct=None, customs_pct=None, local_cost_per_kg_est_usd=None,
        machinery_availability=None, raw_material_local=None, skills_availability=None,
        local_factories=None, factories_saturation=None,
        machinery="", raw_materials="", data_status="ESTIMATE",
        source_notes=f"Imports: UN Comtrade public preview API (Jordan=400, partner World, flow M, CIF USD), "
                     f"HS {trade.hs6} guessed by the AI.",
        source_url=BASE_URL,
    )


def preview_report(trade: TradeSeries, name_en: str, name_ar: str) -> FeasibilityReport:
    report = compute_report(preview_record(trade, name_en, name_ar))
    note = (f"market preview only: built from UN Comtrade imports for HS {trade.hs6}, a code guessed by the AI "
            f"(please check it); cost, feasibility and competition data are missing, so this is not a "
            f"feasibility verdict")
    return report.model_copy(update={"flags": [*report.flags, MARKET_PREVIEW_FLAG], "notes": [*report.notes, note]})


_T = {
    "en": {
        "summary": "This is a preliminary market scan for {name}, not a full assessment: the product is outside "
                   "the supported categories, so only UN Comtrade import data for HS {hs6} was used (the code was "
                   "guessed by the AI; please check it). Jordan imported about {imports} million USD in {year}. "
                   "Without cost, manufacturing and competition data there is no real verdict yet, so the result "
                   "is held at MAYBE.",
        "market": "Jordan imported about {imports} million USD under HS {hs6} in {year}.",
        "trend": "Imports changed by {growth}% per year from {first} to {year}.",
        "weight": "That is about {tons} tonnes of imports in {year}.",
        "official": "The import figures are official UN Comtrade statistics reported by Jordan.",
        "concerns": [
            "No cost data: the import price per kg, the customs duty and an estimated local production cost are needed to compare local production with imports.",
            "No manufacturing data: machinery, raw-material and skills availability in Jordan are unknown.",
            "No competition data: the number of local factories already making this product is unknown.",
        ],
        "next_steps": [
            "Check that HS {hs6} really matches your product (Jordan Customs tariff or WITS); the import figures belong to that code.",
            "Get supplier quotes for machines and raw materials to estimate the local production cost per kg.",
            "Ask the Jordan Chamber of Industry how many local factories make this product.",
        ],
        "caveats": [
            "Preliminary market scan only: cost, manufacturing and competition were not assessed.",
            "The HS code was guessed by the AI and may be wrong.",
            "This is a quick screening estimate, not a business plan or financial advice.",
        ],
    },
    "ar": {
        "summary": "هذا مسح أولي للسوق لمنتج {name} وليس تقييماً كاملاً: المنتج خارج الفئات المدعومة، لذلك "
                   "استُخدمت بيانات الواردات من UN Comtrade فقط للرمز الجمركي HS {hs6} (الرمز اقترحه الذكاء "
                   "الاصطناعي، يرجى التحقق منه). استورد الأردن حوالي {imports} مليون دولار في {year}. وبدون "
                   "بيانات التكلفة والتصنيع والمنافسة لا يوجد حكم فعلي بعد، لذلك بقيت النتيجة «ربما».",
        "market": "استورد الأردن حوالي {imports} مليون دولار تحت الرمز HS {hs6} في {year}.",
        "trend": "تغيرت الواردات بنسبة {growth}% سنوياً من {first} إلى {year}.",
        "weight": "أي حوالي {tons} طن من الواردات في {year}.",
        "official": "أرقام الواردات إحصاءات رسمية من UN Comtrade كما أبلغ عنها الأردن.",
        "concerns": [
            "لا توجد بيانات تكلفة: نحتاج سعر الاستيراد للكيلوغرام والرسوم الجمركية وتكلفة إنتاج محلية تقديرية للمقارنة مع الاستيراد.",
            "لا توجد بيانات تصنيع: توفر الآلات والمواد الخام والمهارات في الأردن غير معروف.",
            "لا توجد بيانات منافسة: عدد المصانع المحلية التي تنتج هذا المنتج غير معروف.",
        ],
        "next_steps": [
            "تحقق من أن الرمز HS {hs6} يطابق منتجك فعلاً (التعرفة الجمركية الأردنية أو WITS)؛ أرقام الواردات تخص هذا الرمز.",
            "اطلب عروض أسعار للآلات والمواد الخام لتقدير تكلفة الإنتاج المحلي للكيلوغرام.",
            "اسأل غرفة صناعة الأردن عن عدد المصانع المحلية التي تنتج هذا المنتج.",
        ],
        "caveats": [
            "هذا مسح أولي للسوق فقط: لم يتم تقييم التكلفة والتصنيع والمنافسة.",
            "الرمز الجمركي اقترحه الذكاء الاصطناعي وقد يكون خاطئاً.",
            "هذا تقدير أولي سريع وليس خطة عمل أو نصيحة مالية.",
        ],
    },
}


def preview_explanation(report: FeasibilityReport, language: Language) -> Explanation:
    t = _T[language]
    k = key_figures(report)
    name = report.name_ar if language == "ar" else report.name_en
    values = {"name": name, "hs6": report.hs6, "imports": _fmt(k["latest_imports_usd_millions"]),
              "year": k["latest_year"], "first": min(report.imports_usd), "growth": _fmt(k["import_growth_per_year_pct"])}
    reasons = [t["market"].format(**values)]
    if report.market.cagr is not None:
        reasons.append(t["trend"].format(**values))
    if report.import_weight_kg_2024:
        reasons.append(t["weight"].format(tons=f"{report.import_weight_kg_2024 / 1000:,.0f}", **values))
    reasons = (reasons + [t["official"]])[:3]
    if len(reasons) < 3:  # no trend and no weight: repeat nothing, add the official-source line only once
        reasons.append(t["caveats"][0])
    return Explanation(
        language=language, summary=t["summary"].format(**values), reasons_for=reasons,
        concerns=list(t["concerns"]), next_steps=[s.format(**values) for s in t["next_steps"]],
        caveats=list(t["caveats"]),
    )
