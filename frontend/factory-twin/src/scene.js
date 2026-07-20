import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

export class FactoryScene {
  constructor(mount, labelLayer, onSelect, onFocus) {
    this.mount = mount;
    this.labelLayer = labelLayer;
    this.onSelect = onSelect;
    this.onFocus = onFocus;
    this.startedAt = performance.now();
    this.root = new THREE.Group();
    this.labels = [];
    this.tickHandlers = new Set();
    this.running = true;
    this.selectedHelper = null;
    this.highlightedRoute = null;
    this.cameraMode = "orthographic";
    this.savedTarget = new THREE.Vector3();

    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "high-performance" });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setClearColor(0xe8edf1, 1);
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFShadowMap;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    mount.replaceChildren(this.renderer.domElement);

    this.scene = new THREE.Scene();
    this.scene.fog = new THREE.Fog(0xe8edf1, 95, 190);
    this.scene.add(this.root);
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0xa7b0b8, 2.2));
    const key = new THREE.DirectionalLight(0xffffff, 3.1);
    key.position.set(28, 54, 32);
    key.castShadow = true;
    key.shadow.mapSize.set(2048, 2048);
    key.shadow.camera.left = -80;
    key.shadow.camera.right = 80;
    key.shadow.camera.top = 80;
    key.shadow.camera.bottom = -80;
    this.scene.add(key);

    this.orthographicCamera = new THREE.OrthographicCamera(-40, 40, 24, -24, 0.1, 400);
    this.perspectiveCamera = new THREE.PerspectiveCamera(42, 1, 0.1, 400);
    this.camera = this.orthographicCamera;
    this.camera.position.set(64, 52, 72);
    this.camera.lookAt(25, 0, 0);
    this.controls = this.createControls(this.camera);
    this.raycaster = new THREE.Raycaster();
    this.pointer = new THREE.Vector2();
    this.handlePointer = event => this.pick(event);
    this.handleDoubleClick = event => {
      this.pick(event);
      this.onFocus?.();
    };
    this.renderer.domElement.addEventListener("pointerup", this.handlePointer);
    this.renderer.domElement.addEventListener("dblclick", this.handleDoubleClick);
    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(mount);
    this.resize();
    this.animate = this.animate.bind(this);
    this.renderer.setAnimationLoop(this.animate);
  }

  createControls(camera) {
    const controls = new OrbitControls(camera, this.renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.screenSpacePanning = true;
    controls.maxPolarAngle = Math.PI * 0.49;
    controls.minDistance = 12;
    controls.maxDistance = 180;
    controls.target.copy(this.savedTarget);
    return controls;
  }

  setBounds(bounds) {
    this.bounds = bounds;
    this.pendingFit = true;
    const min = bounds.min;
    const max = bounds.max;
    const width = max[0] - min[0];
    const depth = max[2] - min[2];
    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(width + 20, depth + 20),
      new THREE.MeshStandardMaterial({ color: 0xf3f5f7, roughness: 0.96 })
    );
    floor.rotation.x = -Math.PI / 2;
    floor.position.set((min[0] + max[0]) / 2, -0.08, (min[2] + max[2]) / 2);
    floor.receiveShadow = true;
    floor.userData.disposeMaterial = true;
    this.root.add(floor);
    const grid = new THREE.GridHelper(Math.max(width, depth) + 20, 36, 0xa8b1b9, 0xd5dade);
    grid.position.copy(floor.position);
    grid.position.y = 0;
    this.root.add(grid);
    if (this.mount.clientWidth > 0 && this.mount.clientHeight > 0) {
      this.pendingFit = false;
      this.focusBounds(bounds);
    }
  }

  focusBounds(bounds) {
    const min = new THREE.Vector3(...bounds.min);
    const max = new THREE.Vector3(...bounds.max);
    const center = min.clone().add(max).multiplyScalar(0.5);
    const size = max.clone().sub(min);
    const aspect = Math.max(0.5, this.mount.clientWidth / Math.max(1, this.mount.clientHeight));
    this.focus(center, Math.max(size.z, size.x / aspect) * 1.18);
  }

  focus(position, span = 18) {
    const target = position.isVector3 ? position.clone() : new THREE.Vector3(...position);
    this.savedTarget.copy(target);
    const direction = new THREE.Vector3(0.72, 0.72, 0.9).normalize();
    const distance = Math.max(18, span * 1.45);
    this.camera.position.copy(target).add(direction.multiplyScalar(distance));
    this.controls.target.copy(target);
    if (this.camera.isOrthographicCamera) {
      this.camera.userData.viewSpan = Math.max(16, span);
      this.resize();
    }
    this.camera.lookAt(target);
    this.controls.update();
  }

  toggleCameraMode() {
    const previous = this.camera;
    const target = this.controls.target.clone();
    const position = previous.position.clone();
    this.controls.dispose();
    if (previous.isOrthographicCamera) {
      this.camera = this.perspectiveCamera;
      this.cameraMode = "perspective";
    } else {
      this.camera = this.orthographicCamera;
      this.cameraMode = "orthographic";
    }
    this.camera.position.copy(position);
    this.camera.lookAt(target);
    this.controls = this.createControls(this.camera);
    this.controls.target.copy(target);
    this.resize();
    return this.cameraMode;
  }

  addLabel(object, text, id) {
    const element = document.createElement("span");
    element.className = "factory-twin-label";
    element.textContent = text;
    element.dataset.entityId = id;
    element.dataset.entityType = object.userData.entityRef?.entityType || "entity";
    this.labelLayer.appendChild(element);
    this.labels.push({ object, element });
  }

  setLabelsVisible(visible) {
    this.labelLayer.hidden = !visible;
  }

  selectObject(object) {
    if (this.selectedHelper) {
      this.scene.remove(this.selectedHelper);
      this.selectedHelper.geometry.dispose();
      this.selectedHelper.material.dispose();
      this.selectedHelper = null;
    }
    if (!object) return;
    this.selectedHelper = new THREE.BoxHelper(object, 0x0f62fe);
    this.selectedHelper.material.depthTest = false;
    this.selectedHelper.material.transparent = true;
    this.selectedHelper.material.opacity = 0.95;
    this.selectedHelper.renderOrder = 20;
    this.scene.add(this.selectedHelper);
  }

  highlightRoute(route) {
    if (this.highlightedRoute?.material) {
      this.highlightedRoute.material.color.setHex(0x66737e);
      this.highlightedRoute.material.emissive.setHex(0x000000);
    }
    this.highlightedRoute = route || null;
    if (this.highlightedRoute?.material) {
      this.highlightedRoute.material.color.setHex(0x0f62fe);
      this.highlightedRoute.material.emissive.setHex(0x001d6c);
      this.highlightedRoute.material.emissiveIntensity = 0.35;
    }
  }

  pick(event) {
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    this.raycaster.setFromCamera(this.pointer, this.camera);
    const intersections = this.raycaster.intersectObjects(this.root.children, true);
    for (const hit of intersections) {
      const ref = hit.object.userData.entityRef;
      const instanceIds = hit.object.userData.instanceEntityIds;
      if (instanceIds && Number.isInteger(hit.instanceId) && instanceIds[hit.instanceId]) {
        this.onSelect(instanceIds[hit.instanceId], hit.object);
        return;
      }
      if (ref) {
        this.onSelect(ref, this.entityRoot(hit.object));
        return;
      }
    }
  }

  entityRoot(object) {
    let current = object;
    while (current.parent && current.parent !== this.root && current.parent.userData.entityRef === current.userData.entityRef) {
      current = current.parent;
    }
    return current;
  }

  resize() {
    const width = Math.max(1, this.mount.clientWidth);
    const height = Math.max(1, this.mount.clientHeight);
    const aspect = width / height;
    const span = this.orthographicCamera.userData.viewSpan || 70;
    this.orthographicCamera.left = -span * aspect / 2;
    this.orthographicCamera.right = span * aspect / 2;
    this.orthographicCamera.top = span / 2;
    this.orthographicCamera.bottom = -span / 2;
    this.orthographicCamera.updateProjectionMatrix();
    this.perspectiveCamera.aspect = aspect;
    this.perspectiveCamera.updateProjectionMatrix();
    this.renderer.setSize(width, height, false);
    this.mount.dataset.cameraDebug = JSON.stringify({
      mode: this.cameraMode,
      width,
      height,
      aspect,
      span,
      left: this.orthographicCamera.left,
      right: this.orthographicCamera.right,
      top: this.orthographicCamera.top,
      bottom: this.orthographicCamera.bottom,
      zoom: this.orthographicCamera.zoom,
    });
    if (this.pendingFit && this.mount.clientWidth > 0 && this.mount.clientHeight > 0) {
      this.pendingFit = false;
      this.focusBounds(this.bounds);
    }
  }

  animate() {
    if (!this.running) return;
    const elapsed = (performance.now() - this.startedAt) / 1000;
    this.controls.update();
    this.tickHandlers.forEach(handler => handler(elapsed));
    if (this.selectedHelper) this.selectedHelper.update();
    this.updateLabels();
    this.renderer.render(this.scene, this.camera);
  }

  updateLabels() {
    const width = this.mount.clientWidth;
    const height = this.mount.clientHeight;
    const point = new THREE.Vector3();
    const overview = this.camera.isOrthographicCamera
      ? (this.camera.userData.viewSpan || 70) > 48
      : this.camera.position.distanceTo(this.controls.target) > 72;
    this.labels.forEach(({ object, element }) => {
      object.getWorldPosition(point);
      point.y += 2.4;
      point.project(this.camera);
      const visible = point.z > -1 && point.z < 1
        && !(overview && element.dataset.entityType === "equipment")
        && !(!overview && element.dataset.entityType === "operation");
      element.hidden = !visible;
      if (visible) {
        element.style.left = `${(point.x * 0.5 + 0.5) * width}px`;
        element.style.top = `${(-point.y * 0.5 + 0.5) * height}px`;
      }
    });
  }

  setActive(active) {
    this.running = active;
    this.renderer.setAnimationLoop(active ? this.animate : null);
    if (active) this.resize();
  }

  dispose() {
    this.renderer.setAnimationLoop(null);
    this.resizeObserver.disconnect();
    this.renderer.domElement.removeEventListener("pointerup", this.handlePointer);
    this.renderer.domElement.removeEventListener("dblclick", this.handleDoubleClick);
    this.controls.dispose();
    this.scene.traverse(object => {
      if (object.geometry && !object.isInstancedMesh) object.geometry.dispose();
      if (object.userData.disposeMaterial && object.material) object.material.dispose();
    });
    this.labelLayer.replaceChildren();
    this.renderer.dispose();
    this.mount.replaceChildren();
  }
}
