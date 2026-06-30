// ─────────────────────────────────────────────────────────────────────────
//  shotPage — screenshot arbitrary app routes (desktop + mobile) for design
//  review. Dev-only. Requires `next dev` on :3000 and CHROME_BIN.
//  Usage: node scripts/shotPage.mjs /pricing /about /features
//  Output: scratch/page-shots/<slug>-desktop.png and -mobile.png
// ─────────────────────────────────────────────────────────────────────────

import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT = join(__dirname, "..", "scratch", "page-shots");
const BASE = process.env.BASE_URL || "http://localhost:3000";

const paths = process.argv.slice(2).filter((a) => !a.startsWith("--"));
if (!paths.length) { console.log("usage: node scripts/shotPage.mjs /pricing /about ..."); process.exit(1); }

const slug = (p) => (p === "/" ? "home" : p.replace(/^\//, "").replace(/\//g, "-").replace(/\?.*$/, "")) || "home";

async function shoot(page, path, suffix) {
  await page.goto(BASE + path, { waitUntil: "networkidle", timeout: 60000 });
  await page.waitForTimeout(1800);
  const file = join(OUT, `${slug(path)}-${suffix}.png`);
  await page.screenshot({ path: file, fullPage: true });
  console.log(`✓ ${path} (${suffix}) → ${file}`);
}

async function main() {
  await mkdir(OUT, { recursive: true });
  const browser = await chromium.launch({
    executablePath: process.env.CHROME_BIN || undefined,
    args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--no-sandbox"],
  });
  const desk = await browser.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1.25 });
  desk.on("pageerror", (e) => console.log("  [pageerror]", String(e).slice(0, 160)));
  const mob = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });

  for (const p of paths) {
    try { await shoot(desk, p, "desktop"); } catch (e) { console.log(`✗ ${p} desktop: ${String(e).slice(0,120)}`); }
    try { await shoot(mob, p, "mobile"); } catch (e) { console.log(`✗ ${p} mobile: ${String(e).slice(0,120)}`); }
  }
  await browser.close();
}
main().catch((e) => { console.error(e); process.exit(1); });
