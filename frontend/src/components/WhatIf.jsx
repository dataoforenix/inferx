import { useEffect, useState } from 'react';
import { ArrowCounterClockwise, SlidersHorizontal } from '@phosphor-icons/react';
import { postWhatIf, USD_TO_JOD } from '../lib/api';

const DEBOUNCE_MS = 150;

function Slider({ label, value, display, min, max, step, onChange, ltr = true }) {
  return (
    <label className="block">
      <span className="flex items-baseline justify-between gap-3 text-[14px]">
        <span className="font-medium text-ink">{label}</span>
        <span className={`text-[13px] text-ink ${ltr ? 'font-mono' : 'font-medium'}`} dir={ltr ? 'ltr' : undefined}>
          {display}
        </span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-2 w-full accent-[#1c2024]"
      />
    </label>
  );
}

/**
 * "What if?" scenario: change customs or the local cost and re-score instantly via POST /api/whatif
 * (pure Python on the backend, no AI call). Collapsed by default to keep the result page calm.
 */
export default function WhatIf({ whatIf, baseScore, verdicts }) {
  const [open, setOpen] = useState(false);
  const [customs, setCustoms] = useState(whatIf.customsPct);
  const [localJod, setLocalJod] = useState(whatIf.localCostJod);
  const [scenario, setScenario] = useState(null);
  const [failed, setFailed] = useState(false);

  const changed = customs !== whatIf.customsPct || localJod !== whatIf.localCostJod;

  useEffect(() => {
    if (!open || !changed) return undefined;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      postWhatIf(whatIf.categoryId, { customs_pct: customs, local_cost_per_kg_est_usd: localJod / USD_TO_JOD }, controller.signal)
        .then((s) => {
          setScenario(s);
          setFailed(false);
        })
        .catch((err) => err.name !== 'AbortError' && setFailed(true));
    }, DEBOUNCE_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [open, changed, customs, localJod, whatIf]);

  const reset = () => {
    setCustoms(whatIf.customsPct);
    setLocalJod(whatIf.localCostJod);
  };

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="rise-in mt-6 inline-flex items-center gap-2 rounded-[10px] border border-ink/15 bg-white px-4 py-2.5 text-[14px] font-medium text-ink transition-[border-color,color,scale] duration-150 hover:border-brand hover:text-brand focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal active:scale-[0.97]"
        style={{ '--i': 7 }}
      >
        <SlidersHorizontal className="size-4" aria-hidden="true" />
        جرّب سيناريو: ماذا لو؟
      </button>
    );
  }

  const localMax = Math.max(0.5, Math.ceil(whatIf.localCostJod * 2 * 10) / 10);
  // A stale scenario from before "reset" is ignored rather than cleared in the effect.
  const shown = changed ? scenario : null;
  const verdict = shown && verdicts[shown.verdict];

  return (
    <section
      aria-label="سيناريو ماذا لو"
      className="mt-6 rounded-2xl border border-hairline bg-white/75 p-5 shadow-[0_24px_48px_-36px_rgb(14_23_38/0.35)] backdrop-blur-sm md:p-6"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h4 className="flex items-center gap-2 text-[15px] font-semibold text-ink">
          <SlidersHorizontal className="size-5 text-ink" aria-hidden="true" />
          ماذا لو؟
        </h4>
        <button
          type="button"
          onClick={reset}
          disabled={!changed}
          className="inline-flex items-center gap-1.5 rounded-md text-[13px] text-ink-muted transition-colors duration-150 hover:text-ink disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal"
        >
          <ArrowCounterClockwise className="size-4" aria-hidden="true" />
          القيم الأصلية
        </button>
      </div>

      <div className="mt-5 grid gap-5 md:grid-cols-[1fr_1fr_auto] md:items-end md:gap-8">
        <Slider
          label="الجمرك على المستورد"
          value={customs}
          display={`${Math.round(customs * 100)}%`}
          min={0}
          max={1}
          step={0.01}
          onChange={setCustoms}
        />
        <Slider
          label="كلفة الإنتاج المحلي للكغ"
          value={localJod}
          display={`${localJod.toFixed(2)} دينار`}
          ltr={false}
          min={0.05}
          max={localMax}
          step={0.01}
          onChange={setLocalJod}
        />
        <div className="flex items-center gap-3 md:justify-end" aria-live="polite">
          <p className="font-display text-[1.75rem] leading-none font-bold text-ink" dir="ltr">
            <span className="text-ink-muted">{baseScore.toFixed(1)}</span>
            <span className="mx-2 text-[1.25rem] text-ink-muted">→</span>
            <span>{shown ? shown.score.toFixed(1) : '—'}</span>
          </p>
          {verdict && (
            <span className={`rounded-[4px] px-2.5 py-1 font-display text-[13px] font-semibold ${verdict.badge}`}>
              {verdict.label}
            </span>
          )}
        </div>
      </div>

      <p className="mt-4 text-[12.5px] leading-[1.8] text-ink-muted">
        {failed
          ? 'تعذّر حساب السيناريو الآن، حاول مرة أخرى.'
          : 'سيناريو افتراضي: الدرجة تُحسب فوراً من البيانات نفسها، والشرح أعلاه لا يتغيّر.'}
      </p>
    </section>
  );
}
