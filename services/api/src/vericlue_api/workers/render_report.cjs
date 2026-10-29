// Trusted server HTML only. Playwright/Chromium runtime is configured separately.
const path = require("node:path");
const MAX_PACKET = 8 * 1024 * 1024;
const MAX_PDF = 32 * 1024 * 1024;
let browser;
let timer;

async function main() {
  const chunks = [];
  let size = 0;
  for await (const chunk of process.stdin) {
    size += chunk.length;
    if (size > MAX_PACKET) throw new Error("packet_too_large");
    chunks.push(chunk);
  }
  const packet = JSON.parse(Buffer.concat(chunks).toString("utf8"));
  if (typeof packet.html !== "string" || Buffer.byteLength(packet.html) > 4 * 1024 * 1024 ||
      !path.isAbsolute(packet.module_dir) || !Number.isInteger(packet.timeout_ms) ||
      packet.timeout_ms < 1000 || packet.timeout_ms > 60000) throw new Error("invalid_packet");
  timer = setTimeout(async () => {
    try { if (browser) await browser.close(); } finally { process.exit(1); }
  }, packet.timeout_ms);
  const { chromium } = require(packet.module_dir);
  browser = await chromium.launch({ headless: true, chromiumSandbox: true, timeout: packet.timeout_ms });
  const context = await browser.newContext({ javaScriptEnabled: false, serviceWorkers: "block", offline: true });
  await context.route("**/*", route => route.abort());
  const page = await context.newPage();
  await page.setContent(packet.html, { waitUntil: "load", timeout: packet.timeout_ms });
  const pdf = await page.pdf({ format: "A4", printBackground: true,
    margin: { top: "18mm", bottom: "20mm", left: "16mm", right: "16mm" },
    displayHeaderFooter: true, headerTemplate: "<span></span>",
    footerTemplate: '<div style="width:100%;font-family:Arial,sans-serif;font-size:8px;text-align:center;color:#64748b">VeriClue - <span class="pageNumber"></span> / <span class="totalPages"></span></div>' });
  if (!pdf.length || pdf.length > MAX_PDF) throw new Error("pdf_too_large");
  await browser.close();
  browser = undefined;
  clearTimeout(timer);
  process.stdout.write(pdf);
}

main().catch(async () => {
  clearTimeout(timer);
  try { if (browser) await browser.close(); } catch { /* parent also enforces deadline */ }
  process.stderr.write("pdf_render_failed\n");
  process.exitCode = 1;
});
