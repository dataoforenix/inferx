import { motion, useTransform } from 'motion/react';
import MakeItButton from './MakeItButton';

/** Each line rises in as the part settles beside the headline (end of the opening). */
function Reveal({ story, i, className, children, as = 'div' }) {
  const start = 0.78 + i * 0.03;
  const opacity = useTransform(story, [start, start + 0.1], [0, 1]);
  const transform = useTransform(story, [start, Math.min(start + 0.14, 1)], ['translateY(18px)', 'translateY(0px)']);
  const Tag = motion[as];
  return (
    <Tag style={{ opacity, transform }} className={className}>
      {children}
    </Tag>
  );
}

export default function HeroCopy({ story }) {
  const visibility = useTransform(story, (v) => (v < 0.8 ? 'hidden' : 'visible'));

  return (
    <motion.div
      style={{ visibility }}
      className="relative z-10 mx-auto flex h-full max-w-[1320px] flex-col justify-end px-5 pb-[8svh] md:justify-center md:px-10 md:pb-0"
    >
      <div className="md:w-[58%] md:max-w-[720px]">
        <Reveal story={story} i={0} as="p" className="flex items-center gap-2.5 text-[13px] font-medium text-ink-muted">
          <span aria-hidden="true" className="inline-block size-1.5 bg-signal" />
          تقييم جدوى التصنيع المحلي
        </Reveal>

        <Reveal
          story={story}
          i={1}
          as="h1"
          className="mt-4 font-display text-[clamp(1.85rem,0.9rem+3.3vw,3.9rem)] leading-[1.2] font-bold text-ink md:mt-6"
        >
          <span id="hero-title">
            <span className="whitespace-nowrap">هل يستحق هذا المنتج</span>
            <br />
            التصنيع <span className="text-brand">محلياً</span>؟
          </span>
        </Reveal>

        <Reveal
          story={story}
          i={2}
          as="p"
          className="mt-5 max-w-[36ch] text-[1.0625rem] leading-[1.9] text-ink-muted md:mt-7 md:text-[1.1875rem]"
        >
          ارفع صورة المنتج أو اكتب اسمه، ونقيس لك فرص تصنيعه محلياً، من حجم السوق والكلفة إلى جاهزية المصانع.
        </Reveal>

        <Reveal story={story} i={3} className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-3 md:mt-10">
          <MakeItButton />
          <p className="text-sm text-ink-muted">صورة واحدة أو اسم المنتج يكفي.</p>
        </Reveal>
      </div>
    </motion.div>
  );
}
