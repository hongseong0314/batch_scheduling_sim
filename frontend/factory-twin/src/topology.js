import * as THREE from "three";
import { createMachine, createQueueRack, createWarehouse } from "./machines.js";
import { factoryMaterials } from "./status-materials.js";

export function buildFactoryTopology(factoryScene, layout) {
  const entities = new Map();
  const routes = new Map();
  const operationPositions = new Map();

  layout.operations.forEach(entity => {
    const mesh = new THREE.Mesh(
      new THREE.BoxGeometry(...entity.size),
      factoryMaterials.zone
    );
    mesh.position.set(...entity.position);
    mesh.receiveShadow = true;
    mesh.userData.entityRef = { entityType: "operation", entityId: entity.id };
    factoryScene.root.add(mesh);
    entities.set(`operation:${entity.id}`, mesh);
    operationPositions.set(entity.id, new THREE.Vector3(...entity.position));
    factoryScene.addLabel(mesh, entity.display_name, entity.id);

    const border = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.BoxGeometry(...entity.size)),
      new THREE.LineBasicMaterial({ color: 0x8d9aa5, transparent: true, opacity: 0.62 })
    );
    border.position.copy(mesh.position);
    border.userData.disposeMaterial = true;
    factoryScene.root.add(border);
  });

  layout.equipment.forEach(entity => {
    const group = createMachine(entity);
    factoryScene.root.add(group);
    entities.set(`equipment:${entity.id}`, group);
    factoryScene.addLabel(group, entity.display_name, entity.id);
  });

  layout.queues.forEach(entity => {
    const group = createQueueRack(entity);
    factoryScene.root.add(group);
    entities.set(`queue:${entity.id}`, group);
  });

  const warehouse = createWarehouse(layout.warehouse);
  factoryScene.root.add(warehouse);
  entities.set(`warehouse:${layout.warehouse.id}`, warehouse);
  factoryScene.addLabel(warehouse, layout.warehouse.display_name, layout.warehouse.id);

  layout.routes.forEach(route => {
    const points = route.points.map(point => new THREE.Vector3(...point));
    const curve = new THREE.CatmullRomCurve3(points, false, "catmullrom", 0.15);
    const geometry = new THREE.TubeGeometry(curve, Math.max(12, points.length * 10), 0.11, 8, false);
    const rail = new THREE.Mesh(geometry, factoryMaterials.rail.clone());
    rail.castShadow = true;
    rail.userData.entityRef = { entityType: "route", entityId: route.id };
    rail.userData.disposeMaterial = true;
    factoryScene.root.add(rail);

    const supportCount = Math.max(2, Math.ceil(curve.getLength() / 12));
    for (let index = 0; index <= supportCount; index += 1) {
      const point = curve.getPoint(index / supportCount);
      const support = new THREE.Mesh(
        new THREE.CylinderGeometry(0.08, 0.11, Math.max(0.5, point.y), 8),
        factoryMaterials.rail
      );
      support.position.set(point.x, point.y / 2, point.z);
      factoryScene.root.add(support);
    }
    routes.set(route.id, { curve, mesh: rail, route });
    entities.set(`route:${route.id}`, rail);
  });

  return { entities, routes, operationPositions };
}
