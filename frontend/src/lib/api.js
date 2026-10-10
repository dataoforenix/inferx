// Client for the inferx backend (docs/api_contract.md in that repo).
// Maps its report to the shape the UI renders. All money is shown in JOD.

export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

// The JOD is pegged to the USD at 0.709.
export const USD_TO_JOD = 0.709;

export class BackendDown extends Error {}

export class ApiError extends Error {
  constructor(code, message, examples = []) {
    super(message);
    this.code = code;
    this.examples = examples;
  }
}

/* ───────────── Formatting ───────────── */

const pct = (f, digits = 0) => `${(f * 100).toFixed(digits)}%`;

/** Formats a JOD amount: millions, thousands, or dinars with two decimals. */
export function formatJod(jod) {
  if (jod >= 1e6) return `${(jod / 1e6).toFixed(1)} مليون دينار`;
  if (jod >= 1e3) return `${Math.round(jod / 1e3)} ألف دينار`;
  return `${jod.toFixed(2)} دينار`;
}

function usdAmountToJod(num, million) {
  const jod = Number(num.replace(/,/g, '')) * USD_TO_JOD;
  if (million) return `${jod.toFixed(1)} مليون دينار أردني`;
  if (jod >= 1000) return `${(Math.round(jod / 100) * 100).toLocaleString('en-US')} دينار أردني`;
  return `${jod.toFixed(2)} دينار أردني`;
}

const NUM = String.raw`(\d[\d,]*(?:\.\d+)?)`;
const MILLION = String.raw`(\s*مليون)?`;
// "20,000 دولار", "2.2 مليون دولار أمريكي", "4.01 USD"
const USD_AFTER = new RegExp(
  String.raw`${NUM}${MILLION}\s*(?:دولار(?:اً|ات)?(?:\s+(?:ال)?أمي?ري?كي(?:اً|ة)?)?|USD)`,
  'g',
);
// "$20,000", "$2.2 مليون"
const USD_BEFORE = new RegExp(String.raw`(?:US)?\$\s?${NUM}${MILLION}`, 'g');

/**
 * The explanation text quotes USD ("20,000 دولار", "$4.01", "2.2 مليون دولار أمريكي"); show them as «… دينار أردني».
 * Thousands are rounded to the nearest 100 JOD, small (per-kg) amounts keep two decimals.
 */
export function usdTextToJod(text) {
  return text
    .replace(USD_AFTER, (_, num, million) => usdAmountToJod(num, million))
    .replace(USD_BEFORE, (_, num, million) => usdAmountToJod(num, million));
}

const hsLabel = (hs6) => (hs6 && hs6.length === 6 ? `${hs6.slice(0, 4)}.${hs6.slice(4)}` : hs6);

export function factoriesNote(n) {
  if (n == null) return null;
  if (n === 0) return 'لا توجد مصانع محلية قائمة في هذا المجال.';
  if (n === 1) return 'مصنع محلي واحد قائم في هذا المجال.';
  if (n === 2) return 'مصنعان محليان قائمان في هذا المجال.';
  if (n <= 10) return `${n} مصانع محلية قائمة في هذا المجال.`;
  return `${n} مصنعاً محلياً قائماً في هذا المجال.`;
}

export function riskHeadline(n) {
  if (n === 0) return 'لا ملاحظات جوهرية';
  if (n === 1) return 'نقطة واحدة تستحق الانتباه';
  if (n === 2) return 'نقطتان تستحقان الانتباه';
  return `${n} نقاط تستحق الانتباه`;
}

const VERDICTS = { MANUFACTURE: 'go', MAYBE: 'maybe', DONT: 'no' };
const TRENDS = { growing: 'في نمو', stable: 'مستقر', declining: 'في تراجع' };

function readinessLabel(score) {
  if (score == null) return 'لا تتوفر بيانات كافية';
  if (score >= 7) return 'جاهزية محلية جيدة';
  if (score >= 4.5) return 'جاهزية محلية متوسطة';
  return 'جاهزية محلية ضعيفة';
}

const scoreText = (s) => (s == null ? 'لا بيانات' : s.toFixed(1));

/* ───────────── Report → UI ───────────── */

function capitalFromReport(r) {
  const jod = r.machine_cost_range_jod;
  const usd = r.capex_usd_range;
  const min = jod?.min ?? (usd?.min != null ? usd.min * USD_TO_JOD : null);
  const max = jod?.max ?? (usd?.max != null ? usd.max * USD_TO_JOD : null);
  if (min == null || max == null) return null;
  return { minK: Math.round(min / 1000), maxK: Math.round(max / 1000) };
}

function breakEvenNote(be) {
  if (!be) return null;
  const tons = Math.round(be.break_even_tons);
  return `نقطة التعادل: بيع حوالي ${tons} طن (${pct(be.share_of_2024_imports, 1)} من واردات 2024) بسعر المستورد يسترد ثمن المعدات (تقديري: المعدات فقط، بدون المباني ورأس المال العامل).`;
}

// Which shown numbers are estimates, per the contract's "Data-quality badges" table.
// Every input of the import/local cost comparison makes the margin (and the break-even) an estimate.
const COST_INPUTS = [
  'local_cost_per_kg_est_usd',
  'import_price_per_kg_usd',
  'customs_pct',
  'shipping_pct',
  'raw_material_price_usd_per_kg',
  'material_kg_per_kg_product',
  'conversion_cost_per_kg_usd',
];
const RATINGS = ['machinery_availability', 'raw_material_local', 'skills_availability'];
const CAPEX = ['machine_cost_usd_min', 'machine_cost_usd_max', 'machine_cost_jod_min', 'machine_cost_jod_max'];

function estimates(fields = []) {
  const has = (...cols) => cols.some((c) => fields.includes(c));
  const cost = has(...COST_INPUTS);
  const capital = has(...CAPEX);
  return {
    market: { headline: has('imports_2024_usd'), body: has('imports_2020_usd', 'imports_2024_usd') },
    cost: { headline: cost, caption: has('customs_pct'), body: cost },
    readiness: { headline: has(...RATINGS), caption: has(...RATINGS), meta: has('local_factories') },
    risk: {},
    plan: { capital, breakEven: capital || cost, factories: has('local_factories') },
  };
}

export function mapReport(body, inputName) {
  const r = body.report;
  const ex = body.explanation ?? {};
  const { market, cost, feasibility, competition, weights } = r;
  const est = estimates(r.estimated_fields);

  const latestJod = market.latest_import_usd != null ? market.latest_import_usd * USD_TO_JOD : null;
  const trend = TRENDS[r.trend_label];
  const marketBody = [
    trend && `الاتجاه: ${trend}`,
    market.cagr != null && `بمعدل ${pct(market.cagr, 1)} سنوياً بين 2020 و2024`,
  ]
    .filter(Boolean)
    .join('، ');

  const margin = cost.margin;
  const costHeadline =
    margin == null
      ? 'لا تتوفر بيانات كافية'
      : margin >= 0
        ? `المحلي أرخص بـ ${pct(margin)}`
        : `المحلي أغلى بـ ${pct(-margin)}`;
  const costBody =
    cost.landed_cost_per_kg_usd != null && cost.local_cost_per_kg_est_usd != null
      ? `كلفة المستورد مع الجمرك ${formatJod(cost.landed_cost_per_kg_usd * USD_TO_JOD)}/كغ، مقابل كلفة محلية تقديرية ${formatJod(cost.local_cost_per_kg_est_usd * USD_TO_JOD)}/كغ.`
      : null;

  const ratingRows = [
    ['الآلات', feasibility.machinery_availability],
    ['المواد الخام', feasibility.raw_material_local],
    ['المهارات', feasibility.skills_availability],
  ].filter(([, v]) => v != null);
  const ratings = ratingRows.map(([k, v]) => `${k} ${v}/5`).join(' · ');

  // Chart data for the factor tiles (the PDF keeps the text form).
  const series = Object.entries(r.imports_usd ?? {})
    .map(([year, usd]) => ({ year, jod: usd != null ? usd * USD_TO_JOD : null }))
    .sort((a, b) => a.year.localeCompare(b.year));
  const perKg = (usd) => (usd != null ? usd * USD_TO_JOD : null);

  const concerns = (ex.concerns ?? (r.risk_notes ? [r.risk_notes] : [])).map(usdTextToJod);

  const formula = [
    `السوق ${scoreText(market.score)} × ${pct(weights.market)}`,
    `الكلفة ${scoreText(cost.score)} × ${pct(weights.cost)}`,
    `الجاهزية ${scoreText(feasibility.score)} × ${pct(weights.feasibility)}`,
    `المنافسة ${scoreText(competition.score)} × ${pct(weights.competition)}`,
  ].join(' + ');
  const capped =
    r.verdict_capped_by === 'cost_gate' ? ' الحكم محدود لأن الإنتاج المحلي أغلى من الاستيراد.' : '';

  return {
    kind: 'result',
    source: body.source,
    productName: body.product?.name_ar || r.name_ar,
    inputName,
    hsCode: hsLabel(r.hs6),
    score: r.score ?? 0,
    verdict: VERDICTS[r.verdict] ?? 'maybe',
    recommend: r.verdict === 'MANUFACTURE',
    summary: usdTextToJod(ex.summary ?? ''),
    formula: `${formula} = ${scoreText(r.score)} من 10.${capped}`,
    highCapital: r.flags.includes('high_capital_requirement'),
    // Baseline values for the what-if sliders (POST /api/whatif); only when both are known.
    whatIf:
      cost.customs_pct != null && cost.local_cost_per_kg_est_usd != null
        ? {
            categoryId: r.category_id,
            customsPct: cost.customs_pct,
            localCostJod: Math.round(cost.local_cost_per_kg_est_usd * USD_TO_JOD * 100) / 100,
            importPriceJod:
              cost.import_price_per_kg_usd != null ? Math.round(cost.import_price_per_kg_usd * USD_TO_JOD * 100) / 100 : null,
          }
        : null,
    factors: [
      {
        id: 'market',
        est: est.market,
        title: 'السوق',
        chart: series.some((d) => d.jod != null) ? { kind: 'series', data: series } : null,
        headline: latestJod != null ? formatJod(latestJod) : 'لا تتوفر بيانات كافية',
        caption: 'واردات الأردن في 2024',
        body: marketBody || null,
        source: 'UN Comtrade',
      },
      {
        id: 'cost',
        est: est.cost,
        title: 'الكلفة',
        chart:
          cost.landed_cost_per_kg_usd != null && cost.local_cost_per_kg_est_usd != null
            ? { kind: 'compare', imported: perKg(cost.landed_cost_per_kg_usd), local: perKg(cost.local_cost_per_kg_est_usd) }
            : null,
        headline: costHeadline,
        caption: cost.customs_pct != null ? `الجمرك على المستورد: ${pct(cost.customs_pct)}` : '',
        body: costBody,
        source: 'WITS والتعرفة الجمركية',
      },
      {
        id: 'readiness',
        est: est.readiness,
        title: 'جاهزية التصنيع',
        chart: ratingRows.length ? { kind: 'ratings', data: ratingRows.map(([label, value]) => ({ label, value })) } : null,
        headline: readinessLabel(feasibility.score),
        caption: ratings,
        body: r.competition_note ? usdTextToJod(r.competition_note) : null,
        meta: factoriesNote(competition.local_factories),
        source: 'تقديرات أولية للسوق المحلي',
      },
      {
        id: 'risk',
        est: est.risk,
        title: 'المراجع الناقد',
        headline: riskHeadline(concerns.length),
        caption: 'نقاط يجب الحذر منها',
        list: concerns,
        source: 'مراجعة نقدية للبيانات',
      },
    ],
    hasEstimates: (r.estimated_fields ?? []).length > 0,
    plan: {
      est: est.plan,
      capital: capitalFromReport(r),
      capitalNote: 'المعدات فقط بأسعار الموردين، بدون الشحن والجمارك والتركيب والمباني.',
      breakEven: breakEvenNote(r.break_even),
      factories: factoriesNote(competition.local_factories),
      machines: r.machinery ?? [],
      rawMaterials: (r.raw_materials ?? []).join('، '),
      steps: (ex.next_steps ?? []).map(usdTextToJod),
    },
  };
}

/**
 * market_preview: the product is outside the categories, so the backend looked up Jordan's real imports for an
 * AI-guessed HS code on UN Comtrade. Only the market is known; the score is not a feasibility score (contract).
 */
export function mapMarketPreview(body, inputName) {
  const r = body.report;
  const ex = body.explanation ?? {};
  const latest = r.market?.latest_import_usd;
  const trend = TRENDS[r.trend_label];
  return {
    kind: 'preview',
    productName: body.product?.name_ar || inputName,
    inputName,
    hsCode: hsLabel(r.hs6 ?? body.product?.hs6_guess),
    importsLatest: latest != null ? formatJod(latest * USD_TO_JOD) : null,
    series: Object.entries(r.imports_usd ?? {})
      .map(([year, usd]) => ({ year, jod: usd != null ? usd * USD_TO_JOD : null }))
      .sort((a, b) => a.year.localeCompare(b.year)),
    trend: [trend && `الاتجاه: ${trend}`, r.market?.cagr != null && `بمعدل ${pct(r.market.cagr, 1)} سنوياً بين 2020 و2024`]
      .filter(Boolean)
      .join('، '),
    summary: usdTextToJod(ex.summary ?? ''),
    missing: (ex.concerns ?? []).map(usdTextToJod),
    steps: (ex.next_steps ?? []).map(usdTextToJod),
  };
}

const PREVIEW_UNAVAILABLE = 'could not be loaded';

/** unsupported: say whether we searched for import data and found too little, or couldn't search at all. */
export function mapUnsupported(body, inputName) {
  const hs6 = body.product?.hs6_guess;
  return {
    kind: 'unsupported',
    productName: body.product?.name_ar || inputName,
    searchedHs: hs6 && (body.warnings ?? []).some((w) => w.includes(PREVIEW_UNAVAILABLE)) ? hsLabel(hs6) : null,
  };
}

/* ───────────── Requests ───────────── */

async function call(path, init) {
  let res;
  try {
    res = await fetch(`${API_URL}${path}`, init);
  } catch (err) {
    if (err.name === 'AbortError') throw err;
    throw new BackendDown('backend unreachable');
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = body.error ?? {};
    // demo_no_match lists the prepared examples after "Try one of:".
    const examples =
      err.code === 'demo_no_match' ? (err.message?.split('Try one of:')[1] ?? '').split(';').map((s) => s.trim()).filter(Boolean) : [];
    throw new ApiError(err.code ?? `http_${res.status}`, err.message ?? '', examples);
  }
  return body;
}

export function postAnalyze({ text, file }) {
  const form = new FormData();
  if (file) form.append('image', file);
  if (text) form.append('text', text);
  form.append('language', 'ar');
  return call('/api/analyze', { method: 'POST', body: form });
}

export function postConfirm(categoryId, product) {
  return call('/api/analyze/confirm', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      category_id: categoryId,
      language: 'ar',
      product: product && { name_en: product.name_en, name_ar: product.name_ar, description: product.description },
    }),
  });
}

/** What-if scenario: pure Python on the backend, instant, no AI call. */
export async function postWhatIf(categoryId, overrides, signal) {
  const body = await call('/api/whatif', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ category_id: categoryId, overrides }),
    signal,
  });
  return { score: body.scenario.score ?? 0, verdict: VERDICTS[body.scenario.verdict] ?? 'maybe' };
}
