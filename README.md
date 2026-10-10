# صنّعها — Sanna'ha

> **Demo mode vs real AI.** In demo mode (`DEMO_MODE=true`, no key) uploaded photos are **not** really analysed:
> the app only recognises a fixed list of prepared inputs and returns prepared answers. To analyse your own text or photos,
> run with the real AI (section 3 below).
>
> **وضع العرض مقابل الذكاء الاصطناعي الحقيقي:** في وضع العرض (`DEMO_MODE=true` بدون مفتاح) **لا يتم تحليل الصور المرفوعة فعلياً**؛
> التطبيق يتعرّف فقط على قائمة ثابتة من المدخلات المجهّزة ويعيد إجابات مجهّزة. لتحليل نصك أو صورك شغّله مع الذكاء الاصطناعي الحقيقي (القسم 3).

---

**Should Jordan make it, or keep importing it?**

Sanna'ha is a tool for Jordanian entrepreneurs and investors who want a quick, data-backed answer to one question: *could this product be manufactured locally instead of imported?*

You upload a photo or type a product name (in Arabic or English), and the system:

1. Identifies what the product is using AI
2. Looks up real trade data for Jordan (import volumes, prices, customs)
3. Runs a scoring model across four dimensions — market size, cost advantage, manufacturing feasibility, and competition
4. Gives you a verdict: **Manufacture**, **Maybe**, or **Don't** — with a plain-language explanation of why

The AI identifies and explains. All numbers and verdicts come from a verified Python model, not the AI.

---

## What it can analyse today

| Product | Verdict |
|---|---|
| Metal / office chairs | Manufacture ✅ |
| Warehouse storage racks | Manufacture ✅ |
| Plastic tableware (plates, cups) | Manufacture ✅ |
| Frozen french fries | Manufacture ✅ |
| Ceiling fans | Maybe ⚠️ |
| Tomato paste | Don't ❌ |

For products outside these categories, it pulls live import data from UN Comtrade to give you a preliminary market scan.

---

## Quick start

Requires **Python 3.11**. All commands run from `backend/`.

### 1. Install

With conda:

```bash
conda create -n sannaha python=3.11 -y
conda activate sannaha
pip install -r requirements.txt
```

Without conda:

```bash
python -m venv .venv
# Windows:
.venv\Scripts\python.exe -m pip install -r requirements.txt
# Mac / Linux:
.venv/bin/python -m pip install -r requirements.txt
```

### 2. Run in demo mode (no API key needed)

```bash
cp .env.example .env      # Mac / Linux
copy .env.example .env    # Windows
```

Make sure `DEMO_MODE=true` in `backend/.env`, then:

```bash
# Windows:
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
# Mac / Linux:
.venv/bin/python -m uvicorn app.main:app --port 8000
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
2. Copy `backend/.env.example` to `backend/.env` and paste the key as `OPENAI_API_KEY`. Make sure `DEMO_MODE=false`.
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

### 4. Frontend / الواجهة

In a second terminal, from `frontend/` (Node.js 20.19 or newer):

```bash
npm ci
npm run dev        # http://localhost:5173  (talks to the backend on http://localhost:8000)
```

---

## Troubleshooting

**"Python was not found"** — close the terminal, reopen it. If it still fails, reinstall Python and tick "Add Python to PATH".

**"npm: command not found"** — close and reopen the terminal after installing Node.js.

**The backend starts but the frontend shows "server unavailable"** — make sure the backend is still running in its terminal.

**Port already in use** — change `--port 8000` to `--port 8001` in the backend command, then open `frontend/.env` (copy from `frontend/.env.example` if it doesn't exist) and set `VITE_API_URL=http://localhost:8001`.

---

## For developers

- Backend details, scoring formula, API contract, test suite: [backend/README.md](backend/README.md)
- Frontend details, component map, API mapping: [frontend/README.md](frontend/README.md)
