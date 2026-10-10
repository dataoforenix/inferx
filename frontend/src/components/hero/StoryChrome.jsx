import { useState } from 'react';
import { motion, useMotionValueEvent, useTransform } from 'motion/react';
import { OPENING_STEPS, range } from '../../lib/timeline';

/** Opening HUD: current beat, a precise progress line, and a skip control. */
export function OpeningChrome({ story, onSkip, visible }) {
  const [step, setStep] = useState(0);
  const opacity = useTransform(story, [0.74, 0.84], [1, 0]);
  const fill = useTransform(story, (v) => `scaleX(${range(v, 0, 0.8)})`);
  useMotionValueEvent(story, 'change', (v) => {
    let i = 0;
    OPENING_STEPS.forEach((s, idx) => {
      if (v >= s.at) i = idx;
    });
    setStep((prev) => (prev === i ? prev : i));
  });

  if (!visible) return null;

  return (
    <motion.div style={{ opacity }} className="absolute inset-x-0 bottom-0 z-20 px-5 pb-8 md:px-10 md:pb-10">
      <div className="mx-auto flex max-w-[1320px] items-end justify-between gap-6">
        <div className="flex items-center gap-4" aria-live="polite">
          <span className="h-px w-32 overflow-hidden bg-ink/12 md:w-56">
            <motion.span style={{ transform: fill }} className="block h-full origin-right bg-accent" />
          </span>
          <span key={step} className="rise-in text-[13px] font-medium text-ink">
            {OPENING_STEPS[step].label}
          </span>
        </div>
        <button
          type="button"
          onClick={onSkip}
          className="rounded-md px-1 text-[13px] font-medium text-ink-muted transition-colors duration-150 hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-signal"
        >
          تخطّي ←
        </button>
      </div>
    </motion.div>
  );
}
