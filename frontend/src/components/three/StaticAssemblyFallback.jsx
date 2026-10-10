// Shown when WebGL is unavailable or the 3D scene fails to load.
export default function StaticAssemblyFallback() {
  return (
    <div className="pointer-events-none absolute inset-0" aria-hidden="true">
      <img
        src="/media/assembly-exploded.webp"
        alt=""
        width="1024"
        height="1024"
        decoding="async"
        style={{ maskImage: "radial-gradient(closest-side, #000 72%, transparent 100%)" }}
        className="absolute top-[7svh] left-1/2 w-[min(82vw,420px)] -translate-x-1/2 mix-blend-multiply md:top-1/2 md:left-[2vw] md:w-[min(46vw,640px)] md:translate-x-0 md:-translate-y-1/2"
      />
    </div>
  );
}
