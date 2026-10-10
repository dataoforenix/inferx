# صنّعها — الواجهة الأمامية

ارفع صورة منتج أو اكتب اسمه، وصنّعها بتقيس لك فرص تصنيعه محلياً في الأردن.
الواجهة مبنية بـ React 19 و Vite و Tailwind CSS 4، ومربوطة بالباك الموجود في `../backend` (FastAPI).

## التشغيل الكامل (الباك + الواجهة)

المتطلبات: Python 3.11 و Node.js 20.19 أو أحدث.

### 1. الباك (نافذة طرفية أولى)

من مجلد `backend/`:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
```

بعدها افتح `backend/.env` واختر واحداً:

- **وضع العرض (بدون مفتاح):** `DEMO_MODE=true`. يعمل مع الأمثلة المجهّزة فقط (أزرار الاقتراحات في الواجهة كلها منها).
- **التحليل الحي:** ضع مفتاح Gemini في `OPENAI_API_KEY` (من https://aistudio.google.com/apikey) واترك `DEMO_MODE=false`. كل تحليل يأخذ حوالي 3 ثوانٍ، والمفتاح المجاني له حد طلبات في الدقيقة.

ثم:

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

على macOS / Linux استبدل `.venv\Scripts\python.exe` بـ `.venv/bin/python` و`copy` بـ `cp`.

### 2. الواجهة (نافذة طرفية ثانية)

من مجلد `frontend/`:

```bash
npm install
npm run dev
```

افتح http://localhost:5173

الواجهة تتصل بالباك على `http://localhost:8000`. لعنوان آخر: انسخ `.env.example` إلى `.env` وغيّر `VITE_API_URL`،
وأضف عنوان الواجهة إلى `CORS_ORIGINS` في `backend/.env`.

إذا كان الباك متوقفاً، تعرض الواجهة رسالة واضحة: «الخادم غير متاح. شغّل الـ backend أولاً كما في README»، ولا تعرض أرقاماً تجريبية مكان التحليل.

## أوامر أخرى

```bash
npm run build     # بناء نسخة الإنتاج في dist/
npm run preview   # معاينة نسخة الإنتاج
npm run lint      # فحص الكود بـ oxlint
```

## ما تعرضه الواجهة من الباك

المرجع: `../backend/docs/api_contract.md`.

| حالة الرد (`status`) | ما يظهر |
|---|---|
| `complete` | الدرجة والحكم (صنّعها / ربما / لا تصنّعها)، العوامل الأربعة، سيناريو «ماذا لو؟»، الخطوة التالية (رأس المال، خطوات البداية، المكائن)، «ابدأ من هنا» (فحص الميزانية، جهات تساعدك، روابط موردين)، طريقة الحساب بالتفصيل، تقرير PDF |
| `needs_confirmation` | «أيّ هذه هو منتجك؟» ثم `POST /api/analyze/confirm` |
| `market_preview` | «مسح أولي للسوق»: واردات رسمية من UN Comtrade، رمز HS المقترح مع تنبيه، وما ينقص للحكم، وتقرير PDF من صفحة واحدة |
| `unsupported` | خارج النطاق، أو «بحثنا ولم نجد بيانات كافية» |

- كل المبالغ تُعرض بالدينار الأردني (`latest_import_jod` من الباك، وغيرها بسعر الربط 0.709 في `src/lib/api.js`).
- أسماء المكائن والمواد الخام والموردين تُعرض بالعربي من `src/lib/terms.js` (الـ CSV فيه الأسماء بالإنجليزي).
- أي رقم مبني على عمود في `estimated_fields` تظهر جنبه شارة «تقدير».
- «ماذا لو؟» يستدعي `POST /api/whatif` (بدون ذكاء اصطناعي، فوري).

## هيكل المجلدات

- `src/lib/api.js`: الاتصال بالباك وتحويل الردود لشكل الواجهة
- `src/lib/analyzeProduct.js`: تشغيل التحليل ورسائل الأخطاء بالعربي
- `src/lib/terms.js`: الأسماء العربية للمكائن والمواد الخام
- `src/components/AnalysisSection.jsx`: النتيجة بكل حالاتها
- `src/components/ActionPlan.jsx`، `GuidancePanels.jsx`، `WhatIf.jsx`، `ReportSheet.jsx`، `ReportButton.jsx`: الخطوة التالية، «ابدأ من هنا»، السيناريو، وتقرير PDF
- `src/components/hero/` و`src/components/three/`: الافتتاحية والمشهد ثلاثي الأبعاد
- `src/legacy/`: الواجهة الأولى للمشروع، محفوظة للرجوع إليها ولا تستخدمها الواجهة الحالية
