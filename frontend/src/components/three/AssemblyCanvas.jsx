import { Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { Environment, Lightformer } from '@react-three/drei';
import MechanicalAssembly from './MechanicalAssembly';

// Studio lighting built from light-formers: no HDR download, renders once.
function StudioLight() {
  return (
    <Environment resolution={256} frames={1}>
      <Lightformer form="rect" intensity={2.4} position={[0, 5, -1]} rotation-x={Math.PI / 2} scale={[12, 6, 1]} />
      <Lightformer form="rect" intensity={1.4} position={[-6, 1, 1]} rotation-y={Math.PI / 2} scale={[8, 2.5, 1]} />
      <Lightformer form="rect" intensity={1.1} position={[6, 0.5, -1]} rotation-y={-Math.PI / 2} scale={[8, 2.5, 1]} />
      <Lightformer form="rect" intensity={1.5} position={[0, 0, 10]} rotation-y={Math.PI} scale={[16, 9, 1]} />
      <Lightformer form="ring" intensity={1.6} color="#fff4e6" position={[2, 2, 6]} scale={3} />
    </Environment>
  );
}

export default function AssemblyCanvas({ progress, scroll, reduce, active, labelsRef, onReady }) {
  return (
    <Canvas
      dpr={[1, 1.5]}
      gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }}
      camera={{ position: [0, 0.2, 8], fov: 30, near: 0.1, far: 40 }}
      frameloop={reduce ? 'demand' : active ? 'always' : 'never'}
      style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}
      aria-hidden="true"
    >
      <ambientLight intensity={0.5} />
      <directionalLight position={[3, 5, 6]} intensity={1.1} />
      <StudioLight />
      <Suspense fallback={null}>
        <MechanicalAssembly progress={progress} scroll={scroll} reduce={reduce} labelsRef={labelsRef} onReady={onReady} />
      </Suspense>
    </Canvas>
  );
}
