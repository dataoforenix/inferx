import { useEffect, useRef } from 'react';
import { useReducedMotion } from 'motion/react';

const GAP = 26; // px between dots
const REACH = 170; // cursor influence radius
const PUSH = 11; // max displacement near the cursor

/**
 * Fixed "pin-board" behind the page: a precise dot field that parallaxes with scroll and parts
 * around the cursor with an accent tint. It redraws only when the pointer moves or the page scrolls
 * (the pointer is eased until it settles), so an idle page costs nothing.
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
    const OFF = -9999;
    const target = { x: OFF, y: OFF };
    const mouse = { x: OFF, y: OFF };
    const BASE = 'rgba(21, 24, 27, 0.13)';

    function draw() {
      ctx.clearRect(0, 0, w, h);
      const offsetY = -((window.scrollY * 0.18) % GAP);
      ctx.fillStyle = BASE;
      for (let gy = -GAP; gy < h + GAP; gy += GAP) {
        for (let gx = GAP / 2; gx < w + GAP; gx += GAP) {
          let x = gx;
          let y = gy + offsetY;
          const dx = x - mouse.x;
          const dy = y - mouse.y;
          const dist = Math.hypot(dx, dy);
          if (dist >= REACH) {
            ctx.fillRect(x - 0.75, y - 0.75, 1.5, 1.5);
            continue;
          }
          let k = 1 - dist / REACH;
          k = k * k * (3 - 2 * k); // smoothstep falloff
          const n = dist || 1;
          x += (dx / n) * PUSH * k;
          y += (dy / n) * PUSH * k;
          const size = 1.5 + k * 1.3;
          ctx.fillStyle = k > 0.02 ? `rgba(201, 154, 18, ${0.2 + k * 0.55})` : BASE;
          ctx.fillRect(x - size / 2, y - size / 2, size, size);
          ctx.fillStyle = BASE;
        }
      }
    }

    // Draw on demand only (pointer, scroll, resize), easing the pointer until it settles; no idle loop.
    const tick = () => {
      frame = 0;
      const ease = reduce ? 1 : 0.2;
      mouse.x += (target.x - mouse.x) * ease;
      mouse.y += (target.y - mouse.y) * ease;
      draw();
      if (Math.abs(target.x - mouse.x) > 0.5 || Math.abs(target.y - mouse.y) > 0.5) frame = requestAnimationFrame(tick);
    };
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(tick);
    };

    const resize = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = window.innerWidth;
      h = window.innerHeight;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      schedule();
    };
    const onMove = (e) => {
      if (e.pointerType !== 'mouse') return;
      // Entering the window: start at the pointer instead of sweeping in from off screen.
      if (mouse.x === OFF) {
        mouse.x = e.clientX;
        mouse.y = e.clientY;
      }
      target.x = e.clientX;
      target.y = e.clientY;
      schedule();
    };
    const onLeave = () => {
      target.x = mouse.x = OFF;
      target.y = mouse.y = OFF;
      schedule();
    };

    resize();
    window.addEventListener('resize', resize);
    window.addEventListener('pointermove', onMove, { passive: true });
    window.addEventListener('scroll', schedule, { passive: true });
    document.documentElement.addEventListener('mouseleave', onLeave);

    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('resize', resize);
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('scroll', schedule);
      document.documentElement.removeEventListener('mouseleave', onLeave);
    };
  }, [reduce]);

  return (
    <div className="pointer-events-none fixed inset-0 -z-10 bg-paper" aria-hidden="true">
      <canvas ref={canvasRef} className="backdrop-fade absolute inset-0 size-full" />
    </div>
  );
}
