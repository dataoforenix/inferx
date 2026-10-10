// The printable report, rendered off-screen only while a PDF is being made.
// Each [data-report-page] is captured as one A4 page (794 × 1123 CSS px).
// html2canvas can't parse color-mix(), so stick to solid colors here:
// no Tailwind opacity modifiers (`/75`) and no backdrop blur.

import EstimateTag from './EstimateTag';

const VERDICT = {
  go: { label: 'صنّعها', badge: 'bg-brand text-white' },
  maybe: { label: 'ربما', badge: 'bg-[#fdf3dc] text-[#8a5a00]' },
  no: { label: 'لا تصنّعها', badge: 'bg-[#fdeee5] text-[#b4400e]' },
};

const today = () => new Intl.DateTimeFormat('ar-JO-u-nu-latn', { dateStyle: 'long' }).format(new Date());

function Page({ children, n, total, title = 'تقرير جدوى التصنيع المحلي' }) {
  return (
    <div data-report-page className="flex h-[1123px] w-[794px] flex-col bg-paper px-14 pt-12 pb-10 text-ink">
      <header className="flex items-center justify-between border-b border-ink pb-4">
        <p className="font-display text-[22px] font-bold text-brand">صنّعها</p>
        <p className="text-[13px] text-ink-muted">
          {title} · {today()}
        </p>
      </header>
      <div className="flex-1">{children}</div>
      <footer className="flex items-center justify-between border-t border-hairline pt-3 text-[11px] text-ink-muted">
        <span>أرقام تقريبية، ولا تغني عن دراسة جدوى تفصيلية.</span>
        <span className="font-mono" dir="ltr">
          {n} / {total}
        </span>
      </footer>
    </div>
  );
}

function SheetFactor({ factor }) {
  const risk = factor.id === 'risk';
  const est = factor.est ?? {};
  return (
    <div className={`rounded-2xl border p-5 ${risk ? 'border-[#f6c8ad] bg-[#fff7f1]' : 'border-hairline bg-white'}`}>
      <p className={`text-[13px] font-semibold ${risk ? 'text-[#b4400e]' : 'text-brand'}`}>{factor.title}</p>
      <p className="mt-2 font-display text-[16px] leading-[1.6] font-semibold">
        {factor.headline}
        <EstimateTag show={est.headline} plain />
      </p>
      <p className="mt-1 text-[11.5px] text-ink-muted">
        {factor.caption}
        <EstimateTag show={est.caption && !est.headline} plain />
      </p>
      {factor.body && (
        <p className="mt-3 text-[12.5px] leading-[1.8]">
          {factor.body}
          <EstimateTag show={est.body} plain />
        </p>
      )}
      {factor.list && (
        <ul className="mt-3 space-y-1.5">
          {factor.list.map((item) => (
            <li key={item} className="flex gap-2 text-[12.5px] leading-[1.75]">
              <span className="mt-[0.7em] size-1.5 shrink-0 bg-signal" />
              {item}
            </li>
          ))}
        </ul>
      )}
      {factor.meta && (
        <p className="mt-2 text-[11.5px] leading-[1.75] text-ink-muted">
          {factor.meta}
          <EstimateTag show={est.meta} plain />
        </p>
      )}
      <p className="mt-3 text-[11px] text-ink-muted">المصدر: {factor.source}</p>
    </div>
  );
}

/** Hidden on screen; exportReportPdf makes it visible only inside html2canvas's clone. */
function SheetRoot({ children }) {
  return (
    <div aria-hidden="true" dir="rtl" className="pointer-events-none invisible absolute top-0 left-0 font-sans">
      {children}
    </div>
  );
}

function SheetList({ items, numbered = false, dot = 'bg-brand' }) {
  const Tag = numbered ? 'ol' : 'ul';
  return (
    <Tag className="mt-3 space-y-2">
      {items.map((item, n) => (
        <li key={item} className="flex gap-2.5 text-[13.5px] leading-[1.8]">
          {numbered ? (
            <span className="font-mono text-[12px] leading-[2] text-brand">0{n + 1}</span>
          ) : (
            <span className={`mt-[0.7em] size-1.5 shrink-0 ${dot}`} />
          )}
          {item}
        </li>
      ))}
    </Tag>
  );
}

/** One-page report for a market_preview: what we found, what's missing to judge, and how to check. */
export function PreviewSheet({ outcome }) {
  return (
    <SheetRoot>
      <Page n={1} total={1} title="مسح أولي للسوق">
        <section className="mt-8">
          <span className="inline-block rounded-full bg-[#fdf3dc] px-4 py-1 font-display text-[14px] font-semibold text-[#8a5a00]">
            ربما: البيانات لا تكفي لحكم كامل
          </span>
          <h1 className="mt-4 font-display text-[26px] leading-[1.45] font-semibold">{outcome.productName}</h1>
          <p className="mt-2 text-[12.5px] text-ink-muted">
            رمز HS مقترح: <span className="font-mono text-ink">{outcome.hsCode}</span>{' '}
            <span className="text-[#8a5a00]">(اقترحه الذكاء الاصطناعي، تأكّد منه)</span>
          </p>
        </section>

        {outcome.summary && <p className="mt-6 text-[14px] leading-[1.9]">{outcome.summary}</p>}

        <section className="mt-6 rounded-2xl border border-hairline bg-white p-6">
          <p className="text-[13px] font-semibold text-brand">السوق: بيانات رسمية</p>
          <p className="mt-2 font-display text-[24px] font-semibold">{outcome.importsLatest ?? 'لا تتوفر بيانات'}</p>
          <p className="mt-1 text-[12px] text-ink-muted">واردات الأردن في 2024 · المصدر: UN Comtrade</p>
          {outcome.trend && <p className="mt-3 text-[13px]">{outcome.trend}</p>}
        </section>

        <section className="mt-4 rounded-2xl border border-[#f1dca8] bg-[#fffaf0] p-6">
          <p className="text-[13px] font-semibold text-[#8a5a00]">لماذا لا يوجد حكم كامل؟ ما ينقصنا لنحكم</p>
          <SheetList items={outcome.missing} dot="bg-[#c98a0b]" />
        </section>

        <section className="mt-4 rounded-2xl border border-hairline bg-white p-6">
          <p className="text-[13px] font-semibold text-brand">خطوات للتحقق</p>
          <SheetList items={outcome.steps} numbered />
        </section>

        <p className="mt-6 text-[12px] leading-[1.9] text-ink-muted">
          هذا مسح أولي فقط: أرقام الواردات رسمية، أما التكلفة والتصنيع والمنافسة فلم تُقيَّم بعد لعدم توفر بياناتها.
        </p>
      </Page>
    </SheetRoot>
  );
}

export default function ReportSheet({ result }) {
  const { plan } = result;
  return (
    <SheetRoot>
      <Page n={1} total={2}>
        <section className="mt-8 flex items-start justify-between gap-8">
          <div className="min-w-0">
            <span
              className={`inline-block rounded-full px-4 py-1 font-display text-[14px] font-semibold ${VERDICT[result.verdict].badge}`}
            >
              {VERDICT[result.verdict].label}
            </span>
            <h1 className="mt-4 font-display text-[26px] leading-[1.45] font-semibold">{result.productName}</h1>
            <p className="mt-2 text-[12.5px] text-ink-muted">
              رمز النظام المنسّق: <span className="font-mono text-ink">HS {result.hsCode}</span>
            </p>
          </div>
          <div className="shrink-0 rounded-2xl border border-hairline bg-white px-6 py-4 text-center">
            <p className="font-display text-[40px] leading-none font-bold text-brand">{result.score.toFixed(1)}</p>
            <p className="mt-2 font-mono text-[12px] text-ink-muted" dir="ltr">
              / 10
            </p>
          </div>
        </section>

        {result.summary && <p className="mt-6 text-[14px] leading-[1.9]">{result.summary}</p>}
        {result.formula && (
          <p className="mt-4 rounded-xl border border-hairline bg-white px-4 py-3 text-[12px] leading-[1.85] text-ink-muted">
            {result.formula}
          </p>
        )}

        <h2 className="mt-8 font-display text-[18px] font-semibold">العوامل الأربعة</h2>
        <div className="mt-4 grid grid-cols-2 gap-4">
          {result.factors.map((f) => (
            <SheetFactor key={f.id} factor={f} />
          ))}
        </div>
        {result.hasEstimates && (
          <p className="mt-3 text-[11.5px] text-ink-muted">
            الأرقام المعلّمة بـ<EstimateTag show plain /> محسوبة تقريبياً، والباقي من مصادر رسمية.
          </p>
        )}
      </Page>

      <Page n={2} total={2}>
        <h2 className="mt-8 font-display text-[22px] font-semibold">الخطوة التالية</h2>
        <p className="mt-2 text-[13px] text-ink-muted">
          {result.verdict === 'go'
            ? `ما تحتاجه لتبدأ تصنيع «${result.productName}» في الأردن.`
            : 'الحكم الحالي لا ينصح بالتصنيع بعد، لكن إذا قررت المضي فهذا ما تحتاجه.'}
        </p>

        <section className="mt-6 rounded-2xl border border-hairline bg-white p-6">
          <p className="text-[13px] font-semibold text-brand">رأس مال المكائن</p>
          {plan.capital ? (
            <>
              <p className="mt-2 font-display text-[24px] font-semibold">
                من {plan.capital.minK} إلى {plan.capital.maxK} ألف دينار أردني
                <EstimateTag show={plan.est?.capital} plain />
              </p>
              <p className="mt-1 text-[12px] text-ink-muted">{plan.capitalNote ?? 'كلفة المكائن فقط، تقدير تقريبي.'}</p>
              {plan.breakEven && (
                <p className="mt-3 text-[13px] leading-[1.8]">
                  {plan.breakEven}
                  <EstimateTag show={plan.est?.breakEven} plain />
                </p>
              )}
            </>
          ) : (
            <p className="mt-2 text-[13px] text-ink-muted">التقدير غير متوفر لهذا المنتج بعد.</p>
          )}
          {plan.factories && (
            <p className="mt-3 text-[13px]">
              {plan.factories}
              <EstimateTag show={plan.est?.factories} plain />
            </p>
          )}
        </section>

        <section className="mt-4 rounded-2xl border border-hairline bg-white p-6">
          <p className="text-[13px] font-semibold text-brand">المكائن المطلوبة</p>
          <ul className="mt-3 space-y-2">
            {plan.machines.map((m) => (
              <li key={m} className="flex gap-2.5 text-[13.5px] leading-[1.8]">
                <span className="mt-[0.7em] size-1.5 shrink-0 bg-brand" />
                {m}
              </li>
            ))}
          </ul>
        </section>

        <section className="mt-4 rounded-2xl border border-hairline bg-white p-6">
          <p className="text-[13px] font-semibold text-brand">{plan.steps.length > 0 ? 'خطوات البداية' : 'أين تبدأ في الأردن'}</p>
          {plan.steps.length > 0 ? (
            <ol className="mt-3 space-y-2">
              {plan.steps.map((step, n) => (
                <li key={step} className="flex gap-2.5 text-[13.5px] leading-[1.8]">
                  <span className="font-mono text-[12px] leading-[2] text-brand">0{n + 1}</span>
                  {step}
                </li>
              ))}
            </ol>
          ) : (
            <p className="mt-3 text-[13.5px] leading-[1.85]">{plan.workshops}</p>
          )}
          {plan.rawMaterials && (
            <p className="mt-3 text-[12.5px] leading-[1.8] text-ink-muted">المواد الخام: {plan.rawMaterials}</p>
          )}
        </section>

        <section className="mt-8">
          <p className="text-[13px] font-semibold">المصادر</p>
          <p className="mt-2 text-[12px] leading-[1.9] text-ink-muted">
            {result.factors.map((f) => f.source).join(' · ')}
          </p>
        </section>
      </Page>
    </SheetRoot>
  );
}
