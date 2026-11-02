// Run with Node after installing apps/web's existing Playwright dependency.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const require = createRequire(new URL('../../web/package.json', import.meta.url));
const { chromium } = require('playwright');
const assets = fileURLToPath(new URL('../app/src/main/assets/three/', import.meta.url));
const output = fileURLToPath(new URL('../../../tmp/app11-ui/three/', import.meta.url));
const origin = 'https://appassets.androidplatform.net';
const types = new Map([['index.html', 'text/html'], ['scene.css', 'text/css'],
  ['scene.js', 'text/javascript'], ['illustrations.js', 'text/javascript'], ['vendor/three.module.min.js', 'text/javascript']]);
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true,
  ...(process.env.VERICLUE_BROWSER_PATH ? { executablePath: process.env.VERICLUE_BROWSER_PATH }
    : process.platform === 'win32' ? { channel: 'msedge' } : {}),
  args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
});
const results = [];
async function pageFor(options = {}) {
  const page = await browser.newPage({ viewport: { width: 360, height: 280 }, ...options });
  const unexpected = [], errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url());
    const name = url.pathname.slice('/three/'.length);
    if (url.origin !== origin || !url.pathname.startsWith('/three/') || !types.has(name) || url.search || request.method() !== 'GET') {
      unexpected.push(request.url()); await route.abort(); return;
    }
    await route.fulfill({ body: await readFile(path.join(assets, name)), contentType: types.get(name) });
  });
  return { page, unexpected, errors };
}
async function open(page) {
  await page.goto(`${origin}/three/index.html`);
  await page.waitForFunction(() => window.vericlueScene?.status === 'ready');
}
try {
  const { page, unexpected, errors } = await pageFor();
  await open(page);
  assert.equal(await page.evaluate(() => window.vericlueScene.playing), false);
  await page.screenshot({ path: path.join(output, 'three-static.png'), omitBackground: true });
  await page.evaluate(() => window.vericlueScene.setActive(true));
  await page.waitForTimeout(900);
  await page.screenshot({ path: path.join(output, 'three-motion.png'), omitBackground: true });
  await page.evaluate(() => window.vericlueScene.setActive(false));
  const paused = await page.evaluate(() => window.vericlueScene.frames);
  await page.waitForTimeout(300);
  assert.equal(await page.evaluate(() => window.vericlueScene.frames), paused, 'Paused scene drew new frames');
  await page.evaluate(() => window.vericlueScene.setActive(true));
  await page.waitForFunction(() => !window.vericlueScene.playing && window.vericlueScene.elapsed === 3);
  const completed = await page.evaluate(() => ({ frames: window.vericlueScene.frames, calls: window.vericlueScene.drawCalls }));
  assert.ok(completed.frames <= 105, `Frame budget exceeded: ${completed.frames}`);
  assert.ok(completed.calls <= 24, `Draw call budget exceeded: ${completed.calls}`);
  await page.waitForTimeout(300);
  assert.equal(await page.evaluate(() => window.vericlueScene.frames), completed.frames);
  await page.setViewportSize({ width: 120, height: 120 });
  await page.screenshot({ path: path.join(output, 'three-compact.png'), omitBackground: true });
  assert.deepEqual(unexpected, []); assert.deepEqual(errors, []);
  await page.evaluate(() => window.vericlueScene.dispose());
  assert.equal(await page.evaluate(() => window.vericlueScene.status), 'disposed');
  results.push({ test: 'WebGL render, pause/resume, three-second budget, resize, dispose, offline', ...completed });
  await page.close();

  const chapters = await pageFor();
  await open(chapters.page);
  const modes = ['card', 'face', 'eyes', 'turn', 'voice', 'privacy', 'success'];
  const memory = {};
  for (const mode of modes) {
    for (const dark of [true, false]) {
      assert.equal(await chapters.page.evaluate(({ mode, dark }) => window.vericlueScene.configure(mode, dark), { mode, dark }), true);
      await chapters.page.evaluate(() => window.vericlueScene.setActive(true));
      await chapters.page.waitForTimeout(550);
      await chapters.page.evaluate(() => window.vericlueScene.setActive(false));
      await chapters.page.screenshot({ path: path.join(output, `${mode}-${dark ? 'dark' : 'light'}.png`), omitBackground: true });
      const metrics = await chapters.page.evaluate(() => ({ scene: window.vericlueScene.scene, memory: window.vericlueScene.memory,
        calls: window.vericlueScene.drawCalls, canvases: document.querySelectorAll('canvas').length }));
      assert.equal(metrics.scene, mode); assert.equal(metrics.canvases, 1);
      assert.equal(await chapters.page.evaluate(() => window.vericlueScene.duration), 3);
      assert.ok(metrics.calls <= 24, `${mode}: too many draw calls`);
      memory[mode] = metrics.memory;
    }
  }
  // Switching reuses one renderer and frees old geometry/instance buffers.
  for (let cycle = 0; cycle < 8; cycle++) {
    for (const mode of modes) {
      const metrics = await chapters.page.evaluate(mode => {
        window.vericlueScene.configure(mode, false); return window.vericlueScene.memory;
      }, mode);
      assert.deepEqual(metrics, memory[mode], `GPU allocations grew for ${mode} in cycle ${cycle}`);
    }
  }
  const unchanged = await chapters.page.evaluate(() => {
    const s = window.vericlueScene;
    return [s.configure('unknown', false), s.configure('face', 'false'), s.scene];
  });
  assert.deepEqual(unchanged, [false, false, 'success']);
  await chapters.page.evaluate(() => { window.vericlueScene.setActive(true); window.vericlueScene.replay(); });
  await chapters.page.waitForFunction(() => window.vericlueScene.elapsed === 3 && !window.vericlueScene.playing);
  await chapters.page.evaluate(() => window.vericlueScene.replay());
  await chapters.page.waitForFunction(() => window.vericlueScene.elapsed > 0.1);
  await chapters.page.emulateMedia({ reducedMotion: 'reduce' });
  await chapters.page.waitForTimeout(100);
  const frozen = await chapters.page.evaluate(() => window.vericlueScene.frames);
  await chapters.page.waitForTimeout(200);
  assert.equal(await chapters.page.evaluate(() => window.vericlueScene.frames), frozen);
  await chapters.page.evaluate(() => window.vericlueScene.configure('turn', true));
  assert.equal(await chapters.page.evaluate(() => window.vericlueScene.playing), false);
  assert.deepEqual(chapters.errors, []); assert.deepEqual(chapters.unexpected, []);
  await chapters.page.evaluate(() => window.vericlueScene.dispose());
  assert.equal(await chapters.page.evaluate(() => window.vericlueScene.memory.geometries), 0);
  results.push({ test: 'Seven chapters, both themes, 56 switches without GPU growth, replay, live reduced motion, invalid input', memory });
  await chapters.page.close();

  const reduced = await pageFor({ reducedMotion: 'reduce' });
  await open(reduced.page);
  await reduced.page.evaluate(() => window.vericlueScene.setActive(true));
  await reduced.page.waitForTimeout(100);
  const still = await reduced.page.evaluate(() => window.vericlueScene.frames);
  await reduced.page.waitForTimeout(300);
  assert.equal(await reduced.page.evaluate(() => window.vericlueScene.frames), still);
  assert.equal(await reduced.page.evaluate(() => window.vericlueScene.playing), false);
  assert.deepEqual(reduced.errors, []); assert.deepEqual(reduced.unexpected, []);
  results.push({ test: 'Reduced motion never schedules animation' });
  await reduced.page.close();

  const unavailable = await pageFor();
  await unavailable.page.addInitScript(() => {
    const getContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (type, ...args) {
      return type.includes('webgl') ? null : getContext.call(this, type, ...args);
    };
  });
  await unavailable.page.goto(`${origin}/three/index.html`);
  await unavailable.page.waitForFunction(() => window.vericlueScene?.status === 'fallback');
  assert.equal(await unavailable.page.evaluate(() => window.vericlueScene.playing), false);
  assert.deepEqual(unavailable.errors, []); assert.deepEqual(unavailable.unexpected, []);
  results.push({ test: 'Missing WebGL signals fallback without an uncaught error' });
  await unavailable.page.close();

  const lost = await pageFor();
  await open(lost.page);
  await lost.page.evaluate(() => document.querySelector('canvas').getContext('webgl2').getExtension('WEBGL_lose_context').loseContext());
  await lost.page.waitForFunction(() => window.vericlueScene.status === 'fallback');
  assert.equal(await lost.page.evaluate(() => window.vericlueScene.playing), false);
  results.push({ test: 'Lost WebGL context signals fallback and stops rendering' });
  await lost.page.close();
  await writeFile(path.join(output, 'browser-results.json'), JSON.stringify({ browser: await browser.version(), results }, null, 2) + '\n');
  console.log(JSON.stringify({ passed: results.length, results }, null, 2));
} finally { await browser.close(); }
