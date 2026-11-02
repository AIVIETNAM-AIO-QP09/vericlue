import * as THREE from './vendor/three.module.min.js';
import { SCENES, createIllustration } from './illustrations.js';

// Original procedural illustration. No identity data, textures, models or requests.
const canvas = document.querySelector('#scene');
const motion = matchMedia('(prefers-reduced-motion: reduce)');
const duration = () => ['privacy', 'success'].includes(mode) ? 3 : 6;
let status = 'loading', renderer, scene, camera, illustration, observer;
let active = false, elapsed = 0, last = 0, frame = 0, frames = 0, disposed = false;
let mode = 'card', dark = true;

function stop() {
  cancelAnimationFrame(frame); frame = 0; last = 0;
}
function render() {
  if (disposed || status === 'fallback') return;
  renderer.render(scene, camera); frames++;
}
function pose(time) { illustration?.pose(time, !motion.matches); }
function configure(next, isDark) {
  if (disposed || !SCENES.includes(next) || typeof isDark !== 'boolean') return false;
  if (illustration && next === mode && isDark === dark) return true;
  stop();
  if (illustration) { scene.remove(illustration.root); illustration.dispose(); }
  mode = next; dark = isDark; elapsed = 0;
  try {
    illustration = createIllustration(mode, dark); scene.add(illustration.root);
    pose(0); render(); schedule(); return true;
  } catch { fail(); return false; }
}
function replay() {
  if (disposed || status !== 'ready') return;
  elapsed = 0; pose(0); render(); schedule();
}
function animate(now) {
  frame = 0;
  if (disposed || !active || document.hidden || motion.matches || elapsed >= duration()) return;
  // Bound drawing to ~30 fps. Keep the animation budget across pause/resume.
  if (last && now - last < 32) { frame = requestAnimationFrame(animate); return; }
  elapsed = Math.min(duration(), elapsed + (last ? (now - last) / 1000 : 0));
  last = now; pose(elapsed); render();
  if (elapsed < duration()) frame = requestAnimationFrame(animate);
}
function schedule() {
  stop();
  if (!disposed && status === 'ready' && active && !document.hidden && !motion.matches && elapsed < duration()) {
    frame = requestAnimationFrame(animate);
  }
}
function motionChanged() { schedule(); pose(elapsed); render(); }
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
  motion.removeEventListener('change', motionChanged);
  illustration?.dispose();
  renderer?.dispose(); renderer?.forceContextLoss();
  if (status !== 'fallback') status = 'disposed';
}

window.vericlueScene = Object.freeze({
  get status() { return status; },
  get scene() { return mode; },
  get dark() { return dark; },
  get memory() { return { ...renderer?.info.memory }; },
  configure, replay,
  get frames() { return frames; },
  get elapsed() { return elapsed; },
  get duration() { return duration(); },
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
  if (!configure('card', true)) throw new Error('Scene unavailable');
  resize(); status = 'ready';
  observer = new ResizeObserver(resize); observer.observe(canvas);
  canvas.addEventListener('webglcontextlost', event => { event.preventDefault(); fail(); }, { once: true });
  document.addEventListener('visibilitychange', schedule);
  motion.addEventListener('change', motionChanged);
  window.addEventListener('pagehide', dispose, { once: true });
  // Native host starts playback only after readiness and foreground checks.
} catch { fail(); }
