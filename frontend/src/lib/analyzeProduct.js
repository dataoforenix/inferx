import { BackendDown, mapMarketPreview, mapReport, mapUnsupported, postAnalyze, postConfirm } from './api';

// ─── Backend seam ────────────────────────────────────────────────
// The UI depends on `analyzeProduct(input)` and `confirmProduct(...)`, which
// resolve to an outcome: { kind: 'result' | 'confirm' | 'unsupported' | 'error' }.
// Results come from the inferx backend (lib/api.js). If it can't be reached, the UI shows a clear
// error: it never shows sample figures in place of a real analysis.
// ────────────────────────────────────────────────────────────────

export const ANALYSIS_MS = 4800;

export const ANALYSIS_STEPS = [
  { id: 'market', label: 'حجم السوق والواردات', source: 'UN Comtrade' },
  { id: 'cost', label: 'الكلفة والجمارك', source: 'التعرفة الجمركية' },
  { id: 'readiness', label: 'جاهزية المصانع والمواد الخام', source: 'تقديرات السوق المحلي' },
  { id: 'risk', label: 'المراجع الناقد يبحث عن المخاطر', source: 'وكيل ذكاء اصطناعي' },
];

const BACKEND_DOWN = 'الخادم غير متاح. شغّل الـ backend أولاً كما في README';

const ERRORS = {
  demo_no_match: 'وضع العرض يعرف الأمثلة المجهّزة فقط. جرّب واحداً منها:',
  image_too_large: 'حجم الصورة أكبر من 8MB.',
  payload_too_large: 'حجم الصورة أكبر من 8MB.',
  unsupported_image_type: 'استخدم صورة JPEG أو PNG أو WebP.',
  invalid_image: 'تعذّرت قراءة الصورة، جرّب صورة أخرى.',
  text_too_long: 'الوصف أطول من 1000 حرف.',
  rate_limited: 'طلبات كثيرة خلال وقت قصير، انتظر قليلاً ثم حاول.',
  input_refused: 'لا نستطيع تحليل هذا المدخل.',
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const isArabic = (t) => /[؀-ۿ]/.test(t);

async function toOutcome(request, inputName) {
  try {
    const body = await request();
    if (body.status === 'complete') return mapReport(body, inputName);
    if (body.status === 'needs_confirmation') {
      return {
        kind: 'confirm',
        productName: body.product?.name_ar || inputName,
        product: body.product,
        candidates: body.candidates.map((c) => ({ id: c.category_id, name: c.name_ar })),
      };
    }
    if (body.status === 'market_preview') return mapMarketPreview(body, inputName);
    return mapUnsupported(body, inputName);
  } catch (err) {
    if (err instanceof BackendDown) return { kind: 'error', message: BACKEND_DOWN, examples: [] };
    return {
      kind: 'error',
      message: ERRORS[err.code] ?? 'حدث خطأ أثناء التحليل، حاول مرة أخرى.',
      examples: (err.examples ?? []).filter(isArabic),
    };
  }
}

/** Runs the analysis; never resolves before the staged UI has had time to play. */
export async function analyzeProduct(input) {
  const [outcome] = await Promise.all([toOutcome(() => postAnalyze(input), input.name), sleep(ANALYSIS_MS)]);
  return outcome;
}

/** Re-runs the analysis for the category the user picked from the candidates. */
export async function confirmProduct(categoryId, product, inputName) {
  const [outcome] = await Promise.all([toOutcome(() => postConfirm(categoryId, product), inputName), sleep(ANALYSIS_MS)]);
  return outcome;
}
