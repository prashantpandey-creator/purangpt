// ─────────────────────────────────────────────────────────────────────────
//  shotBindu — offline WebGL2 screenshot harness for the Bindu shaders.
//
//  Renders any shader from src/lib/binduShaders.mjs in headless Chromium
//  (SwiftShader) at sampled (t, lv) and writes PNGs to scratch/bindu-shots/.
//  This is a DEV tool — it lets me actually SEE shader output and tune against
//  pixels instead of guessing. Not shipped, not imported by the app.
//
//  Usage:
//    node scripts/shotBindu.mjs                 # all iterations, default samples
//    node scripts/shotBindu.mjs E2 E4           # just these keys
//    node scripts/shotBindu.mjs E2 --t=0,3,6,9 --lv=1   # custom time/level samples
//
//  Output: one PNG per (key, t, lv) plus a per-key horizontal contact strip.
// ─────────────────────────────────────────────────────────────────────────

import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import * as S from "../src/lib/binduShaders.mjs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT = join(__dirname, "..", "scratch", "bindu-shots");

const ALL = {
  A: S.ITER_A, B: S.ITER_B, C: S.ITER_C, D: S.ITER_D, E: S.ITER_E,
  E1: S.ITER_E1, E2: S.ITER_E2, E3: S.ITER_E3, E4: S.ITER_E4, E5: S.ITER_E5,
  "4D": S.ITER_4D,
};

// ── Parse CLI ──
const argv = process.argv.slice(2);
const keys = argv.filter((a) => !a.startsWith("--"));
const flag = (name, def) => {
  const f = argv.find((a) => a.startsWith(`--${name}=`));
  return f ? f.split("=")[1] : def;
};
const SIZE = parseInt(flag("size", "320"), 10);
const ts = flag("t", "0,2.5,5,7.5,10").split(",").map(Number);
const lvs = flag("lv", "0,1").split(",").map(Number);
const pickKeys = keys.length ? keys : Object.keys(ALL);

// HTML harness — compiles one shader, draws ONE frame at given (t, lv).
const HARNESS = (vs, fs, size) => `<!doctype html><html><head><meta charset="utf-8">
<style>html,body{margin:0;background:#0A0810}canvas{display:block}</style></head>
<body><canvas id="c" width="${size}" height="${size}"></canvas>
<script>
const VS = ${JSON.stringify(vs)};
const FS = ${JSON.stringify(fs)};
const gl = document.getElementById('c').getContext('webgl2', {alpha:true, premultipliedAlpha:true, antialias:true});
function sh(type, src){const s=gl.createShader(type);gl.shaderSource(s,src);gl.compileShader(s);
  if(!gl.getShaderParameter(s,gl.COMPILE_STATUS)){document.title='ERR:'+gl.getShaderInfoLog(s);throw new Error(gl.getShaderInfoLog(s));}return s;}
const p=gl.createProgram();
gl.attachShader(p, sh(gl.VERTEX_SHADER, VS));
gl.attachShader(p, sh(gl.FRAGMENT_SHADER, FS));
gl.linkProgram(p);
if(!gl.getProgramParameter(p,gl.LINK_STATUS)){document.title='LINKERR:'+gl.getProgramInfoLog(p);throw new Error('link');}
gl.useProgram(p);
const buf=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buf);
gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]),gl.STATIC_DRAW);
const a=gl.getAttribLocation(p,'a_pos');gl.enableVertexAttribArray(a);gl.vertexAttribPointer(a,2,gl.FLOAT,false,0,0);
const uT=gl.getUniformLocation(p,'u_t'), uLv=gl.getUniformLocation(p,'u_lv');
window.draw=(t,lv)=>{
  gl.viewport(0,0,${size},${size});
  gl.clearColor(0.039,0.031,0.063,1.0); // #0A0810 opaque so the PNG has the void bg
  gl.clear(gl.COLOR_BUFFER_BIT);
  gl.enable(gl.BLEND);gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
  gl.uniform1f(uT,t);gl.uniform1f(uLv,lv);
  gl.drawArrays(gl.TRIANGLES,0,6);
  gl.finish();
};
document.title='READY';
</script></body></html>`;

async function main() {
  await mkdir(OUT, { recursive: true });
  const browser = await chromium.launch({
    executablePath: process.env.CHROME_BIN || undefined,
    args: [
      "--use-gl=angle",
      "--use-angle=swiftshader",
      "--enable-unsafe-swiftshader",
      "--ignore-gpu-blocklist",
      "--no-sandbox",
    ],
  });
  const page = await browser.newPage({ viewport: { width: SIZE, height: SIZE }, deviceScaleFactor: 2 });
  page.on("console", (m) => { if (m.type() === "error") console.log("  [page error]", m.text()); });

  const index = [];
  for (const key of pickKeys) {
    const fs = ALL[key];
    if (!fs) { console.log(`! unknown key ${key}`); continue; }
    await page.setContent(HARNESS(S.VS, fs, SIZE), { waitUntil: "load" });
    const title = await page.title();
    if (title.startsWith("ERR") || title.startsWith("LINKERR")) {
      console.log(`✗ ${key} shader error: ${title}`);
      continue;
    }
    const canvas = page.locator("#c");
    for (const lv of lvs) {
      const strip = [];
      for (const t of ts) {
        await page.evaluate(([t, lv]) => window.draw(t, lv), [t, lv]);
        await page.waitForTimeout(30);
        const file = `${key}_lv${lv}_t${t}.png`;
        await canvas.screenshot({ path: join(OUT, file) });
        strip.push(file);
      }
      index.push({ key, lv, strip });
      console.log(`✓ ${key} lv=${lv} → ${strip.length} frames`);
    }
  }
  await browser.close();

  // A simple HTML contact sheet to eyeball everything at once.
  const html = `<!doctype html><meta charset=utf-8><body style="background:#0A0810;color:#e7cd84;font-family:sans-serif;padding:16px">
  <h1>Bindu shots</h1>` +
    index.map(({ key, lv, strip }) =>
      `<div style="margin:8px 0"><div>${key} — lv ${lv}</div>` +
      strip.map((f) => `<img src="${f}" width="200" style="background:#0A0810;margin:2px">`).join("") +
      `</div>`).join("") + `</body>`;
  await writeFile(join(OUT, "index.html"), html);
  console.log(`\nWrote ${index.length} strips → ${OUT}/index.html`);
}

main().catch((e) => { console.error(e); process.exit(1); });
