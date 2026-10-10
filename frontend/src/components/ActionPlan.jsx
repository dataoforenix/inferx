import { ListNumbers, MapPin, Wallet, Wrench } from '@phosphor-icons/react';
import EstimateTag from './EstimateTag';
import ReportButton from './ReportButton';
import ReportSheet from './ReportSheet';

const PANEL = 'rounded-[16px] border border-hairline bg-white';

function TileHeader({ icon: Icon, children, tone = 'text-ink-muted' }) {
  return (
    <header className={`flex items-center gap-2 ${tone}`}>
      <Icon className="size-5 shrink-0" aria-hidden="true" />
      <h4 className="text-[14.5px] font-semibold">{children}</h4>
    </header>
  );
}

export default function ActionPlan({ result }) {
  const { plan } = result;

  return (
    <section className="mt-16" aria-labelledby="plan-heading">
      <div className="rise-in mb-7 flex flex-col gap-5 md:flex-row md:items-end md:justify-between" style={{ '--i': 7 }}>
        <div>
          <h3 id="plan-heading" className="font-display text-[1.75rem] font-bold text-ink">
            الخطوة التالية
          </h3>
          <p className="mt-2 text-[14.5px] text-ink-muted">
            {result.verdict === 'go'
              ? 'ما تحتاجه لتبدأ، بأرقام تقريبية من بيانات المنتج.'
              : 'إذا قررت المضي، هذا ما تحتاجه بأرقام تقريبية.'}
          </p>
        </div>
        <ReportButton productName={result.productName} renderSheet={() => <ReportSheet result={result} />} />
      </div>

      <div className="grid gap-3 lg:grid-cols-12 lg:gap-4">
        {/* The one dark tile on the page: the number a workshop owner asks first. */}
        <article className="rise-in flex flex-col rounded-[16px] bg-brand p-6 text-white lg:col-span-5 lg:p-8" style={{ '--i': 8 }}>
          <TileHeader icon={Wallet} tone="text-white/65">
            رأس مال المكائن
          </TileHeader>
          {plan.capital ? (
            <>
              <p className="mt-6 font-display leading-[1.15] font-bold">
                <span className="text-[1.25rem] text-white/60">من </span>
                <span className="text-[clamp(2.5rem,2rem+2vw,3.5rem)] tabular-nums">{plan.capital.minK}</span>
                <span className="text-[1.25rem] text-white/60"> إلى </span>
                <span className="text-[clamp(2.5rem,2rem+2vw,3.5rem)] tabular-nums">{plan.capital.maxK}</span>
                <span className="ms-2 text-[1.25rem] text-white/75">ألف دينار</span>
                <EstimateTag show={plan.est?.capital} />
              </p>
              <p className="mt-2 text-[13px] leading-[1.75] text-white/60">{plan.capitalNote ?? 'كلفة المكائن فقط، تقدير تقريبي'}</p>
              {plan.breakEven && (
                <p className="mt-6 border-s-2 border-accent ps-4 text-[14.5px] leading-[1.85] text-white/90">
                  {plan.breakEven}
                  <EstimateTag show={plan.est?.breakEven} />
                </p>
              )}
            </>
          ) : (
            <p className="mt-6 text-[15px] text-white/75">التقدير غير متوفر لهذا المنتج بعد.</p>
          )}
          {plan.factories && (
            <p className="mt-auto pt-8 text-[13.5px] leading-[1.75] text-white/65">
              {plan.factories}
              <EstimateTag show={plan.est?.factories} />
            </p>
          )}
        </article>

        {plan.steps.length > 0 ? (
          <article className={`rise-in ${PANEL} p-6 lg:col-span-7 lg:p-8`} style={{ '--i': 9 }}>
            <TileHeader icon={ListNumbers}>خطوات البداية</TileHeader>
            <ol className="mt-6 space-y-5">
              {plan.steps.map((step, n) => (
                <li key={step} className="grid grid-cols-[2rem_1fr] gap-3 text-[14.5px] leading-[1.85] text-ink/85 lg:text-[15.5px]">
                  <span className="font-display text-[1.5rem] leading-[1.15] font-bold text-ink/20 tabular-nums" dir="ltr">
                    {n + 1}
                  </span>
                  {step}
                </li>
              ))}
            </ol>
          </article>
        ) : (
          <article className={`rise-in ${PANEL} p-6 lg:col-span-7 lg:p-8`} style={{ '--i': 9 }}>
            <TileHeader icon={MapPin}>أين تبدأ في الأردن</TileHeader>
            <p className="mt-6 text-[15px] leading-[1.9] text-ink/85">{plan.workshops}</p>
          </article>
        )}

        <article className={`rise-in ${PANEL} p-6 lg:col-span-12 lg:p-8`} style={{ '--i': 10 }}>
          <TileHeader icon={Wrench}>المكائن المطلوبة</TileHeader>
          <ul className="mt-5 gap-x-10 sm:columns-2 lg:columns-3">
            {plan.machines.map((m) => (
              <li key={m} className="flex break-inside-avoid gap-2.5 py-1.5 text-[14px] leading-[1.75] text-ink/85">
                <span className="mt-[0.85em] h-px w-3 shrink-0 bg-ink/40" aria-hidden="true" />
                {m}
              </li>
            ))}
          </ul>
          {plan.rawMaterials && <p className="mt-4 text-[13.5px] leading-[1.8] text-ink-muted">المواد الخام: {plan.rawMaterials}</p>}
        </article>
      </div>
    </section>
  );
}
