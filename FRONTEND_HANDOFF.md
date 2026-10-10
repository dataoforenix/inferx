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

## 7. Optional response cache (branch `db-cache`, only if it is merged)

- `POST /api/analyze` may carry `"cache": "hit" | "miss"` (only when the server runs with `DB_ENABLED=true`, never in demo mode).
  - **Show:** on `hit`, a small grey note «نتيجة محفوظة من تحليل سابق (أقل من 24 ساعة)».
  - On `hit` the analysis is instant, so the staged 4.8 s animation (`ANALYSIS_MS`) is optional.
  - Don't rely on the field being present.
- `GET /api/searches/top?limit=10` → `{searches: [{category_id, hs6_guess, name_en, name_ar, count}]}`.
  - It returns 404 when the cache is off, so hide the widget then.
  - **Show:** a «الأكثر بحثاً» list of `name_ar` with the count. A click can pre-fill the input with `name_ar`.
  - Contains no personal data.

---

## Browser test of the current frontend (2026-10-10, measured; no frontend file was changed)

**Setup:**
- Frontend: `npm ci && npm run build` (build OK) and `npm run dev` on `http://localhost:5173`.
- Backend: `DEMO_MODE=true` on port 8000, no key.
- Browser: Microsoft Edge (installed), headless, driven by `playwright-core`. Viewport 1366×900, plus one 390×844 phone-size run.
- Screenshots were taken, but they are not in the repo.

| Flow | Result |
|---|---|
| Page load | Title OK, `<html dir="rtl" lang="ar">`, no API call on load, no 404 for any asset. |
| Analyze «كرسي مكتب معدني منجد» | `POST /api/analyze` → 200 `complete`; verdict صنّعها, score 7.0 shown; Arabic AI summary; HS 9401.71. ✅ |
| What-if sliders | 3 sliders (customs 0–1, local cost 0.05–5.3 JOD, import price 0.05–11 JOD). Local cost to max → `POST /api/whatif` → score 7.0→3.9 «لا تصنّعها» shown; customs to 0 → request sent, stays 3.9 (cost gate). ✅ |
| needs_confirmation «plastic chair with metal legs» | 200 `needs_confirmation`; «أيّ هذه هو منتجك؟» with one choice «كرسي معدني منجّد»; click → `POST /api/analyze/confirm` → 200 `complete`, 7.0. ✅ (see bug 1 below) |
| Arabic, DONT + cost gate «معجون بندورة» | 200 `complete`; «لا تصنّعها» 3.9, red verdict, «يحتاج رأس مال مرتفعاً» chip, Arabic summary quoting the cost gap. ✅ |
| Unknown «محرك سفينة فضائية» | 404 `demo_no_match` → «تعذّر إكمال التحليل» + the Arabic prepared examples. ✅ The browser logs one console error for this 404 fetch; that is expected. |
| English text «frozen french fries» | 200 `complete`, Arabic UI and Arabic summary. ✅ |
| Phone size 390×844 «مروحة سقف» | 200 `complete`; no horizontal overflow (0 px). ✅ |

Console/page errors during all flows: only the expected 404 above. No JavaScript exceptions.

### Bugs and issues for the frontend owner (not fixed here)

1. **Machinery and raw materials show in English inside the Arabic UI.** Examples: "Washer and sorter", "Vacuum evaporator", "Fresh tomatoes (grown in Jordan)". These come from the CSV, which has those lists in English only. Options:
   - label the lists «(بالإنجليزية)»;
   - or keep a small Arabic map in the UI.

   The new `report.suppliers` items use the same English names, which works well for the marketplace searches.
2. ✅ **Fixed (2026-10-10):** a fifth suggestion button «كرسي بلاستيك بأرجل معدنية» now shows the confirmation step. **The demo-no-match list hides the confirmation example.** The examples are filtered to Arabic only (`isArabic` in `analyzeProduct.js`), and the needs-confirmation demo input's example text is English ("plastic chair with metal legs"), so it is never suggested. The 4 suggestion buttons don't include it either. To show the confirmation step in the demo, add a suggestion button with «كرسي بلاستيك بأرجل معدنية», which is one of that entry's match keywords.
3. ✅ **Not a real bug:** `EngineeringCursor` is only enabled for `(hover: hover) and (pointer: fine)`, so touch phones never show it. The headless run emulated a phone-size window with a mouse. **The custom gear cursor (`EngineeringCursor`) overlaps text at phone size.** Seen in the 390×844 run (headless desktop emulation, not a real touch device). Check on a real phone, and hide the cursor for `(pointer: coarse)`.
4. ✅ **Removed (`3e5e970`): the UI now shows «الخادم غير متاح. شغّل الـ backend أولاً كما في README».** **Offline fallback shows bundled sample products.** When the backend is unreachable (`BackendDown`), `toOutcome()` shows sample products from `legacy/sampleData.js` (e.g. solar panels, screws) with their own figures. The UI shows the notice «الخادم غير متاح الآن، هذه بيانات تجريبية» (in the code; not exercised in this test). Make sure the notice stays very visible during judging, or show an error instead.
5. **USD→JOD rewriting of AI text (risk, not a bug).** `usdTextToJod()` rewrites the dollar amounts in the AI explanation into JOD with regexes. The amounts checked in this test were correct (2.63 and 3.90 JOD/kg = 3.713 and 5.505 USD × 0.709). However, the text the user sees is no longer the exact text that passed the backend's number check. Prefer the new numeric fields (`market.latest_import_jod`, `budget` JOD values) for new UI.
6. **Not frontend, but visible in it (backend demo mode).** After confirming the needs-confirmation example in DEMO_MODE, the summary names «كرسي مكتب معدني منجد» while the product title is «كرسي بلاستيك بأرجل معدنية». Demo mode replays the recorded explanation of another input in the same category. Live mode writes a new explanation. Listed in SUMMARY.md as a known backend limitation.
7. ✅ **Done (2026-10-10):** a new «ابدأ من هنا» section shows next steps, the budget box, advisors, supplier links (with `caption_ar`) and «كيف نحسب؟», and the market tile shows USD ≈ JOD. **The new backend features are not shown yet:** `next_steps`, `advisors`, `suppliers`, `/api/budget`, `/api/methodology` (sections 1–6 above). Expected, since they were just added.
