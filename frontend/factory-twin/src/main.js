import * as THREE from "three";
import { FactoryInspector } from "./inspector.js";
import { MaterialFlowView } from "./material-flow.js";
import { updateMachine } from "./machines.js";
import { FactoryScene } from "./scene.js";
import { buildFactoryTopology } from "./topology.js";

export const FACTORY_TWIN_FRONTEND_READY = true;
export const THREE_REVISION = THREE.REVISION;
const SCHEMA_VERSION = "factory-twin.v1";

class FactoryTwinApp {
  constructor(page) {
    this.page = page;
    this.mount = document.getElementById("factory-twin-canvas");
    this.labelLayer = document.getElementById("factory-twin-label-layer");
    this.message = document.getElementById("factory-twin-message");
    this.connection = document.getElementById("factory-twin-connection");
    this.sourceSelect = document.getElementById("factory-twin-source");
    this.replayControl = document.getElementById("factory-twin-replay-control");
    this.replayInput = document.getElementById("factory-twin-replay-time");
    this.active = false;
    this.initialized = false;
    this.source = "SIMULATOR";
    this.layout = null;
    this.snapshot = null;
    this.scene = null;
    this.topology = null;
    this.materialFlow = null;
    this.websocket = null;
    this.pollTimer = null;
    this.reconnectTimer = null;
    this.reconnectAttempt = 0;
    this.selectedRef = null;
    this.selectedObject = null;
    this.machineStates = new Map();
    this.inspector = new FactoryInspector({
      root: document.getElementById("factory-twin-inspector"),
      type: document.getElementById("factory-twin-entity-type"),
      title: document.getElementById("factory-twin-entity-title"),
      body: document.getElementById("factory-twin-inspector-body"),
      actions: document.getElementById("factory-twin-inspector-actions"),
      close: document.getElementById("factory-twin-inspector-close"),
    });
    this.handleKeyDown = event => {
      if (event.key === "Escape") this.clearSelection();
    };
    document.addEventListener("keydown", this.handleKeyDown);
    document.getElementById("factory-twin-inspector-close").onclick = () => this.clearSelection();
    this.bindControls();
  }

  bindControls() {
    this.sourceSelect.onchange = async event => {
      this.source = event.target.value;
      this.disconnect();
      this.selectedRef = null;
      this.inspector.close();
      if (this.source === "CANONICAL_TWIN") {
        await this.loadReplayRange();
        await this.fetchSnapshot(Number(this.replayInput.value || 0));
        this.setConnection("REPLAY", true);
      } else {
        this.replayControl.hidden = true;
        await this.fetchSnapshot();
        this.connect();
      }
    };
    document.getElementById("factory-twin-overview").onclick = () => this.scene?.focusBounds(this.layout.bounds);
    document.getElementById("factory-twin-selected-camera").onclick = () => this.focusSelected();
    document.getElementById("factory-twin-camera-mode").onclick = event => {
      const mode = this.scene?.toggleCameraMode();
      event.currentTarget.textContent = mode === "perspective" ? "Perspective" : "Orthographic";
    };
    document.getElementById("factory-twin-labels").onchange = event => this.scene?.setLabelsVisible(event.target.checked);
    this.replayInput.oninput = event => {
      document.getElementById("factory-twin-replay-output").textContent = event.target.value;
    };
    this.replayInput.onchange = event => this.fetchSnapshot(Number(event.target.value));
    document.addEventListener("visibilitychange", () => {
      if (this.scene) this.scene.setActive(this.active && !document.hidden);
    });
    window.addEventListener("beforeunload", () => this.dispose(), { once: true });
  }

  async activate() {
    this.active = true;
    this.page.hidden = false;
    if (!this.initialized) {
      await this.initialize();
    } else {
      this.scene?.setActive(true);
      if (this.source === "SIMULATOR" && !this.websocket) this.connect();
    }
  }

  deactivate() {
    this.active = false;
    this.page.hidden = true;
    this.scene?.setActive(false);
    this.disconnect();
  }

  async initialize() {
    this.showMessage("Loading factory topology…");
    try {
      this.layout = await this.fetchJSON("/api/v2/factory-twin/layout");
      this.validateSchema(this.layout);
      this.scene = new FactoryScene(
        this.mount,
        this.labelLayer,
        (ref, object) => this.select(ref, object),
        () => this.focusSelected(),
      );
      this.scene.setBounds(this.layout.bounds);
      this.topology = buildFactoryTopology(this.scene, this.layout);
      this.materialFlow = new MaterialFlowView(this.scene, this.layout, this.topology);
      this.scene.tickHandlers.add(elapsed => {
        this.machineStates.forEach((state, equipmentId) => {
          const group = this.topology.entities.get(`equipment:${equipmentId}`);
          if (group) updateMachine(group, state, elapsed);
        });
      });
      this.renderCameraPresets();
      await this.fetchSnapshot();
      this.connect();
      this.initialized = true;
      this.hideMessage();
    } catch (error) {
      this.showMessage(`Factory twin unavailable: ${error.message}`);
      this.setConnection("ERROR", false);
    }
  }

  async fetchSnapshot(atTime = null) {
    const params = new URLSearchParams({ source: this.source });
    if (atTime !== null && this.source === "CANONICAL_TWIN") params.set("at_time", String(atTime));
    const snapshot = await this.fetchJSON(`/api/v2/factory-twin/snapshot?${params}`);
    this.applySnapshot(snapshot);
  }

  async loadReplayRange() {
    const range = await this.fetchJSON("/api/v2/factory-twin/replay-range");
    this.replayControl.hidden = false;
    const minimum = range.min_time ?? 0;
    const maximum = range.max_time ?? minimum;
    this.replayInput.min = String(minimum);
    this.replayInput.max = String(maximum);
    this.replayInput.value = String(maximum);
    document.getElementById("factory-twin-replay-output").textContent = String(maximum);
    if (!range.available) this.showMessage("No canonical replay records are available for this run. The configured factory remains visible.");
  }

  applySnapshot(snapshot) {
    this.validateSchema(snapshot);
    if (snapshot.layout_id !== this.layout.layout_id) {
      throw new Error("layout changed; reload required");
    }
    this.snapshot = snapshot;
    this.renderState();
  }

  applyDelta(delta) {
    this.validateSchema(delta);
    if (!this.snapshot || delta.base_sequence !== this.snapshot.sequence) {
      this.fetchSnapshot();
      return;
    }
    const keys = {
      equipment: "equipment_id",
      queues: "queue_id",
      work_items: "task_uid",
      carriers: "carrier_id",
      transfers: "transfer_id",
    };
    Object.entries(keys).forEach(([collection, key]) => {
      const rows = new Map((this.snapshot[collection] || []).map(row => [String(row[key]), row]));
      (delta.remove?.[collection] || []).forEach(id => rows.delete(String(id)));
      (delta.upsert?.[collection] || []).forEach(row => rows.set(String(row[key]), row));
      this.snapshot[collection] = Array.from(rows.values());
    });
    if (delta.upsert?.warehouse?.[0]) this.snapshot.warehouse = delta.upsert.warehouse[0];
    this.snapshot.sequence = delta.sequence;
    this.snapshot.time = delta.time;
    this.renderState();
  }

  renderState() {
    if (!this.snapshot || !this.topology) return;
    this.machineStates = new Map(this.snapshot.equipment.map(row => [row.equipment_id, row]));
    this.materialFlow.update(this.snapshot);
    document.getElementById("factory-twin-time").textContent = String(this.snapshot.time);
    document.getElementById("factory-twin-sequence").textContent = `sequence ${this.snapshot.sequence}`;
    document.getElementById("factory-twin-provenance").textContent = `${this.snapshot.state_source} · ${this.snapshot.spatial_source} · ${this.snapshot.transport_source}`;
    const busy = this.snapshot.equipment.filter(row => ["BUSY", "PROCESSING", "RUNNING"].includes(row.status)).length;
    const queued = this.snapshot.queues.reduce((sum, row) => sum + Number(row.count || 0), 0);
    document.getElementById("factory-twin-status-summary").textContent = `${busy}/${this.snapshot.equipment.length} processing · ${queued} queued`;
    document.getElementById("factory-twin-transfer-summary").textContent = `${this.snapshot.carriers.length} carriers · warehouse ${this.snapshot.warehouse.completed_count}`;
    if (this.selectedRef) this.renderSelectedInspector();
    this.hideMessage();
  }

  select(ref, object) {
    this.selectedRef = { entityType: ref.entityType, entityId: String(ref.entityId) };
    this.scene.highlightRoute(null);
    this.selectedObject = ref.entityType === "task"
      ? this.taskLocationObject(this.stateEntity(this.selectedRef))
      : object;
    const selectedState = this.stateEntity(this.selectedRef);
    if (ref.entityType === "carrier") this.highlightCarrierRoute(selectedState);
    this.scene.selectObject(this.selectedObject);
    this.renderSelectedInspector();
  }

  taskLocationObject(state) {
    if (!state) return null;
    const locationType = String(state.location_type || "").toLowerCase();
    if (locationType === "carrier") {
      const entry = this.materialFlow.carriers.get(state.carrier_id || state.location_id);
      this.highlightCarrierRoute(entry?.state);
      return entry?.group || null;
    }
    return this.topology.entities.get(`${locationType}:${state.location_id}`) || null;
  }

  highlightCarrierRoute(carrier) {
    const route = carrier ? this.topology.routes.get(carrier.route_id) : null;
    this.scene.highlightRoute(route?.mesh || null);
  }

  clearSelection() {
    this.selectedRef = null;
    this.selectedObject = null;
    this.scene?.selectObject(null);
    this.scene?.highlightRoute(null);
    this.inspector.close();
  }

  renderSelectedInspector() {
    const ref = this.selectedRef;
    if (!ref || !this.snapshot) return;
    const layoutEntity = this.layoutEntity(ref);
    const stateEntity = this.stateEntity(ref);
    this.inspector.show(ref, layoutEntity, stateEntity);
  }

  layoutEntity(ref) {
    const collections = {
      operation: this.layout.operations,
      equipment: this.layout.equipment,
      queue: this.layout.queues,
      route: this.layout.routes,
      warehouse: [this.layout.warehouse],
    };
    return (collections[ref.entityType] || []).find(row => String(row.id) === ref.entityId) || null;
  }

  stateEntity(ref) {
    const collections = {
      equipment: [this.snapshot.equipment, "equipment_id"],
      queue: [this.snapshot.queues, "queue_id"],
      task: [this.snapshot.work_items, "task_uid"],
      carrier: [this.snapshot.carriers, "carrier_id"],
      transfer: [this.snapshot.transfers, "transfer_id"],
      warehouse: [[this.snapshot.warehouse], "warehouse_id"],
    };
    const [rows, key] = collections[ref.entityType] || [[], ""];
    return rows.find(row => String(row[key]) === ref.entityId) || null;
  }

  focusSelected() {
    if (this.selectedObject) {
      const box = new THREE.Box3().setFromObject(this.selectedObject);
      const center = box.getCenter(new THREE.Vector3());
      const size = box.getSize(new THREE.Vector3());
      this.scene.focus(center, Math.max(12, size.length() * 2.5));
      return;
    }
    const state = this.stateEntity(this.selectedRef || {});
    if (state?.location_id) {
      const object = this.topology.entities.get(`${String(state.location_type || "").toLowerCase()}:${state.location_id}`);
      if (object) this.scene.focus(object.position, 14);
    }
  }

  renderCameraPresets() {
    const target = document.getElementById("factory-twin-camera-presets");
    target.replaceChildren();
    this.layout.operations.forEach(operation => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "button compact";
      button.textContent = operation.id;
      button.title = operation.display_name;
      button.onclick = () => this.scene.focus(operation.position, Math.max(operation.size[0], operation.size[2]) * 1.7);
      target.appendChild(button);
    });
    const warehouse = document.createElement("button");
    warehouse.type = "button";
    warehouse.className = "button compact";
    warehouse.textContent = "Warehouse";
    warehouse.onclick = () => this.scene.focus(this.layout.warehouse.position, 24);
    target.appendChild(warehouse);
  }

  connect() {
    if (!this.active || this.source !== "SIMULATOR" || this.websocket) return;
    this.setConnection("CONNECTING", false);
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${location.host}/api/v2/factory-twin/stream?source=SIMULATOR&schema=${SCHEMA_VERSION}`;
    const socket = new WebSocket(url);
    this.websocket = socket;
    socket.onopen = () => {
      this.reconnectAttempt = 0;
      this.stopPolling();
      this.setConnection("LIVE", true);
    };
    socket.onmessage = event => {
      const message = JSON.parse(event.data);
      if (message.type === "snapshot") this.applySnapshot(message.payload);
      else if (message.type === "delta") this.applyDelta(message.payload);
      else if (message.type === "resync_required") this.fetchSnapshot();
      else if (message.type === "heartbeat") this.setConnection("LIVE", true);
    };
    socket.onerror = () => this.setConnection("STALE", false);
    socket.onclose = () => {
      if (this.websocket === socket) this.websocket = null;
      if (!this.active || this.source !== "SIMULATOR") return;
      this.setConnection("POLLING", false);
      this.startPolling();
      const delay = Math.min(10000, 500 * 2 ** this.reconnectAttempt++);
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = setTimeout(() => this.connect(), delay);
    };
  }

  disconnect() {
    clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
    this.stopPolling();
    if (this.websocket) {
      const socket = this.websocket;
      this.websocket = null;
      socket.onclose = null;
      socket.close();
    }
  }

  startPolling() {
    if (this.pollTimer) return;
    this.pollTimer = setInterval(() => this.fetchSnapshot().catch(() => this.setConnection("STALE", false)), 2000);
  }

  stopPolling() {
    clearInterval(this.pollTimer);
    this.pollTimer = null;
  }

  setConnection(text, healthy) {
    this.connection.textContent = text;
    this.connection.classList.toggle("connected", healthy);
    this.connection.classList.toggle("stale", !healthy && !["CONNECTING", "REPLAY"].includes(text));
  }

  validateSchema(payload) {
    if (payload?.schema_version !== SCHEMA_VERSION) {
      throw new Error(`unsupported schema ${payload?.schema_version || "missing"}`);
    }
  }

  async fetchJSON(url) {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
    return response.json();
  }

  showMessage(text) {
    this.message.textContent = text;
    this.message.hidden = false;
  }

  hideMessage() {
    this.message.hidden = true;
  }

  dispose() {
    this.disconnect();
    document.removeEventListener("keydown", this.handleKeyDown);
    this.materialFlow?.dispose();
    this.scene?.dispose();
    this.initialized = false;
  }
}

function boot() {
  const page = document.getElementById("factory-twin-page");
  if (!page) return;
  const app = new FactoryTwinApp(page);
  const update = () => {
    if ((location.hash || "#fab") === "#factory-twin") app.activate();
    else app.deactivate();
  };
  window.addEventListener("hashchange", update);
  update();
  window.factoryTwinApp = app;
}

if (typeof document !== "undefined") {
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
}
