import { useEffect, useState } from 'react';
import { ArrowCounterClockwise, SlidersHorizontal } from '@phosphor-icons/react';
import { postWhatIf, USD_TO_JOD } from '../lib/api';

const DEBOUNCE_MS = 150;

function Slider({ label, hint, value, display, min, max, step, onChange, ltr = true }) {
  return (
    <label className="block">
      <span className="flex items-baseline justify-between gap-3 text-[14px]">
        <span className="font-medium text-ink">{label}</span>
        <span className={`text-[13.5px] font-semibold text-ink ${ltr ? 'font-mono' : ''}`} dir={ltr ? 'ltr' : undefined}>
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
      <span className="mt-1 block text-[12px] text-ink-muted">{hint}</span>
    </label>
  );
}

const round2 = (v) => Math.round(v * 100) / 100;
const upTo = (base, factor, floor) => Math.max(floor, Math.ceil(base * factor * 10) / 10);

/**
 * "What if?" scenario: change customs, the local cost or the import price and re-score instantly via
 * POST /api/whatif (pure Python on the backend, no AI call). Shown open, as its own section.
 */
export default function WhatIf({ whatIf, baseScore, verdicts }) {
  const hasImport = whatIf.importPriceJod != null;
  const [customs, setCustoms] = useState(whatIf.customsPct);
  const [localJod, setLocalJod] = useState(whatIf.localCostJod);
  const [importJod, setImportJod] = useState(whatIf.importPriceJod);
  const [scenario, setScenario] = useState(null);
  const [failed, setFailed] = useState(false);

  const changed =
    customs !== whatIf.customsPct || localJod !== whatIf.localCostJod || (hasImport && importJod !== whatIf.importPriceJod);

  useEffect(() => {
    if (!changed) return undefined;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      const overrides = { customs_pct: customs, local_cost_per_kg_est_usd: localJod / USD_TO_JOD };
      if (hasImport) overrides.import_price_per_kg_usd = importJod / USD_TO_JOD;
      postWhatIf(whatIf.categoryId, overrides, controller.signal)
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
  }, [changed, customs, localJod, importJod, hasImport, whatIf]);

  const reset = () => {
    setCustoms(whatIf.customsPct);
    setLocalJod(whatIf.localCostJod);
    setImportJod(whatIf.importPriceJod);
  };

  // A stale scenario from before "reset" is ignored rather than cleared in the effect.
  const shown = changed ? scenario : null;
  const verdict = shown && verdicts[shown.verdict];

  return (
    <section aria-labelledby="whatif-heading" className="rise-in mt-14" style={{ '--i': 7 }}>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h3 id="whatif-heading" className="flex items-center gap-2.5 font-display text-[1.75rem] font-bold text-ink">
            <SlidersHorizontal className="size-7" aria-hidden="true" />
            جرّب سيناريو: ماذا لو؟
          </h3>
          <p className="mt-2 max-w-[62ch] text-[14.5px] leading-[1.8] text-ink-muted">
            حرّك الأرقام وشاهد كيف يتغيّر التقييم فوراً، مثلاً لو ارتفع الجمرك أو أسعار المستورد، أو وجدت مواد أرخص.
          </p>
        </div>
        <button
          type="button"
          onClick={reset}
          disabled={!changed}
          className="inline-flex h-10 items-center gap-1.5 rounded-[10px] px-3 text-[14px] text-ink-muted transition-colors duration-150 hover:bg-white hover:text-ink disabled:opacity-40 disabled:hover:bg-transparent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal"
        >
          <ArrowCounterClockwise className="size-4" aria-hidden="true" />
          القيم الأصلية
        </button>
      </div>

      <div className="mt-6 grid gap-3 lg:grid-cols-12 lg:gap-4">
        <div className="grid gap-6 rounded-[16px] border border-hairline bg-white p-5 sm:grid-cols-2 lg:col-span-8 lg:grid-cols-3 lg:p-7">
          <Slider
            label="الجمرك على المستورد"
            hint={`الأصلي ${Math.round(whatIf.customsPct * 100)}%`}
            value={customs}
            display={`${Math.round(customs * 100)}%`}
            min={0}
            max={1}
            step={0.01}
            onChange={setCustoms}
          />
          <Slider
            label="كلفة الإنتاج المحلي للكغ"
            hint={`الأصلي ${whatIf.localCostJod.toFixed(2)} دينار (تقدير)`}
            value={localJod}
            display={`${localJod.toFixed(2)} دينار`}
            ltr={false}
            min={0.05}
            max={upTo(whatIf.localCostJod, 2, 0.5)}
            step={0.01}
            onChange={(v) => setLocalJod(round2(v))}
          />
          {hasImport && (
            <Slider
              label="سعر المستورد للكغ"
              hint={`الأصلي ${whatIf.importPriceJod.toFixed(2)} دينار، قبل الجمرك`}
              value={importJod}
              display={`${importJod.toFixed(2)} دينار`}
              ltr={false}
              min={0.05}
              max={upTo(whatIf.importPriceJod, 2, 0.5)}
              step={0.01}
              onChange={(v) => setImportJod(round2(v))}
            />
          )}
        </div>

        <div className="flex flex-col justify-between rounded-[16px] bg-brand p-5 text-white lg:col-span-4 lg:p-7" aria-live="polite">
          <p className="text-[13px] font-medium text-white/65">التقييم في هذا السيناريو</p>
          <div className="mt-3 flex flex-wrap items-center gap-4">
            <p className="font-display leading-none font-bold tabular-nums" dir="ltr">
              <span className="text-[1.75rem] text-white/45">{baseScore.toFixed(1)}</span>
              <span className="mx-2 text-[1.25rem] text-white/45">→</span>
              <span className="text-[3rem]">{shown ? shown.score.toFixed(1) : baseScore.toFixed(1)}</span>
            </p>
            {verdict && (
              <span className={`rounded-[4px] px-2.5 py-1 font-display text-[14px] font-semibold ${verdict.badgeDark}`}>
                {verdict.label}
              </span>
            )}
          </div>
          <p className="mt-5 text-[12.5px] leading-[1.8] text-white/60">
            {failed
              ? 'تعذّر حساب السيناريو الآن، حاول مرة أخرى.'
              : changed
                ? 'سيناريو افتراضي: الشرح أعلاه لا يتغيّر.'
                : 'حرّك أي شريط لترى التقييم الجديد.'}
          </p>
        </div>
      </div>
    </section>
  );
}
