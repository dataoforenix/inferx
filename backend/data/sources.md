# Category data guide: `categories.csv`

> **Current status:** `categories.csv` holds the real data for 6 categories (installed 2026-10-10,
> `data_status: ESTIMATE`). Trade values and weights come from UN Comtrade (CIF), tariffs from WITS/TRAINS;
> cost, feasibility and equipment figures are partly estimates, listed per row in `estimated_fields`.
> The previous placeholder file is kept as `categories.placeholder.csv` (not used by the app).

This page is for whoever fills in the real data. Start from
[`categories_template.csv`](categories_template.csv): it has the exact header and one fake example
row (`example_product`) that shows the format. Delete the example row in your real file.

Check your file before handing it over:

```powershell
.venv\Scripts\python.exe scripts\check_data.py path\to\your.csv
.venv\Scripts\python.exe scripts\check_data.py data\categories_template.csv --min 1   # the 1-row template
```

It lists every problem with the row, column, value and a plain-language fix, then shows the score and
verdict each category would get. Exit code 0 means the app will accept the file.

## Rules

1. **UTF-8.** Save as "CSV UTF-8" (Excel: *File → Save As → CSV UTF-8*). Arabic must stay readable.
2. **3 to 20 rows**, one per product category. Every `category_id` is unique, lowercase `snake_case`.
3. **Leave unknown cells EMPTY. Never guess.** An empty number switches off the score component that
   needs it and lowers *data completeness*. A guessed number looks real and is worse than nothing.
4. **Fractions, not percentages:** write `0.25`, not `25` or `25%`.
5. **USD, not JOD,** for every money column except the machine-cost columns (those are JOD).
   If you converted from JOD, write the rate you used in `source_notes`
   (for example "converted at 1 JOD = X USD").
6. **Ratings are 0 to 5** (0 = not available in Jordan, 5 = fully available).
7. **`hs6` is text with exactly 6 digits.** Excel drops leading zeros (`070200` becomes `70200`):
   format the column as Text before typing.
8. **`;` separates list items** inside one cell (`keywords_en`, `keywords_ar`, `machinery`,
   `raw_materials`, `estimated_fields`). Commas are fine inside text; Excel will quote the cell.
9. **`estimated_fields` lists the column names that are estimates** rather than measured or published
   values, for example `local_cost_per_kg_est_usd;factories_saturation`. The AI explanation then calls
   those numbers "estimates", and the report shows an "estimate" badge.
10. **Price consistency:** `import_price_per_kg_usd` must equal `imports_2024_usd / import_weight_kg_2024`
    within 5%.
11. **Local cost formula:** `local_cost_per_kg_est_usd` = (raw-material price per kg × kg of material per
    kg of product) + conversion cost per kg (energy, labour, depreciation, overhead).
12. **Consistency checks (warnings):** `local_cost_per_kg_est_usd` within 3% of
    `raw_material_price_usd_per_kg × material_kg_per_kg_product + conversion_cost_per_kg_usd`;
    `machine_cost_jod_*` × 1.4104 within 1% of `machine_cost_usd_*` (USD is the one used).
13. **Import values are CIF** (they already include freight and insurance). The landed cost is
    `import_price_per_kg_usd × (1 + customs_pct)`; `landed_price_per_kg_usd` must match it within 2%.
    `shipping_pct` is kept for information only and does not affect the score.
14. **Set `data_status`** to `VERIFIED` (every number traceable to a cited source), `ESTIMATE` (trade
    figures sourced, cost/feasibility figures are documented estimates) or `TODO_REAL_DATA` (placeholder).

## Column reference

Columns appear in this order. "Required" columns must exist in the header. Their cells may still be
empty where a number is unknown (rule 3), except the identity columns marked **must be filled**.

| # | Column | Meaning | Unit / format | Example | Intended source | Usually an estimate? |
|---|---|---|---|---|---|---|
| 1 | `category_id` | Stable ID used by the API and the frontend. **Must be filled.** | lowercase snake_case | `metal_chair` | You choose | — |
| 2 | `name_en` | Category name in English. **Must be filled.** | text | `Plastic buckets` | You choose | — |
| 3 | `name_ar` | Category name in Arabic. **Must be filled.** | text | `دلاء بلاستيكية` | You choose | — |
| 4 | `description_en` | One-sentence description. The AI uses it to classify photos. **Must be filled.** | text | `Plastic buckets for paint, water and storage.` | You write it | — |
| 5 | `keywords_en` | Typical product words in English (helps classification) | `;` list | `plastic bucket;paint bucket` | You write it | — |
| 6 | `keywords_ar` | Typical product words in Arabic | `;` list | `دلو بلاستيك;سطل` | You write it | — |
| 7 | `hs6` | Harmonized System code, 6 digits. **Must be filled.** | text, 6 digits | `392490` | Jordan Customs tariff / WCO | No |
| 8–12 | `imports_2020_usd` … `imports_2024_usd` | Value of Jordan's imports of this HS6 code per year (CIF) | USD | `1400000` | UN Comtrade (reporter Jordan, flow Import) or Jordan Dept. of Statistics | No |
| 13 | `import_weight_kg_2024` | Net weight imported in 2024 | kg | `700000` | Same as above | No |
| 14 | `import_price_per_kg_usd` | Average import price, = imports_2024 / weight (rule 10) | USD/kg | `2.00` | Calculated | No (derived) |
| 15 | `shipping_pct` | Freight + insurance + clearing, as a share of the import price | fraction | `0.10` | Freight-forwarder quotes | Often yes |
| 16 | `customs_pct` | Customs duty (+ other import fees) on this HS code | fraction | `0.20` | Jordan Customs tariff schedule | No |
| 17 | `local_cost_per_kg_est_usd` | Cost to make 1 kg locally (rule 11) | USD/kg | `1.50` | Supplier quotes, factory interviews | Yes |
| 18 | `machinery_availability` | Can the machines be bought/serviced in Jordan? | 0–5 | `3` | Suppliers, Chamber of Industry | Yes (expert rating) |
| 19 | `raw_material_local` | Are raw materials available locally? | 0–5 | `2` | Suppliers | Yes (expert rating) |
| 20 | `skills_availability` | Are trained workers available? | 0–5 | `4` | Vocational bodies, factories | Yes (expert rating) |
| 21 | `local_factories` | Number of local factories already making it | whole number | `4` | Jordan / Amman Chamber of Industry registry | No (if counted) |
| 22 | `factories_saturation` | Factory count at which the market is considered full (must be ≥ 1) | whole number | `20` | Team judgement | Yes |
| 23 | `machinery` | Main machines needed | `;` list | `Injection moulding machine;Bucket mould` | Suppliers | — |
| 24 | `raw_materials` | Main raw materials | `;` list | `PP resin granules;Steel wire` | Suppliers | — |
| 25 | `data_status` | `VERIFIED`, `ESTIMATE` or `TODO_REAL_DATA` (rule 14). **Must be filled.** | one of three | `ESTIMATE` | — | — |
| 26 | `source_notes` | Where each number came from; JOD→USD rate used | text | `Comtrade 2024; customs tariff 2025; rate 1 JOD = X USD` | — | — |
| 27 | `risk_notes` | Main risk for a new factory (shown as the first concern) | text | `Resin prices follow oil prices.` | Team research | — |
| 28 | `competition_note` | Short note on the competition | text | `Two importers supply most shops.` | Team research | — |
| 29 | `source_url` | Link to the main trade-data source | `http(s)://` URL | `https://comtrade.un.org/...` | — | — |
| 30 | `tariff_source_url` | Link to the tariff source | `http(s)://` URL | `https://www.customs.gov.jo/...` | — | — |
| 31 | `estimated_fields` | Column names (from this table) whose values are estimates (rule 9) | `;` list | `local_cost_per_kg_est_usd;factories_saturation` | — | — |
| 32 | `machine_cost_jod_min` | Lower bound of the machinery investment, in JOD (kept for older files; `machine_cost_usd_*` is canonical) | JOD | `10000` | Supplier quotes | Usually |
| 33 | `machine_cost_jod_max` | Upper bound (must be ≥ min) | JOD | `25000` | Supplier quotes | Usually |
| 34 | `raw_material_price_usd_per_kg` | Price of the main raw material | USD/kg | `1.49` | Import statistics of the raw material, market bulletins | Sometimes |
| 35 | `material_kg_per_kg_product` | kg of raw material per kg of finished product (yield, scrap allowance) | ratio | `1.15` | Process data, supplier info | Usually |
| 36 | `conversion_cost_per_kg_usd` | Labour, energy and overheads per kg | USD/kg | `2.0` | Factory interviews | Yes |
| 37 | `protection_pct` | Total border protection for a local producer (information only) | fraction | `0.515` | Tariff + freight | Usually |
| 38 | `landed_price_per_kg_usd` | Landed import price = `import_price_per_kg_usd × (1 + customs_pct)` (rule 13) | USD/kg | `5.505` | Calculated | No (derived) |
| 39 | `machine_cost_usd_min` | Lower bound of the **equipment** cost (canonical) | USD | `9200` | Supplier listings | Usually |
| 40 | `machine_cost_usd_max` | Upper bound (must be ≥ min). ≥ 250,000 flags a high capital requirement | USD | `30800` | Supplier listings | Usually |
| 41 | `machine_source` | Where the equipment prices come from (suppliers, models, date) | text | `Made-in-China listings, Oct 2026: …` | — | — |
| 42 | `machine_source_urls` | Links to those listings | `;` list of `http(s)://` URLs | `https://a… ; https://b…` | — | — |

Rows 8–12 are five columns, one per year, so the file has 42 columns in total (26 required + 16 optional).
Columns 27–42 are optional: the header may omit them (the loader warns) and their cells may be empty.
They never lower data completeness and never change the score directly (the score uses
`local_cost_per_kg_est_usd`, `import_price_per_kg_usd` and `customs_pct`). The machine-cost columns are
**equipment only**: supplier listing prices ex-works, excluding shipping, customs, installation, moulds and buildings.

### What an empty cell switches off

| Empty cell(s) | Effect |
|---|---|
| `imports_2024_usd` | Market score unavailable → completeness drops to 65% → verdict forced to MAYBE |
| `imports_2020_usd` (or 0) | Trend unavailable; market uses volume only (completeness 86%) |
| any of `import_price_per_kg_usd`, `customs_pct`, `local_cost_per_kg_est_usd` | Cost score unavailable → completeness 70% → forced MAYBE |
| `shipping_pct` | Nothing: it is information only (freight is already in the CIF import price) |
| any of the three 0–5 ratings | Feasibility score unavailable (completeness 80%) |
| `local_factories` or `factories_saturation` | Competition score unavailable (completeness 85%) |

## Per-category sources

Update this table when you replace a row with real figures.

| category_id | HS6 | Status | Source |
|---|---|---|---|
| metal_chair | 940171 | ESTIMATE | UN Comtrade 2020–2024 (Jordan imports, CIF); WITS/TRAINS MFN 2023; freight quote Goodhope Freight Sep 2026; equipment: Made-in-China listings Oct 2026 |
| warehouse_racks | 940320 | ESTIMATE | Same sources; raw material: WITS 721049 coated flat-rolled steel |
| plastic_tableware | 392410 | ESTIMATE | Same sources; raw material: WITS 390210 polypropylene |
| ceiling_fan | 841451 | ESTIMATE | Same sources; raw-material price is an estimate (motor + steel/plastic) |
| frozen_fries | 200410 | ESTIMATE | Same trade/tariff sources; potato price: Ministry of Agriculture bulletin, Amman Central Market, 29 Mar 2026 |
| tomato_paste | 200290 | ESTIMATE | Same trade/tariff sources; tomato price: Ministry of Agriculture bulletin, 29 Mar 2026; Brix ratio 29/4.5 |

Full citations are in each row's `source_notes`, `source_url`, `tariff_source_url`, `machine_source` and `machine_source_urls`.

Re-checked 2026-10-10 with `scripts/refresh_trade_data.py`: all 30 import values and 6 import weights match UN
Comtrade exactly.

## Refreshing the trade figures

`scripts/refresh_trade_data.py` re-pulls `imports_2020_usd` … `imports_2024_usd` and `import_weight_kg_2024` from
the UN Comtrade public preview API for every row (by `hs6`) and writes `data/categories.refreshed.csv`. It never
overwrites `data/categories.csv` and copies every other column unchanged; a value Comtrade doesn't return keeps its
old value. It prints old / new / % change and marks changes over 5%. Then:

1. Review the marked values (a revision by the reporting country is normal; a jump of 50% is worth a look).
2. `import_price_per_kg_usd` is **not** recomputed: if the 2024 value or weight moved, update it by hand
   (= imports_2024_usd / import_weight_kg_2024) and run `scripts/check_data.py data/categories.refreshed.csv`.
3. Update the "pulled" date in each row's `source_notes` **by hand** (the script never edits text).
4. Copy the file over `data/categories.csv`, run the tests, and update `tests/test_real_data.py` if a verdict moved.
