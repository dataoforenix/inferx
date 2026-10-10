"""Static, deterministic guidance attached to every report: next steps by verdict, advisory bodies,
supplier search links, the equipment-budget check and the methodology text. No LLM, no I/O.

Every URL below was opened and checked on 2026-10-10 (Jordan time) before it was added:
- each advisory body's official site loads and itself describes the service listed for it;
- the Made-in-China search URL pattern returns a product search page for the query;
- the Jordan Chamber of Industry industrial directory page lists Jordanian manufacturers.
Alibaba search URLs were NOT added: the page could not be verified (no search results in the served HTML).
Never add a named supplier, company, person or phone number here.
"""

from __future__ import annotations

from urllib.parse import quote_plus

from app.data_store import JOD_TO_USD
from app.schemas import (
    CAPEX_DESCRIPTION,
    Advisor,
    FeasibilityReport,
    LocalizedSteps,
    SupplierItemLinks,
    SupplierLink,
    SupplierLinks,
    Verdict,
)

# Fixed JOD peg: 1 USD = 0.709 JOD (CBJ). JOD_TO_USD (1.4104) in data_store is the same peg the other way round.
USD_TO_JOD = 0.709


def usd_to_jod(usd: float | None) -> float | None:
    return None if usd is None else round(usd * USD_TO_JOD, 2)


# --- c. next steps by verdict ---------------------------------------------------------------

NEXT_STEPS: dict[str, dict[str, list[str]]] = {
    "MANUFACTURE": {
        "en": [
            "Get written quotes for the machinery and raw materials listed in the report.",
            "Confirm demand and target prices with local wholesalers and retailers.",
            "Register the company and check industrial licensing requirements.",
            "Ask a support body (see advisors) about feasibility-study, financing or loan-guarantee programmes.",
        ],
        "ar": [
            "اطلب عروض أسعار مكتوبة للآلات والمواد الخام المذكورة في التقرير.",
            "تأكد من الطلب والأسعار المستهدفة مع تجار الجملة والتجزئة المحليين.",
            "سجّل الشركة وتحقق من متطلبات الترخيص الصناعي.",
            "اسأل إحدى جهات الدعم (انظر قائمة الجهات) عن برامج دراسات الجدوى أو التمويل أو ضمان القروض.",
        ],
    },
    "MAYBE": {
        "en": [
            "Check the estimated figures first: get real quotes for local production cost and equipment.",
            "Try the what-if tool to see which change (cost, customs, competition) would move the verdict.",
            "Talk to local buyers to test whether they would switch from imports.",
            "Ask a support body (see advisors) for a professional feasibility study before investing.",
        ],
        "ar": [
            "تحقق أولاً من الأرقام التقديرية: اطلب عروض أسعار حقيقية لكلفة الإنتاج المحلي والمعدات.",
            "جرّب أداة «ماذا لو» لمعرفة أي تغيير (الكلفة، الجمارك، المنافسة) يغيّر النتيجة.",
            "تحدث مع المشترين المحليين لمعرفة إن كانوا سيتحولون عن المستورد.",
            "اطلب من إحدى جهات الدعم (انظر قائمة الجهات) دراسة جدوى مهنية قبل الاستثمار.",
        ],
    },
    "DONT": {
        "en": [
            "Do not invest in equipment based on this result.",
            "Use the what-if tool to see what local cost or customs level would be needed to compete with imports.",
            "Consider a related product, or trading and distribution instead of manufacturing.",
            "If you still want to proceed, ask a support body (see advisors) for an independent feasibility study.",
        ],
        "ar": [
            "لا تستثمر في المعدات بناءً على هذه النتيجة.",
            "استخدم أداة «ماذا لو» لمعرفة الكلفة المحلية أو نسبة الجمارك اللازمة لمنافسة المستورد.",
            "فكّر في منتج قريب، أو في التجارة والتوزيع بدلاً من التصنيع.",
            "إذا أردت المتابعة، اطلب من إحدى جهات الدعم (انظر قائمة الجهات) دراسة جدوى مستقلة.",
        ],
    },
}


def next_steps_for(verdict: Verdict) -> LocalizedSteps:
    steps = NEXT_STEPS[verdict]
    return LocalizedSteps(en=list(steps["en"]), ar=list(steps["ar"]))


# --- d. advisory bodies (verified 2026-10-10) ---------------------------------------------------

ADVISORS: list[Advisor] = [
    Advisor(
        name_en="Jordan Enterprise Development Corporation (JEDCO)",
        name_ar="المؤسسة الأردنية لتطوير المشاريع الاقتصادية (جيدكو)",
        offer_en="Support programmes, technical assistance and financing tools for SMEs, start-ups and manufacturers.",
        offer_ar="برامج دعم ومساعدة فنية وأدوات تمويل للمشاريع الصغيرة والمتوسطة والريادية والصناعية.",
        url="https://www.jedco.gov.jo",
    ),
    Advisor(
        name_en="Jordan Chamber of Industry",
        name_ar="غرفة صناعة الأردن",
        offer_en="Sector studies and industrial data, export support and an industrial directory for manufacturers.",
        offer_ar="دراسات وبيانات قطاعية، ودعم للتصدير، ودليل صناعي للمصانع الأردنية.",
        url="https://www.jci.org.jo",
    ),
    Advisor(
        name_en="Ministry of Industry, Trade and Supply",
        name_ar="وزارة الصناعة والتجارة والتموين",
        offer_en="Industrial development services, importer/exporter registration and import/export licences.",
        offer_ar="خدمات التنمية الصناعية، وتسجيل المستوردين والمصدرين، ورخص الاستيراد والتصدير.",
        url="https://www.mit.gov.jo",
    ),
    Advisor(
        name_en="Companies Control Department",
        name_ar="دائرة مراقبة الشركات",
        offer_en="Registration of new companies (online services).",
        offer_ar="تسجيل الشركات الجديدة (خدمات إلكترونية).",
        url="https://www.ccd.gov.jo",
    ),
    Advisor(
        name_en="Jordan Standards and Metrology Organization (JSMO)",
        name_ar="مؤسسة المواصفات والمقاييس الأردنية",
        offer_en="Jordanian standards, quality mark and conformity certification for products.",
        offer_ar="المواصفات القياسية الأردنية وعلامة الجودة وشهادات المطابقة للمنتجات.",
        url="https://www.jsmo.gov.jo",
    ),
    Advisor(
        name_en="Jordan Loan Guarantee Corporation",
        name_ar="الشركة الأردنية لضمان القروض",
        offer_en="Loan guarantees that improve access to credit for micro, small and medium enterprises.",
        offer_ar="ضمانات قروض تسهّل حصول المؤسسات المتناهية الصغر والصغيرة والمتوسطة على التمويل.",
        url="https://www.jlgc.com",
    ),
]


# --- e. supplier search links -------------------------------------------------------------------

SUPPLIER_CAPTION_EN = "Search links, not supplier recommendations. Verify suppliers yourself."
SUPPLIER_CAPTION_AR = "روابط بحث وليست توصيات بموردين. تحقّق من الموردين بنفسك."
MADE_IN_CHINA_SEARCH = "https://www.made-in-china.com/multi-search/{query}/F1/1.html"
LOCAL_DIRECTORY = Advisor(
    name_en="Jordan Chamber of Industry: industrial directory",
    name_ar="غرفة صناعة الأردن: الدليل الصناعي",
    offer_en="Directory of Jordanian industrial establishments, filterable by sector.",
    offer_ar="دليل المنشآت الصناعية الأردنية مع تصفية حسب القطاع.",
    url="https://jci.org.jo/%d8%a7%d9%84%d8%af%d9%84%d9%8a%d9%84-%d8%a7%d9%84%d8%b5%d9%86%d8%a7%d8%b9%d9%8a/",
)


def _search_links(item: str) -> list[SupplierLink]:
    return [SupplierLink(marketplace="Made-in-China.com",
                         url=MADE_IN_CHINA_SEARCH.format(query=quote_plus(item.strip())))]


def supplier_links(machinery: list[str], raw_materials: list[str]) -> SupplierLinks:
    items = [SupplierItemLinks(item=m, kind="machinery", links=_search_links(m)) for m in machinery if m.strip()]
    items += [SupplierItemLinks(item=r, kind="raw_material", links=_search_links(r)) for r in raw_materials if r.strip()]
    return SupplierLinks(caption_en=SUPPLIER_CAPTION_EN, caption_ar=SUPPLIER_CAPTION_AR, items=items,
                         local_directory=LOCAL_DIRECTORY)


# --- b. equipment budget check ------------------------------------------------------------------

BUDGET_CAPTION_AR = ("المعدات فقط: أسعار الموردين المعلنة من المصنع، بدون الشحن والجمارك والتركيب والقوالب "
                     "والمباني (محوّلة إلى الدينار بسعر ثابت 1 دولار = 0.709 دينار).")
BUDGET_CAPTION_EN = CAPEX_DESCRIPTION.replace("(USD).", "(converted to JOD at the fixed peg 1 USD = 0.709 JOD).")


def budget_check(report: FeasibilityReport, budget_jod: float) -> dict:
    """covered: budget >= top of the equipment range; partial: >= bottom; short: below the bottom.
    gap_jod = what is still missing to reach the top of the range (0 when covered)."""
    capex = report.capex_usd_range
    lo, hi = usd_to_jod(capex.min), usd_to_jod(capex.max)
    status = "covered" if budget_jod >= hi else "partial" if budget_jod >= lo else "short"
    return {
        "category_id": report.category_id, "budget_jod": budget_jod, "status": status,
        "capex_jod_range": {"min": lo, "max": hi}, "gap_jod": round(max(0.0, hi - budget_jod), 2),
        "caption_en": BUDGET_CAPTION_EN, "caption_ar": BUDGET_CAPTION_AR,
    }


assert abs(USD_TO_JOD * JOD_TO_USD - 1) < 1e-3  # the two directions of the same peg


# --- f. methodology -----------------------------------------------------------------------------

def methodology() -> dict:
    from app.scoring import (
        COST_GATE_DONT_BELOW, COST_GATE_DONT_SCORE_CAP, COST_GATE_MAYBE_BELOW, COST_GATE_MAYBE_SCORE_CAP,
        HIGH_CAPEX_USD, MANUFACTURE_THRESHOLD, MAYBE_THRESHOLD, MIN_COMPLETENESS, WEIGHTS,
    )

    w = {k: round(v * 100) for k, v in WEIGHTS.items()}
    mc = round(MIN_COMPLETENESS * 100)
    en = [
        {"title": "Score", "body": (
            f"The 0-10 score is a weighted average of four components, each 0-10: market {w['market']}%, "
            f"cost {w['cost']}%, manufacturing feasibility {w['feasibility']}%, competition {w['competition']}%. "
            f"{MANUFACTURE_THRESHOLD:g} or more = MANUFACTURE, {MAYBE_THRESHOLD:g} or more = MAYBE, otherwise DONT. "
            "Everything is calculated in Python; the AI only explains the result.")},
        {"title": "Components", "body": (
            "Market = 0.6 x import volume (log scale of the latest year's imports) + 0.4 x growth trend (5 + annual "
            "growth x 50). Cost = 5 + margin x 25, where margin = (landed import cost - local cost) / landed import "
            "cost and landed cost = CIF import price x (1 + customs); freight is already in the CIF price. "
            "Feasibility = (machinery + raw material + skills ratings, each 0-5) / 15 x 10. "
            "Competition = 10 x (1 - local factories / saturation level).")},
        {"title": "Cost gate", "body": (
            f"If producing locally costs more than importing (margin below {COST_GATE_MAYBE_BELOW:g}), the verdict is "
            f"at most MAYBE and the score is capped at {COST_GATE_MAYBE_SCORE_CAP:g}. If the margin is below "
            f"{COST_GATE_DONT_BELOW:g}, the verdict is DONT and the score is capped at {COST_GATE_DONT_SCORE_CAP:g}.")},
        {"title": "Data completeness", "body": (
            "Missing data is never guessed: the affected component is switched off and the score is recalculated "
            f"from the remaining ones. If less than {mc}% of the weight is backed by data, the verdict is forced to "
            f"MAYBE. Equipment costing {HIGH_CAPEX_USD:,} USD or more is flagged as a high capital requirement "
            "(no score change).")},
        {"title": "Data sources", "body": (
            "Imports and import weight: UN Comtrade (Jordan, CIF, USD). Customs duties: WITS/TRAINS. Equipment "
            "prices: supplier listings (equipment only). Local costs, ratings and factory counts: partly estimates, "
            "marked in each report's estimated_fields. Money is converted at the fixed peg 1 JOD = 1.4104 USD.")},
        {"title": "Known limitation: growth", "body": (
            "Growth is measured from 2020 to 2024. 2020 was a COVID low year for many imports, so growth from that "
            "base can look stronger than the long-term trend.")},
    ]
    ar = [
        {"title": "التقييم", "body": (
            f"التقييم من 0 إلى 10 هو متوسط مرجّح لأربعة عناصر، كل منها من 0 إلى 10: السوق {w['market']}%، "
            f"الكلفة {w['cost']}%، إمكانية التصنيع {w['feasibility']}%، المنافسة {w['competition']}%. "
            f"{MANUFACTURE_THRESHOLD:g} فأكثر = صنّعها، {MAYBE_THRESHOLD:g} فأكثر = ربما، وأقل من ذلك = لا تصنّعها. "
            "كل الحسابات تتم ببرنامج بايثون؛ الذكاء الاصطناعي يشرح النتيجة فقط.")},
        {"title": "العناصر", "body": (
            "السوق = 0.6 × حجم الاستيراد (مقياس لوغاريتمي لواردات آخر سنة) + 0.4 × اتجاه النمو (5 + النمو السنوي × 50). "
            "الكلفة = 5 + الهامش × 25، والهامش = (كلفة المستورد الواصل − الكلفة المحلية) ÷ كلفة المستورد الواصل، "
            "وكلفة المستورد الواصل = سعر الاستيراد شامل الشحن والتأمين × (1 + الجمارك)؛ الشحن مشمول أصلاً في السعر. "
            "إمكانية التصنيع = (تقييم الآلات + المواد الخام + المهارات، كل منها 0-5) ÷ 15 × 10. "
            "المنافسة = 10 × (1 − عدد المصانع المحلية ÷ حد التشبع).")},
        {"title": "شرط الكلفة", "body": (
            f"إذا كان الإنتاج المحلي أغلى من الاستيراد (هامش أقل من {COST_GATE_MAYBE_BELOW:g})، تكون النتيجة «ربما» "
            f"كحد أقصى ويُحدّ التقييم عند {COST_GATE_MAYBE_SCORE_CAP:g}. وإذا كان الهامش أقل من {COST_GATE_DONT_BELOW:g} "
            f"تكون النتيجة «لا تصنّعها» ويُحدّ التقييم عند {COST_GATE_DONT_SCORE_CAP:g}.")},
        {"title": "اكتمال البيانات", "body": (
            "لا يتم تخمين أي بيانات ناقصة: يُستبعد العنصر المتأثر ويُعاد حساب التقييم من العناصر المتبقية. "
            f"إذا كانت البيانات تغطي أقل من {mc}% من الأوزان تصبح النتيجة «ربما». "
            f"المعدات التي تكلف {HIGH_CAPEX_USD:,} دولار أو أكثر تُعلَّم كمتطلب رأس مال مرتفع (دون تغيير التقييم).")},
        {"title": "مصادر البيانات", "body": (
            "الواردات ووزنها: UN Comtrade (الأردن، شاملة الشحن والتأمين، بالدولار). الرسوم الجمركية: WITS/TRAINS. "
            "أسعار المعدات: عروض الموردين المعلنة (المعدات فقط). الكلفة المحلية والتقييمات وعدد المصانع: تقديرية جزئياً، "
            "ومذكورة في estimated_fields لكل تقرير. التحويل بسعر ثابت 1 دينار = 1.4104 دولار.")},
        {"title": "قيد معروف: النمو", "body": (
            "يُقاس النمو من 2020 إلى 2024. كانت 2020 سنة منخفضة بسبب كورونا لكثير من الواردات، لذلك قد يبدو "
            "النمو من تلك السنة أقوى من الاتجاه طويل المدى.")},
    ]
    return {
        "weights": dict(WEIGHTS),
        "thresholds": {"manufacture": MANUFACTURE_THRESHOLD, "maybe": MAYBE_THRESHOLD},
        "cost_gate": {"maybe_below_margin": COST_GATE_MAYBE_BELOW, "maybe_score_cap": COST_GATE_MAYBE_SCORE_CAP,
                      "dont_below_margin": COST_GATE_DONT_BELOW, "dont_score_cap": COST_GATE_DONT_SCORE_CAP},
        "min_completeness": MIN_COMPLETENESS,
        "growth_years": {"first": 2020, "last": 2024, "note": "2020 was a COVID low base year"},
        "sections": {"en": en, "ar": ar},
    }
