import * as THREE from "three";
import { factoryMaterials } from "./status-materials.js";

const tokenGeometry = new THREE.CylinderGeometry(0.34, 0.34, 0.16, 18);
const carrierBodyGeometry = new THREE.BoxGeometry(1.25, 0.55, 0.9);
const carrierHookGeometry = new THREE.BoxGeometry(0.18, 0.9, 0.18);

export class MaterialFlowView {
  constructor(factoryScene, layout, topology) {
    this.scene = factoryScene;
    this.layout = layout;
    this.topology = topology;
    this.queueMeshes = new Map();
    this.carriers = new Map();
    this.warehouseTokens = null;
    this.reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    this.createQueueMeshes();
    this.createWarehouseTokens();
    factoryScene.tickHandlers.add(elapsed => this.tick(elapsed));
  }

  createQueueMeshes() {
    this.layout.queues.forEach(queue => {
      const capacity = Math.max(1, Number(queue.metadata?.visible_capacity || 24));
      const mesh = new THREE.InstancedMesh(tokenGeometry, factoryMaterials.work, capacity);
      mesh.count = 0;
      mesh.castShadow = true;
      mesh.userData.queue = queue;
      mesh.userData.instanceEntityIds = [];
      this.scene.root.add(mesh);
      this.queueMeshes.set(queue.id, mesh);
    });
  }

  createWarehouseTokens() {
    const capacity = Math.max(1, Number(this.layout.warehouse.metadata?.visible_slots || 48));
    const mesh = new THREE.InstancedMesh(tokenGeometry, factoryMaterials.work, capacity);
    mesh.count = 0;
    mesh.castShadow = true;
    mesh.userData.instanceEntityIds = [];
    this.scene.root.add(mesh);
    this.warehouseTokens = mesh;
  }

  update(snapshot) {
    snapshot.queues.forEach(queue => this.updateQueue(queue));
    this.updateCarriers(snapshot.carriers || []);
    this.updateWarehouse(snapshot.warehouse);
  }

  updateQueue(state) {
    const mesh = this.queueMeshes.get(state.queue_id);
    if (!mesh) return;
    const queue = mesh.userData.queue;
    const visible = state.visible_task_uids || [];
    const count = Math.min(visible.length, mesh.instanceMatrix.count);
    const matrix = new THREE.Matrix4();
    const position = new THREE.Vector3();
    for (let index = 0; index < count; index += 1) {
      const column = index % 5;
      const row = Math.floor(index / 5);
      position.set(
        queue.position[0] + (column - 2) * 0.72,
        queue.position[1] + 0.58 + row * 0.19,
        queue.position[2]
      );
      matrix.makeRotationX(Math.PI / 2);
      matrix.setPosition(position);
      mesh.setMatrixAt(index, matrix);
    }
    mesh.count = count;
    mesh.userData.instanceEntityIds = visible.slice(0, count).map(uid => ({ entityType: "task", entityId: String(uid) }));
    mesh.instanceMatrix.needsUpdate = true;
  }

  updateCarriers(states) {
    const activeIds = new Set(states.map(state => state.carrier_id));
    for (const [carrierId, entry] of this.carriers) {
      if (!activeIds.has(carrierId)) {
        this.scene.root.remove(entry.group);
        entry.material.dispose();
        this.carriers.delete(carrierId);
      }
    }
    states.forEach(state => {
      let entry = this.carriers.get(state.carrier_id);
      if (!entry) {
        const group = new THREE.Group();
        const material = factoryMaterials.carrier.clone();
        const body = new THREE.Mesh(carrierBodyGeometry, material);
        body.castShadow = true;
        group.add(body);
        const hook = new THREE.Mesh(carrierHookGeometry, material);
        hook.position.y = 0.68;
        group.add(hook);
        group.userData.entityRef = { entityType: "carrier", entityId: state.carrier_id };
        group.traverse(child => { child.userData.entityRef = group.userData.entityRef; });
        this.scene.root.add(group);
        entry = { group, material, currentProgress: Number(state.progress || 0), targetProgress: Number(state.progress || 0), state };
        this.carriers.set(state.carrier_id, entry);
      }
      entry.state = state;
      entry.targetProgress = Math.max(0, Math.min(1, Number(state.progress || 0)));
    });
  }

  updateWarehouse(state) {
    if (!state || !this.warehouseTokens) return;
    const warehouse = this.layout.warehouse;
    const count = Math.min(Number(state.completed_count || 0), this.warehouseTokens.instanceMatrix.count);
    const matrix = new THREE.Matrix4();
    for (let index = 0; index < count; index += 1) {
      const column = index % 8;
      const row = Math.floor(index / 8) % 4;
      const shelf = Math.floor(index / 32);
      matrix.makeRotationX(Math.PI / 2);
      matrix.setPosition(
        warehouse.position[0] - 4.6 + column * 1.3,
        warehouse.position[1] - 1.2 + row * 0.8,
        warehouse.position[2] - 3.4 + shelf * 2.2
      );
      this.warehouseTokens.setMatrixAt(index, matrix);
    }
    this.warehouseTokens.count = count;
    this.warehouseTokens.userData.instanceEntityIds = Array.from({ length: count }, (_, index) => ({
      entityType: "warehouse",
      entityId: state.warehouse_id,
      slot: index,
    }));
    this.warehouseTokens.instanceMatrix.needsUpdate = true;
  }

  tick() {
    this.carriers.forEach(entry => {
      const route = this.topology.routes.get(entry.state.route_id);
      if (!route) return;
      if (this.reducedMotion) entry.currentProgress = entry.targetProgress;
      else entry.currentProgress += (entry.targetProgress - entry.currentProgress) * 0.12;
      const progress = Math.max(0, Math.min(1, entry.currentProgress));
      const point = route.curve.getPoint(progress);
      const tangent = route.curve.getTangent(progress);
      entry.group.position.copy(point);
      entry.group.position.y -= 0.48;
      entry.group.rotation.y = Math.atan2(tangent.x, tangent.z);
    });
  }

  dispose() {
    this.queueMeshes.forEach(mesh => {
      this.scene.root.remove(mesh);
      mesh.dispose();
    });
    this.carriers.forEach(entry => entry.material.dispose());
    this.carriers.clear();
    if (this.warehouseTokens) this.warehouseTokens.dispose();
  }
}
