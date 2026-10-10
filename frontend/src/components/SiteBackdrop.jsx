import { useEffect, useRef } from 'react';
import { useReducedMotion } from 'motion/react';

const GAP = 26; // px between dots
const REACH = 170; // cursor influence radius
const PUSH = 11; // max displacement near the cursor

/**
 * Fixed "pin-board" behind the page: a precise dot field that breathes slowly,
 * parallaxes with scroll, and parts around the cursor with a blue tint
 * (the cursor position is eased, so it follows like a spring rather than snapping).
 */
export default function SiteBackdrop() {
  const reduce = useReducedMotion();
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!ctx) return undefined;

    let w = 0;
    let h = 0;
    let dpr = 1;
    let frame = 0;
    const target = { x: -9999, y: -9999 };
    const mouse = { x: -9999, y: -9999 };

    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = window.innerWidth;
      h = window.innerHeight;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      if (reduce) draw(0);
    };

    function draw(t) {
      ctx.clearRect(0, 0, w, h);
      mouse.x += (target.x - mouse.x) * 0.14;
      mouse.y += (target.y - mouse.y) * 0.14;
      const offsetY = -((window.scrollY * 0.18) % GAP);
      for (let gy = -GAP; gy < h + GAP; gy += GAP) {
        for (let gx = GAP / 2; gx < w + GAP; gx += GAP) {
          const baseY = gy + offsetY;
          const wave = reduce ? 0 : Math.sin(t * 0.0007 + gx * 0.011 + baseY * 0.007);
          let x = gx;
          let y = baseY + wave * 1.6;
          const dx = x - mouse.x;
          const dy = y - mouse.y;
          const dist = Math.hypot(dx, dy);
          let k = 0;
          if (dist < REACH) {
            k = 1 - dist / REACH;
            k = k * k * (3 - 2 * k); // smoothstep falloff
            const n = dist || 1;
            x += (dx / n) * PUSH * k;
            y += (dy / n) * PUSH * k;
          }
          const size = 1.5 + k * 1.3;
          if (k > 0.02) {
            ctx.fillStyle = `rgba(201, 154, 18, ${0.2 + k * 0.55})`;
          } else {
            ctx.fillStyle = `rgba(21, 24, 27, ${0.12 + wave * 0.035})`;
          }
          ctx.fillRect(x - size / 2, y - size / 2, size, size);
        }
      }
    }

    const loop = (t) => {
      draw(t);
      frame = requestAnimationFrame(loop);
    };
    const onMove = (e) => {
      if (e.pointerType !== 'mouse') return;
      target.x = e.clientX;
      target.y = e.clientY;
    };
    const onLeave = () => {
      target.x = -9999;
      target.y = -9999;
    };
    const onScroll = () => reduce && draw(0);
    const onVisibility = () => {
      cancelAnimationFrame(frame);
      frame = 0;
      if (!document.hidden && !reduce) frame = requestAnimationFrame(loop);
    };

    resize();
    window.addEventListener('resize', resize);
    window.addEventListener('pointermove', onMove, { passive: true });
    window.addEventListener('scroll', onScroll, { passive: true });
    document.documentElement.addEventListener('mouseleave', onLeave);
    document.addEventListener('visibilitychange', onVisibility);
    if (!reduce) frame = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('resize', resize);
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('scroll', onScroll);
      document.documentElement.removeEventListener('mouseleave', onLeave);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [reduce]);

  return (
    <div className="pointer-events-none fixed inset-0 -z-10 bg-paper" aria-hidden="true">
      <canvas ref={canvasRef} className="backdrop-fade absolute inset-0 size-full" />
    </div>
  );
}
