// Engineering callouts. Their position/opacity is written every frame by the
// 3D scene (projected part anchors), so React never re-renders during scroll.

const NOTES = [
  { id: 'gear', title: 'ترس عدلي', spec: 'Z32 · m3 · AL-6061', sx: -1, sy: -1 },
  { id: 'bearing', title: 'محمل كروي', spec: '6204-2RS · 20×47×14', sx: 1, sy: 1 },
  { id: 'clip', title: 'حلقة تثبيت', spec: 'DIN 471 · Ø20', sx: -1, sy: 1 },
];

const ELBOW = { x: 26, y: 34 };
const SHELF = 172;

export default function Annotations({ labelsRef }) {
  const register = (id, key) => (el) => {
    labelsRef.current[id] ??= {};
    labelsRef.current[id][key] = el;
  };

  return (
    <div className="pointer-events-none absolute inset-0 z-[5]" aria-hidden="true">
      {NOTES.map(({ id, title, spec, sx, sy }) => (
        <div
          key={id}
          ref={register(id, 'root')}
          className="absolute top-0 left-0 opacity-0 will-change-[transform,opacity]"
        >
          <span className="absolute size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-[1.5px] border-brand bg-paper" />
          <svg className="absolute top-0 left-0 overflow-visible" width="1" height="1">
            <polyline
              ref={register(id, 'line')}
              points={`0,0 ${sx * ELBOW.x},${sy * ELBOW.y} ${sx * SHELF},${sy * ELBOW.y}`}
              fill="none"
              stroke="#1c2024"
              strokeWidth="1"
              pathLength="1"
              strokeDasharray="1"
              strokeDashoffset="1"
              vectorEffect="non-scaling-stroke"
            />
          </svg>
          <div
            className="absolute w-[146px]"
            style={{
              left: sx < 0 ? -SHELF : ELBOW.x,
              top: sy < 0 ? -ELBOW.y - 8 : ELBOW.y + 8,
              transform: sy < 0 ? 'translateY(-100%)' : undefined,
              textAlign: sx < 0 ? 'right' : 'left',
            }}
          >
            <p className="text-[14.5px] leading-snug font-semibold text-ink">{title}</p>
            <p dir="ltr" className="mt-0.5 font-mono text-[11.5px] tracking-tight text-ink-muted" style={{ textAlign: 'inherit' }}>
              {spec}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
