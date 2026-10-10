import { ListChecks, MapPin, Wallet, Wrench } from 'lucide-react';
import ReportButton from './ReportButton';
import ReportSheet from './ReportSheet';

function PlanCard({ icon: Icon, title, i, children }) {
  return (
    <article
      className="rise-in flex min-w-0 flex-col rounded-2xl border border-hairline bg-white/75 p-4 shadow-[0_24px_48px_-36px_rgb(14_23_38/0.35)] backdrop-blur-sm lg:rounded-3xl lg:p-6"
      style={{ '--i': i }}
    >
      <header className="flex items-center gap-2 lg:gap-3">
        <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-brand/8 text-brand lg:size-9 lg:rounded-xl">
          <Icon className="size-4 lg:size-[18px]" strokeWidth={1.75} aria-hidden="true" />
        </span>
        <h4 className="text-[13px] leading-snug font-semibold text-ink lg:text-[15px]">{title}</h4>
      </header>
      {children}
    </article>
  );
}

export default function ActionPlan({ result }) {
  const { plan } = result;

  return (
    <section className="mt-14" aria-labelledby="plan-heading">
      <div className="rise-in mb-6 flex flex-col gap-4 md:flex-row md:items-end md:justify-between" style={{ '--i': 7 }}>
        <div>
          <h3 id="plan-heading" className="font-display text-[1.5rem] font-semibold text-ink">
            الخطوة التالية
          </h3>
          <p className="mt-2 text-[14px] text-ink-muted">
            {result.verdict === 'go'
              ? 'ما تحتاجه لتبدأ، بأرقام تقريبية من بيانات المنتج.'
              : 'إذا قررت المضي، هذا ما تحتاجه بأرقام تقريبية.'}
          </p>
        </div>
        <ReportButton
          productName={result.productName}
          renderSheet={() => <ReportSheet result={result} />}
        />
      </div>

      <div className="grid gap-3 md:grid-cols-3 lg:gap-4">
        <PlanCard icon={Wallet} title="رأس مال المكائن" i={8}>
          {plan.capital ? (
            <>
              <p className="mt-3 font-display text-[1.375rem] leading-[1.4] font-semibold text-ink lg:mt-5">
                من {plan.capital.minK} إلى {plan.capital.maxK} ألف دينار
              </p>
              <p className="mt-1.5 text-[12px] leading-[1.7] text-ink-muted lg:text-[12.5px]">
                {plan.capitalNote ?? 'كلفة المكائن فقط، تقدير تقريبي'}
              </p>
              {plan.breakEven && (
                <p className="mt-3 text-[12.5px] leading-[1.8] text-ink/80 lg:text-[13.5px]">{plan.breakEven}</p>
              )}
            </>
          ) : (
            <p className="mt-3 text-[14px] text-ink-muted lg:mt-5">التقدير غير متوفر لهذا المنتج بعد.</p>
          )}
          {plan.factories && (
            <div className="mt-auto pt-4 lg:pt-5">
              <p className="border-t border-hairline pt-3 text-[12.5px] leading-[1.75] text-ink/80 lg:text-[13.5px]">
                {plan.factories}
              </p>
            </div>
          )}
        </PlanCard>

        <PlanCard icon={Wrench} title="المكائن المطلوبة" i={9}>
          <ul className="mt-3 space-y-2 lg:mt-5 lg:space-y-2.5">
            {plan.machines.map((m) => (
              <li key={m} className="flex gap-2 text-[12.5px] leading-[1.75] text-ink/80 lg:gap-2.5 lg:text-[14px] lg:leading-[1.8]">
                <span className="mt-[0.7em] size-1.5 shrink-0 bg-brand" aria-hidden="true" />
                {m}
              </li>
            ))}
          </ul>
        </PlanCard>

        {plan.steps.length > 0 ? (
          <PlanCard icon={ListChecks} title="خطوات البداية" i={10}>
            <ol className="mt-3 space-y-2.5 lg:mt-5">
              {plan.steps.map((step, n) => (
                <li key={step} className="flex gap-2.5 text-[12.5px] leading-[1.8] text-ink/80 lg:text-[14px]">
                  <span className="font-mono text-[12px] leading-[2] text-brand" dir="ltr">
                    0{n + 1}
                  </span>
                  {step}
                </li>
              ))}
            </ol>
            {plan.rawMaterials && (
              <p className="mt-3 text-[12px] leading-[1.75] text-ink-muted lg:text-[12.5px] lg:leading-[1.8]">
                المواد الخام: {plan.rawMaterials}
              </p>
            )}
          </PlanCard>
        ) : (
          <PlanCard icon={MapPin} title="أين تبدأ في الأردن" i={10}>
            <p className="mt-3 text-[12.5px] leading-[1.8] text-ink/80 lg:mt-5 lg:text-[14px] lg:leading-[1.85]">
              {plan.workshops}
            </p>
            <p className="mt-3 text-[12px] leading-[1.75] text-ink-muted lg:text-[12.5px] lg:leading-[1.8]">
              المواد الخام: {plan.rawMaterials}
            </p>
          </PlanCard>
        )}
      </div>

    </section>
  );
}
