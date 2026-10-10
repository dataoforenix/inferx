# صنّعها — Sanna'ha

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

## Running the project

You need two terminals open at the same time — one for the backend, one for the frontend.

### What you need

- **Python 3.11** — https://www.python.org/downloads/ (Windows: tick "Add Python to PATH")
- **Node.js 20+** — https://nodejs.org/
- **Gemini API key** — https://aistudio.google.com/apikey (free)

---

### Part 1 — Backend

Open a terminal in the `backend/` folder.

**Install dependencies:**

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**Set up your API key:**

```powershell
copy .env.example .env
notepad .env
```

In `.env`, set:
```
OPENAI_API_KEY=your-gemini-key-here
DEMO_MODE=false
```

**Start the backend:**

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

You should see `Application startup complete.` — leave this terminal open.

**Mac / Linux:**
```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env   # then open .env and set OPENAI_API_KEY and DEMO_MODE=false
.venv/bin/python -m uvicorn app.main:app --port 8000
```

---

### Part 2 — Frontend

Open a **second terminal** in the `frontend/` folder.

```bash
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.

---

### Running without an API key (demo mode)

Demo mode works without any API key — it returns pre-recorded answers for a fixed list of inputs.

In `backend/.env`, set `DEMO_MODE=true` and leave `OPENAI_API_KEY` empty, then start the backend as above.

Demo mode only recognises these inputs:

| Text | Language |
|---|---|
| metal office chair | en |
| كرسي مكتب معدني منجد | ar |
| steel shelving unit for a warehouse | en |
| رفوف مستودعات | ar |
| plastic plates and cups | en |
| صحون بلاستيك للمطبخ | ar |
| ceiling fan with three blades | en |
| مروحة سقف | ar |
| frozen french fries | en |
| بطاطا مجمدة فرنش فرايز | ar |
| canned tomato paste | en |
| معجون بندورة | ar |

Any other input returns an error with the full list of accepted inputs.

---

## Troubleshooting

**"Python was not found"** — close the terminal and reopen it. If it still fails, reinstall Python and tick "Add Python to PATH".

**"npm: command not found"** — close and reopen the terminal after installing Node.js.

**Frontend shows "server unavailable"** — make sure the backend is still running in its terminal.

**Port already in use** — change `--port 8000` to `--port 8001` in the backend command, then create `frontend/.env` from `frontend/.env.example` and set `VITE_API_URL=http://localhost:8001`.

---

## For developers

- Backend details, scoring formula, API contract, test suite: [backend/README.md](backend/README.md)
- Frontend details, component map, API mapping: [frontend/README.md](frontend/README.md)
