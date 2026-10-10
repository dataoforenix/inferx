import { useEffect, useState } from 'react';
import { motion, useMotionValue, useReducedMotion, useSpring } from 'motion/react';

// Things the ring grows over. Text fields get the native I-beam instead (see index.css).
const INTERACTIVE = 'a, button, summary, label, select, [role="button"], input[type="range"], input[type="file"]';
const TEXT = 'textarea, input:not([type="range"]):not([type="file"]):not([type="checkbox"]):not([type="radio"])';
const RING = { stiffness: 520, damping: 38, mass: 0.6 };

/**
 * Precision cursor: a dot exactly at the pointer and a ring that trails it on a spring.
 * Mouse only (fine pointer + hover); the native cursor stays everywhere else and over text fields.
 */
export default function SiteCursor() {
  const reduce = useReducedMotion();
  const [enabled, setEnabled] = useState(false);
  const [mode, setMode] = useState('idle'); // idle | hover | text | hidden
  const [pressed, setPressed] = useState(false);

  const x = useMotionValue(-100);
  const y = useMotionValue(-100);
  const rx = useSpring(x, RING);
  const ry = useSpring(y, RING);

  useEffect(() => {
    const mq = window.matchMedia('(hover: hover) and (pointer: fine)');
    const sync = () => setEnabled(mq.matches);
    sync();
    mq.addEventListener('change', sync);
    return () => mq.removeEventListener('change', sync);
  }, []);

  useEffect(() => {
    if (!enabled) return undefined;
    const root = document.documentElement;
    root.classList.add('has-cursor');

    const onMove = (e) => {
      if (e.pointerType !== 'mouse') return;
      x.set(e.clientX);
      y.set(e.clientY);
    };
    const onOver = (e) => {
      const el = e.target instanceof Element ? e.target : null;
      if (!el) return;
      if (el.closest(TEXT)) setMode('text');
      else if (el.closest(INTERACTIVE)) setMode('hover');
      else setMode('idle');
    };
    const onDown = () => setPressed(true);
    const onUp = () => setPressed(false);
    const onLeave = () => setMode('hidden');

    window.addEventListener('pointermove', onMove, { passive: true });
    window.addEventListener('pointerover', onOver, { passive: true });
    window.addEventListener('pointerdown', onDown, { passive: true });
    window.addEventListener('pointerup', onUp, { passive: true });
    root.addEventListener('mouseleave', onLeave);
    return () => {
      root.classList.remove('has-cursor');
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerover', onOver);
      window.removeEventListener('pointerdown', onDown);
      window.removeEventListener('pointerup', onUp);
      root.removeEventListener('mouseleave', onLeave);
    };
  }, [enabled, x, y]);

  if (!enabled) return null;

  const hidden = mode === 'text' || mode === 'hidden';
  const hover = mode === 'hover';
  const ringScale = hidden ? 0.4 : pressed ? 0.75 : hover ? 1.55 : 1;

  return (
    <div className="pointer-events-none fixed inset-0 z-[100]" aria-hidden="true">
      <motion.div
        style={{ x: reduce ? x : rx, y: reduce ? y : ry }}
        className="absolute top-0 left-0"
      >
        <span
          className={`absolute size-8 -translate-x-1/2 -translate-y-1/2 rounded-full border transition-[scale,opacity,background-color,border-color] duration-200 ease-(--ease-out) ${
            hover ? 'border-ink/0 bg-accent/35' : 'border-ink/45 bg-transparent'
          }`}
          style={{ scale: ringScale, opacity: hidden ? 0 : 1 }}
        />
      </motion.div>
      <motion.div style={{ x, y }} className="absolute top-0 left-0">
        <span
          className="absolute size-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-ink transition-opacity duration-150"
          style={{ opacity: hidden ? 0 : 1 }}
        />
      </motion.div>
    </div>
  );
}
