import { SAMPLE_PRODUCTS } from '../legacy/sampleData';
import { BackendDown, factoriesNote, mapMarketPreview, mapReport, mapUnsupported, postAnalyze, postConfirm, riskHeadline, USD_TO_JOD, usdTextToJod } from './api';

// ─── Backend seam ────────────────────────────────────────────────
// The UI depends on `analyzeProduct(input)` and `confirmProduct(...)`, which
// resolve to an outcome: { kind: 'result' | 'confirm' | 'unsupported' | 'error' }.
// Results come from the inferx backend (lib/api.js); if it can't be reached,
// the sample data below stands in so the demo never breaks.
// ────────────────────────────────────────────────────────────────

export const ANALYSIS_MS = 4800;

export const ANALYSIS_STEPS = [
  { id: 'market', label: 'حجم السوق والواردات', source: 'UN Comtrade' },
  { id: 'cost', label: 'الكلفة والجمارك', source: 'التعرفة الجمركية' },
  { id: 'readiness', label: 'جاهزية المصانع والمواد الخام', source: 'تقديرات السوق المحلي' },
  { id: 'risk', label: 'المراجع الناقد يبحث عن المخاطر', source: 'وكيل ذكاء اصطناعي' },
];

const KEYWORDS = [
  ['solar-panels', ['شمس', 'solar', 'كهروضوئي']],
  ['plastic-cutlery', ['بلاستيك', 'ملاعق', 'أواني', 'cutlery']],
  ['electrical-enclosures', ['لوح', 'كهرب', 'توزيع', 'enclosure']],
  ['screws-bolts', ['براغي', 'برغ', 'مسامير', 'صواميل', 'bolt', 'screw']],
  ['storage-racks', ['رف', 'مستودع', 'rack', 'shelf']],
  ['chair', ['كرس', 'chair']],
];

function pickSample(name = '') {
  const text = name.toLowerCase();
  const hit = KEYWORDS.find(([, words]) => words.some((w) => text.includes(w)));
  if (hit) return SAMPLE_PRODUCTS.find((p) => p.id === hit[0]);
  // Unknown product: deterministic pick so the same input shows the same demo result.
  let h = 0;
  for (const ch of text) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return SAMPLE_PRODUCTS[h % SAMPLE_PRODUCTS.length];
}

function capitalRange([min, max]) {
  const k = (usd) => Math.round((usd * USD_TO_JOD) / 1000);
  return { minK: k(min), maxK: k(max) };
}

/** Maps a sample record (offline fallback) to the shape the UI renders. */
function normalizeSample(p, inputName) {
  return {
    kind: 'result',
    source: 'sample',
    productName: p.productName,
    inputName,
    hsCode: p.hsCode,
    score: p.score,
    verdict: p.decision === 'صنّعها' ? 'go' : 'no',
    recommend: p.decision === 'صنّعها',
    summary: p.calculationBreakdown?.explanation ?? '',
    formula: p.calculationBreakdown?.formula ?? '',
    factors: [
      {
        id: 'market',
        title: 'السوق',
        headline: p.market.imports5Years,
        caption: 'واردات آخر 5 سنوات',
        body: p.market.sizeDescription,
        meta: p.market.trend,
        source: 'دائرة الإحصاءات العامة',
      },
      {
        id: 'cost',
        title: 'الكلفة',
        headline: p.cost.customsDuty,
        caption: usdTextToJod(`شحن المستورد: ${p.cost.shippingEstimate}`),
        body: p.cost.savingsNote,
        source: 'جدول التعرفة الجمركية',
      },
      {
        id: 'readiness',
        title: 'جاهزية التصنيع',
        headline: p.manufacturing.workshopsStatus,
        caption: 'الورش والمعدات',
        body: `المعدات: ${p.manufacturing.machines}`,
        meta: `المواد الخام: ${p.manufacturing.rawMaterials}`,
        source: 'غرفة صناعة الأردن',
      },
      {
        id: 'risk',
        title: 'المراجع الناقد',
        headline: riskHeadline(p.skeptic.reasons.length),
        caption: p.skeptic.warningTitle,
        list: p.skeptic.reasons,
        source: 'مراجعة نقدية للبيانات',
      },
    ],
    plan: {
      capital: p.plan ? capitalRange(p.plan.machineCostUsd) : null,
      machines: p.manufacturing.machines.split('،').map((m) => m.trim()).filter(Boolean),
      rawMaterials: p.manufacturing.rawMaterials,
      workshops: p.manufacturing.workshopsStatus,
      steps: [],
      factories: factoriesNote(p.plan?.localFactories),
    },
  };
}

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
    if (err instanceof BackendDown) return normalizeSample(pickSample(inputName), inputName);
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
