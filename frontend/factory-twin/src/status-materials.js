import * as THREE from "three";

export const STATUS_COLORS = {
  IDLE: 0x24a148,
  AVAILABLE: 0x24a148,
  RESERVED: 0xf1c21b,
  BUSY: 0x0f62fe,
  PROCESSING: 0x0f62fe,
  RUNNING: 0x0f62fe,
  SETUP: 0xff832b,
  ATTENTION: 0xff832b,
  HOLD: 0xda1e28,
  DOWN: 0xda1e28,
  REJECTED: 0xda1e28,
  UNKNOWN: 0x8d8d8d,
};

export const factoryMaterials = {
  cabinet: new THREE.MeshStandardMaterial({ color: 0xdde3e8, roughness: 0.68, metalness: 0.12 }),
  cabinetDark: new THREE.MeshStandardMaterial({ color: 0x8a969f, roughness: 0.62, metalness: 0.2 }),
  glass: new THREE.MeshStandardMaterial({ color: 0x79a9c8, roughness: 0.2, metalness: 0.05, transparent: true, opacity: 0.62 }),
  floor: new THREE.MeshStandardMaterial({ color: 0xe7ebee, roughness: 0.92, metalness: 0 }),
  zone: new THREE.MeshStandardMaterial({ color: 0xf8fafb, roughness: 0.95, metalness: 0 }),
  rail: new THREE.MeshStandardMaterial({ color: 0x66737e, roughness: 0.48, metalness: 0.62 }),
  carrier: new THREE.MeshStandardMaterial({ color: 0x3a4650, roughness: 0.55, metalness: 0.35 }),
  work: new THREE.MeshStandardMaterial({ color: 0x8a3ffc, roughness: 0.55, metalness: 0.08 }),
  warehouse: new THREE.MeshStandardMaterial({ color: 0xb6bec5, roughness: 0.72, metalness: 0.25 }),
};

export function statusColor(status) {
  return STATUS_COLORS[String(status || "UNKNOWN").toUpperCase()] ?? STATUS_COLORS.UNKNOWN;
}

export function disposeFactoryMaterials() {
  Object.values(factoryMaterials).forEach(material => material.dispose());
}
