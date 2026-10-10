import * as THREE from 'three';

// All parts are built around the Z axis (the shaft axis), centered at z = 0.

function circlePath(r, clockwise = false) {
  const path = new THREE.Path();
  path.absarc(0, 0, r, 0, Math.PI * 2, clockwise);
  path.autoClose = true;
  return path;
}

function extrudeCentered(shape, depth, bevel = 0.012) {
  const geo = new THREE.ExtrudeGeometry(shape, {
    depth,
    bevelEnabled: bevel > 0,
    bevelThickness: bevel,
    bevelSize: bevel,
    bevelSegments: 2,
    curveSegments: 64,
  });
  geo.translate(0, 0, -depth / 2);
  geo.computeVertexNormals();
  return geo;
}

function lathe(profile, segments = 96) {
  // LatheGeometry spins around Y; rotate so the axis becomes Z.
  const geo = new THREE.LatheGeometry(
    profile.map(([r, z]) => new THREE.Vector2(r, z)),
    segments,
  );
  geo.rotateX(Math.PI / 2);
  geo.computeVertexNormals();
  return geo;
}

export const DIM = {
  flangeR: 1.32,
  flangeT: 0.18,
  boltCircle: 1.1,
  shaftR: 0.2,
  shaftLen: 2.7,
  gearR: 0.95,
  bearingOuter: 0.56,
  bearingInner: 0.21,
  bearingW: 0.22,
};

export function createFlangeGeometry() {
  const shape = new THREE.Shape();
  shape.absarc(0, 0, DIM.flangeR, 0, Math.PI * 2, false);
  shape.holes.push(circlePath(DIM.shaftR + 0.04, true));
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * Math.PI * 2 + Math.PI / 6;
    const hole = new THREE.Path();
    hole.absarc(Math.cos(a) * DIM.boltCircle, Math.sin(a) * DIM.boltCircle, 0.075, 0, Math.PI * 2, true);
    shape.holes.push(hole);
  }
  return extrudeCentered(shape, DIM.flangeT, 0.02);
}

export function createFlangeBossGeometry() {
  const r0 = DIM.shaftR + 0.04;
  return lathe([
    [r0, -0.22],
    [0.5, -0.22],
    [0.54, -0.18],
    [0.54, 0.22],
    [r0, 0.22],
    [r0, -0.22],
  ]);
}

export function createShaftGeometry() {
  const r = DIM.shaftR;
  const h = DIM.shaftLen / 2;
  const c = 0.035;
  return lathe([
    [0, -h],
    [r - c, -h],
    [r, -h + c],
    [r, h - c],
    [r - c, h],
    [0, h],
  ]);
}

export function createBearingRingGeometry(inner, outer, width) {
  const h = width / 2;
  const c = 0.018;
  return lathe([
    [inner + c, -h],
    [outer - c, -h],
    [outer, -h + c],
    [outer, h - c],
    [outer - c, h],
    [inner + c, h],
    [inner, h - c],
    [inner, -h + c],
    [inner + c, -h],
  ]);
}

export function createCirclipGeometry() {
  const outer = 0.4;
  const inner = 0.3;
  const gap = 0.42; // radians of opening
  const start = Math.PI / 2 + gap / 2;
  const end = Math.PI / 2 - gap / 2 + Math.PI * 2;
  const shape = new THREE.Shape();
  shape.absarc(0, 0, outer, start, end, false);
  shape.absarc(0, 0, inner, end, start, true);
  shape.closePath();

  // Two lugs with holes at the opening, like a DIN 471 ring.
  const lugs = [start, end].map((a, i) => {
    const lug = new THREE.Shape();
    const cx = Math.cos(a) * 0.4;
    const cy = Math.sin(a) * 0.4 + 0.02;
    lug.absarc(cx + (i ? 0.04 : -0.04), cy, 0.075, 0, Math.PI * 2, false);
    const hole = new THREE.Path();
    hole.absarc(cx + (i ? 0.04 : -0.04), cy, 0.028, 0, Math.PI * 2, true);
    lug.holes.push(hole);
    return lug;
  });
  return extrudeCentered([shape, ...lugs], 0.045, 0.008);
}

/** Procedural spur gear — fallback if the generated GLB is unavailable. */
export function createGearGeometry({ teeth = 32, outer = DIM.gearR, root = 0.86, width = 0.24 } = {}) {
  const shape = new THREE.Shape();
  const step = (Math.PI * 2) / teeth;
  for (let i = 0; i < teeth; i++) {
    const a = i * step;
    const pts = [
      [root, a],
      [root, a + step * 0.18],
      [outer, a + step * 0.32],
      [outer, a + step * 0.58],
      [root, a + step * 0.72],
    ];
    pts.forEach(([r, t], j) => {
      const x = Math.cos(t) * r;
      const y = Math.sin(t) * r;
      if (i === 0 && j === 0) shape.moveTo(x, y);
      else shape.lineTo(x, y);
    });
  }
  shape.closePath();
  shape.holes.push(circlePath(DIM.shaftR + 0.01, true));
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * Math.PI * 2;
    const hole = new THREE.Path();
    hole.absarc(Math.cos(a) * 0.56, Math.sin(a) * 0.56, 0.13, 0, Math.PI * 2, true);
    shape.holes.push(hole);
  }
  return extrudeCentered(shape, width, 0.015);
}
