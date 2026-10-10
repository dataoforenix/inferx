import { useState } from 'react';
import { motion, useMotionValueEvent, useTransform } from 'motion/react';
import { OPENING_STEPS, range } from '../../lib/timeline';

/** Registration marks framing the first screen. */
export function CornerMarks() {
  const mark = 'absolute size-4 border-ink/25';
  return (
    <div className="pointer-events-none absolute inset-0" aria-hidden="true">
      <span className={`${mark} top-5 right-5 border-t border-r md:top-6 md:right-6`} />
      <span className={`${mark} top-5 left-5 border-t border-l md:top-6 md:left-6`} />
      <span className={`${mark} right-5 bottom-5 border-r border-b md:right-6 md:bottom-6`} />
      <span className={`${mark} bottom-5 left-5 border-b border-l md:bottom-6 md:left-6`} />
    </div>
  );
}

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
          <span className="font-mono text-[12px] text-brand" dir="ltr">
            0{step} / 03
          </span>
          <span className="h-px w-32 overflow-hidden bg-ink/12 md:w-56">
            <motion.span style={{ transform: fill }} className="block h-full origin-right bg-brand" />
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

/** "Scroll" hint once the site opens; fades as soon as the visitor scrolls. */
export function ScrollCue({ story, scroll }) {
  const opacity = useTransform([story, scroll], ([s, y]) => range(s, 0.94, 1) * (1 - range(y, 0, 0.06)));
  return (
    <motion.div
      style={{ opacity }}
      className="pointer-events-none absolute bottom-7 left-1/2 z-10 hidden -translate-x-1/2 flex-col items-center gap-3 md:flex"
      aria-hidden="true"
    >
      <span className="text-[12.5px] text-ink-muted">مرّر للأسفل</span>
      <span className="relative h-9 w-px overflow-hidden bg-ink/15">
        <span className="cue-dot absolute inset-x-0 top-0 h-1/3 bg-brand" />
      </span>
    </motion.div>
  );
}
