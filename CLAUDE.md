# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

**Sanna'ha (صنّعها)** — FastAPI backend that helps Jordanian entrepreneurs assess whether an imported product could be manufactured locally. Users send a photo and/or Arabic/English description; the backend identifies the product with an LLM, scores feasibility in Python, then has the LLM explain the result.

**Core rule:** LLMs only classify and explain. They never produce the score, verdict, or any statistic — all numeric decisions live in Python (`app/scoring.py`).

## Setup

All commands run from `backend/`. Requires Python 3.11 and [uv](https://docs.astral.sh/uv/).

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv -r requirements.txt
copy .env.example .env   # set OPENAI_API_KEY, or set DEMO_MODE=true
```

## Running and testing

```powershell
# Start the dev server
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000

# Run all offline tests (no API key needed; LLM is mocked)
.venv\Scripts\python.exe -m pytest

# Run a single test file
.venv\Scripts\python.exe -m pytest tests/test_scoring.py -v

# Run real LLM integration tests (requires OPENAI_API_KEY)
.venv\Scripts\python.exe -m pytest -m llm -v

# Validate categories.csv (shows every error with a fix)
.venv\Scripts\python.exe scripts\check_data.py
```

Interactive API docs: http://localhost:8000/docs

## Architecture

```
POST /api/analyze
  image_utils     → validate, strip EXIF, resize; stays in memory, never written to disk
  llm.normalize   → LLM: product names + category_id from the CSV, or "unsupported"
  pipeline        → Python gate: unsupported / needs_confirmation (confidence < 0.7) / continue
                    (physical + no category: UN Comtrade market preview via comtrade.py)
  scoring         → Pure Python: weighted 0–10 score + MANUFACTURE / MAYBE / DONT verdict
  llm.explain     → LLM writes explanation; grounding guard verifies every number vs. the report
                    (one retry with feedback, then deterministic template on second failure)
```

**Module responsibilities:**

| Module | Responsibility |
|---|---|
| `app/factory.py` | `create_app(settings, llm=None)` — used by tests and scripts; side-effect free |
| `app/main.py` | ASGI entry point; loads `data/categories.csv` on import |
| `app/config.py` | `Settings` dataclass loaded from env / `.env`; `get_settings()` is LRU-cached |
| `app/data_store.py` | CSV schema, `load_categories` (fails fast on errors), `inspect_categories` |
| `app/scoring.py` | Pure scoring; see constants `WEIGHTS`, `COST_GATE_*`, `HIGH_CAPEX_USD` |
| `app/pipeline.py` | Request orchestration, grounding retry, `timings_ms` |
| `app/llm.py` | OpenAI client wrapper (structured JSON output, retries, per-call logging) |
| `app/explanation.py` | Key figures for the LLM, grounding guard, template fallback (EN/AR) |
| `app/comtrade.py` | UN Comtrade public preview API (paced 2.5 s/req, 24 h cache, never raises) |
| `app/routers/` | `analyze`, `whatif`, `meta` endpoints |

## Key design invariants

- **Scoring is pure Python.** `app/scoring.py` has no I/O or LLM calls. Tests in `tests/test_real_data.py` pin the verdict and score for every category in `data/categories.csv` — a data change that flips a verdict will be caught.
- **Offline tests never touch `data/`.** They use frozen fixtures in `tests/fixtures/`. `pytest` (no flags) runs entirely offline.
- **`app/factory.py` is the test/script entry point**, not `app/main.py`. `create_app(settings, llm=...)` accepts an injected LLM for testing.
- **Grounding guard:** every number in the LLM explanation must match the Python report or CSV free-text notes. One retry with offending numbers listed, then template fallback (`explanation_source: "fallback"`).
- **Prompt injection defence:** user text is wrapped in data blocks; the model can only answer with a fixed JSON shape; category is constrained to CSV values.

## Data

`data/categories.csv` drives everything: categories, names, scoring inputs. The app refuses to start on an invalid file.

After replacing the CSV:
1. Run `check_data.py` (exit 0 = loadable)
2. Update `data/demo_inputs.json` (`expected_category_id` must match new `category_id`s)
3. Delete `data/demo_cache/*.json`, then rebuild: `scripts\record_demo_cache.py`
4. Run tests; update pinned verdicts in `tests/test_real_data.py` deliberately

## API endpoints

| Method | Path | Notes |
|---|---|---|
| POST | `/api/analyze` | multipart `image?`, `text?`, `language`; returns `complete` / `needs_confirmation` / `unsupported` / `market_preview` |
| POST | `/api/analyze/confirm` | JSON `{category_id, language, product?}` after `needs_confirmation` |
| POST | `/api/whatif` | JSON `{category_id, overrides}`; no LLM |
| GET | `/api/categories` | CSV categories list |
| GET | `/api/health` | server status |

All errors: `{"error": {"code", "message", "request_id", "details?"}}`. All responses carry `X-Request-ID`.

Full API contract for frontend integration: [`backend/docs/api_contract.md`](backend/docs/api_contract.md).

## Demo mode

`DEMO_MODE=true` serves `data/demo_cache/*.json` without LLM calls. Scores are always recomputed live from the CSV — only LLM outputs are cached. Cached explanations still pass the grounding guard.

## Regenerating frontend docs

Run these offline (no API key needed) after any API change:

```powershell
.venv\Scripts\python.exe scripts\export_openapi.py   # docs/openapi.json
.venv\Scripts\python.exe scripts\build_examples.py   # docs/examples/*.json
```

`tests/test_examples.py` fails if `docs/openapi.json` is stale.
