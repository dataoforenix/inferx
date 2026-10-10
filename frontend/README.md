# صنّعها — الواجهة الأمامية

ارفع صورة منتج أو اكتب اسمه، وصنّعها بتقيس لك فرص تصنيعه محلياً.

مبنية بـ React 19 و Vite و Tailwind CSS 4، والمشهد ثلاثي الأبعاد في الافتتاحية بـ Three.js و React Three Fiber.

## التشغيل

```bash
npm install
npm run dev       # بيئة التطوير
npm run build     # بناء نسخة الإنتاج في dist/
npm run preview   # معاينة نسخة الإنتاج
npm run lint      # فحص الكود بـ oxlint
```

## هيكل المجلدات

- `src/components/hero/`: الافتتاحية (القصة، النصوص، زر "صنّعها")
- `src/components/three/`: المشهد ثلاثي الأبعاد، بيتحمّل بشكل كسول (lazy) وإله بديل ثابت إذا WebGL مش مدعوم
- `src/components/`: إدخال المنتج، قسم التحليل، الهيدر والفوتر
- `src/lib/analyzeProduct.js`: التحليل، حالياً بيانات تجريبية لحد ما يجهز الـ API
- `src/lib/timeline.js`: توقيت الافتتاحية وأعلام التصحيح
- `src/legacy/`: الواجهة القديمة، بس `sampleData.js` لسا مستخدم
- `public/models/`, `public/media/`: موديل الـ 3D والصور
