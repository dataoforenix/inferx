import { useEffect, useMemo, useRef } from 'react';
import * as THREE from 'three';
import { useFrame, useThree } from '@react-three/fiber';
import { ContactShadows, Line, useGLTF } from '@react-three/drei';
import {
  annotateAt,
  clamp01,
  easeOutQuint,
  explodeAt,
  INTRO_SECONDS,
  heroAt,
  lerp,
} from '../../lib/timeline';
import {
  DIM,
  createBearingRingGeometry,
  createCirclipGeometry,
  createFlangeBossGeometry,
  createFlangeGeometry,
  createGearGeometry,
  createShaftGeometry,
} from './geometry';
import { createMaterials } from './materials';

const GEAR_URL = '/models/gear.glb';

// Assembled z position and exploded offset (along the shaft axis) per part.
const PARTS = {
  bolts: { z: -0.375, dz: -1.0, radial: 0.25 },
  flange: { z: -0.5, dz: -0.45 },
  gear: { z: 0, dz: 0.35 },
  bearing: { z: 0.5, dz: 1.05 },
  clip: { z: 0.66, dz: 1.65 },
  shaft: { z: 0.25, dz: 2.5 },
};
const EXPLODED_CENTER_SHIFT = 1.1;

// Callout anchors, in each part's local (unrotated) space.
const ANCHORS = {
  gear: new THREE.Vector3(0, DIM.gearR, 0),
  bearing: new THREE.Vector3(0, -DIM.bearingOuter, 0),
  clip: new THREE.Vector3(0.36, -0.2, 0),
};

const BASE_TILT = new THREE.Euler(0.3, -0.62, 0);

function useGearGeometry() {
  const gltf = useGLTF(GEAR_URL);
  return useMemo(() => {
    let source = null;
    gltf.scene.traverse((o) => {
      if (!source && o.isMesh) source = o.geometry;
    });
    if (!source) return createGearGeometry();
    const geo = source.clone();
    geo.center();
    geo.computeBoundingBox();
    const box = geo.boundingBox;
    const size = new THREE.Vector3();
    box.getSize(size);
    // Tripo exports the gear with its axis on X: turn it onto Z.
    if (size.x < size.y && size.x < size.z) geo.rotateY(Math.PI / 2);
    else if (size.y < size.x && size.y < size.z) geo.rotateX(Math.PI / 2);
    geo.computeBoundingBox();
    geo.boundingBox.getSize(size);
    const s = (DIM.gearR * 2) / Math.max(size.x, size.y);
    geo.scale(s, s, s * 0.8);
    geo.computeVertexNormals();
    return geo;
  }, [gltf]);
}

function usePointerTilt(enabled) {
  const pointer = useRef({ x: 0, y: 0 });
  useEffect(() => {
    if (!enabled) return undefined;
    const fine = window.matchMedia('(hover: hover) and (pointer: fine)');
    if (!fine.matches) return undefined;
    const onMove = (e) => {
      pointer.current.x = (e.clientX / window.innerWidth) * 2 - 1;
      pointer.current.y = (e.clientY / window.innerHeight) * 2 - 1;
    };
    window.addEventListener('pointermove', onMove, { passive: true });
    return () => window.removeEventListener('pointermove', onMove);
  }, [enabled]);
  return pointer;
}

export default function MechanicalAssembly({ progress, scroll, reduce, labelsRef, onReady }) {
  const { camera, size } = useThree();
  const materials = useMemo(() => createMaterials(), []);
  const gearGeometry = useGearGeometry();
  const geo = useMemo(
    () => ({
      flange: createFlangeGeometry(),
      boss: createFlangeBossGeometry(),
      shaft: createShaftGeometry(),
      outerRace: createBearingRingGeometry(0.44, DIM.bearingOuter, DIM.bearingW),
      innerRace: createBearingRingGeometry(DIM.bearingInner, 0.3, DIM.bearingW),
      ball: new THREE.SphereGeometry(0.068, 24, 16),
      clip: createCirclipGeometry(),
      boltHead: new THREE.CylinderGeometry(0.085, 0.085, 0.07, 6).rotateX(Math.PI / 2),
      boltShank: new THREE.CylinderGeometry(0.045, 0.045, 0.34, 16).rotateX(Math.PI / 2),
    }),
    [],
  );

  const rig = useRef(null);
  const tilt = useRef(null);
  const axis = useRef(null);
  const axisLine = useRef(null);
  const slider = useRef({});
  const gearSpin = useRef(null);
  const boltRefs = useRef([]);
  const intro = useRef(reduce ? 1 : 0);
  const pointer = usePointerTilt(!reduce);
  const scratch = useMemo(() => new THREE.Vector3(), []);

  useEffect(() => {
    onReady?.();
  }, [onReady]);

  useFrame((state, delta) => {
    const dt = Math.min(delta, 1 / 30);
    const p = progress.get();

    // Intro: parts arrive loose and click together (time-based, not scroll).
    if (intro.current < 1) intro.current = clamp01(intro.current + dt / INTRO_SECONDS);
    const introT = easeOutQuint(intro.current);
    const introLoose = 1 - introT;

    const e = Math.max(explodeAt(p), introLoose * 0.85);
    const shift = -e * EXPLODED_CENTER_SHIFT;

    for (const [name, cfg] of Object.entries(PARTS)) {
      const g = slider.current[name];
      if (g) g.position.z = cfg.z + cfg.dz * e + shift;
    }
    boltRefs.current.forEach((b, i) => {
      if (!b) return;
      const a = (i / 6) * Math.PI * 2 + Math.PI / 6;
      const r = DIM.boltCircle + PARTS.bolts.radial * e;
      b.position.set(Math.cos(a) * r, Math.sin(a) * r, 0);
    });
    if (gearSpin.current) gearSpin.current.rotation.z = e * 0.55 + introLoose * 0.6;

    // Layout: centered opening stage → resting beside the headline.
    const narrow = size.width < 768;
    const halfH = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * camera.position.z;
    const halfW = halfH * (size.width / size.height);
    const toHero = heroAt(p);
    const sc = scroll ? scroll.get() : 0;
    const stage = narrow ? { x: 0, y: halfH * 0.05, s: halfW * 0.3 } : { x: 0, y: 0.05, s: 0.82 };
    const hero = narrow
      ? { x: 0, y: halfH * 0.44, s: halfW * 0.4 }
      : { x: -Math.min(halfW * 0.56, 2.7), y: 0.05, s: 0.7 };
    // After the opening, scrolling away lets the part lag behind (parallax) and turn.
    const x = lerp(stage.x, hero.x, toHero);
    const y = lerp(stage.y, hero.y, toHero) - sc * halfH * 0.55;
    const s = lerp(stage.s, hero.s, toHero) * (0.94 + 0.06 * introT);

    if (rig.current) {
      rig.current.position.set(x, y, 0);
      rig.current.scale.setScalar(s);
    }

    if (tilt.current) {
      const t = state.clock.elapsedTime;
      const idle = reduce ? 0 : Math.sin(t * 0.5) * 0.025;
      const targetY = BASE_TILT.y + sc * 1.1 + pointer.current.x * 0.14 + idle - introLoose * 0.5;
      const targetX = BASE_TILT.x + sc * 0.25 + pointer.current.y * 0.09;
      tilt.current.rotation.y = THREE.MathUtils.damp(tilt.current.rotation.y, targetY, 5, dt);
      tilt.current.rotation.x = THREE.MathUtils.damp(tilt.current.rotation.x, targetX, 5, dt);
    }

    // Engineering reveal: axis line + callouts projected onto the DOM layer.
    const a = reduce ? 0 : annotateAt(p);
    if (axisLine.current) axisLine.current.material.opacity = a * 0.55;
    if (axis.current) axis.current.position.z = shift;

    const labels = labelsRef?.current;
    if (!labels) return;
    Object.entries(ANCHORS).forEach(([id, anchor], i) => {
      const label = labels[id];
      const part = slider.current[id];
      if (!label?.root || !part) return;
      const ai = clamp01(a * 1.6 - i * 0.22);
      if (ai <= 0.001) {
        if (label.root.style.opacity !== '0') label.root.style.opacity = '0';
        return;
      }
      part.updateWorldMatrix(true, false);
      scratch.copy(anchor).applyMatrix4(part.matrixWorld).project(camera);
      const px = (scratch.x * 0.5 + 0.5) * size.width;
      const py = (-scratch.y * 0.5 + 0.5) * size.height;
      label.root.style.transform = `translate3d(${px.toFixed(1)}px, ${py.toFixed(1)}px, 0)`;
      label.root.style.opacity = String(Math.min(1, ai * 1.4));
      if (label.line) label.line.style.strokeDashoffset = String(1 - ai);
    });
  });

  return (
    <>
      <group ref={rig}>
        <group ref={tilt} rotation={BASE_TILT}>
          <group ref={axis}>
            <Line
              ref={axisLine}
              points={[
                [0, 0, -2.2],
                [0, 0, 4.6],
              ]}
              color="#1e4fd6"
              lineWidth={1}
              dashed
              dashSize={0.08}
              gapSize={0.06}
              transparent
              opacity={0}
            />
          </group>

          <group ref={(el) => (slider.current.flange = el)}>
            <mesh geometry={geo.flange} material={materials.brushedSteel} />
            <mesh geometry={geo.boss} material={materials.brushedSteel} position={[0, 0, -0.31]} />
          </group>

          <group ref={(el) => (slider.current.bolts = el)}>
            {Array.from({ length: 6 }, (_, i) => (
              <group key={i} ref={(el) => (boltRefs.current[i] = el)}>
                <mesh geometry={geo.boltHead} material={materials.blackOxide} />
                <mesh geometry={geo.boltShank} material={materials.blackOxide} position={[0, 0, -0.2]} />
              </group>
            ))}
          </group>

          <group ref={(el) => (slider.current.gear = el)}>
            <group ref={gearSpin}>
              <mesh geometry={gearGeometry} material={materials.anodizedBlue} />
            </group>
          </group>

          <group ref={(el) => (slider.current.bearing = el)}>
            <mesh geometry={geo.outerRace} material={materials.polishedSteel} />
            <mesh geometry={geo.innerRace} material={materials.polishedSteel} />
            {Array.from({ length: 11 }, (_, i) => {
              const a = (i / 11) * Math.PI * 2;
              return (
                <mesh
                  key={i}
                  geometry={geo.ball}
                  material={materials.chrome}
                  position={[Math.cos(a) * 0.37, Math.sin(a) * 0.37, 0]}
                />
              );
            })}
          </group>

          <group ref={(el) => (slider.current.clip = el)}>
            <mesh geometry={geo.clip} material={materials.signalOrange} />
          </group>

          <group ref={(el) => (slider.current.shaft = el)}>
            <mesh geometry={geo.shaft} material={materials.polishedSteel} />
          </group>
        </group>
        <ContactShadows
          position={[0, -1.45, 0]}
          opacity={0.22}
          scale={6}
          blur={3}
          far={3.2}
          resolution={512}
          color="#0e1726"
          frames={reduce ? 1 : Infinity}
        />
      </group>
    </>
  );
}

useGLTF.preload(GEAR_URL);
