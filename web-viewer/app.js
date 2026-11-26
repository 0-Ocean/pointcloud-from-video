import * as THREE from 'three';
import { OrbitControls } from './vendor/OrbitControls.js';
import { PLYLoader } from './vendor/PLYLoader.js';
import { distanceMetres, midpoint, metresPerUnit } from './measurement.js';

const $ = (id) => document.getElementById(id);
const viewport = $('viewport');
const scene = new THREE.Scene();
scene.background = new THREE.Color('#101a23');
const camera = new THREE.PerspectiveCamera(45, 1, 0.001, 1000);
camera.up.set(0, 0, 1);
let renderer;
try {
  renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
} catch (error) {
  $('loading').hidden = true;
  $('empty-error').hidden = false;
  $('empty-error').textContent = 'Trình duyệt không mở được WebGL. Hãy bật tăng tốc đồ họa hoặc thử trình duyệt khác.';
  throw error;
}
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
$('canvas-mount').appendChild(renderer.domElement);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.09;
const light = new THREE.HemisphereLight(0xffffff, 0x607080, 2.8);
scene.add(light);
const sun = new THREE.DirectionalLight(0xffffff, 1.5);
sun.position.set(3, -4, 8);
scene.add(sun);
const annotations = new THREE.Group();
scene.add(annotations);
const raycaster = new THREE.Raycaster();
const ndc = new THREE.Vector2();
const projected = new THREE.Vector3();
const loader = new PLYLoader();
const state = { model: null, extent: 1, centre: new THREE.Vector3(), picks: [], mode: 'navigate', units: 'unknown', loading: false, sequence: 0 };
let segment = null;
let markers = [];
let pointerStart = null;
const unitNames = { m: 'Mét', cm: 'Centimét', mm: 'Milimét', unknown: 'Chưa rõ đơn vị' };

function disposeObject(object) {
  object.traverse((child) => {
    child.geometry?.dispose();
    const materials = Array.isArray(child.material) ? child.material : [child.material];
    materials.forEach((material) => material?.dispose());
  });
}

function resize() {
  const { width, height } = viewport.getBoundingClientRect();
  camera.aspect = width / Math.max(height, 1);
  camera.updateProjectionMatrix();
  renderer.setSize(width, height);
}
new ResizeObserver(resize).observe(viewport);

function fitCamera() {
  const distance = state.extent * 1.65;
  const direction = new THREE.Vector3(1.2, -1.6, 1).normalize();
  camera.position.copy(state.centre).addScaledVector(direction, distance);
  camera.near = Math.max(state.extent / 10000, 0.000001);
  camera.far = state.extent * 1000;
  camera.updateProjectionMatrix();
  controls.target.copy(state.centre);
  controls.minDistance = state.extent / 1000;
  controls.maxDistance = state.extent * 50;
  controls.update();
}

function selectMode(mode) {
  state.mode = mode;
  viewport.classList.toggle('measuring', mode === 'measure');
  for (const key of ['navigate', 'measure']) {
    $(key).classList.toggle('active', key === mode);
    $(key).setAttribute('aria-pressed', String(key === mode));
  }
  updateStatus();
}

function updateStatus(message) {
  $('undo').disabled = !state.picks.length;
  $('clear').disabled = !state.picks.length;
  $('selection-status').textContent = message || (state.units === 'unknown'
    ? 'Chưa xác định đơn vị. Hãy chọn đơn vị đúng trong thiết lập trước khi đo.'
    : state.picks.length === 2
      ? 'Đã chọn A và B. Chọn điểm tiếp theo để bắt đầu phép đo mới.'
      : state.picks.length === 1
        ? 'Đã chọn A. Nhấp vào vị trí điểm B trên mô hình.'
        : state.mode === 'measure'
          ? 'Nhấp vào mô hình để chọn điểm A. Có thể kéo chuột để đổi góc nhìn.'
          : 'Bật chế độ đo hoặc giữ Shift khi nhấp chọn điểm.');
}

function redrawMeasurement() {
  for (const child of [...annotations.children]) {
    disposeObject(child);
    annotations.remove(child);
  }
  segment = null;
  markers = [];
  $('measure-label').hidden = true;
  $('point-a').hidden = true;
  $('point-b').hidden = true;
  for (const selection of state.picks) {
    const marker = new THREE.Mesh(new THREE.SphereGeometry(1, 16, 12), new THREE.MeshBasicMaterial({ color: '#ffce75', depthTest: false }));
    marker.position.copy(selection.point);
    marker.renderOrder = 20;
    markers.push(marker);
    annotations.add(marker);
  }
  if (state.picks.length === 2) {
    const a = state.picks[0].point;
    const b = state.picks[1].point;
    segment = new THREE.Line(new THREE.BufferGeometry().setFromPoints([a, b]), new THREE.LineBasicMaterial({ color: '#f9cb73', depthTest: false, transparent: true }));
    segment.renderOrder = 19;
    annotations.add(segment);
    const distance = distanceMetres(a.toArray(), b.toArray(), state.units);
    $('measure-label').textContent = `${distance.toLocaleString('vi-VN', { minimumFractionDigits: 3, maximumFractionDigits: 3 })} m`;
    viewport.dataset.distanceMetres = String(distance);
  } else {
    delete viewport.dataset.distanceMetres;
  }
  updateStatus();
}

function labelAt(element, point, yOffset = 0) {
  projected.copy(point).project(camera);
  const width = viewport.clientWidth;
  const height = viewport.clientHeight;
  const inView = projected.z > -1 && projected.z < 1 && Math.abs(projected.x) < 1.1 && Math.abs(projected.y) < 1.1;
  element.hidden = !inView;
  if (inView) {
    element.style.left = `${(projected.x + 1) * width / 2}px`;
    element.style.top = `${(-projected.y + 1) * height / 2 + yOffset}px`;
  }
}

function animate() {
  controls.update();
  for (let i = 0; i < state.picks.length; i++) {
    const point = state.picks[i].point;
    const worldPerPixel = 2 * camera.position.distanceTo(point) * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) / Math.max(viewport.clientHeight, 1);
    markers[i].scale.setScalar(worldPerPixel * 4);
    labelAt($(i === 0 ? 'point-a' : 'point-b'), point, -19);
  }
  if (state.picks.length === 2) {
    const centre = midpoint(state.picks[0].point.toArray(), state.picks[1].point.toArray());
    labelAt($('measure-label'), new THREE.Vector3(...centre));
  }
  renderer.render(scene, camera);
}
renderer.setAnimationLoop(animate);

function pick(clientX, clientY) {
  if (!state.model || state.loading) return;
  if (!metresPerUnit(state.units)) { updateStatus(); return; }
  const rect = renderer.domElement.getBoundingClientRect();
  ndc.set(((clientX - rect.left) / rect.width) * 2 - 1, -((clientY - rect.top) / rect.height) * 2 + 1);
  raycaster.setFromCamera(ndc, camera);
  const worldPerPixel = 2 * camera.position.distanceTo(state.centre) * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) / Math.max(rect.height, 1);
  raycaster.params.Points.threshold = worldPerPixel * Math.max(3, Number($('point-size').value) * 1.5);
  const hits = raycaster.intersectObject(state.model, false);
  let chosen = null;
  for (const hit of hits) {
    const point = state.model.isPoints ? new THREE.Vector3().fromBufferAttribute(state.model.geometry.attributes.position, hit.index) : hit.point.clone();
    projected.copy(point).project(camera);
    const sx = rect.left + (projected.x + 1) * rect.width / 2;
    const sy = rect.top + (-projected.y + 1) * rect.height / 2;
    if (Math.hypot(sx - clientX, sy - clientY) <= 6) { chosen = { point, index: hit.index ?? null }; break; }
  }
  if (!chosen) { updateStatus('Không có điểm tại vị trí này. Hãy phóng to và chọn trên bề mặt mô hình.'); return; }
  if (state.picks.length === 2) state.picks = [];
  if (state.picks.length && state.picks[0].point.distanceTo(chosen.point) < Number.EPSILON) { updateStatus('Hãy chọn điểm B khác điểm A.'); return; }
  state.picks.push(chosen);
  redrawMeasurement();
}

renderer.domElement.addEventListener('pointerdown', (event) => {
  if (event.isPrimary && event.button === 0) pointerStart = { x: event.clientX, y: event.clientY, id: event.pointerId, shift: event.shiftKey, moved: false };
});
renderer.domElement.addEventListener('pointermove', (event) => {
  if (pointerStart && Math.hypot(event.clientX - pointerStart.x, event.clientY - pointerStart.y) > 5) pointerStart.moved = true;
});
renderer.domElement.addEventListener('pointerup', (event) => {
  const start = pointerStart; pointerStart = null;
  if (!start || start.id !== event.pointerId || start.moved || event.button !== 0) return;
  if (state.mode === 'measure' || start.shift) pick(event.clientX, event.clientY);
});
renderer.domElement.addEventListener('pointercancel', () => { pointerStart = null; });
renderer.domElement.addEventListener('contextmenu', (event) => {
  event.preventDefault();
  if (event.shiftKey) { state.picks.pop(); redrawMeasurement(); }
});

function showError(message) {
  $('empty-error').textContent = message;
  $('empty-error').hidden = false;
}

async function openBuffer(buffer, name, configuredUnits = 'unknown') {
  const header = new TextDecoder().decode(buffer.slice(0, Math.min(buffer.byteLength, 65536))).split('end_header')[0];
  if (!/^ply\r?\n/.test(header)) throw new Error('Tệp không phải định dạng PLY hợp lệ.');
  const geometry = loader.parse(buffer);
  try {
    const positions = geometry.getAttribute('position');
    if (!positions || positions.count < 2) throw new Error('File cần có ít nhất hai điểm.');
    for (const value of positions.array) if (!Number.isFinite(value)) throw new Error('File có tọa độ không hợp lệ. Hãy kiểm tra cloud gốc.');
    geometry.computeBoundingBox();
    geometry.computeBoundingSphere();
    const extent = geometry.boundingBox.getSize(new THREE.Vector3()).length();
    if (!(extent > 0)) throw new Error('Mô hình không có kích thước không gian hợp lệ.');
    const isMesh = /element face\s+[1-9]\d*/.test(header);
    const hasColors = !!geometry.getAttribute('color');
    let model;
    if (isMesh) {
      if (!geometry.hasAttribute('normal')) geometry.computeVertexNormals();
      model = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({ vertexColors: hasColors, color: hasColors ? 0xffffff : 0xd1dedb, roughness: 0.9, side: THREE.DoubleSide }));
    } else {
      model = new THREE.Points(geometry, new THREE.PointsMaterial({ size: Number($('point-size').value), sizeAttenuation: false, vertexColors: hasColors, color: hasColors ? 0xffffff : 0xb5d3dc }));
    }
    if (state.model) { scene.remove(state.model); disposeObject(state.model); }
    scene.add(model);
    state.model = model;
    state.extent = extent;
    geometry.boundingBox.getCenter(state.centre);
    state.picks = [];
    state.units = /comment units:\s*metres\b/i.test(header) ? 'm' : configuredUnits;
    if (!metresPerUnit(state.units)) state.units = 'unknown';
    $('file-units').value = state.units;
    $('units').textContent = unitNames[state.units];
    $('model-name').textContent = name;
    $('point-count').textContent = `${positions.count.toLocaleString('vi-VN')} ${isMesh ? 'đỉnh' : 'điểm'}`;
    $('view-label').textContent = `${isMesh ? 'MESH' : 'POINT CLOUD'} / ${name.toUpperCase()}`;
    viewport.dataset.modelReady = 'true';
    viewport.dataset.pointCount = String(positions.count);
    redrawMeasurement();
    fitCamera();
  } catch (error) { geometry.dispose(); throw error; }
}

async function loadDefault() {
  const sequence = ++state.sequence;
  state.loading = true;
  $('loading').hidden = false;
  $('empty-error').hidden = true;
  try {
    const configResponse = await fetch('./model.json', { cache: 'no-cache' });
    if (!configResponse.ok) throw new Error('Không đọc được model.json.');
    const config = await configResponse.json();
    const response = await fetch(config.url);
    if (!response.ok) throw new Error(`Không tải được mô hình (${response.status}). Bạn vẫn có thể chọn Mở file PLY.`);
    const total = Number(response.headers.get('content-length'));
    const reader = response.body?.getReader();
    let buffer;
    if (reader) {
      const chunks = []; let received = 0;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        chunks.push(value); received += value.length;
        $('loading-detail').textContent = total ? `${Math.round(received / total * 100)}% · ${(received / 1048576).toFixed(1)} MB` : `${(received / 1048576).toFixed(1)} MB`;
      }
      buffer = new Uint8Array(received);
      let offset = 0; for (const chunk of chunks) { buffer.set(chunk, offset); offset += chunk.length; }
      buffer = buffer.buffer;
    } else buffer = await response.arrayBuffer();
    if (sequence !== state.sequence) return;
    $('loading-detail').textContent = 'Đang dựng mô hình…';
    await new Promise(requestAnimationFrame);
    if (sequence !== state.sequence) return;
    await openBuffer(buffer, config.name, config.units);
  } catch (error) {
    if (sequence === state.sequence) showError(error.message);
  } finally {
    if (sequence === state.sequence) { state.loading = false; $('loading').hidden = true; }
  }
}

$('navigate').addEventListener('click', () => selectMode('navigate'));
$('measure').addEventListener('click', () => selectMode('measure'));
$('undo').addEventListener('click', () => { state.picks.pop(); redrawMeasurement(); });
$('clear').addEventListener('click', () => { state.picks = []; redrawMeasurement(); });
$('reset-camera').addEventListener('click', fitCamera);
$('point-size').addEventListener('input', () => {
  $('point-size-value').textContent = `${$('point-size').value} px`;
  if (state.model?.isPoints) state.model.material.size = Number($('point-size').value);
});
$('file-units').addEventListener('change', () => {
  state.units = $('file-units').value;
  state.picks = [];
  $('units').textContent = unitNames[state.units];
  redrawMeasurement();
});
$('open-file').addEventListener('click', () => $('file').click());
$('file').addEventListener('change', async () => {
  const file = $('file').files[0];
  if (!file) return;
  if (file.size > 200 * 1024 * 1024) { showError('File lớn hơn 200 MB. Hãy dùng bản cloud nhẹ hơn cho trình duyệt.'); return; }
  const sequence = ++state.sequence;
  state.loading = true;
  $('loading').hidden = false;
  $('empty-error').hidden = true;
  $('loading-detail').textContent = 'Đang đọc tệp trên máy…';
  try { const buffer = await file.arrayBuffer(); if (sequence !== state.sequence) return; await openBuffer(buffer, file.name); }
  catch (error) { showError(error.message); }
  finally { if (sequence === state.sequence) { state.loading = false; $('loading').hidden = true; } $('file').value = ''; }
});
window.addEventListener('keydown', (event) => {
  if (['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;
  if (event.key.toLowerCase() === 'r') { state.picks = []; redrawMeasurement(); }
  if (event.key === 'Backspace' && state.picks.length) { event.preventDefault(); state.picks.pop(); redrawMeasurement(); }
  if (event.key === 'Escape') selectMode('navigate');
});
renderer.domElement.addEventListener('webglcontextlost', (event) => { event.preventDefault(); showError('Ngữ cảnh đồ họa đã bị mất. Hãy tải lại trang hoặc mở file nhẹ hơn.'); });
resize();
loadDefault();