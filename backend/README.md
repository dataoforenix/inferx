# Sanna'ha (صنّعها) — MVP backend

FastAPI backend that helps Jordanian entrepreneurs judge whether an imported product could be
manufactured locally. A user sends a photo and/or an Arabic or English description; the backend
identifies the product with an LLM (Google Gemini, called through its OpenAI-compatible endpoint with the
OpenAI Python SDK), scores feasibility **in Python**, and has the LLM explain the result.

> **Data status:** `data/categories.csv` holds the real data for 6 categories (`data_status: ESTIMATE`):
> trade figures from UN Comtrade / WITS, cost and feasibility figures partly estimated (each row lists its
> estimated columns in `estimated_fields`). See [Data status](#data-status) and [`data/sources.md`](data/sources.md).

**Frontend developers:** start with [`docs/api_contract.md`](docs/api_contract.md) and the real
response bodies in [`docs/examples/`](docs/examples/).

## How it works

```
photo / text ──► image_utils     validate, strip metadata, resize; memory only
             ──► llm.normalize   LLM: product names + category (a CSV category or "unsupported")
             ──► pipeline        Python decides: unsupported / needs_confirmation (confidence < 0.7) / continue
                                 (unsupported but physical + AI HS6 guess: UN Comtrade market preview, live mode only)
             ──► scoring         Python only: 0–10 score + MANUFACTURE / MAYBE / DONT
             ──► llm.explain     LLM explains the Python report (en / ar)
             ──► grounding guard every number in the explanation must exist in the report (or the CSV notes);
                                 one retry with feedback, then a deterministic template explanation
```

**Rule:** LLMs classify and explain; they never produce the score, verdict or any statistic.

| Module | Responsibility |
|---|---|
| `app/main.py` | ASGI entry point (`uvicorn app.main:app`); loads `data/categories.csv` on import |
| `app/factory.py` | `create_app()`; side-effect free, used by tests and scripts |
| `app/config.py` | Settings from env / `.env` |
| `app/data_store.py` | CSV schema, validation (`inspect_categories` collects issues; `load_categories` fails fast) |
| `app/scoring.py` | Pure scoring functions and the report (no I/O, no LLM) |
| `app/image_utils.py` | Image validation and sanitising |
| `app/llm.py` | LLM calls via the OpenAI SDK to Gemini's OpenAI-compatible endpoint (structured JSON output, validation, retries, error mapping, per-call logging) |
| `app/explanation.py` | Key figures for the LLM, grounding guard, template explanation (en/ar) |
| `app/demo.py` | Demo cache and demo inputs |
| `app/pipeline.py` | Orchestration, grounding retry, timings |
| `app/comtrade.py` | UN Comtrade public preview client (Jordan imports per HS6; paced, 24 h cache, never raises) |
| `app/market_preview.py` | Market-preview report and template explanation for products outside the categories |
| `app/rate_limit.py` | In-memory per-IP limiter |
| `app/routers/` | `analyze`, `whatif`, `meta` endpoints |

## Setup

Requires Python 3.11 (the commands use [uv](https://docs.astral.sh/uv/); plain `python -m venv` + `pip` works too).

**Windows (PowerShell), from `backend/`:**
```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv -r requirements.txt
copy .env.example .env          # then edit .env: set OPENAI_API_KEY, or DEMO_MODE=true
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

**macOS / Linux, from `backend/`:**
```bash
uv venv --python 3.11 .venv
uv pip install --python .venv -r requirements.txt
cp .env.example .env            # then edit .env
.venv/bin/python -m pytest
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

Interactive API docs: http://localhost:8000/docs

## Configuration (`.env`)

| Variable | Default | Notes |
|---|---|---|
| `OPENAI_API_KEY` | — | The **Gemini** API key (name kept for the OpenAI SDK). Required for live analysis. Never logged or returned. |
| `OPENAI_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta/openai/` | Gemini's OpenAI-compatible endpoint; any OpenAI-compatible URL works |
| `NORMALIZE_MODEL` / `EXPLAIN_MODEL` | `gemini-3.5-flash-lite` | Must support vision and JSON structured outputs on that endpoint (see [Speed and cost](#speed-and-cost)) |
| `LLM_REASONING_EFFORT` | `low` | Sent as `reasoning_effort` on both calls; `default` = don't send it (for models that reject it) |
| `LLM_TIMEOUT_SECONDS` / `LLM_MAX_RETRIES` | `15` / `1` | Per call; the SDK retries timeouts, 408/409/429/5xx and connection errors |
| `DEMO_MODE` | `false` | Serve prepared examples, no LLM calls |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:5173` | Comma-separated, or `*` |
| `MAX_UPLOAD_MB` / `MAX_TEXT_CHARS` | `8` / `1000` | Input limits |
| `CONFIRM_CONFIDENCE_THRESHOLD` | `0.7` | Below this the user must confirm the category |
| `RATE_LIMIT_PER_MINUTE` | `30` | Limit **per client IP** on `POST /api/analyze` and `/api/analyze/confirm`; `0` disables. Behind a dev proxy (e.g. Vite `server.proxy`) every browser shares the proxy's IP, so use ~`300` while rehearsing |
| `MARKET_PREVIEW` | `true` | UN Comtrade market preview for physical products outside the categories (live mode only; never in demo mode) |
| `CATEGORIES_CSV` / `DEMO_CACHE_DIR` | `data/categories.csv` / `data/demo_cache` | |

## Data

`data/categories.csv` holds **3 to 20 categories** (one row each) with 26 required and 16 optional
columns (42 in total). The full column reference (meaning, unit, example, source, estimate or not) and the
filling rules are in [`data/sources.md`](data/sources.md); the exact header plus one fake example row is
[`data/categories_template.csv`](data/categories_template.csv).

The app refuses to start on an invalid file. To see **every** problem at once, with a plain-language
fix for each and the resulting score per category:

```powershell
.venv\Scripts\python.exe scripts\check_data.py                                   # data/categories.csv
.venv\Scripts\python.exe scripts\check_data.py path\to\new.csv
.venv\Scripts\python.exe scripts\check_data.py data\categories_template.csv --min 1
```

Exit code 0 = the app will load the file (warnings are fine), 1 = errors. The summary warns if no
category scores DONT or none scores MANUFACTURE (the demo needs both).

### Data status

Installed 2026-10-10 from `data/incoming_products_data.csv` (kept unchanged next to it; the previous
placeholder file is `data/categories.placeholder.csv`). `check_data.py`: 0 errors, 0 warnings.

| category_id | Score | Verdict | Cost margin | Notes |
|---|---|---|---|---|
| metal_chair | 7.0 | MANUFACTURE | +0.326 | |
| warehouse_racks | 7.2 | MANUFACTURE | +0.350 | |
| plastic_tableware | 6.2 | MANUFACTURE | +0.137 | |
| ceiling_fan | 5.2 | MAYBE | −0.036 | local slightly dearer than import (gate allows at most MAYBE) |
| frozen_fries | 8.6 | MANUFACTURE | +0.123 | high_capital_requirement (equipment up to 420,000 USD) |
| tomato_paste | 3.9 | DONT | −1.787 | cost gate (weighted 4.7); high_capital_requirement (500,000 USD) |

`tests/test_real_data.py` pins these results, so a data update that changes a verdict is noticed.

### Updating the data

1. Replace `data/categories.csv` with the new file (same header as `data/categories_template.csv`).
2. `.venv\Scripts\python.exe scripts\check_data.py`: fix every error; read the warnings.
3. Edit `data/demo_inputs.json` so each `expected_category_id` (and any `alternatives`) is one of the
   new `category_id`s, or `unsupported`. Adjust `text`, `match_keywords` and the placeholder names to match.
4. Delete the old demo cache: `Remove-Item data\demo_cache\*.json`.
5. Rebuild it: `.venv\Scripts\python.exe scripts\record_demo_cache.py` with an API key (records real
   outputs), or `... record_demo_cache.py --placeholders` without one. Both stop with a clear message if
   `demo_inputs.json` doesn't match the CSV.
6. `.venv\Scripts\python.exe -m pytest` (offline; uses frozen fixtures, except `tests/test_real_data.py`,
   whose expected verdicts and scores you update deliberately), then
   `.venv\Scripts\python.exe -m pytest -m llm -v` with a key (classifies the real categories using
   `demo_inputs.json`).
7. Update the per-category source table in `data/sources.md`.

No code changes are needed: categories, counts and names all come from the CSV.

### Refreshing the trade figures

```powershell
.venv\Scripts\python.exe scripts\refresh_trade_data.py      # ~25 s per category (public API, paced 5 s per request)
```

Re-pulls `imports_2020_usd`…`imports_2024_usd` and `import_weight_kg_2024` from UN Comtrade for every category
(reusing `app/comtrade.py`) and writes **`data/categories.refreshed.csv`**; `data/categories.csv` is never
overwritten and all other columns are copied unchanged. It prints old / new / % change per value and marks changes
over 5%. To install: review the marked values, recompute `import_price_per_kg_usd` by hand if 2024 moved, update
the "pulled" dates in `source_notes` **by hand**, run `scripts\check_data.py data\categories.refreshed.csv`, then
copy it over `data/categories.csv` and run the tests. Exit code 0 = all values refreshed, 2 = some kept their old
value, 1 = nothing written. Full steps: [`data/sources.md`](data/sources.md#refreshing-the-trade-figures).
On 2026-10-10 every installed trade value matched Comtrade exactly.

## API

Full contract for the frontend: [`docs/api_contract.md`](docs/api_contract.md). Summary:

| Method | Path | Notes |
|---|---|---|
| POST | `/api/analyze` | multipart `image?`, `text?`, `language`; returns `complete` / `needs_confirmation` / `unsupported` / `market_preview` |
| POST | `/api/analyze/confirm` | JSON `{category_id, language, product?}` after `needs_confirmation`; works without an API key (template explanation) |
| POST | `/api/whatif` | JSON `{category_id, overrides}`; no LLM; returns `baseline`, `scenario`, `score_delta` |
| GET | `/api/categories` | the CSV categories |
| GET | `/api/health` | `ok`/`degraded`, demo mode, data warnings, demo-cache counts |

Every report carries the scores plus the CSV context for the cards: `trend_label`, `machinery`,
`raw_materials`, `risk_notes`, `competition_note`, `source_notes`, `sources`, `estimated_fields`,
`machine_cost_range_jod`, `capex_usd_range`, `import_weight_kg_2024` and `break_even`. Every analyze/confirm response carries `timings_ms` (`normalize`, `score`,
`explain`, `total`).

All errors look like `{"error": {"code", "message", "request_id", "details?"}}`; every response carries
an `X-Request-ID` header. `POST /api/analyze` requires a `Content-Length` header (browsers send it;
dev proxies must not switch to chunked encoding).

```bash
curl -X POST http://localhost:8000/api/analyze -F "text=plastic plates and cups" -F "language=ar"
curl -X POST http://localhost:8000/api/analyze -F "image=@photo.jpg" -F "language=en"
curl -X POST http://localhost:8000/api/whatif -H "Content-Type: application/json" \
  -d '{"category_id": "tomato_paste", "overrides": {"customs_pct": 0.5, "local_cost_per_kg_est_usd": 1.0}}'
```

> **Windows curl + Arabic:** curl on Windows may not send command-line Arabic as UTF-8. Put the text in a
> UTF-8 file and use `-F "text=<desc.txt"`. Browsers and Python clients are unaffected.

Regenerate the frontend docs after an API change (both run offline, no key):

```powershell
.venv\Scripts\python.exe scripts\export_openapi.py   # docs/openapi.json
.venv\Scripts\python.exe scripts\build_examples.py   # docs/examples/*.json
```

`tests/test_examples.py` fails if `docs/openapi.json` is stale or an example no longer matches its model.

## Scoring

Weights: market 35%, cost 30%, manufacturing feasibility 20%, competition 15%.

- Market = 0.6 × volume + 0.4 × trend; volume = `10·log10(1 + imports/1e6)/log10(101)`; trend = `5 + CAGR·50`
- Cost = `5 + margin·25`, margin = `(landed − local)/landed`, landed = `price·(1+customs)`. Import values are **CIF**:
  freight and insurance are already inside `import_price_per_kg_usd`, so `shipping_pct` is information only and never
  changes the score (a what-if override of it returns a note saying so).
- Feasibility = `(machinery + raw material + skills)/15 · 10` (each rated 0–5)
- Competition = `10·(1 − min(1, factories/saturation))`

Components are clamped to 0–10; the total is rounded half-up to one decimal. ≥ 6 MANUFACTURE, ≥ 4 MAYBE, else DONT.

**Cost gate** (constants at the top of `app/scoring.py`), applied after the weighted score, with `m` = cost margin:

| Condition | Effect |
|---|---|
| `m < 0` (`COST_GATE_MAYBE_BELOW`) | verdict at most MAYBE, score capped at 5.9 |
| `m < −0.25` (`COST_GATE_DONT_BELOW`) | verdict DONT, score capped at 3.9 |

If the cap changes the score or verdict, the report sets `verdict_capped_by: "cost_gate"` and adds a note quoting the
local and landed costs; the explanation says the verdict was limited because producing locally costs more than
importing. When low data completeness also forces MAYBE, the lower verdict applies.

**Capital flag** (no score change): `machine_cost_usd_max ≥ 250,000` (`HIGH_CAPEX_USD`) adds `"high_capital_requirement"` to
`report.flags` and a note; the explanation lists it as a concern and always describes `capex_usd_range` as equipment only and
partial (ex-works supplier listing prices, excluding shipping, customs, installation, moulds and buildings).
**Break-even** (no score change): `report.break_even = {capex_mid_usd, unit_saving_usd_per_kg, break_even_tons,
share_of_2024_imports}` with capex_mid = (`machine_cost_usd_min` + `max`)/2, unit_saving = landed − local,
break-even kg = capex_mid / unit_saving, share = break-even kg / `import_weight_kg_2024`. `null` when any input is
missing or local production is not cheaper. It uses the what-if values, so sliders move it. Caption it as
*indicative: equipment only, excludes buildings and working capital, assumes selling at import-parity price*.
Installed data: metal_chair 11 t (2.2% of 2024 imports), warehouse_racks 68 t (1.1%), plastic_tableware 88 t (2.2%),
frozen_fries 1,458 t (1.8%); ceiling_fan and tomato_paste `null`. Both template explanations add it as one sentence.

`trend_label` (display only): `growing` if CAGR > 3%, `declining` if < −3%, else `stable`.

Missing or invalid inputs disable the affected component (never guessed); the score is renormalised over the
remaining components and `data_completeness` drops. Below 80% completeness the verdict is forced to MAYBE.
The optional columns never affect the score or completeness.

## Explanations and the grounding guard

The explanation LLM sees only the product and the Python report. Every number it writes must match a
number in the report, the key figures, or the CSV free-text notes (`risk_notes`, `competition_note`,
`source_notes`, `machine_source`, `machinery`, `raw_materials`), at the precision written. The long notes are
sent to the model once, in a separate `<data_notes>` block (not repeated in the key figures or the report). If not, the model gets **one
retry** with the offending numbers listed; if that also fails, the deterministic template explanation is
used (`explanation_source: "fallback"`). Numbers from columns listed in `estimated_fields` must be called
"estimates", and the template adds a caveat naming them. A non-empty `risk_notes` is the template's first concern.

## Market preview (products outside the categories)

When the AI says a product is **physical but fits no category**, it also returns `hs6_guess` (a 6-digit HS code,
or `null`). In live mode the backend then asks the public UN Comtrade preview API
(`https://comtradeapi.un.org/public/v1/preview/C/A/HS`, no key, no LLM web search) for Jordan's imports
(`reporterCode=400`, `partnerCode=0`, `flowCode=M`) of that code, one request per year 2020–2024. If 2024 comes
back, the response has status `market_preview`: a report built from imports and import weight only (cost,
feasibility and competition are missing, so completeness forces MAYBE), flag `market_preview_only`, the HS code for
the user to check (`product.hs6_guess`), and a template explanation in EN/AR (no LLM call) saying it is a preliminary
market scan and which data is needed to decide. If Comtrade fails, the normal `unsupported` response is returned
with a warning.

**Rate limit (measured 2026-10-10):** the public preview accepts one period per request and about one request
every 2–3 s per IP (HTTP 429 "Try again in N seconds"). The client paces requests 2.5 s apart (shared by all
requests to the server), honours the server's retry delay once, and stops at a ~10 s budget. It fetches **2024
first, then 2020** (the two years the score uses), then 2021–2023 (display only), so in practice the middle years
are often `null`. A missing 2024 means no preview. Successful lookups are cached in memory for 24 h; failures
aren't cached. Turn the feature off with `MARKET_PREVIEW=false`.

## Demo mode

`DEMO_MODE=true` serves `data/demo_cache/*.json` without calling the LLM. Only LLM outputs are cached;
**scores are always recomputed live from the CSV**, and cached explanations still pass the grounding guard.

The demo inputs live in [`data/demo_inputs.json`](data/demo_inputs.json) (text, match keywords, expected
category, placeholder recognition): two per category (English and Arabic, e.g. "metal office chair",
"رفوف مستودعات", "canned tomato paste", "معجون بندورة"), "plastic chair with metal legs" (→ needs confirmation:
recorded as metal_chair at confidence 0.6), "accounting software for small shops" (→ unsupported, not physical) and
"rooftop solar panel" (→ unsupported, physical but outside the catalogue). Other inputs return `404 demo_no_match`.

The shipped cache entries were **recorded from the live pipeline** on 2026-10-10 (`generated_by: pipeline`,
gemini-3.5-flash-lite at reasoning effort `low`). Every complete entry has English and Arabic AI explanations that
passed the grounding guard, so demo mode shows `explanation_source: "llm"` for them. To re-record with a key, or to go
back to hand-written placeholders without one:

```powershell
.venv\Scripts\python.exe scripts\record_demo_cache.py               # live pipeline, a few cents
.venv\Scripts\python.exe scripts\record_demo_cache.py --placeholders # offline placeholders
```

In live mode, if the LLM is unavailable and the input matches a cached example, that example is served with
`source: "demo_cache"` and a warning; otherwise the API returns `503 llm_unavailable`.

## Speed and cost

The defaults were picked by measurement on 2026-10-10. The same text request ("plastic plates and cups") and
image request (a tomato-paste can) were sent through the full `/api/analyze` pipeline. The first row is the earlier
smoke test (old defaults: 60 s timeout, 2 SDK retries); the other rows ran with a 120 s timeout and SDK retries off:

| Model | `reasoning_effort` | Text request | Image request |
|---|---|---|---|
| `gemini-3.8-flash` | (not sent) | 237.6 s, explanation timed out → template | 239.6 s, `llm`, correct (incl. SDK timeout retries) |
| `gemini-3.8-flash` | `minimal` | rejected immediately (`502 llm_error`, < 1 s) | rejected immediately (`502 llm_error`, < 1 s) |
| `gemini-3.8-flash` | `low` | 55.9 s, `llm`, correct | recognition call > 120 s → `503` |
| **`gemini-3.5-flash-lite`** | **`low`** | **3.6 s, `llm`, correct** | **2.8 s, `llm`, correct** |

So the default is `gemini-3.5-flash-lite` at `low`, with a 15 s per-call timeout and one SDK retry. A stuck call
can't turn a request into minutes: worst case one recognition call plus up to two explanation calls (grounding
retry), each at most 2 × 15 s, and a failed explanation falls back to the template. To change model or provider, edit `.env`:

```
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
NORMALIZE_MODEL=gemini-3.5-flash-lite
EXPLAIN_MODEL=gemini-3.5-flash-lite
LLM_REASONING_EFFORT=low
```

The model must accept images and `response_format` JSON-schema structured outputs. Any reply the SDK can't
parse (cut off, invalid JSON, wrong shape) is retried once and then returned as `502 llm_invalid_output`; every
other SDK failure maps to `llm_unavailable` / `llm_error` / `input_refused`, never a raw 500.

To measure, read the logs and the response:
- one log line per API call: `llm_call op=… model=… attempt=… latency_ms=… input_tokens=… output_tokens=… finish_reason=…`
  (never prompt, image or reply content);
- one line per HTTP request with status and duration;
- `timings_ms` in every analyze/confirm response.

## Safety measures

- Images: format sniffed (not trusted from headers), size and pixel limits, EXIF orientation applied, all metadata
  stripped by re-encoding, never written to disk (uploads stay in memory; requests without `Content-Length` are refused).
- Prompt injection: user text, and the product fields sent to `/confirm`, have breakout tags removed and are
  wrapped in data blocks the system prompt tells the model to ignore instructions in. The model can only answer
  with a fixed JSON shape, and the category is limited to the CSV categories. The confirmation decision and
  every number are computed in Python.
- Rate limit: 30 analyze/confirm requests per minute per IP by default (`429 rate_limited` + `Retry-After`).
  The key is the client IP the server sees, in memory and per process: behind a dev or reverse proxy all
  clients share the proxy's IP (and one limit), so set `RATE_LIMIT_PER_MINUTE=300` for rehearsals.
- Bodies are never logged; API keys never appear in logs, `repr(settings)` or responses.

## Tests

```powershell
.venv\Scripts\python.exe -m pytest            # all offline tests, no API key needed (LLM is mocked)
.venv\Scripts\python.exe -m pytest -m llm -v  # real Gemini API tests (needs OPENAI_API_KEY; skips cleanly without)
```

Offline tests never read `data/categories.csv` or `data/demo_cache/`: they use frozen copies in
`tests/fixtures/`, so replacing the data can't break them. The live tests deliberately use the real
`data/categories.csv` and `data/demo_inputs.json`.

## Known limitations

- Cost and feasibility figures are partly estimates (see `estimated_fields` per category).
- `risk_notes` / `competition_note` are written in Arabic, so the **English template** explanation quotes the
  risk note in Arabic (the AI explanation writes in the requested language).
- Grounding guard is lightweight: small counts 0–10, data years and the HS code are always allowed.
- Demo matching is keyword-based; image demo entries need `image_sha256` of the sanitised JPEG.
- The rate limiter is in-memory and per process.
- No database, auth, PDF export or frontend (out of MVP scope).
- Market preview: the HS code is the AI's guess, and the public Comtrade API is rate-limited (middle years often
  missing; up to ~10 s added to the request). Its `report.score` is the market component alone.
