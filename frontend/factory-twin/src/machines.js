import * as THREE from "three";
import { factoryMaterials, statusColor } from "./status-materials.js";

const geometries = {
  body: new THREE.BoxGeometry(1, 1, 1),
  cylinder: new THREE.CylinderGeometry(0.5, 0.5, 1, 20),
};

function box(group, size, position, material = factoryMaterials.cabinet) {
  const mesh = new THREE.Mesh(geometries.body, material);
  mesh.scale.set(...size);
  mesh.position.set(...position);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  group.add(mesh);
  return mesh;
}

function cylinder(group, radius, height, position, material = factoryMaterials.cabinetDark) {
  const mesh = new THREE.Mesh(geometries.cylinder, material);
  mesh.scale.set(radius * 2, height, radius * 2);
  mesh.position.set(...position);
  mesh.castShadow = true;
  group.add(mesh);
  return mesh;
}

export function createMachine(entity) {
  const group = new THREE.Group();
  const [width, height, depth] = entity.size;
  box(group, [width, height * 0.82, depth], [0, 0, 0]);
  box(group, [width * 0.82, height * 0.12, depth * 0.88], [0, height * 0.47, 0], factoryMaterials.cabinetDark);

  if (entity.archetype === "lithography_cell") {
    box(group, [width * 0.22, height * 0.44, depth * 0.25], [-width * 0.25, -height * 0.05, depth * 0.58], factoryMaterials.cabinetDark);
    box(group, [width * 0.22, height * 0.44, depth * 0.25], [width * 0.1, -height * 0.05, depth * 0.58], factoryMaterials.cabinetDark);
    box(group, [width * 0.32, height * 0.34, 0.05], [width * 0.22, height * 0.08, depth * 0.51], factoryMaterials.glass);
  } else if (entity.archetype === "wet_clean_cell") {
    [-0.3, 0, 0.3].forEach(fraction => {
      box(group, [width * 0.22, height * 0.52, depth * 0.12], [width * fraction, 0, depth * 0.54], factoryMaterials.glass);
    });
    box(group, [width * 0.76, height * 0.12, depth * 0.24], [0, -height * 0.34, depth * 0.55], factoryMaterials.cabinetDark);
  } else if (entity.archetype === "packing_cell") {
    box(group, [width * 0.78, height * 0.18, depth * 0.54], [0, -height * 0.16, depth * 0.42], factoryMaterials.cabinetDark);
    box(group, [width * 0.4, height * 0.32, depth * 0.14], [0, height * 0.13, depth * 0.55], factoryMaterials.glass);
  } else {
    box(group, [width * 0.46, height * 0.38, 0.08], [0, 0, depth * 0.52], factoryMaterials.glass);
  }

  const lampMaterial = new THREE.MeshStandardMaterial({ color: statusColor("UNKNOWN"), emissive: statusColor("UNKNOWN"), emissiveIntensity: 0.65 });
  const lamp = cylinder(group, 0.11, 0.42, [width * 0.34, height * 0.72, 0], lampMaterial);
  group.userData.statusLamp = lamp;
  group.userData.lampMaterial = lampMaterial;
  group.position.set(...entity.position);
  group.rotation.set(...entity.rotation);
  group.userData.entityRef = { entityType: "equipment", entityId: entity.id };
  group.traverse(child => { child.userData.entityRef = group.userData.entityRef; });
  return group;
}

export function updateMachine(group, state, elapsedSeconds) {
  const color = statusColor(state?.status);
  const material = group.userData.lampMaterial;
  if (material) {
    material.color.setHex(color);
    material.emissive.setHex(color);
    const running = ["BUSY", "PROCESSING", "RUNNING"].includes(String(state?.status || "").toUpperCase());
    material.emissiveIntensity = running ? 0.7 + Math.sin(elapsedSeconds * 5) * 0.2 : 0.58;
  }
}

export function createQueueRack(entity) {
  const group = new THREE.Group();
  const [width, height, depth] = entity.size;
  box(group, [width, 0.12, depth], [0, -height * 0.42, 0], factoryMaterials.cabinetDark);
  [-0.45, 0.45].forEach(x => box(group, [0.09, height, depth], [x * width, 0, 0], factoryMaterials.cabinetDark));
  group.position.set(...entity.position);
  group.userData.entityRef = { entityType: "queue", entityId: entity.id };
  group.traverse(child => { child.userData.entityRef = group.userData.entityRef; });
  return group;
}

export function createWarehouse(entity) {
  const group = new THREE.Group();
  const [width, height, depth] = entity.size;
  const columns = 4;
  const rows = 3;
  for (let column = 0; column <= columns; column += 1) {
    box(group, [0.12, height, depth], [(column / columns - 0.5) * width, 0, 0], factoryMaterials.warehouse);
  }
  for (let row = 0; row <= rows; row += 1) {
    box(group, [width, 0.1, depth], [0, (row / rows - 0.5) * height, 0], factoryMaterials.warehouse);
  }
  group.position.set(...entity.position);
  group.userData.entityRef = { entityType: "warehouse", entityId: entity.id };
  group.traverse(child => { child.userData.entityRef = group.userData.entityRef; });
  return group;
}

export function disposeMachine(group) {
  if (group?.userData?.lampMaterial) group.userData.lampMaterial.dispose();
}

export function disposeSharedMachineGeometry() {
  Object.values(geometries).forEach(geometry => geometry.dispose());
}
