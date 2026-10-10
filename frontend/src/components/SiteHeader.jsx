export function BrandMark({ className = 'size-8' }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <rect width="32" height="32" rx="8" fill="#1e4fd6" />
      <circle cx="16" cy="16" r="8.5" fill="none" stroke="#fff" strokeWidth="3" strokeDasharray="4.2 2.47" />
      <circle cx="16" cy="16" r="3" fill="#f0641e" />
    </svg>
  );
}

export default function SiteHeader() {
  return (
    <header className="site-header absolute inset-x-0 top-0 z-30">
      <div className="mx-auto flex h-20 max-w-[1320px] items-center justify-between px-5 md:h-24 md:px-10">
        <a
          href="/"
          className="flex items-center gap-3 rounded-lg focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-signal"
          aria-label="صنّعها — الصفحة الرئيسية"
        >
          <BrandMark />
          <span className="font-display text-[1.375rem] font-bold text-ink">صنّعها</span>
        </a>
        <a
          href="#product-input"
          className="header-link rounded-md text-sm font-medium text-ink-muted underline-offset-[6px] transition-colors duration-150 hover:text-ink hover:underline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-signal"
        >
          ابدأ التقييم
        </a>
      </div>
    </header>
  );
}
