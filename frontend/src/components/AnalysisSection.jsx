import { useEffect, useRef, useState } from 'react';
import { Check, CircleHelp, Coins, Factory, ListChecks, Package, RotateCcw, ShieldAlert, TrendingUp } from 'lucide-react';
import { ANALYSIS_MS, ANALYSIS_STEPS } from '../lib/analyzeProduct';
import ActionPlan from './ActionPlan';
import EstimateTag from './EstimateTag';
import ReportButton from './ReportButton';
import { PreviewSheet } from './ReportSheet';
import WhatIf from './WhatIf';

const STEP_MS = ANALYSIS_MS / ANALYSIS_STEPS.length;
const ICONS = { market: TrendingUp, cost: Coins, readiness: Factory, risk: ShieldAlert };
const STATION_TITLES = { market: 'السوق', cost: 'الكلفة', readiness: 'الجاهزية', risk: 'المراجع الناقد' };

const VERDICT_UI = {
  go: { label: 'صنّعها', badge: 'bg-brand text-white', color: '#1e4fd6' },
  maybe: { label: 'ربما', badge: 'bg-[#fdf3dc] text-[#8a5a00]', color: '#c98a0b' },
  no: { label: 'لا تصنّعها', badge: 'bg-signal/12 text-[#b4400e]', color: '#f0641e' },
};

const SOURCE_NOTES = {
  live: 'تحليل مباشر: الأرقام محسوبة من البيانات، والذكاء الاصطناعي يشرحها فقط.',
  demo_cache: 'وضع العرض: مثال مجهّز مسبقاً، والأرقام محسوبة مباشرة من البيانات.',
  sample: 'الخادم غير متاح الآن، هذه بيانات تجريبية.',
};

const shorten = (text, max = 42) => (text.length > max ? `${text.slice(0, max - 2).trim()}…` : text);

/* ───────────── Running: the product rides a production line ───────────── */

function AssemblyLine({ input }) {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setStep((s) => Math.min(s + 1, ANALYSIS_STEPS.length - 1)), STEP_MS);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="rounded-[28px] border border-hairline bg-white/70 p-5 shadow-[0_30px_60px_-44px_rgb(14_23_38/0.4)] backdrop-blur-sm md:p-8">
      <div className="flex items-center justify-between gap-4">
        <p className="flex min-w-0 items-center gap-3 text-[14px] text-ink-muted">
          <span className="grid size-9 shrink-0 place-items-center overflow-hidden rounded-lg bg-ink text-paper">
            {input.preview ? (
              <img src={input.preview} alt="" className="size-full object-cover" />
            ) : (
              <Package className="size-4" strokeWidth={2} aria-hidden="true" />
            )}
          </span>
          <span className="truncate">
            على خط التقييم: <span className="font-semibold text-ink">{shorten(input.name, 60)}</span>
          </span>
        </p>
        <span className="shrink-0 font-mono text-[12px] text-brand" dir="ltr">
          STATION 0{step + 1} / 04
        </span>
      </div>

      <div className="relative mt-8 overflow-x-clip md:mt-10" style={{ '--line-ms': `${ANALYSIS_MS}ms` }}>
        {/* Conveyor belt between the first and last station */}
        <div className="absolute inset-x-[12.5%] top-7 -translate-y-1/2">
          <div className="belt h-2 rounded-full" />
          <div className="puck-travel absolute inset-x-0 top-1/2 h-0">
            <span className="absolute top-0 right-0 grid size-9 translate-x-1/2 -translate-y-[130%] place-items-center rounded-lg bg-ink text-paper shadow-[0_8px_18px_-8px_rgb(14_23_38/0.6)]">
              <Package className="size-4" strokeWidth={2} aria-hidden="true" />
            </span>
          </div>
        </div>

        <ol className="relative grid grid-cols-4" aria-label="مراحل التحليل">
          {ANALYSIS_STEPS.map((s, i) => {
            const state = i < step ? 'done' : i === step ? 'active' : 'pending';
            const Icon = ICONS[s.id];
            return (
              <li
                key={s.id}
                className="flex flex-col items-center text-center"
                aria-current={state === 'active' ? 'step' : undefined}
              >
                <span className="relative grid size-14 place-items-center">
                  {state === 'active' && <span className="gear-spinner absolute -inset-1.5" aria-hidden="true" />}
                  <span
                    className={`grid size-14 place-items-center rounded-full border transition-[background-color,border-color,color] duration-300 ${
                      state === 'done'
                        ? 'border-brand bg-brand text-white'
                        : state === 'active'
                          ? 'border-brand bg-white text-brand'
                          : 'border-ink/15 bg-paper text-ink-muted/60'
                    }`}
                  >
                    {state === 'done' ? (
                      <Check className="pop-in size-5" strokeWidth={2.75} aria-hidden="true" />
                    ) : (
                      <Icon className="size-5" strokeWidth={1.75} aria-hidden="true" />
                    )}
                  </span>
                </span>
                <span
                  className={`mt-3 text-[13px] font-semibold transition-colors duration-300 md:text-[15px] ${
                    state === 'pending' ? 'text-ink-muted/60' : 'text-ink'
                  }`}
                >
                  {STATION_TITLES[s.id]}
                </span>
                <span className="mt-0.5 hidden text-[12px] text-ink-muted md:block">{s.source}</span>
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}

/* ───────────── Done: verdict + four factors side by side ───────────── */

function ScoreDial({ score, color }) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    const t = requestAnimationFrame(() => setShown(score));
    return () => cancelAnimationFrame(t);
  }, [score]);
  const r = 70;
  const c = 2 * Math.PI * r;
  return (
    <div className="relative size-40 shrink-0 md:size-48" role="img" aria-label={`التقييم ${score} من 10`}>
      <svg viewBox="0 0 180 180" className="size-full -rotate-90">
        <circle cx="90" cy="90" r={r} fill="none" stroke="rgb(14 23 38 / 0.08)" strokeWidth="10" />
        {Array.from({ length: 10 }, (_, i) => (
          <line key={i} x1="90" y1="8" x2="90" y2="14" stroke="rgb(14 23 38 / 0.25)" strokeWidth="1.5" transform={`rotate(${i * 36} 90 90)`} />
        ))}
        <circle
          cx="90"
          cy="90"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - shown / 10)}
          className="transition-[stroke-dashoffset] duration-[1400ms] ease-(--ease-out)"
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">
        <div>
          <p className="font-display text-[3rem] leading-none font-bold text-ink md:text-[3.5rem]" dir="ltr">
            {score.toFixed(1)}
          </p>
          <p className="mt-1 font-mono text-[12px] text-ink-muted" dir="ltr">
            / 10
          </p>
        </div>
      </div>
    </div>
  );
}

function FactorCard({ factor, i }) {
  const Icon = ICONS[factor.id];
  const est = factor.est ?? {};
  const risk = factor.id === 'risk';
  const long = factor.headline.length > 28;
  return (
    <article
      className={`rise-in flex min-w-0 flex-col rounded-2xl border p-3.5 shadow-[0_24px_48px_-36px_rgb(14_23_38/0.35)] backdrop-blur-sm sm:p-4 lg:rounded-3xl lg:p-6 ${
        risk ? 'border-signal/20 bg-[#fff7f1]/85' : 'border-hairline bg-white/75'
      }`}
      style={{ '--i': i + 3 }}
    >
      <header className="flex items-center gap-2 lg:gap-3">
        <span
          className={`grid size-7 shrink-0 place-items-center rounded-lg lg:size-9 lg:rounded-xl ${risk ? 'bg-signal/12 text-[#b4400e]' : 'bg-brand/8 text-brand'}`}
        >
          <Icon className="size-4 lg:size-[18px]" strokeWidth={1.75} aria-hidden="true" />
        </span>
        <h4 className="text-[13px] leading-snug font-semibold text-ink lg:text-[15px]">{factor.title}</h4>
        <span className="ms-auto hidden font-mono text-[12px] text-ink-muted lg:inline" dir="ltr">
          0{i + 1}
        </span>
      </header>

      <p
        className={`mt-3 font-display font-semibold text-ink lg:mt-5 ${
          long ? 'text-[13.5px] leading-[1.7] lg:text-[1rem] lg:leading-[1.75]' : 'text-[1.0625rem] leading-[1.4] lg:text-[1.375rem]'
        }`}
      >
        {factor.headline}
        <EstimateTag show={est.headline} />
      </p>
      <p className="mt-1.5 text-[12px] leading-[1.7] text-ink-muted lg:text-[12.5px]">
        {factor.caption}
        <EstimateTag show={est.caption && !est.headline} />
      </p>

      {factor.body && (
        <p className="mt-3 text-[12.5px] leading-[1.8] text-ink/80 lg:mt-4 lg:text-[14px] lg:leading-[1.85]">
          {factor.body}
          <EstimateTag show={est.body} />
        </p>
      )}
      {factor.list && (
        <ul className="mt-3 space-y-2 lg:mt-4 lg:space-y-2.5">
          {factor.list.map((item) => (
            <li key={item} className="flex gap-2 text-[12.5px] leading-[1.75] text-ink/80 lg:gap-2.5 lg:text-[14px] lg:leading-[1.8]">
              <span className="mt-[0.7em] size-1.5 shrink-0 bg-signal" aria-hidden="true" />
              {item}
            </li>
          ))}
        </ul>
      )}
      {factor.meta && (
        <p className="mt-3 text-[12px] leading-[1.75] text-ink-muted lg:text-[12.5px] lg:leading-[1.8]">
          {factor.meta}
          <EstimateTag show={est.meta} />
        </p>
      )}

      <div className="mt-auto pt-4 lg:pt-5">
        <p className="border-t border-hairline pt-3 text-[11.5px] leading-[1.6] text-ink-muted lg:pt-3.5 lg:text-[12px]">المصدر: {factor.source}</p>
      </div>
    </article>
  );
}

function ResetButton({ onReset }) {
  return (
    <button
      type="button"
      onClick={onReset}
      className="inline-flex h-12 items-center gap-2.5 rounded-[14px] border border-ink/15 bg-white px-5 text-[15px] font-semibold text-ink transition-[background-color,border-color,scale] duration-150 ease-(--ease-out) hover:border-ink/30 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-signal active:scale-[0.97]"
    >
      <RotateCcw className="size-4" aria-hidden="true" />
      حلّل منتجاً آخر
    </button>
  );
}

const CHIP =
  'rounded-full border border-ink/12 bg-white px-4 py-2 text-[14px] text-ink transition-[border-color,color,scale] duration-150 hover:border-brand hover:text-brand active:scale-[0.97] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal';

function MessageCard({ children, onReset }) {
  return (
    <div className="rise-in rounded-[28px] border border-hairline bg-white/75 p-6 shadow-[0_30px_60px_-40px_rgb(14_23_38/0.4)] backdrop-blur-sm md:p-10">
      {children}
      <div className="mt-8 border-t border-hairline pt-6">
        <ResetButton onReset={onReset} />
      </div>
    </div>
  );
}

/** The AI wasn't sure which category the product is: let the user pick. */
function ConfirmView({ outcome, onConfirm, onReset }) {
  return (
    <MessageCard onReset={onReset}>
      <p className="text-[1.0625rem] leading-[1.9] text-ink-muted">
        تعرّفنا على <span className="font-semibold text-ink">«{outcome.productName}»</span>، لكننا لسنا متأكدين من
        فئته. اختر الأقرب لمنتجك:
      </p>
      <div className="mt-5 flex flex-wrap gap-2.5">
        {outcome.candidates.map((c) => (
          <button key={c.id} type="button" onClick={() => onConfirm(c.id)} className={CHIP}>
            {c.name}
          </button>
        ))}
      </div>
    </MessageCard>
  );
}

function UnsupportedView({ outcome, onReset }) {
  return (
    <MessageCard onReset={onReset}>
      {outcome.searchedHs ? (
        <>
          <p className="text-[1.0625rem] leading-[1.9] text-ink-muted">
            تعرّفنا على <span className="font-semibold text-ink">«{outcome.productName}»</span>. هو خارج المنتجات التي
            نملك بياناتها، فبحثنا عن بيانات استيراده الرسمية في UN Comtrade (رمز HS مقترح:{' '}
            <span className="font-mono text-ink" dir="ltr">
              {outcome.searchedHs}
            </span>
            ) ولم نجد بيانات كافية، لذلك لا نستطيع تقييمه الآن.
          </p>
          <p className="mt-3 text-[14px] leading-[1.9] text-ink-muted">
            قد يكون الرمز المقترح غير دقيق: جرّب وصفاً أدق للمنتج أو صورة أوضح.
          </p>
        </>
      ) : (
        <p className="text-[1.0625rem] leading-[1.9] text-ink-muted">
          تعرّفنا على <span className="font-semibold text-ink">«{outcome.productName}»</span>، لكنه خارج المنتجات التي
          نملك بياناتها حالياً. نعمل على إضافة منتجات أكثر.
        </p>
      )}
    </MessageCard>
  );
}

function InfoCard({ icon: Icon, title, i, tone = 'brand', children }) {
  return (
    <article
      className="rise-in flex min-w-0 flex-col rounded-2xl border border-hairline bg-white/75 p-4 shadow-[0_24px_48px_-36px_rgb(14_23_38/0.35)] backdrop-blur-sm lg:rounded-3xl lg:p-6"
      style={{ '--i': i }}
    >
      <header className="flex items-center gap-2 lg:gap-3">
        <span
          className={`grid size-7 shrink-0 place-items-center rounded-lg lg:size-9 lg:rounded-xl ${
            tone === 'warn' ? 'bg-[#fdf3dc] text-[#8a5a00]' : 'bg-brand/8 text-brand'
          }`}
        >
          <Icon className="size-4 lg:size-[18px]" strokeWidth={1.75} aria-hidden="true" />
        </span>
        <h4 className="text-[13px] leading-snug font-semibold text-ink lg:text-[15px]">{title}</h4>
      </header>
      {children}
    </article>
  );
}

const listItem = 'flex gap-2.5 text-[13px] leading-[1.8] text-ink/80 lg:text-[14px]';

/** market_preview: real import figures for an AI-guessed HS code, plus what's still missing to judge. */
function PreviewView({ outcome, onReset }) {
  return (
    <div>
      <div className="rise-in rounded-[32px] border border-hairline bg-white/75 p-6 shadow-[0_30px_60px_-40px_rgb(14_23_38/0.4)] backdrop-blur-sm md:p-10">
        <span className="inline-flex items-center gap-2 rounded-full bg-[#fdf3dc] px-4 py-1.5 font-display text-[15px] font-semibold text-[#8a5a00]">
          ربما: البيانات لا تكفي لحكم كامل
        </span>
        <h3 className="mt-5 font-display text-[clamp(1.5rem,1rem+1.6vw,2.25rem)] leading-[1.35] font-semibold text-ink">
          {outcome.productName}
        </h3>
        <p className="mt-4 max-w-[70ch] text-[1.0625rem] leading-[1.9] text-ink-muted">{outcome.summary}</p>
        <p className="mt-5 flex flex-wrap gap-x-5 gap-y-1 text-[13px] text-ink-muted">
          <span>
            رمز HS مقترح:{' '}
            <span className="font-mono text-ink" dir="ltr">
              {outcome.hsCode}
            </span>{' '}
            <span className="text-[#8a5a00]">(اقترحه الذكاء الاصطناعي، تأكّد منه)</span>
          </span>
          <span>بحثت عن: «{shorten(outcome.inputName, 50)}»</span>
        </p>
      </div>

      <div className="mt-6 grid gap-3 md:grid-cols-3 lg:gap-4">
        <InfoCard icon={TrendingUp} title="السوق: بيانات رسمية" i={3}>
          <p className="mt-3 font-display text-[1.375rem] leading-[1.4] font-semibold text-ink lg:mt-5">
            {outcome.importsLatest ?? 'لا تتوفر بيانات'}
          </p>
          <p className="mt-1.5 text-[12.5px] text-ink-muted">واردات الأردن في 2024</p>
          {outcome.trend && <p className="mt-3 text-[13px] leading-[1.8] text-ink/80 lg:text-[14px]">{outcome.trend}</p>}
          <div className="mt-auto pt-4 lg:pt-5">
            <p className="border-t border-hairline pt-3 text-[12px] text-ink-muted">المصدر: UN Comtrade</p>
          </div>
        </InfoCard>

        <InfoCard icon={CircleHelp} title="ما ينقصنا لنحكم" i={4} tone="warn">
          <ul className="mt-3 space-y-2.5 lg:mt-5">
            {outcome.missing.map((m) => (
              <li key={m} className={listItem}>
                <span className="mt-[0.7em] size-1.5 shrink-0 bg-[#c98a0b]" aria-hidden="true" />
                {m}
              </li>
            ))}
          </ul>
        </InfoCard>

        <InfoCard icon={ListChecks} title="خطوات للتحقق" i={5}>
          <ol className="mt-3 space-y-2.5 lg:mt-5">
            {outcome.steps.map((step, n) => (
              <li key={step} className={listItem}>
                <span className="font-mono text-[12px] leading-[2] text-brand" dir="ltr">
                  0{n + 1}
                </span>
                {step}
              </li>
            ))}
          </ol>
        </InfoCard>
      </div>

      <div className="mt-12 flex flex-col items-start gap-4 border-t border-hairline pt-8 md:flex-row md:items-center md:justify-between">
        <p className="text-[13px] text-ink-muted">مسح أولي: أرقام الواردات رسمية، والتكلفة والتصنيع والمنافسة لم تُقيَّم بعد.</p>
        <div className="flex flex-wrap items-start gap-3">
          <ReportButton
            productName={outcome.productName}
            renderSheet={() => <PreviewSheet outcome={outcome} />}
            align="start"
          />
          <ResetButton onReset={onReset} />
        </div>
      </div>
    </div>
  );
}

function ErrorView({ outcome, onAnalyze, onReset }) {
  return (
    <MessageCard onReset={onReset}>
      <p role="alert" className="text-[1.0625rem] leading-[1.9] text-ink">
        {outcome.message}
      </p>
      {outcome.examples.length > 0 && (
        <div className="mt-5 flex flex-wrap gap-2.5">
          {outcome.examples.map((ex) => (
            <button key={ex} type="button" onClick={() => onAnalyze({ name: ex, text: ex })} className={CHIP}>
              {ex}
            </button>
          ))}
        </div>
      )}
    </MessageCard>
  );
}

function ResultView({ result, onReset }) {
  const verdict = VERDICT_UI[result.verdict];
  return (
    <div>
      <div className="rise-in flex flex-col items-start gap-8 rounded-[32px] border border-hairline bg-white/75 p-6 shadow-[0_30px_60px_-40px_rgb(14_23_38/0.4)] backdrop-blur-sm md:flex-row md:items-center md:gap-12 md:p-10">
        <ScoreDial score={result.score} color={verdict.color} />
        <div className="min-w-0">
          <span
            className={`inline-flex items-center gap-2 rounded-full px-4 py-1.5 font-display text-[15px] font-semibold ${verdict.badge}`}
          >
            {result.verdict === 'go' && <Check className="size-4" strokeWidth={2.75} aria-hidden="true" />}
            {verdict.label}
          </span>
          <h3 className="mt-5 font-display text-[clamp(1.5rem,1rem+1.6vw,2.25rem)] leading-[1.35] font-semibold text-ink">
            {result.productName}
          </h3>
          <p className="mt-4 max-w-[62ch] text-[1.0625rem] leading-[1.9] text-ink-muted">{result.summary}</p>
          <p className="mt-5 flex flex-wrap gap-x-5 gap-y-1 text-[13px] text-ink-muted">
            <span>
              رمز النظام المنسّق: <span className="font-mono text-ink" dir="ltr">HS {result.hsCode}</span>
            </span>
            <span>بحثت عن: «{shorten(result.inputName, 50)}»</span>
            {result.highCapital && <span className="font-medium text-[#b4400e]">يحتاج رأس مال مرتفعاً</span>}
          </p>
          {result.formula && (
            <details className="group mt-5 max-w-[70ch]">
              <summary className="inline-flex list-none items-center gap-2 rounded-md text-[14px] font-medium text-brand focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-signal [&::-webkit-details-marker]:hidden">
                <span className="grid size-5 place-items-center rounded-full border border-brand/40 text-[12px] leading-none transition-transform duration-200 group-open:rotate-45">
                  +
                </span>
                كيف حسبنا التقييم؟
              </summary>
              <p className="mt-3 rounded-2xl border border-hairline bg-paper px-4 py-3 text-[14px] leading-[1.9] text-ink/80">
                {result.formula}
              </p>
            </details>
          )}
        </div>
      </div>

      <div className="rise-in mt-14 mb-6 flex flex-col gap-2 md:flex-row md:items-end md:justify-between" style={{ '--i': 2 }}>
        <h3 className="font-display text-[1.5rem] font-semibold text-ink">العوامل الأربعة</h3>
        <p className="text-[14px] text-ink-muted">ثلاثة عوامل من مصادر رسمية، والرابع من «المراجع الناقد»: وكيل ذكاء اصطناعي يعارض الحكم ويبحث عن المخاطر.</p>
      </div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 lg:gap-4">
        {result.factors.map((f, i) => (
          <FactorCard key={f.id} factor={f} i={i} />
        ))}
      </div>
      {result.hasEstimates && (
        <p className="mt-3 text-[12.5px] text-ink-muted">
          الأرقام المعلّمة بـ<EstimateTag show /> محسوبة تقريبياً، والباقي من مصادر رسمية.
        </p>
      )}
      {result.whatIf && <WhatIf whatIf={result.whatIf} baseScore={result.score} verdicts={VERDICT_UI} />}

      <ActionPlan result={result} />

      <div className="mt-12 flex flex-col items-start gap-4 border-t border-hairline pt-8 md:flex-row md:items-center md:justify-between">
        <p className="text-[13px] text-ink-muted">{SOURCE_NOTES[result.source] ?? ''}</p>
        <ResetButton onReset={onReset} />
      </div>
    </div>
  );
}

/* ───────────── Section shell ───────────── */

const HEADINGS = {
  result: 'هل يستحق التصنيع محلياً؟',
  preview: 'مسح أولي للسوق',
  confirm: 'أيّ هذه هو منتجك؟',
  unsupported: 'هذا المنتج خارج نطاقنا حالياً',
  error: 'تعذّر إكمال التحليل',
};

function Outcome({ outcome, onReset, onConfirm, onAnalyze }) {
  switch (outcome.kind) {
    case 'result':
      return <ResultView result={outcome} onReset={onReset} />;
    case 'preview':
      return <PreviewView outcome={outcome} onReset={onReset} />;
    case 'confirm':
      return <ConfirmView outcome={outcome} onConfirm={onConfirm} onReset={onReset} />;
    case 'unsupported':
      return <UnsupportedView outcome={outcome} onReset={onReset} />;
    default:
      return <ErrorView outcome={outcome} onAnalyze={onAnalyze} onReset={onReset} />;
  }
}

export default function AnalysisSection({ run, onReset, onConfirm, onAnalyze }) {
  const sectionRef = useRef(null);
  const headingRef = useRef(null);

  useEffect(() => {
    sectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [run.id]);
  useEffect(() => {
    if (run.status === 'done') headingRef.current?.focus({ preventScroll: true });
  }, [run.status]);

  const done = run.status === 'done';

  return (
    <section ref={sectionRef} id="analysis" aria-labelledby="analysis-title" className="relative border-t border-hairline">
      <div className="mx-auto max-w-[1320px] px-5 py-20 md:px-10 md:py-24">
        <div className="mb-10 max-w-[760px]">
          <p className="flex items-center gap-2.5 text-[13px] font-medium text-ink-muted">
            <span aria-hidden="true" className="inline-block size-1.5 bg-signal" />
            {done ? 'النتيجة' : 'الخطوة الثانية'}
          </p>
          <h2
            ref={headingRef}
            id="analysis-title"
            tabIndex={-1}
            aria-live="polite"
            className="mt-4 font-display text-[clamp(1.75rem,1.1rem+2vw,2.6rem)] leading-[1.3] font-semibold text-ink outline-none"
          >
            {done ? HEADINGS[run.outcome.kind] : 'نمرّر منتجك على خط التقييم…'}
          </h2>
        </div>

        {done ? (
          <Outcome outcome={run.outcome} onReset={onReset} onConfirm={onConfirm} onAnalyze={onAnalyze} />
        ) : (
          <AssemblyLine key={run.id} input={run.input} />
        )}
      </div>
    </section>
  );
}
