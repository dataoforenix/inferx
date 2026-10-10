import { useEffect, useRef, useState } from 'react';
import { ArrowUpLeft, BookOpen, Buildings, Calculator, ListChecks, MagnifyingGlass } from '@phosphor-icons/react';
import { PANEL, TileHeader } from './ActionPlan';
import { formatJod, getMethodology, postBudget } from '../lib/api';

// New backend guidance (FRONTEND_HANDOFF.md, sections 2-6). Built only from the existing tokens and the
// ActionPlan panel/header so the theme is unchanged. Arabic fields only; mandatory captions always shown.

const LINK =
  'inline-flex items-center gap-1 rounded-sm text-[14px] font-medium text-ink underline decoration-ink/25 underline-offset-[6px] hover:decoration-ink focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-signal';
const CAPTION = 'mt-4 rounded-[10px] bg-paper-2/70 px-4 py-3 text-[13px] leading-[1.8] text-ink-muted';
const BUDGET_STATUS = {
  covered: { label: 'تكفي لثمن المعدات', tone: 'text-ink' },
  partial: { label: 'تكفي جزئياً', tone: 'text-ink' },
  short: { label: 'لا تكفي', tone: 'text-signal' },
};

function ExternalLink({ href, children }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className={LINK}>
      {children}
      <ArrowUpLeft className="size-3.5" aria-hidden="true" />
    </a>
  );
}

function BudgetBox({ categoryId }) {
  const [value, setValue] = useState('');
  const [state, setState] = useState({ status: 'idle' });
  const abort = useRef(null);

  useEffect(() => () => abort.current?.abort(), []);

  const onSubmit = async (e) => {
    e.preventDefault();
    const budget = Number(value);
    if (!Number.isFinite(budget) || budget < 0 || value === '') return;
    abort.current?.abort();
    abort.current = new AbortController();
    setState({ status: 'loading' });
    try {
      const body = await postBudget(categoryId, budget, abort.current.signal);
      setState({ status: 'done', body });
    } catch (err) {
      if (err.name === 'AbortError') return;
      setState({ status: 'error' });
    }
  };

  const body = state.body;
  const st = body && BUDGET_STATUS[body.status];
  return (
    <article className={`rise-in ${PANEL} p-6 lg:col-span-6 lg:p-8`} style={{ '--i': 12 }}>
      <TileHeader icon={Calculator}>كم تقدر تستثمر؟ (دينار)</TileHeader>
      <form onSubmit={onSubmit} className="mt-5 flex flex-wrap items-center gap-3" noValidate>
        <label className="sr-only" htmlFor="budget-jod">
          ميزانيتك للمعدات بالدينار
        </label>
        <input
          id="budget-jod"
          type="number"
          inputMode="numeric"
          min="0"
          step="1000"
          dir="ltr"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="50000"
          className="h-11 w-44 rounded-[10px] border border-hairline bg-white px-3 text-[15px] text-ink tabular-nums focus:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal"
        />
        <button
          type="submit"
          disabled={value === '' || state.status === 'loading'}
          className="inline-flex h-11 items-center rounded-[10px] bg-brand px-5 font-display text-[1rem] font-semibold text-white transition-[background-color,opacity,scale] duration-150 ease-(--ease-out) hover:bg-brand-deep focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-signal active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-35 disabled:hover:bg-brand"
        >
          {state.status === 'loading' ? 'جارٍ الحساب…' : 'احسب'}
        </button>
      </form>
      <div aria-live="polite">
        {state.status === 'error' && (
          <p className="mt-4 text-[14px] text-signal">تعذّر الحساب الآن، حاول مرة أخرى.</p>
        )}
        {state.status === 'done' && st && (
          <>
            <p className={`mt-5 font-display text-[1.375rem] font-bold ${st.tone}`}>{st.label}</p>
            <p className="mt-2 text-[14.5px] leading-[1.85] text-ink/85">
              كلفة المعدات من {formatJod(body.capex_jod_range.min)} إلى {formatJod(body.capex_jod_range.max)}
              {body.gap_jod > 0 && <>، ينقصك حوالي {formatJod(body.gap_jod)} للوصول إلى الحد الأعلى</>}.
            </p>
            <p className={CAPTION}>{body.caption_ar}</p>
          </>
        )}
      </div>
    </article>
  );
}

function Methodology() {
  const [state, setState] = useState({ status: 'idle' });
  const onToggle = async (e) => {
    if (!e.currentTarget.open || state.status !== 'idle') return;
    setState({ status: 'loading' });
    try {
      setState({ status: 'done', sections: (await getMethodology()).sections.ar });
    } catch {
      setState({ status: 'error' });
    }
  };
  return (
    <details className="group mt-8" onToggle={onToggle}>
      <summary className={`${LINK} cursor-pointer list-none [&::-webkit-details-marker]:hidden`}>
        <BookOpen className="size-4" aria-hidden="true" />
        كيف نحسب؟
      </summary>
      <div className="mt-4 max-w-[75ch]" aria-live="polite">
        {state.status === 'loading' && <p className="text-[14px] text-ink-muted">جارٍ التحميل…</p>}
        {state.status === 'error' && <p className="text-[14px] text-signal">تعذّر تحميل طريقة الحساب.</p>}
        {state.status === 'done' &&
          state.sections.map((s) => (
            <div key={s.title} className="mt-4">
              <h5 className="text-[14.5px] font-semibold text-ink">{s.title}</h5>
              <p className="mt-1 text-[14px] leading-[1.9] text-ink/85">{s.body}</p>
            </div>
          ))}
      </div>
    </details>
  );
}

export default function GuidancePanels({ guidance }) {
  const { categoryId, hasCapex, nextSteps, advisors, suppliers } = guidance;
  const supplierItems = suppliers?.items ?? [];

  return (
    <section className="mt-16" aria-labelledby="guidance-heading">
      <h3 id="guidance-heading" className="rise-in mb-7 font-display text-[1.75rem] font-bold text-ink" style={{ '--i': 11 }}>
        ابدأ من هنا
      </h3>
      <div className="grid gap-3 lg:grid-cols-12 lg:gap-4">
        {nextSteps.length > 0 && (
          <article className={`rise-in ${PANEL} p-6 lg:col-span-6 lg:p-8`} style={{ '--i': 12 }}>
            <TileHeader icon={ListChecks}>خطوات البدء</TileHeader>
            <ol className="mt-6 space-y-4">
              {nextSteps.map((step, n) => (
                <li key={step} className="grid grid-cols-[2rem_1fr] gap-3 text-[14.5px] leading-[1.85] text-ink/85">
                  <span className="font-display text-[1.5rem] leading-[1.15] font-bold text-ink/20 tabular-nums" dir="ltr">
                    {n + 1}
                  </span>
                  {step}
                </li>
              ))}
            </ol>
          </article>
        )}

        {hasCapex && <BudgetBox categoryId={categoryId} />}

        {advisors.length > 0 && (
          <article className={`rise-in ${PANEL} p-6 lg:col-span-12 lg:p-8`} style={{ '--i': 13 }}>
            <TileHeader icon={Buildings}>جهات تساعدك</TileHeader>
            <ul className="mt-5 grid gap-x-10 gap-y-5 md:grid-cols-2">
              {advisors.map((a) => (
                <li key={a.url} className="text-[14px] leading-[1.75]">
                  <p className="font-semibold text-ink">{a.name_ar}</p>
                  <p className="mt-1 text-ink/85">{a.offer_ar}</p>
                  <p className="mt-1.5">
                    <ExternalLink href={a.url}>الموقع الرسمي</ExternalLink>
                  </p>
                </li>
              ))}
            </ul>
          </article>
        )}

        {suppliers && (supplierItems.length > 0 || suppliers.local_directory) && (
          <article className={`rise-in ${PANEL} p-6 lg:col-span-12 lg:p-8`} style={{ '--i': 14 }}>
            <TileHeader icon={MagnifyingGlass}>موردين محتملين</TileHeader>
            <p className={CAPTION}>{suppliers.caption_ar}</p>
            <ul className="mt-5 gap-x-10 sm:columns-2 lg:columns-3">
              {supplierItems.map((it) => (
                <li key={`${it.kind}-${it.item}`} className="flex break-inside-avoid flex-wrap items-baseline gap-x-2 py-1.5 text-[14px] leading-[1.75] text-ink/85">
                  <span dir="ltr" className="font-medium text-ink">{it.item}</span>
                  <span aria-hidden="true" className="text-ink/40">·</span>
                  {it.links.map((l) => (
                    <ExternalLink key={l.url} href={l.url}>
                      ابحث في {l.marketplace}
                    </ExternalLink>
                  ))}
                </li>
              ))}
            </ul>
            {suppliers.local_directory && (
              <p className="mt-5 text-[14px] leading-[1.75] text-ink/85">
                {suppliers.local_directory.offer_ar}{' '}
                <ExternalLink href={suppliers.local_directory.url}>{suppliers.local_directory.name_ar}</ExternalLink>
              </p>
            )}
          </article>
        )}
      </div>
      <Methodology />
    </section>
  );
}
