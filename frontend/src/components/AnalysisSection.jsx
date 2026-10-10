import { useEffect, useRef, useState } from 'react';
import {
  ArrowCounterClockwise,
  Check,
  Coins,
  Factory,
  ListNumbers,
  Package,
  Question,
  ShieldWarning,
  TrendUp,
} from '@phosphor-icons/react';
import { ANALYSIS_MS, ANALYSIS_STEPS } from '../lib/analyzeProduct';
import { formatJod } from '../lib/api';
import ActionPlan from './ActionPlan';
import GuidancePanels, { Methodology } from './GuidancePanels';
import EstimateTag from './EstimateTag';
import ReportButton from './ReportButton';
import { PreviewSheet } from './ReportSheet';
import WhatIf from './WhatIf';

const STEP_MS = ANALYSIS_MS / ANALYSIS_STEPS.length;
const ICONS = { market: TrendUp, cost: Coins, readiness: Factory, risk: ShieldWarning };
const STATION_TITLES = { market: 'السوق', cost: 'الكلفة', readiness: 'الجاهزية', risk: 'المراجع الناقد' };

// `badge` on light surfaces, `badgeDark` on the graphite what-if result; `word` styles the large verdict.
const VERDICT_UI = {
  go: { label: 'صنّعها', badge: 'bg-accent text-ink', badgeDark: 'bg-accent text-ink', word: 'text-ink', mark: true },
  maybe: { label: 'ربما', badge: 'border border-ink/30 text-ink', badgeDark: 'border border-white/40 text-white', word: 'text-ink' },
  no: { label: 'لا تصنّعها', badge: 'bg-signal text-white', badgeDark: 'bg-signal text-white', word: 'text-signal' },
};

const SOURCE_NOTES = {
  live: 'تحليل مباشر: الأرقام محسوبة من البيانات، والذكاء الاصطناعي يشرحها فقط.',
  demo_cache: 'وضع العرض: مثال مجهّز مسبقاً، والأرقام محسوبة مباشرة من البيانات.',
  sample: 'الخادم غير متاح الآن، هذه بيانات تجريبية.',
};

const shorten = (text, max = 42) => (text.length > max ? `${text.slice(0, max - 2).trim()}…` : text);

const PANEL = 'rounded-[16px] border border-hairline bg-white';
const SECONDARY_BTN =
  'inline-flex h-12 items-center gap-2.5 rounded-[12px] border border-ink/15 bg-white px-5 text-[15px] font-semibold text-ink transition-[background-color,border-color,scale] duration-150 ease-(--ease-out) hover:border-ink/35 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-signal active:scale-[0.98]';
const CHOICE_BTN =
  'rounded-[10px] border border-ink/15 bg-white px-4 py-2.5 text-[15px] font-medium text-ink transition-[border-color,background-color,scale] duration-150 hover:border-ink/40 active:scale-[0.98] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal';

/* ───────────── Running: the product rides a production line ───────────── */

function AssemblyLine({ input }) {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setStep((s) => Math.min(s + 1, ANALYSIS_STEPS.length - 1)), STEP_MS);
    return () => clearInterval(t);
  }, []);

  return (
    <div className={`${PANEL} p-5 md:p-8`}>
      <p className="flex min-w-0 items-center gap-3 text-[14px] text-ink-muted">
        <span className="grid size-9 shrink-0 place-items-center overflow-hidden rounded-[8px] bg-ink text-white">
          {input.preview ? (
            <img src={input.preview} alt="" className="size-full object-cover" />
          ) : (
            <Package className="size-4" weight="bold" aria-hidden="true" />
          )}
        </span>
        <span className="truncate">
          على خط التقييم: <span className="font-semibold text-ink">{shorten(input.name, 60)}</span>
        </span>
      </p>

      <div className="relative mt-8 overflow-x-clip md:mt-10" style={{ '--line-ms': `${ANALYSIS_MS}ms` }}>
        {/* Conveyor belt between the first and last station */}
        <div className="absolute inset-x-[12.5%] top-7 -translate-y-1/2">
          <div className="belt h-2 rounded-full" />
          <div className="puck-travel absolute inset-x-0 top-1/2 h-0">
            <span className="absolute top-0 right-0 grid size-9 translate-x-1/2 -translate-y-[130%] place-items-center rounded-[8px] bg-accent text-ink shadow-[0_8px_18px_-8px_rgb(21_24_27/0.5)]">
              <Package className="size-4" weight="bold" aria-hidden="true" />
            </span>
          </div>
        </div>

        <ol className="relative grid grid-cols-4" aria-label="مراحل التحليل">
          {ANALYSIS_STEPS.map((s, i) => {
            const state = i < step ? 'done' : i === step ? 'active' : 'pending';
            const Icon = ICONS[s.id];
            return (
              <li key={s.id} className="flex flex-col items-center text-center" aria-current={state === 'active' ? 'step' : undefined}>
                <span className="relative grid size-14 place-items-center">
                  {state === 'active' && <span className="gear-spinner absolute -inset-1.5" aria-hidden="true" />}
                  <span
                    className={`grid size-14 place-items-center rounded-full border transition-[background-color,border-color,color] duration-300 ${
                      state === 'done'
                        ? 'border-brand bg-brand text-white'
                        : state === 'active'
                          ? 'border-brand bg-white text-ink'
                          : 'border-ink/15 bg-paper text-ink-muted/60'
                    }`}
                  >
                    {state === 'done' ? (
                      <Check className="pop-in size-5" weight="bold" aria-hidden="true" />
                    ) : (
                      <Icon className="size-5" aria-hidden="true" />
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

/* ───────────── Score: a number and where it sits between the three verdicts ───────────── */

function ScoreMeter({ score }) {
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const t = requestAnimationFrame(() => setShown(true));
    return () => cancelAnimationFrame(t);
  }, []);
  const filled = Math.round(score);
  return (
    <div className="w-full max-w-[340px]" role="img" aria-label={`التقييم ${score.toFixed(1)} من 10`}>
      <p className="text-[13px] font-medium text-ink-muted">التقييم</p>
      <p dir="ltr" className="mt-1 text-end font-display leading-none font-bold text-ink tabular-nums">
        <span className="text-[clamp(3.5rem,2.5rem+3vw,5rem)]">{score.toFixed(1)}</span>
        <span className="ms-1 text-[1.25rem] text-ink-muted">/10</span>
      </p>
      <div dir="ltr" className="mt-4 grid grid-cols-10 gap-1" aria-hidden="true">
        {Array.from({ length: 10 }, (_, i) => (
          <span
            key={i}
            className={`h-2.5 rounded-[2px] transition-colors duration-500 ${shown && i < filled ? 'bg-ink' : 'bg-ink/10'}`}
            style={{ transitionDelay: `${i * 45}ms` }}
          />
        ))}
      </div>
      {/* The verdict bands: below 4, 4 to 5.9, 6 and above */}
      <div dir="ltr" className="mt-2 grid grid-cols-10 gap-1 text-[11.5px] text-ink-muted" aria-hidden="true">
        <span className="col-span-4 text-center">لا تصنّعها</span>
        <span className="col-span-2 text-center">ربما</span>
        <span className="col-span-4 text-center">صنّعها</span>
      </div>
    </div>
  );
}

/* ───────────── Factor tiles: each draws its own data ───────────── */

function SeriesChart({ data }) {
  const max = Math.max(...data.map((d) => d.jod ?? 0)) || 1;
  const last = data.length - 1;
  return (
    <div dir="ltr" className="flex h-28 items-end gap-2 lg:h-36 lg:gap-3" role="img" aria-label="واردات الأردن حسب السنة">
      {data.map((d, i) => (
        <div key={d.year} className="flex h-full min-w-0 flex-1 flex-col justify-end">
          {d.jod != null ? (
            <div
              className={`rise-in rounded-t-[3px] ${i === last ? 'bg-accent' : 'bg-ink/15'}`}
              style={{ height: `${Math.max(6, (d.jod / max) * 100)}%`, '--i': i + 4 }}
              title={formatJod(d.jod)}
            />
          ) : (
            <div className="h-[6%] rounded-t-[3px] border border-dashed border-ink/25" title="لا تتوفر بيانات" />
          )}
          <span className={`mt-1.5 text-center font-mono text-[10.5px] lg:text-[11.5px] ${i === last ? 'text-ink' : 'text-ink-muted'}`}>
            {d.year}
          </span>
        </div>
      ))}
    </div>
  );
}

function CompareChart({ imported, local }) {
  const max = Math.max(imported, local);
  const cheaper = local < imported;
  const rows = [
    { label: 'المستورد مع الجمرك', value: imported, bar: 'bg-ink/25' },
    { label: 'الإنتاج المحلي', value: local, bar: cheaper ? 'bg-accent' : 'bg-signal' },
  ];
  return (
    <div className="space-y-3">
      {rows.map((r) => (
        <div key={r.label}>
          <div className="flex items-baseline justify-between gap-2 text-[12px] lg:text-[13px]">
            <span className="text-ink-muted">{r.label}</span>
            <span className="shrink-0 font-mono whitespace-nowrap text-ink tabular-nums">{r.value.toFixed(2)} د/كغ</span>
          </div>
          <div className="mt-1.5 h-2.5 rounded-[2px] bg-ink/[0.06]">
            <div className={`h-full rounded-[2px] ${r.bar}`} style={{ width: `${(r.value / max) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function RatingsChart({ data }) {
  return (
    <div className="space-y-2.5">
      {data.map((r) => (
        <div key={r.label} className="flex items-center justify-between gap-3">
          <span className="text-[12px] text-ink-muted lg:text-[13px]">{r.label}</span>
          <span dir="ltr" className="flex gap-1" role="img" aria-label={`${r.label} ${r.value} من 5`}>
            {Array.from({ length: 5 }, (_, i) => (
              <span key={i} className={`h-2.5 w-4 rounded-[2px] lg:w-6 ${i < Math.round(r.value) ? 'bg-ink' : 'bg-ink/10'}`} />
            ))}
          </span>
        </div>
      ))}
    </div>
  );
}

function FactorChart({ chart }) {
  if (chart.kind === 'series') return <SeriesChart data={chart.data} />;
  if (chart.kind === 'compare') return <CompareChart imported={chart.imported} local={chart.local} />;
  return <RatingsChart data={chart.data} />;
}

// Bento rhythm on large screens: 7/5 then 5/7. Two columns on phones (the 2x2 the team chose).
const SPANS = { market: 'lg:col-span-7', cost: 'lg:col-span-5', readiness: 'lg:col-span-5', risk: 'lg:col-span-7' };

function FactorTile({ factor, i }) {
  const Icon = ICONS[factor.id];
  const est = factor.est ?? {};
  const risk = factor.id === 'risk';
  const long = factor.headline.length > 28;
  return (
    <article
      className={`rise-in flex min-w-0 flex-col rounded-[16px] border p-3.5 sm:p-5 lg:p-7 ${SPANS[factor.id]} ${
        risk ? 'border-signal/20 bg-signal/[0.05]' : 'border-hairline bg-white'
      }`}
      style={{ '--i': i + 3 }}
    >
      <header className={`flex items-center gap-2 ${risk ? 'text-signal' : 'text-ink-muted'}`}>
        <Icon className="size-4 shrink-0 lg:size-5" aria-hidden="true" />
        <h4 className="text-[13px] font-semibold lg:text-[14.5px]">{factor.title}</h4>
      </header>

      <p
        className={`mt-3 font-display font-bold text-ink lg:mt-4 ${
          long ? 'text-[14px] leading-[1.7] lg:text-[1.125rem] lg:leading-[1.65]' : 'text-[1.125rem] leading-[1.35] lg:text-[1.875rem]'
        }`}
      >
        {factor.headline}
        <EstimateTag show={est.headline} />
      </p>
      {factor.caption && (
        <p className="mt-1.5 text-[12px] leading-[1.7] text-ink-muted lg:text-[13px]">
          {factor.caption}
          <EstimateTag show={est.caption && !est.headline} />
        </p>
      )}

      {factor.chart && (
        <div className="mt-5 lg:mt-7">
          <FactorChart chart={factor.chart} />
        </div>
      )}

      {factor.body && (
        <p className="mt-4 text-[12.5px] leading-[1.8] text-ink/80 lg:mt-5 lg:text-[14px] lg:leading-[1.85]">
          {factor.body}
          <EstimateTag show={est.body} />
        </p>
      )}
      {factor.list && (
        <ul className="mt-4 space-y-2.5 lg:mt-5">
          {factor.list.map((item) => (
            <li key={item} className="flex gap-2.5 text-[12.5px] leading-[1.75] text-ink/85 lg:text-[14.5px] lg:leading-[1.8]">
              <span className="mt-[0.75em] h-px w-3 shrink-0 bg-signal" aria-hidden="true" />
              {item}
            </li>
          ))}
        </ul>
      )}
      {factor.meta && (
        <p className="mt-3 text-[12px] leading-[1.75] text-ink-muted lg:text-[13px]">
          {factor.meta}
          <EstimateTag show={est.meta} />
        </p>
      )}

      <p className="mt-auto pt-5 text-[11.5px] leading-[1.6] text-ink-muted lg:text-[12px]">المصدر: {factor.source}</p>
    </article>
  );
}

/* ───────────── Shared bits ───────────── */

function ResetButton({ onReset }) {
  return (
    <button type="button" onClick={onReset} className={SECONDARY_BTN}>
      <ArrowCounterClockwise className="size-4" weight="bold" aria-hidden="true" />
      حلّل منتجاً آخر
    </button>
  );
}

function MessageCard({ children, onReset }) {
  return (
    <div className={`rise-in ${PANEL} p-6 md:p-10`}>
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
      <p className="max-w-[62ch] text-[1.0625rem] leading-[1.9] text-ink-muted">
        تعرّفنا على <span className="font-semibold text-ink">«{outcome.productName}»</span>، لكننا لسنا متأكدين من
        فئته. اختر الأقرب لمنتجك:
      </p>
      <div className="mt-5 flex flex-wrap gap-2.5">
        {outcome.candidates.map((c) => (
          <button key={c.id} type="button" onClick={() => onConfirm(c.id)} className={CHOICE_BTN}>
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
          <p className="max-w-[62ch] text-[1.0625rem] leading-[1.9] text-ink-muted">
            تعرّفنا على <span className="font-semibold text-ink">«{outcome.productName}»</span>. هو خارج المنتجات التي
            نملك بياناتها، فبحثنا عن بيانات استيراده الرسمية في UN Comtrade (رمز HS مقترح:{' '}
            <span className="font-mono text-ink" dir="ltr">
              {outcome.searchedHs}
            </span>
            ) ولم نجد بيانات كافية، لذلك لا نستطيع تقييمه الآن.
          </p>
          <p className="mt-3 text-[14px] leading-[1.9] text-ink-muted">قد يكون الرمز المقترح غير دقيق: جرّب وصفاً أدق للمنتج أو صورة أوضح.</p>
        </>
      ) : (
        <p className="max-w-[62ch] text-[1.0625rem] leading-[1.9] text-ink-muted">
          تعرّفنا على <span className="font-semibold text-ink">«{outcome.productName}»</span>، لكنه خارج المنتجات التي
          نملك بياناتها حالياً. نعمل على إضافة منتجات أكثر.
        </p>
      )}
    </MessageCard>
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
            <button key={ex} type="button" onClick={() => onAnalyze({ name: ex, text: ex })} className={CHOICE_BTN}>
              {ex}
            </button>
          ))}
        </div>
      )}
    </MessageCard>
  );
}

function NumberedList({ items }) {
  return (
    <ol className="space-y-4">
      {items.map((item, n) => (
        <li key={item} className="grid grid-cols-[auto_1fr] gap-4 text-[14px] leading-[1.85] text-ink/85 lg:text-[15px]">
          <span className="font-display text-[1.375rem] leading-[1.2] font-bold text-ink/25 tabular-nums" dir="ltr">
            {n + 1}
          </span>
          {item}
        </li>
      ))}
    </ol>
  );
}

/** market_preview: real import figures for an AI-guessed HS code, plus what's still missing to judge. */
function PreviewView({ outcome, onReset }) {
  return (
    <div>
      <div className="rise-in border-b border-hairline pb-10">
        <p className="font-display text-[clamp(3rem,2rem+4vw,5.5rem)] leading-[1.1] font-bold text-ink">ربما</p>
        <p className="mt-4 text-[1.0625rem] font-medium text-ink-muted">البيانات لا تكفي لحكم كامل بعد.</p>
        <h3 className="mt-7 font-display text-[clamp(1.375rem,1rem+1.2vw,2rem)] leading-[1.35] font-semibold text-ink">
          {outcome.productName}
        </h3>
        <p className="mt-3 max-w-[66ch] text-[1.0625rem] leading-[1.9] text-ink-muted">{outcome.summary}</p>
        <p className="mt-5 flex flex-wrap gap-x-6 gap-y-1 text-[13.5px] text-ink-muted">
          <span>
            رمز HS مقترح:{' '}
            <span className="font-mono text-ink" dir="ltr">
              {outcome.hsCode}
            </span>{' '}
            (اقترحه الذكاء الاصطناعي، تأكّد منه)
          </span>
          <span>بحثت عن: «{shorten(outcome.inputName, 50)}»</span>
        </p>
      </div>

      <div className="mt-8 grid gap-3 lg:grid-cols-12 lg:gap-4">
        <article className={`rise-in ${PANEL} flex flex-col p-5 lg:col-span-7 lg:p-7`} style={{ '--i': 3 }}>
          <header className="flex items-center gap-2 text-ink-muted">
            <TrendUp className="size-5" aria-hidden="true" />
            <h4 className="text-[14.5px] font-semibold">السوق: بيانات رسمية</h4>
          </header>
          <p className="mt-4 font-display text-[1.875rem] leading-[1.35] font-bold text-ink">{outcome.importsLatest ?? 'لا تتوفر بيانات'}</p>
          <p className="mt-1.5 text-[13px] text-ink-muted">واردات الأردن في 2024</p>
          {outcome.series?.some((d) => d.jod != null) && (
            <div className="mt-6">
              <SeriesChart data={outcome.series} />
            </div>
          )}
          {outcome.trend && <p className="mt-4 text-[14px] leading-[1.85] text-ink/80">{outcome.trend}</p>}
          <p className="mt-auto pt-5 text-[12px] text-ink-muted">المصدر: UN Comtrade</p>
        </article>

        <article className="rise-in flex flex-col rounded-[16px] border border-ink/10 bg-paper-2/60 p-5 lg:col-span-5 lg:p-7" style={{ '--i': 4 }}>
          <header className="flex items-center gap-2 text-ink">
            <Question className="size-5" aria-hidden="true" />
            <h4 className="text-[14.5px] font-semibold">ما ينقصنا لنحكم</h4>
          </header>
          <ul className="mt-5 space-y-3">
            {outcome.missing.map((m) => (
              <li key={m} className="flex gap-2.5 text-[14px] leading-[1.85] text-ink/85">
                <span className="mt-[0.8em] h-px w-3 shrink-0 bg-ink/50" aria-hidden="true" />
                {m}
              </li>
            ))}
          </ul>
        </article>

        <article className={`rise-in ${PANEL} p-5 lg:col-span-12 lg:p-7`} style={{ '--i': 5 }}>
          <header className="flex items-center gap-2 text-ink-muted">
            <ListNumbers className="size-5" aria-hidden="true" />
            <h4 className="text-[14.5px] font-semibold">خطوات للتحقق</h4>
          </header>
          <div className="mt-5 max-w-[80ch]">
            <NumberedList items={outcome.steps} />
          </div>
        </article>
      </div>

      <div className="mt-12 flex flex-col items-start gap-4 border-t border-hairline pt-8 md:flex-row md:items-center md:justify-between">
        <p className="text-[13px] text-ink-muted">مسح أولي: أرقام الواردات رسمية، والتكلفة والتصنيع والمنافسة لم تُقيَّم بعد.</p>
        <div className="flex flex-wrap items-start gap-3">
          <ReportButton productName={outcome.productName} renderSheet={() => <PreviewSheet outcome={outcome} />} align="start" />
          <ResetButton onReset={onReset} />
        </div>
      </div>
    </div>
  );
}

function ResultView({ result, onReset }) {
  const verdict = VERDICT_UI[result.verdict];
  return (
    <div>
      <div className="rise-in grid gap-10 border-b border-hairline pb-12 lg:grid-cols-[minmax(0,1fr)_340px] lg:items-end lg:gap-16">
        <div className="min-w-0">
          <p className={`font-display text-[clamp(3.25rem,2rem+5vw,6.5rem)] leading-[1.1] font-bold ${verdict.word}`}>
            <span className={verdict.mark ? 'mark' : undefined}>{verdict.label}</span>
          </p>
          <h3 className="mt-7 font-display text-[clamp(1.375rem,1rem+1.2vw,2rem)] leading-[1.35] font-semibold text-ink">
            {result.productName}
          </h3>
          <p className="mt-3 max-w-[64ch] text-[1.0625rem] leading-[1.9] text-ink-muted">{result.summary}</p>
          <p className="mt-5 flex flex-wrap gap-x-6 gap-y-1 text-[13.5px] text-ink-muted">
            <span>
              رمز النظام المنسّق: <span className="font-mono text-ink" dir="ltr">HS {result.hsCode}</span>
            </span>
            <span>بحثت عن: «{shorten(result.inputName, 50)}»</span>
            {result.highCapital && <span className="font-medium text-signal">يحتاج رأس مال مرتفعاً</span>}
          </p>
          {result.formula && (
            <details className="group mt-5 max-w-[70ch]">
              <summary className="inline-flex cursor-pointer list-none items-center gap-2 rounded-sm text-[14px] font-medium text-ink underline decoration-ink/25 underline-offset-[6px] hover:decoration-ink focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-signal [&::-webkit-details-marker]:hidden">
                كيف حسبنا التقييم؟
              </summary>
              <p className="mt-3 rounded-[10px] bg-paper-2/70 px-4 py-3 text-[14px] leading-[1.9] text-ink/85">{result.formula}</p>
              <Methodology />
            </details>
          )}
        </div>
        <ScoreMeter score={result.score} />
      </div>

      <div className="rise-in mt-14" style={{ '--i': 2 }}>
        <h3 className="font-display text-[1.75rem] font-bold text-ink">العوامل الأربعة</h3>
        <p className="mt-2 max-w-[70ch] text-[14.5px] leading-[1.8] text-ink-muted">
          ثلاثة عوامل من مصادر رسمية، والرابع من «المراجع الناقد»: وكيل ذكاء اصطناعي يعارض الحكم ويبحث عن المخاطر.
        </p>
      </div>
      <div className="mt-7 grid grid-cols-2 gap-3 lg:grid-cols-12 lg:gap-4">
        {result.factors.map((f, i) => (
          <FactorTile key={f.id} factor={f} i={i} />
        ))}
      </div>
      {result.hasEstimates && (
        <p className="mt-3 text-[12.5px] text-ink-muted">
          الأرقام المعلّمة بـ<EstimateTag show /> محسوبة تقريبياً، والباقي من مصادر رسمية.
        </p>
      )}
      {result.whatIf && <WhatIf whatIf={result.whatIf} baseScore={result.score} verdicts={VERDICT_UI} />}

      <ActionPlan result={result} />
      {result.guidance && <GuidancePanels guidance={result.guidance} />}

      <div className="mt-14 flex flex-col items-start gap-4 border-t border-hairline pt-8 md:flex-row md:items-center md:justify-between">
        <p className="text-[13px] text-ink-muted">{SOURCE_NOTES[result.source] ?? ''}</p>
        <ResetButton onReset={onReset} />
      </div>
    </div>
  );
}

/* ───────────── Section shell ───────────── */

// The result leads with its verdict, so its section heading is a quiet question; other outcomes lead with the heading.
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
  const quiet = done && (run.outcome.kind === 'result' || run.outcome.kind === 'preview');

  return (
    <section ref={sectionRef} id="analysis" aria-labelledby="analysis-title" className="relative border-t border-hairline">
      <div className="mx-auto max-w-[1320px] px-5 py-20 md:px-10 md:py-24">
        <h2
          ref={headingRef}
          id="analysis-title"
          tabIndex={-1}
          aria-live="polite"
          className={`mb-8 max-w-[760px] font-display outline-none ${
            quiet
              ? 'text-[1.125rem] font-medium text-ink-muted'
              : 'mb-10 text-[clamp(1.75rem,1.1rem+2vw,2.6rem)] leading-[1.3] font-bold text-ink'
          }`}
        >
          {done ? HEADINGS[run.outcome.kind] : 'نمرّر منتجك على خط التقييم…'}
        </h2>

        {done ? (
          <Outcome outcome={run.outcome} onReset={onReset} onConfirm={onConfirm} onAnalyze={onAnalyze} />
        ) : (
          <AssemblyLine key={run.id} input={run.input} />
        )}
      </div>
    </section>
  );
}
