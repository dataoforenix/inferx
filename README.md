# inferx: Sanna'ha (صنّعها)

Sanna'ha helps Jordanian entrepreneurs decide whether an imported product could be manufactured locally.
Send a product photo and/or an Arabic or English description. An LLM identifies the product, Python
code scores feasibility from 0 to 10 (MANUFACTURE / MAYBE / DONT) from real UN Comtrade and WITS trade data,
and the LLM explains the result in English or Arabic. Every number in the explanation is checked against
the computed report.

This repository holds the **FastAPI backend** (`backend/`). Full documentation:
[`backend/README.md`](backend/README.md); API contract for the frontend:
[`backend/docs/api_contract.md`](backend/docs/api_contract.md).

## Quick start for judges

Requires **Python 3.11**. All commands run from `backend/`.

### 1. Install

With conda:
```bash
conda create -n inferx python=3.11 -y
conda activate inferx
cd backend
pip install -r requirements.txt
```

Or with a plain virtualenv:
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run without any API key (demo mode)

Demo mode serves prepared product recognitions. Scores are still computed live from the data.

```bash
# macOS/Linux
DEMO_MODE=true python -m uvicorn app.main:app --port 8000
# Windows PowerShell
$env:DEMO_MODE="true"; python -m uvicorn app.main:app --port 8000
```

Open http://localhost:8000/docs, or try:

```bash
curl -X POST http://localhost:8000/api/analyze -F "text=metal office chair" -F "language=en"
curl -X POST http://localhost:8000/api/analyze -F "text=canned tomato paste" -F "language=en"
curl -X POST http://localhost:8000/api/whatif -H "Content-Type: application/json" \
  -d '{"category_id": "tomato_paste", "overrides": {"local_cost_per_kg_est_usd": 1.0}}'
```

Demo mode only recognises the prepared examples (for example "metal office chair", "steel shelving unit for a
warehouse", "ceiling fan with three blades", "frozen french fries", "canned tomato paste", "plastic folding chair").
Any other input returns `404 demo_no_match`, and the error message lists the examples.

### 3. Run with the live AI (Google Gemini)

The backend calls Gemini through its OpenAI-compatible endpoint using the OpenAI Python SDK.

```bash
cp .env.example .env        # Windows: copy .env.example .env
# edit .env and set OPENAI_API_KEY=<your Gemini API key>
python -m uvicorn app.main:app --port 8000
```

`GET /api/health` reports `"status": "ok"` and `"llm_configured": true` when the key is set. Text and photo
uploads both work:

```bash
curl -X POST http://localhost:8000/api/analyze -F "text=plastic plates and cups" -F "language=ar"
curl -X POST http://localhost:8000/api/analyze -F "image=@photo.jpg" -F "language=en"
```

### 4. Run the tests

The offline tests need no key and no network; the LLM is mocked:

```bash
python -m pytest
```

The live tests call the real Gemini API. They cost a few cents and are skipped without a key:

```bash
python -m pytest -m llm -v
```

## Endpoints

| Method | Path | What it does |
|---|---|---|
| POST | `/api/analyze` | photo and/or text → `complete` / `needs_confirmation` / `unsupported` / `market_preview` |
| POST | `/api/analyze/confirm` | the user picks the category after `needs_confirmation` |
| POST | `/api/whatif` | recompute the score with changed customs, costs or factory count (no AI) |
| GET | `/api/categories` | the supported product categories |
| GET | `/api/health` | service status |
