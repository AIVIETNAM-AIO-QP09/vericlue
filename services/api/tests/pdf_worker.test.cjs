const assert = require("node:assert/strict");
const http = require("node:http");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { test } = require("node:test");

const worker = path.resolve(__dirname, "../src/vericlue_api/workers/render_report.cjs");
const moduleDir = path.resolve(__dirname, "../../../apps/web/node_modules/playwright");
const keep = new Set(["PATH", "SYSTEMROOT", "WINDIR", "HOME", "TEMP", "TMP", "USERPROFILE", "LOCALAPPDATA", "APPDATA", "PLAYWRIGHT_BROWSERS_PATH"]);
const env = Object.fromEntries(Object.entries(process.env).filter(([key]) => keep.has(key.toUpperCase())));

function run(packet) {
  return new Promise((resolve, reject) => {
    const processChild = spawn(process.execPath, [worker], { env, windowsHide: true });
    const output = [];
    const errors = [];
    processChild.stdout.on("data", chunk => output.push(chunk));
    processChild.stderr.on("data", chunk => errors.push(chunk));
    processChild.on("error", reject);
    processChild.on("close", code => resolve({ code, pdf: Buffer.concat(output), error: Buffer.concat(errors).toString() }));
    processChild.stdin.end(JSON.stringify(packet));
  });
}

test("actual Chromium worker outputs PDF and does not fetch report resources", { timeout: 45000 }, async () => {
  let requests = 0;
  const server = http.createServer((_request, response) => { requests += 1; response.end("unexpected"); });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  try {
    const port = server.address().port;
    const result = await run({ html: `<html><meta charset="utf-8"><h1>Dữ liệu tổng hợp kiểm PDF</h1><img src="http://127.0.0.1:${port}/must-not-fetch"><script>fetch('http://127.0.0.1:${port}/must-not-execute')</script></html>`, module_dir: moduleDir, timeout_ms: 30000 });
    assert.equal(result.code, 0, result.error);
    assert.equal(result.pdf.subarray(0, 5).toString(), "%PDF-");
    assert.ok(result.pdf.length > 1000 && result.pdf.length < 32 * 1024 * 1024);
    assert.equal(requests, 0);
  } finally { await new Promise(resolve => server.close(resolve)); }
});

test("invalid worker packet fails without exposing document contents", { timeout: 10000 }, async () => {
  const result = await run({ html: "SYNTHETIC_PRIVATE_SENTINEL", module_dir: "relative-is-not-allowed", timeout_ms: 30000 });
  assert.notEqual(result.code, 0);
  assert.equal(result.pdf.length, 0);
  assert.ok(!result.error.includes("SYNTHETIC_PRIVATE_SENTINEL"));
});
