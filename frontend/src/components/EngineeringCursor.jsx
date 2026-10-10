import { useEffect, useRef, useState } from 'react';
import { useReducedMotion } from 'motion/react';

const INTERACTIVE = 'a, button, summary, [role="button"], input[type="range"], input[type="file"], select, label, [data-cursor]';
// Over text fields the gear steps aside for the native I-beam (see .has-cursor in index.css).
const TEXT = 'textarea, input:not([type="range"]):not([type="file"]):not([type="checkbox"]):not([type="radio"])';

function gearPath(teeth, outer, root, hole) {
  const step = (Math.PI * 2) / teeth;
  let d = '';
  for (let i = 0; i < teeth; i++) {
    const a = i * step;
    [
      [root, a],
      [outer, a + step * 0.2],
      [outer, a + step * 0.5],
      [root, a + step * 0.7],
    ].forEach(([r, t], j) => {
      d += `${i === 0 && j === 0 ? 'M' : 'L'}${(Math.cos(t) * r).toFixed(2)} ${(Math.sin(t) * r).toFixed(2)} `;
    });
  }
  d += `Z M${hole} 0 A${hole} ${hole} 0 1 0 ${-hole} 0 A${hole} ${hole} 0 1 0 ${hole} 0 Z`;
  return d;
}

const GEAR = gearPath(10, 10, 7.6, 3.2);

/**
 * Gear cursor (mouse only): it rolls as the pointer travels, like a gear on a rack,
 * and engages (grows, turns the accent yellow, spins) over anything clickable.
 */
export default function EngineeringCursor() {
  const reduce = useReducedMotion();
  const [enabled] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(hover: hover) and (pointer: fine)').matches,
  );
  const [action, setAction] = useState(false);
  const [pressed, setPressed] = useState(false);
  const [visible, setVisible] = useState(false);
  const [overText, setOverText] = useState(false);
  const posRef = useRef(null);
  const gearRef = useRef(null);
  const actionRef = useRef(false);

  useEffect(() => {
    if (!enabled) return undefined;
    const root = document.documentElement;
    root.classList.add('has-cursor');
    let last = null;
    let angle = 0;
    let shown = 0;
    let frame = 0;
    let x = -100;
    let y = -100;
    const loop = () => {
      // Over actions the gear idles forward; otherwise it eases toward the rolled angle.
      if (actionRef.current && !reduce) angle += 4;
      shown += (angle - shown) * 0.35;
      if (posRef.current) posRef.current.style.transform = `translate3d(${x}px, ${y}px, 0)`;
      if (gearRef.current) gearRef.current.style.transform = `rotate(${shown.toFixed(1)}deg)`;
      frame = Math.abs(angle - shown) > 0.1 || actionRef.current ? requestAnimationFrame(loop) : 0;
    };
    const kick = () => {
      if (!frame) frame = requestAnimationFrame(loop);
    };
    const onMove = (e) => {
      x = e.clientX;
      y = e.clientY;
      if (last && !reduce) {
        // Circumference ≈ 63px at r = 10: roll by the dominant travel axis.
        const dx = x - last.x;
        const dy = y - last.y;
        angle += ((Math.abs(dx) > Math.abs(dy) ? -dx : dy) / 63) * 360;
      }
      last = { x, y };
      setOverText(Boolean(e.target.closest?.(TEXT)));
      const isAction = Boolean(e.target.closest?.(INTERACTIVE));
      actionRef.current = isAction;
      setAction(isAction);
      setVisible(true);
      kick();
    };
    const onDown = () => setPressed(true);
    const onUp = () => setPressed(false);
    const onLeave = () => setVisible(false);
    window.addEventListener('pointermove', onMove, { passive: true });
    window.addEventListener('pointerdown', onDown);
    window.addEventListener('pointerup', onUp);
    root.addEventListener('mouseleave', onLeave);
    return () => {
      cancelAnimationFrame(frame);
      root.classList.remove('has-cursor');
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerdown', onDown);
      window.removeEventListener('pointerup', onUp);
      root.removeEventListener('mouseleave', onLeave);
    };
  }, [enabled, reduce]);

  if (!enabled) return null;

  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 z-[100] transition-opacity duration-200"
      style={{ opacity: visible && !overText ? 1 : 0 }}
    >
      <div ref={posRef} className="absolute top-0 left-0 will-change-transform">
        <div
          className="-mt-3 -ml-3 size-6 transition-transform duration-200 ease-(--ease-out)"
          style={{ transform: `scale(${pressed ? 0.82 : action ? 1.4 : 1})` }}
        >
          <svg viewBox="-12 -12 24 24" className="size-6 overflow-visible drop-shadow-[0_2px_3px_rgb(21_24_27/0.25)]">
            <g ref={gearRef}>
              <path
                d={GEAR}
                fillRule="evenodd"
                stroke="#f9faf9"
                strokeWidth="1.4"
                paintOrder="stroke"
                className={`transition-[fill] duration-200 ${action ? 'fill-accent' : 'fill-ink'}`}
              />
            </g>
            <circle r="1.5" className={`transition-[fill] duration-200 ${action ? 'fill-ink' : 'fill-paper'}`} />
          </svg>
        </div>
      </div>
    </div>
  );
}
