# inferx: Sanna'ha (صنّعها)

Sanna'ha helps Jordanian entrepreneurs decide whether an imported product could be manufactured locally.
Send a product photo and/or an Arabic or English description. An LLM identifies the product, Python
code scores feasibility from 0 to 10 (MANUFACTURE / MAYBE / DONT) from real UN Comtrade and WITS trade data,
and the LLM explains the result in English or Arabic. Every number in the explanation is checked against
the computed report.

This repository holds the **FastAPI backend** (`backend/`). Full documentation:
[`backend/README.md`](backend/README.md); API contract for the frontend:
[`backend/docs/api_contract.md`](backend/docs/api_contract.md).

> **Demo mode vs real AI.** In demo mode (`DEMO_MODE=true`, no key) uploaded photos are **not** really analysed:
> the app only recognises a fixed list of prepared inputs and returns prepared answers. To analyse your own text or photos,
> run with the real AI (section 3).
>
> **وضع العرض مقابل الذكاء الاصطناعي الحقيقي:** في وضع العرض (`DEMO_MODE=true` بدون مفتاح) **لا يتم تحليل الصور المرفوعة فعلياً**؛
> التطبيق يتعرّف فقط على قائمة ثابتة من المدخلات المجهّزة ويعيد إجابات مجهّزة. لتحليل نصك أو صورك شغّله مع الذكاء الاصطناعي الحقيقي (القسم 3).

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

### 3. Run with the real AI (Google Gemini) / التشغيل مع الذكاء الاصطناعي الحقيقي

1. Get a free Gemini API key at https://aistudio.google.com/apikey.
   **If the organisers gave you a judges' key, paste that one instead.**
2. Copy `backend/.env.example` to `backend/.env` and paste the key as `OPENAI_API_KEY`. The name is kept for the
   OpenAI SDK; the backend talks to Gemini's OpenAI-compatible endpoint. Make sure `DEMO_MODE=false`.
3. Restart the backend.

Windows PowerShell, from the repository root:

```powershell
cd backend
Copy-Item .env.example .env
notepad .env        # set:  OPENAI_API_KEY=<your Gemini key>   and   DEMO_MODE=false   then save
# stop the running backend with Ctrl+C in its window, then start it again:
python -m uvicorn app.main:app --port 8000
```

Check it: `Invoke-RestMethod http://localhost:8000/api/health` must show `llm_configured : True` and
`demo_mode : False`. Never commit `backend/.env` (it is gitignored).

**Limits:**
- The free Gemini tier allows 15 AI requests per minute per model. Each analysis uses 2 of them, so expect
  **about 7 analyses per minute**; above that the app answers "AI unavailable" for a moment.
- **Repeated searches come from the cache:** the same text (or the same photo) in the same language within 24 hours is
  answered instantly from a local SQLite cache, without using the AI quota (`"cache": "hit"`).

بالعربية:
1. احصل على مفتاح Gemini مجاني من https://aistudio.google.com/apikey.
   **إذا أعطاكم المنظمون مفتاحاً خاصاً بالحكّام، استخدموه بدلاً منه.**
2. انسخ `backend/.env.example` إلى `backend/.env`، والصق المفتاح في `OPENAI_API_KEY`، وتأكد أن `DEMO_MODE=false`.
3. أعد تشغيل الباك بأوامر PowerShell أعلاه.

الحد المجاني حوالي **7 تحليلات في الدقيقة** (15 طلب ذكاء اصطناعي في الدقيقة، وكل تحليل يستخدم طلبين). البحث المكرر
(نفس النص أو نفس الصورة ونفس اللغة خلال 24 ساعة) يأتي من الذاكرة المؤقتة فوراً ولا يستهلك من الحد.

### Frontend / الواجهة

In a second terminal, from `frontend/` (Node.js 20.19 or newer):

```powershell
npm ci
npm run dev        # http://localhost:5173  (talks to the backend on http://localhost:8000)
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
