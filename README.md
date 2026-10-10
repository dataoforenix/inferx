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

Demo mode replays product recognitions and AI explanations recorded from the live pipeline. Scores are still
computed live from the data.

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

Demo mode only recognises these prepared inputs (from `backend/data/demo_inputs.json`):

| Text | Text language | Demo result |
|---|---|---|
| metal office chair | en | complete (metal_chair) |
| كرسي مكتب معدني منجد | ar | complete (metal_chair) |
| steel shelving unit for a warehouse | en | complete (warehouse_racks) |
| رفوف مستودعات | ar | complete (warehouse_racks) |
| plastic plates and cups | en | complete (plastic_tableware) |
| صحون بلاستيك للمطبخ | ar | complete (plastic_tableware) |
| ceiling fan with three blades | en | complete (ceiling_fan) |
| مروحة سقف | ar | complete (ceiling_fan) |
| frozen french fries | en | complete (frozen_fries) |
| بطاطا مجمدة فرنش فرايز | ar | complete (frozen_fries) |
| canned tomato paste | en | complete (tomato_paste) |
| معجون بندورة | ar | complete (tomato_paste) |
| plastic chair with metal legs | en | needs_confirmation (metal_chair, confidence 0.6) |
| accounting software for small shops | en | unsupported (not a physical product) |
| rooftop solar panel | en | unsupported (physical, outside the categories) |

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
