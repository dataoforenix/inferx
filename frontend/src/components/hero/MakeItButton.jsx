import { motion, useMotionTemplate, useMotionValue, useReducedMotion, useSpring } from 'motion/react';
import { ArrowLeft } from '@phosphor-icons/react';

const MAGNET = { stiffness: 320, damping: 22, mass: 0.5 };

/** Primary CTA. A real link (works without JS), with a soft magnetic pull on mouse only. */
export default function MakeItButton({ href = '#product-input', label = 'ابدأ التقييم' }) {
  const reduce = useReducedMotion();
  const mx = useMotionValue(0);
  const my = useMotionValue(0);
  const x = useSpring(mx, MAGNET);
  const y = useSpring(my, MAGNET);
  const transform = useMotionTemplate`translate3d(${x}px, ${y}px, 0)`;

  const onPointerMove = (e) => {
    if (reduce || e.pointerType !== 'mouse') return;
    const r = e.currentTarget.getBoundingClientRect();
    mx.set((e.clientX - (r.left + r.width / 2)) * 0.16);
    my.set((e.clientY - (r.top + r.height / 2)) * 0.26);
  };
  const reset = () => {
    mx.set(0);
    my.set(0);
  };

  const onClick = (e) => {
    const target = document.getElementById(href.slice(1));
    if (!target) return;
    e.preventDefault();
    const focusEl = target.querySelector('[data-autofocus]') ?? target;
    const focus = () => focusEl.focus({ preventScroll: true });
    target.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
    window.history.replaceState(null, '', href);
    if (reduce || !('onscrollend' in window)) setTimeout(focus, reduce ? 0 : 900);
    else window.addEventListener('scrollend', focus, { once: true });
  };

  return (
    <motion.span style={{ transform }} className="inline-block">
      <a
        href={href}
        onClick={onClick}
        onPointerMove={onPointerMove}
        onPointerLeave={reset}
        className="group relative inline-flex h-14 items-center gap-5 rounded-[12px] bg-brand ps-7 pe-2 font-display text-[1.0625rem] font-semibold text-white shadow-[0_16px_30px_-18px_rgb(21_24_27/0.75)] transition-[background-color,scale] duration-150 ease-(--ease-out) select-none hover:bg-brand-deep focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-signal active:scale-[0.98]"
      >
        <span>{label}</span>
        <span aria-hidden="true" className="relative grid size-10 place-items-center overflow-hidden rounded-[9px] bg-accent text-ink">
          <ArrowLeft
            weight="bold"
            className="size-[18px] transition-transform duration-250 ease-(--ease-out) group-hover:-translate-x-[180%]"
          />
          <ArrowLeft
            weight="bold"
            className="absolute size-[18px] translate-x-[180%] transition-transform duration-250 ease-(--ease-out) group-hover:translate-x-0"
          />
        </span>
      </a>
    </motion.span>
  );
}
