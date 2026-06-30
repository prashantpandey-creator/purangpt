// Generates the Capacitor `webDir` (out/) used by `npx cap sync`.
//
// PuranGPT's mobile app runs in *remote-URL mode* — the native WebView loads
// https://purangpt.com (or http://localhost:3000 when CAP_ENV=local) directly,
// so the bundled web assets are never actually served at runtime. Capacitor
// still requires `webDir` to exist and contain an index.html in order to sync,
// and Next.js (output: "standalone") can't `next export` because of API routes.
//
// This script produces a tiny self-contained placeholder so `cap sync` succeeds
// in CI without a full static export. It shows the brand splash colour and a
// loading hint in the rare event the WebView falls back to local assets.

import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const outDir = resolve(process.cwd(), "out");
mkdirSync(outDir, { recursive: true });

const html = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
    <title>PuranGPT</title>
    <style>
      html, body {
        margin: 0;
        height: 100%;
        background: #131313;
        color: #ffda75;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      }
      .wrap {
        height: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        text-align: center;
      }
      .glow {
        font-size: 1.1rem;
        letter-spacing: 0.04em;
        opacity: 0.85;
        text-shadow: 0 0 14px rgba(255, 153, 51, 0.65);
      }
    </style>
  </head>
  <body>
    <div class="wrap"><div class="glow">Loading PuranGPT…</div></div>
  </body>
</html>
`;

writeFileSync(resolve(outDir, "index.html"), html, "utf8");
console.log("[cap-webdir] wrote placeholder out/index.html");
