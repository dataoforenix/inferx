// The opening is one timeline (0 → 1) played over OPENING_SECONDS:
// assemble → explode → engineering callouts → reassemble → glide into the hero.

export const clamp01 = (v) => Math.min(1, Math.max(0, v));
export const range = (v, start, end) => clamp01((v - start) / (end - start));
export const lerp = (a, b, t) => a + (b - a) * t;

export const easeOutQuint = (t) => 1 - Math.pow(1 - t, 5);
export const easeInOutCubic = (t) =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

export const OPENING_SECONDS = 4.2;
export const INTRO_SECONDS = 1;

export const PHASE = {
  explode: [0.2, 0.42],
  annotate: [0.4, 0.64],
  assemble: [0.62, 0.8],
  toHero: [0.78, 1],
};

/** 0 = assembled, 1 = fully exploded. */
export function explodeAt(p) {
  const out = easeInOutCubic(range(p, ...PHASE.explode));
  const back = easeInOutCubic(range(p, ...PHASE.assemble));
  return out * (1 - back);
}

/** Visibility of the engineering callouts. */
export function annotateAt(p) {
  return range(p, 0.38, 0.46) * (1 - range(p, 0.6, 0.66));
}

/** 0 = centered opening stage, 1 = resting beside the headline. */
export const heroAt = (p) => easeInOutCubic(range(p, ...PHASE.toHero));

export const OPENING_STEPS = [
  { at: 0, label: 'فكرة' },
  { at: PHASE.explode[0], label: 'تفكيك' },
  { at: PHASE.annotate[0], label: 'هندسة' },
  { at: PHASE.assemble[0], label: 'تصنيع' },
];

const params =
  typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : null;

/** Dev-only: `?p=0.5` freezes the opening at a given point for screenshots. */
export const DEBUG_PROGRESS =
  import.meta.env.DEV && params?.has('p') ? clamp01(Number(params.get('p'))) : null;

/** `?no3d` forces the static fallback (handy for testing low-end paths). */
export const FORCE_NO_3D = params?.has('no3d') ?? false;
