import * as THREE from './vendor/three.module.min.js';

// Original procedural illustration. No identity data, textures, models or requests.
const canvas = document.querySelector('#scene');
const motion = matchMedia('(prefers-reduced-motion: reduce)');
const MAX_SECONDS = 6;
let status = 'loading', renderer, scene, camera, group, ring, observer;
let active = false, elapsed = 0, last = 0, frame = 0, frames = 0, disposed = false;
const resources = new Set();

function keep(resource) { resources.add(resource); return resource; }
function rounded(width, height, radius) {
  const s = new THREE.Shape(), x = -width / 2, y = -height / 2;
  s.moveTo(x + radius, y);
  s.lineTo(x + width - radius, y); s.quadraticCurveTo(x + width, y, x + width, y + radius);
  s.lineTo(x + width, y + height - radius); s.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
  s.lineTo(x + radius, y + height); s.quadraticCurveTo(x, y + height, x, y + height - radius);
  s.lineTo(x, y + radius); s.quadraticCurveTo(x, y, x + radius, y);
  return s;
}
function plate(width, height, radius, depth, material) {
  const geometry = keep(new THREE.ExtrudeGeometry(rounded(width, height, radius), {
    depth, bevelEnabled: true, bevelSize: 0.025, bevelThickness: 0.025, bevelSegments: 2, curveSegments: 8,
  }));
  return new THREE.Mesh(geometry, material);
}
function stop() {
  cancelAnimationFrame(frame); frame = 0; last = 0;
}
function render() {
  if (disposed || status === 'fallback') return;
  renderer.render(scene, camera); frames++;
}
function pose(time) {
  group.rotation.set(0.12 + Math.sin(time * 0.8) * 0.035, -0.3 + Math.sin(time * 0.55) * 0.16, -0.08);
  group.position.y = Math.sin(time * 0.9) * 0.045;
  ring.rotation.z = time * 0.12;
}
function animate(now) {
  frame = 0;
  if (disposed || !active || document.hidden || motion.matches || elapsed >= MAX_SECONDS) return;
  // Bound drawing to ~30 fps. Keep the animation budget across pause/resume.
  if (last && now - last < 32) { frame = requestAnimationFrame(animate); return; }
  elapsed = Math.min(MAX_SECONDS, elapsed + (last ? (now - last) / 1000 : 0));
  last = now; pose(elapsed); render();
  if (elapsed < MAX_SECONDS) frame = requestAnimationFrame(animate);
}
function schedule() {
  stop();
  if (!disposed && status === 'ready' && active && !document.hidden && !motion.matches && elapsed < MAX_SECONDS) {
    frame = requestAnimationFrame(animate);
  }
}
function resize() {
  if (disposed || !renderer) return;
  const width = Math.max(1, canvas.clientWidth), height = Math.max(1, canvas.clientHeight);
  const aspect = width / height, span = 3.65 / Math.min(1, aspect);
  camera.left = -span * aspect / 2; camera.right = span * aspect / 2;
  camera.top = span / 2; camera.bottom = -span / 2;
  camera.updateProjectionMatrix();
  renderer.setSize(width, height, false); render();
}
function fail() {
  if (disposed) return;
  status = 'fallback'; dispose();
  // Fixed signal to the host; no JavaScript/native bridge or user payload.
  console.error('vericlue-scene-fallback');
}
function dispose() {
  if (disposed) return;
  stop(); disposed = true; observer?.disconnect();
  document.removeEventListener('visibilitychange', schedule);
  motion.removeEventListener('change', schedule);
  resources.forEach(resource => resource.dispose()); resources.clear();
  renderer?.dispose(); renderer?.forceContextLoss();
  if (status !== 'fallback') status = 'disposed';
}

window.vericlueScene = Object.freeze({
  get status() { return status; },
  get frames() { return frames; },
  get elapsed() { return elapsed; },
  get playing() { return frame !== 0; },
  get drawCalls() { return renderer?.info.render.calls ?? 0; },
  setActive(value) { active = value === true; schedule(); },
  dispose,
});

try {
  renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, powerPreference: 'low-power' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  renderer.setClearColor(0x000000, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  scene = new THREE.Scene(); camera = new THREE.OrthographicCamera(-2, 2, 2, -2, 0.1, 30);
  camera.position.set(0, 0, 8);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x3064a4, 3));
  const key = new THREE.DirectionalLight(0xffead3, 3); key.position.set(-3, 4, 6); scene.add(key);
  const rim = new THREE.DirectionalLight(0x6fa3ff, 2); rim.position.set(4, -1, 2); scene.add(rim);
  const ivory = keep(new THREE.MeshStandardMaterial({ color: 0xfaf8f5, roughness: 0.35, metalness: 0.08 }));
  const navy = keep(new THREE.MeshStandardMaterial({ color: 0x246bdf, roughness: 0.3, metalness: 0.25 }));
  const gold = keep(new THREE.MeshStandardMaterial({ color: 0xe2b86e, roughness: 0.3, metalness: 0.6 }));
  const line = keep(new THREE.MeshStandardMaterial({ color: 0x729eb1, roughness: 0.6 }));
  group = new THREE.Group(); scene.add(group);
  const card = plate(2.45, 1.55, 0.16, 0.085, ivory); group.add(card);
  const back = plate(2.45, 1.55, 0.16, 0.07, navy);
  back.position.set(0.12, 0.12, -0.18); back.rotation.z = 0.09; group.add(back);
  const chip = plate(0.42, 0.31, 0.05, 0.02, gold); chip.position.set(-0.77, 0.32, 0.13); group.add(chip);
  [1.05, 0.78, 0.9].forEach((width, i) => {
    const bar = plate(width, 0.06, 0.025, 0.006, line);
    bar.position.set(-0.39, -0.12 - i * 0.2, 0.13); group.add(bar);
  });
  const medallion = new THREE.Mesh(keep(new THREE.CylinderGeometry(0.4, 0.4, 0.09, 40)), navy);
  medallion.rotation.x = Math.PI / 2; medallion.position.set(0.7, 0.12, 0.18); group.add(medallion);
  const head = new THREE.Mesh(keep(new THREE.SphereGeometry(0.105, 16, 12)), ivory);
  head.position.set(0.7, 0.23, 0.25); group.add(head);
  const shoulders = plate(0.38, 0.17, 0.08, 0.02, ivory);
  shoulders.position.set(0.7, -0.03, 0.25); group.add(shoulders);
  ring = new THREE.Group(); ring.position.z = -0.5; scene.add(ring);
  const orbit = new THREE.Mesh(keep(new THREE.TorusGeometry(1.52, 0.012, 6, 80)),
    keep(new THREE.MeshBasicMaterial({ color: 0x6fa3ff, transparent: true, opacity: 0.5 })));
  orbit.scale.y = 0.83; ring.add(orbit);
  [0.4, 2.5, 4.6].forEach((angle, i) => {
    const bead = new THREE.Mesh(keep(new THREE.SphereGeometry(0.06, 12, 8)),
      keep(new THREE.MeshStandardMaterial({ color: [0xe8743b, 0x6fa3ff, 0x4cd497][i], roughness: 0.35 })));
    bead.position.set(Math.cos(angle) * 1.52, Math.sin(angle) * 1.52 * 0.83, 0); ring.add(bead);
  });
  pose(0); resize(); status = 'ready';
  observer = new ResizeObserver(resize); observer.observe(canvas);
  canvas.addEventListener('webglcontextlost', event => { event.preventDefault(); fail(); }, { once: true });
  document.addEventListener('visibilitychange', schedule);
  motion.addEventListener('change', schedule);
  window.addEventListener('pagehide', dispose, { once: true });
  // Native host starts playback only after readiness and foreground checks.
} catch { fail(); }
