# Frontend handoff: new backend features (branch `claude-review`)

Everything below is **additive**. No existing endpoint, request or response field changed (checked by diffing
`backend/docs/openapi.json` before and after), so the current frontend keeps working unchanged.
Full schema: `backend/docs/openapi.json`. Real response bodies: `backend/docs/examples/` (`budget_partial.json`,
`methodology.json`, and every `report` in the analyze/confirm/whatif examples now carries the new fields).
None of the new features calls the AI, and all of them work in `DEMO_MODE`.

The natural place to read the new report fields is `mapReport()` in `frontend/src/lib/api.js` (`body.report`).

---

## 1. `report.market.latest_import_jod` (new field)

```json
"market": { "latest_import_usd": 21465982.0, "latest_import_jod": 15219381.24, ... }
```

- **Derived**: `latest_import_usd × 0.709` (fixed peg), computed on the server. `null` when the USD value is null.
- The UI already converts USD to JOD with `USD_TO_JOD = 0.709` in `api.js`. You can now read this field instead
  of converting yourself; the numbers are identical.
- Show: "≈ 15.2 مليون دينار (محوّل من الدولار)". Label it as converted, not as a separate statistic.

## 2. `POST /api/budget` (new endpoint)

Request:
```json
{ "category_id": "tomato_paste", "budget_jod": 100000 }
```
Response (`backend/docs/examples/budget_partial.json`):
```json
{
  "request_id": "…",
  "category_id": "tomato_paste",
  "budget_jod": 100000.0,
  "status": "partial",
  "capex_jod_range": { "min": 35450.0, "max": 354500.0 },
  "gap_jod": 254500.0,
  "caption_en": "Equipment only: supplier listing prices ex-works, excluding shipping, customs, installation, moulds and buildings (converted to JOD at the fixed peg 1 USD = 0.709 JOD).",
  "caption_ar": "المعدات فقط: أسعار الموردين المعلنة من المصنع، بدون الشحن والجمارك والتركيب والقوالب والمباني (محوّلة إلى الدينار بسعر ثابت 1 دولار = 0.709 دينار)."
}
```
- `status`:
  - `covered`: the budget reaches the top of the equipment range;
  - `partial`: it reaches the bottom but not the top;
  - `short`: it's below the bottom.
- `gap_jod`: what is still missing to reach the top of the range; 0 when covered.
- Errors:
  - `404 unknown_category`;
  - `422 capex_unavailable` (category without an equipment range);
  - `422 validation_error` (negative or missing `budget_jod`, or extra keys).
- No AI call, a few ms: fine to call on input change (debounce about 300 ms).
- **Show:** a number input "ميزانيتك للمعدات (دينار)", then a badge:
  - covered = «تكفي»
  - partial = «تكفي جزئياً»
  - short = «لا تكفي»

  Next to the badge, show the JOD range and «ينقصك X دينار» when `gap_jod > 0`.
- **Mandatory:** always show `caption_ar` (or `caption_en`) right under the result. The range is equipment only, never the total investment.

## 3. `report.next_steps` (new field)

```json
"next_steps": {
  "en": ["Do not invest in equipment based on this result.", "…"],
  "ar": ["لا تستثمر في المعدات بناءً على هذه النتيجة.", "…"]
}
```
- Fixed steps chosen by `verdict` (MANUFACTURE / MAYBE / DONT), 4 per language. **Not AI text.**
- This is different from `explanation.next_steps`, which the AI writes. The UI can show both, or prefer
  `report.next_steps` when `explanation_source` is `fallback`.
- **Show:** a numbered "الخطوات التالية" list using `next_steps.ar` in the Arabic UI.

## 4. `report.advisors` (new field)

```json
"advisors": [
  { "name_en": "Jordan Enterprise Development Corporation (JEDCO)",
    "name_ar": "المؤسسة الأردنية لتطوير المشاريع الاقتصادية (جيدكو)",
    "offer_en": "Support programmes, technical assistance and financing tools for SMEs, start-ups and manufacturers.",
    "offer_ar": "برامج دعم ومساعدة فنية وأدوات تمويل للمشاريع الصغيرة والمتوسطة والريادية والصناعية.",
    "url": "https://www.jedco.gov.jo" }
]
```
- 6 official bodies:
  - JEDCO;
  - Jordan Chamber of Industry;
  - Ministry of Industry, Trade and Supply;
  - Companies Control Department;
  - Jordan Standards and Metrology Organization (JSMO);
  - Jordan Loan Guarantee Corporation.
- Every URL was opened on 2026-10-10 and the site itself describes the listed service.
- No phone numbers or personal names; don't add any in the UI.
- Same list on every report.
- **Show:** a "جهات تساعدك" card. Per body: `name_ar`, `offer_ar`, and a link «الموقع الرسمي» (`target="_blank" rel="noopener"`).

## 5. `report.suppliers` (new field)

```json
"suppliers": {
  "caption_en": "Search links, not supplier recommendations. Verify suppliers yourself.",
  "caption_ar": "روابط بحث وليست توصيات بموردين. تحقّق من الموردين بنفسك.",
  "items": [
    { "item": "Washer and sorter", "kind": "machinery",
      "links": [ { "marketplace": "Made-in-China.com",
                   "url": "https://www.made-in-china.com/multi-search/Washer+and+sorter/F1/1.html" } ] }
  ],
  "local_directory": { "name_en": "Jordan Chamber of Industry: industrial directory",
                       "name_ar": "غرفة صناعة الأردن: الدليل الصناعي", "offer_en": "…", "offer_ar": "…",
                       "url": "https://jci.org.jo/%d8%a7…/" }
}
```
- One entry per item of `report.machinery` and `report.raw_materials`, in the same order; `kind` says which.
- Each link is a **marketplace search built from the item name**, not a supplier.
- Only Made-in-China is included. Its search URL format was verified. Alibaba's could not be verified, so it was left out.
- `local_directory` is the Jordan Chamber of Industry's industrial directory (verified).
- **Show:** under the existing machinery / raw-material lists, a small «ابحث» link per item, plus one link to the local directory.
- **Mandatory:** always show `caption_ar` / `caption_en` next to the links. Never present a link as a recommended supplier.

## 6. `GET /api/methodology` (new endpoint)

Response (`backend/docs/examples/methodology.json`):
```json
{
  "request_id": "…",
  "weights": { "market": 0.35, "cost": 0.3, "feasibility": 0.2, "competition": 0.15 },
  "thresholds": { "manufacture": 6.0, "maybe": 4.0 },
  "cost_gate": { "maybe_below_margin": 0.0, "maybe_score_cap": 5.9, "dont_below_margin": -0.25, "dont_score_cap": 3.9 },
  "min_completeness": 0.8,
  "growth_years": { "first": 2020, "last": 2024, "note": "2020 was a COVID low base year" },
  "sections": { "en": [ { "title": "Score", "body": "…" }, … ], "ar": [ { "title": "التقييم", "body": "…" }, … ] }
}
```
- 6 sections per language:
  1. score;
  2. components (formulas);
  3. cost gate;
  4. data completeness;
  5. data sources;
  6. known limitation: growth.
- The numbers come from the scoring code, so they can't drift from the real calculation.
- **Show:** a «كيف نحسب التقييم؟» link (footer or next to the score) that opens a modal listing `sections.ar` (title + body).
  Fetch it once and cache it.
- Keep the last section (the COVID 2020 base-year note) visible. It is an honest limitation.

---

## Frontend bugs found in testing (not fixed: for the frontend owner)

See the section added below after the browser test.
