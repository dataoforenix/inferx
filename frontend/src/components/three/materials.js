import * as THREE from 'three';

export function createMaterials() {
  return {
    anodizedBlue: new THREE.MeshPhysicalMaterial({
      color: '#2a2f35',
      metalness: 0.6,
      roughness: 0.32,
      clearcoat: 0.7,
      clearcoatRoughness: 0.18,
    }),
    brushedSteel: new THREE.MeshPhysicalMaterial({
      color: '#d4d7dc',
      metalness: 0.72,
      roughness: 0.4,
    }),
    polishedSteel: new THREE.MeshPhysicalMaterial({
      color: '#e2e5e9',
      metalness: 0.9,
      roughness: 0.2,
    }),
    chrome: new THREE.MeshPhysicalMaterial({
      color: '#eef0f3',
      metalness: 1,
      roughness: 0.06,
    }),
    blackOxide: new THREE.MeshPhysicalMaterial({
      color: '#262b33',
      metalness: 0.75,
      roughness: 0.42,
    }),
    signalOrange: new THREE.MeshPhysicalMaterial({
      color: '#e6b325',
      metalness: 0.25,
      roughness: 0.32,
      clearcoat: 0.6,
      clearcoatRoughness: 0.2,
    }),
  };
}
