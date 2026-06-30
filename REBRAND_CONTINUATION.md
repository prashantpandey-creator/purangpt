# PuranGPT Rebrand — Continuation / Handoff

> A self-contained brief to resume the visual rebrand work in a **fresh session**.
> The canonical living state is still `PROJECT_LEDGER.md` in the **purangpt** (backend) repo —
> read its top entries first. This file is the focused handoff for the rebrand thread.

**Branch (both repos):** `claude/chat-tier-modes-naming-48z104`
**Deploy:** pushing this branch auto-merges → `main` → deploys to **purangpt.com** (~3–4 min). No PR needed.
**Verify before every push:** `npx tsc --noEmit` clean — *ignore* the pre-existing `sql.js` / `onnxruntime-web` errors (filter them: `| grep -v "sql.js\|onnxruntime-web"`). Builds ignore TS/ESLint, so tsc is your only gate.

---

## How to resume in one minute

The big enabler this thread is a **visual feedback loop** — render real pages/shaders headless and look at the pixels. A fresh container has neither the dev server nor a browser. Re-establish both:

### 1. Dev server (Next on :3000)
```bash
cd /home/user/purangpt-next
# .env.local is gitignored — recreate it so the app boots (placeholders are fine):
cat > .env.local <<'EOF'
NEXT_PUBLIC_API_URL=http://localhost:9999
NEXT_PUBLIC_BASE_URL=http://localhost:3000
NEXT_PUBLIC_CORPUS_URL=http://localhost:9999/corpus
NEXT_PUBLIC_MODEL_URL=http://localhost:9999/model
NEXT_PUBLIC_GUEST_SOFT_LIMIT=5
NEXT_PUBLIC_LOGTO_APP_ID=dev-placeholder
NEXT_PUBLIC_LOGTO_ENDPOINT=http://localhost:9999
NEXT_PUBLIC_RAZORPAY_KEY_ID=rzp_test_placeholder
EOF
nohup env PORT=3000 npx next dev > /tmp/nd.log 2>&1 &
disown || true
# wait for it (do NOT use `sleep` — it's blocked; curl-retry instead):
curl -s -o /dev/null -w "%{http_code}\n" --retry 30 --retry-delay 2 --retry-connrefused --max-time 120 http://localhost:3000/chat
```
**GOTCHA:** never `pkill -f "next dev"` — your own shell command line contains "next dev" so pkill kills itself (and `set -e` aborts the script). If the port is free just relaunch; otherwise kill by a tighter pattern / by PID.

### 2. Headless Chromium (for screenshots)
Not in a fresh container. Playwright's own installer **dies on the egress proxy** mid-download — fetch with resumable curl instead:
```bash
cd /home/user/purangpt-next
npm i -D playwright   # the scripts do `import { chromium } from "playwright"`
cd "$SCRATCH"         # your session scratchpad dir
URL="https://cdn.playwright.dev/builds/cft/149.0.7827.55/linux64/chrome-headless-shell-linux64.zip"
for i in $(seq 1 50); do curl -fsSL -C - --cacert /root/.ccr/ca-bundle.crt --max-time 90 -o chs.zip "$URL" && break; done
mkdir -p chs && (unzip -oq chs.zip -d chs || python3 -c "import zipfile;zipfile.ZipFile('chs.zip').extractall('chs')")
export CHROME_BIN="$PWD/chs/chrome-headless-shell-linux64/chrome-headless-shell"
"$CHROME_BIN" --version   # sanity
```
(The Playwright **chromium** version may differ; if `npx playwright install` half-runs it prints the needed CfT version + URL — use that URL with the curl loop.)

### 3. Take screenshots (output → `scratch/...`, gitignored)
```bash
export CHROME_BIN=...   # from step 2
# Any Bindu Lab shader (key = A..E, E1..E5, 4D). Heavy shaders (E4, 4D) MUST be small —
# SwiftShader aborts a full-size render (watchdog) and yields a blank/identical frame:
node scripts/shotBindu.mjs 4D --t=0,4,8 --lv=0,1 --size=200
# Real chat (seeds a conversation via localStorage, no backend needed):
node scripts/shotChat.mjs
# Arbitrary routes:
node scripts/shotPage.mjs /pricing /about /features
# The WebGL logo at large size: there's no big logo on a normal page, so render a
# THROWAWAY route and delete it after (never commit it):
#   write src/app/logotest/page.tsx rendering <Logo size={240|120|64|32}/>, then
#   node scripts/shotPage.mjs /logotest ; rm -rf src/app/logotest
```
Then **Read** the PNGs to actually look at them.

---

## What's DONE (shipped to the branch / live)

- **Chat answer streaming** — *not a bug.* The answer already floats card-less on the void with a smooth proportional reveal (`ChatInterface.tsx` `.answer-manifest` + `revealedLenRef`); verified in prod (computed style: transparent, no border). Any "card" the user still sees is a **stale client cache** (hard-refresh / incognito; the Capacitor WebView is the prime suspect on mobile).
- **Pricing page** (`src/components/landing/Pricing.tsx`) — premium Twilight-Sanctum restyle: indigo-aubergine card gradients, gold-glow Pro card, "PLANS" eyebrow, Marcellus gold prices, denser gold-disc feature rows, conversion trust strip. **No billing logic touched.** (Hero *copy* still the generic i18n "Simple, Transparent Pricing" — a future i18n pass: en/hi/ru.)
- **Brand logo** (`src/components/ui/ConcentricBindu.tsx`, used by `Logo.tsx`) — the static amoeba centre was replaced by the **Guruji WebGL flame heart wrapped in the approved Prāṇa Shakti aura** (orbiting blue→pink→gold wisps), inside the concentric SVG rings. WebGL2 per instance + graceful static-SVG fallback + reduced-motion freeze. (History: a flat SVG teardrop was tried first and **rejected** — the user wants the rich complex flame, not a simple teardrop.)
- **Main chat emblem** is `ShaktiBindu.tsx` = **Prāṇa Breath** Shakti void (Bindu Lab E2), driven by `state` prop; the void/`CosmicHum`/emblem share one `binduPulse` signal.
- **Nāda (`CosmicHum.tsx`)** — state-aware: dark/veiled near-subliminal at rest, blooms (filter opens, harmonics + Aum formants, deeper breath) when thinking. Topbar mute toggle persists (`humControl.ts`).

## What's PENDING / open decisions

1. **4D Bindu — promotion decision (live now in the Lab only).** A raymarched 3D void-orb in `binduShaders.mjs` (`ITER_4D`), shown at `/bindu-lab` → **Dimensional** section. It's a **3D realization of the flat Bindu**: deep dark **void** centre (+ tiny Bindu seed), **gravity-wave** ripple disturbances + slow gravity **pulse**, **7 orbiting aura particles** (tilted 3D rings, blue→pink→gold), gold **Fresnel rim** + specular, `fwidth` antialiased edge, interior fire rotating through the **4th dimension** (xw/yw/zw plane rotations). **User likes the direction.** Awaiting: promote to the main emblem and/or the logo centre, or keep tuning. Tuning levers (all in `ITER_4D`): void size = `voidShadow` smoothstep range; particle count/size/speed = the `particles()` loop (`k<7`, `exp(-dd*dd*150.0)`, `ang` speed); gravity ripple = `grav` term; rotation speed = the `rot*W` angle coefficients in `dens4`; rim = the `fres` term.
   - To **promote**: make a `Bindu4D.tsx` component (mirror `ShaktiBindu.tsx`'s WebGL boilerplate — `state`→`lv` easing, reduced-motion freeze, fallback) using `VS` + `ITER_4D`, then swap the import in `ChatInterface.tsx` (currently `ShaktiBindu`) and/or fold the shader into `ConcentricBindu.tsx` for the logo. **Watch the WebGL context budget** (chat page already runs VoidField + emblem + 1–2 logos + MorphicField).
2. **Favicon / app icons** (`public/icon-192.png`, `icon-512.png`, `apple-touch-icon.png`) still show the OLD mark — regenerate from the new flame+aura (or 4D) mark (render to PNG headless).
3. **Continue the premium page refinement loop** — next candidates: `/about` hero, `/features`, `/capabilities`, sidebar, modals. Pricing hero copy (i18n).

## The running `/loop`

A self-paced **premium refinement `/loop`** is active (the user opted in). Each tick: pick the highest-impact element → redesign for **information density + conversion + premium aesthetics**, **avoid** Bootstrap look / generic-SaaS templates / large purposeless heroes → keep the theme → verify before/after screenshots → tsc → push → update ledger → show before/after. User **vetoes** anything; keep steps small + revertible. If a fresh session inherits a `ScheduleWakeup`, it will re-enter this loop; to stop, just don't reschedule.

---

## Theme / design system (Twilight Sanctum) — must obey

- Palette tokens (single source: `src/app/globals.css :root` + `tailwind.config.ts`): base indigo-aubergine `#0A0810`; surfaces `#141121`/`#16131F`; gold `#cba455` (Tailwind `saffron`, var `--gold`); highlight `#e7cd84`; aged-brass `#b8893b`; slate `#7e92b8` (only cool accent); ivory text `#e2d4b2`. Use tokens, not raw hex, where possible.
- Type: **Marcellus** for wordmarks/headers/titles; Inter/Geist for body. NOTE: `font-cinzel` is **aliased to Marcellus** in tailwind.config — it is NOT a violation. No real Cinzel/Yatra One.
- Glow is restrained, focal-only (≤0.30 alpha tokens / `drop-shadow-[0_0_Npx_rgba(203,164,85,≤0.45)]`). No neon `#ff9933`. Tailwind arbitrary values can't contain spaces: `rgba(203,164,85,0.3)`.

## Key files

```
purangpt-next/
  src/lib/binduShaders.mjs (+ .d.ts)   # SINGLE SOURCE for all Bindu Lab shaders
                                         # (VS, NOISE, ITER_A..E, ITER_E1..E5, ITER_4D).
                                         # Imported by the lab page AND the screenshot harness.
  src/app/bindu-lab/page.tsx           # /bindu-lab gallery (Core / Shakti / Dimensional)
  src/components/guruji/ShaktiBindu.tsx# LIVE chat emblem (Prāṇa void). state/size props.
  src/components/guruji/GurujiBindu.tsx# the flame shader source (orphaned but kept)
  src/components/ui/ConcentricBindu.tsx# brand logo mark (WebGL flame + Shakti aura + rings)
  src/components/ui/Logo.tsx           # wraps ConcentricBindu (topbar/sidebar/navbar)
  src/components/chat/ChatInterface.tsx# chat; .answer-manifest float, revealedLenRef reveal
  src/components/chat/VoidField.tsx    # full-viewport gravitational-wave void behind chat
  src/components/chat/CosmicHum.tsx    # the Nāda (state-aware Om drone)
  src/lib/binduPulse.ts                # shared intelligence signal (void + emblem + hum)
  src/lib/humControl.ts                # Nāda mute toggle (persisted)
  src/components/landing/Pricing.tsx   # refined pricing
  scripts/shotBindu.mjs  shotChat.mjs  shotPage.mjs   # screenshot harnesses (dev-only)
  scratch/                             # gitignored screenshot output
```

## Gotchas (learned the hard way)

- `pkill -f "next dev"` kills its own shell (command line contains the pattern) → no server. Don't.
- The bash snapshot runs `set -e` → guard non-zero commands (`pkill … || true`); launch the server with `nohup … &` (orphan), not as a tracked background task.
- Foreground `sleep` is blocked — wait via `curl --retry … --retry-connrefused` or a `timeout`'d run.
- SwiftShader (headless) **aborts heavy shaders at full size** (E4, 4D) → blank/identical frames. Render `--size=128..220`. They're fine on a real GPU.
- Playwright browser CDN downloads die on the proxy → fetch the zip with `curl -C -` (resumable) + `--cacert /root/.ccr/ca-bundle.crt`, point Playwright at it via `executablePath` / `CHROME_BIN`.
- Volumetric/emissive shaders output **premultiplied** alpha (canvas `premultipliedAlpha:true`, `blendFunc(ONE, ONE_MINUS_SRC_ALPHA)`): accumulate `col` as emission×coverage and output `o = vec4(col, alpha)` (don't re-multiply).
- `.mjs` shader module + sibling `.d.ts` keeps both Next (runtime) and `tsc` (types) happy.
