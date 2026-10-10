import { BrandMark } from './SiteHeader';

const SOURCES = ['UN Comtrade', 'WITS / TRAINS', 'قوائم أسعار الموردين'];

export default function SiteFooter() {
  return (
    <footer className="border-t border-hairline">
      <div className="mx-auto flex max-w-[1320px] flex-col gap-8 px-5 py-12 md:flex-row md:items-end md:justify-between md:px-10">
        <div className="max-w-[46ch]">
          <p className="flex items-center gap-3">
            <BrandMark className="size-7" />
            <span className="font-display text-lg font-bold text-ink">صنّعها</span>
          </p>
          <p className="mt-4 text-[14px] leading-[1.9] text-ink-muted">
            تقييم أوّلي لفرص تصنيع المنتجات محلياً. النتائج استرشادية ولا تغني عن دراسة جدوى تفصيلية.
          </p>
        </div>
        <div>
          <p className="text-[12px] font-medium text-ink-muted">مصادر البيانات</p>
          <ul className="mt-2 space-y-1">
            {SOURCES.map((s) => (
              <li key={s} className="text-[14px] text-ink/80">
                {s}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </footer>
  );
}
