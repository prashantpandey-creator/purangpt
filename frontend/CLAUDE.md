@AGENTS.md

# PuranGPT Next.js - Project Context & Onboarding

## 📒 Project Ledger — READ FIRST, UPDATE LAST (mandatory)

The single source of truth for the live state of the whole app (frontend **and** backend) and key
engineering events is **`PROJECT_LEDGER.md` in the `purangpt` backend repo**. Read its **Current
State** before starting, and prepend a dated entry (+ update Current State) after finishing any unit
of work — including frontend changes. If the backend repo isn't checked out in your session, ask for
it so the ledger stays the sole, shared knowledge base.

## Workflow (Git)
- **Push changes automatically.** After completing a change, commit and push to a branch (and open a PR) without waiting for confirmation. Don't ask permission for the commit/push/PR steps.
- **Still confirm before merging to `main`.** Merging deploys to the live site via the Hetzner Action, so ask before merging to production unless explicitly told to auto-merge.

## Tech Stack
- **Framework:** Next.js 16.2.7 (App Router), React 19
- **Styling:** Tailwind CSS, Custom SVGs, Vanilla CSS
- **Database:** Logto Postgres (shared with backend via `DATABASE_URL`)
- **Vector DB/Search:** `pgvector` in the backend Postgres (`VECTOR_DB_URL`)
- **Authentication:** Direct Google OAuth + API-driven email auth via Logto backend — **no Logto hosted UI anywhere**
- **Billing:** Stripe (US/Canada/International) + Razorpay (India)
- **AI/LLM:** Local execution for Embeddings (`sentence-transformers/all-MiniLM-L6-v2`)

## Auth Architecture (2026-06-30 — post-cleanup)

**Two sign-in paths. Zero Logto hosted UI.**

| Path | Flow | Cookie | Backend verify |
|------|------|--------|---------------|
| **Google** | `SignInModal` → `signIn("google")` → `/api/auth/google` → Google consent → `/api/auth/google/callback` → `purangpt_session` | HMAC-signed, 7d, contains `accessToken` + `refreshToken` | `auth.py` → `_verify_google_token()` via Google tokeninfo |
| **Email** | `SignInModal` → email form → `signInWithEmail()` → POST `/api/auth/email` → Logto API (server-to-server) → `logto_session` | HMAC-signed, 7d, contains `accessToken` + `user` | `auth.py` → Logto JWKS RS256 verify |

**Key files:**
- `src/context/AuthContext.tsx` — Single `AuthProvider` renders one `SignInModal` (dynamic import). `signIn("google")` for Google, `signInWithEmail()` for email, `openSignInModal()` for programmatic triggers. Periodic health check (15min) silently refreshes Google tokens via `/api/auth/refresh`.
- `src/components/auth/SignInModal.tsx` — Custom UI: Google button + email form. Terms checkbox below buttons. No Logto branding.
- `src/app/api/auth/google/route.ts` + `callback/route.ts` — Direct Google OAuth with `offline_access` for refresh tokens.
- `src/app/api/auth/email/route.ts` — Server-to-server Logto API call (extracts auth code, exchanges for tokens, sets cookie). No Logto UI.
- `src/app/api/logto/[action]/route.ts` — `callback` (OIDC for email flow), `sign-out`, `user`. `sign-in`/`sign-up` removed.
- `src/lib/auth/index.ts` — `getAccessToken()`: client fetches from `/api/logto/token` for chat API Bearer header.
- `src/lib/session.ts` — Server-side HMAC verify + parse for both session cookies.

**What was removed:**
- Logto hosted UI redirects (`/api/logto/sign-in`, `/api/logto/sign-up`) — dead endpoints now
- Duplicate `SignInModal` instances in `ChatInterface` and `UsageContext` — single instance in `AuthProvider`
- Old `signIn()` without args that redirected to Logto page — now opens our modal

**Session refresh:**
Google access tokens expire in ~1h. The `purangpt_session` cookie stores a `refreshToken` (obtained via `access_type=offline`). Every 15min, `AuthContext` probes `/api/logto/token`; on 401, it calls `/api/auth/refresh` which uses the Google refresh token to obtain a new access token and updates the cookie. Only if refresh also fails is the session cleared.

## Deployment & Hosting (HETZNER)
- **Cloud Provider:** Hetzner VPS (CX33 or CCX33). IP: `204.168.176.229`.
- **SSH Key:** Located at `~/.ssh/purangpt_hetzner`.
- **Hands-off pipeline — nobody manages the repo manually.** The GitHub Action
  (`.github/workflows/deploy.yml`) is the single source of deploys and runs on
  **every push to `main` *and* every push to any `claude/**` branch**:
  - Push to `main` → deploy immediately (SSH, hard-reset box to `origin/main`,
    render secrets, `docker compose build --no-cache frontend && up -d`, ~3-4 min).
  - Push to `claude/**` → the Action first **auto-merges that branch into `main`**
    (fast-forward when possible, else a merge commit) and then deploys. So work
    pushed to a `claude/**` branch reaches production on its own — no PR, no
    manual merge. A real merge conflict **fails the run visibly** in Actions
    instead of silently shipping stale code; resolve it (merge `main` into the
    branch locally) and re-push.
  - **Keep `claude/**` branches fresh.** Because the auto-merge is a plain
    `git merge`, a branch that has drifted far behind `main` will conflict and
    block its own deploy. Rebase/merge `main` in early and often.
  - The merge is pushed with `GITHUB_TOKEN`, which (by GitHub design) does **not**
    re-trigger the workflow, so there is no deploy loop. **No extra secrets**
    beyond those already listed in `deploy.yml`.
- **Instant Hot Reload (PM2)** *(optional manual bypass)*: The server has `pm2` running `next dev --port 3000` (see `ecosystem.config.js`). To push instantaneous changes bypassing Docker, `rsync` your files directly to `/root/purangpt-next` using the local SSH key.
  ```bash
  rsync -avz -e "ssh -i ~/.ssh/purangpt_hetzner -o StrictHostKeyChecking=no" --exclude node_modules --exclude .git --exclude .next . root@204.168.176.229:/root/purangpt-next
  ```

### CI / PR Autofix & Autodeploy Workflow
- **Deploy trigger:** The Hetzner deploy Action fires **only on push to `main`**. Work happens on feature branches (e.g. `claude/...`) and reaches production by merging the PR into `main` — branches are never deployed directly.
- **Watch every PR:** After opening a PR, subscribe to its activity (`subscribe_pr_activity`) and keep it watched until the PR is **merged or closed**.
- **Autofix all fixable failures:** When CI fails or a review comment lands, investigate and push a fix automatically when the fix is small and unambiguous. Re-kick CI until green (rebase / re-run / push). Only stop to ask when a fix is ambiguous or architecturally significant; skip events that need no action.
- **Don't rely on webhooks alone:** CI *success*, new pushes, and merge-conflict transitions are not delivered. Schedule a periodic self check-in to re-verify CI + mergeability, and re-arm it silently if nothing changed.
- **Verify before pushing:** `npx tsc --noEmit` must be clean. Builds ignore ESLint/TS errors (see Gotchas), so type-check locally — CI/runtime won't catch them for you.

## Mobile Build (Capacitor)
- **Apps:** Capacitor 8 wraps the site as native **Android** (`android/`) + **iOS** (`ios/`, SPM-based) apps. App id `com.fcpuru95.purangpt`.
- **Remote-URL mode:** The native WebView loads `https://purangpt.com` directly (`capacitor.config.ts` `server.url`); it does **not** ship a bundled JS bundle. Set `CAP_ENV=local` to point the WebView at `http://localhost:3000`.
- **webDir placeholder:** Because the app is remote-URL and Next.js uses `output: "standalone"` (can't `next export`), `npm run cap:webdir` (`scripts/cap-webdir.mjs`) writes a tiny `out/index.html` so `npx cap sync` succeeds. Don't expect a real export in `out/`.
- **CI pipeline:** `.github/workflows/mobile.yml` builds artifacts on manual dispatch, version tags (`v*`), and pushes that touch mobile files.
  - **Android** (always): debug **APK** (installable) + release **AAB**. Release is signed only when keystore secrets are set, else built unsigned.
  - **iOS** (dispatch/tags only, macOS runner): unsigned compile to validate the project. App Store signing/upload is a manual/Fastlane step (needs Apple certs).
- **Local scripts:** `npm run cap:sync:android` / `cap:sync:ios`, `npm run android:apk` (debug APK), `npm run android:aab` (release AAB).
- **Release signing secrets** (optional, repo Actions secrets): `ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD`. CI decodes them into `android/keystore.properties` + `android/release.keystore` (both gitignored); `android/app/build.gradle` activates the release `signingConfig` only when present.

## UI/UX Guidelines (CRITICAL)
> **DIRECTION SHIFT — 2026-06-28 (owner-approved "richer / living gold + glass").**
> The owner judged the old "Twilight Sanctum" execution *washed-out and lifeless*:
> the gold read as weak pale yellow, the chat background never reached true OLED
> black (the `VoidField` base was indigo `#0A0810` + chat panels were grey
> `#131313`), and the answer floated as bare text on the void. The approved
> direction is **richer**: living amber-gold, true OLED black, and **text housed in
> glass surfaces with real (but tasteful) glow**. The notes below are rewritten to
> match what shipped — do **not** revert to the old restraint clauses or the pale
> `#cba455`/`#0A0810` values. (Neon-saffron `#ff9933` is still banned — richer gold
> is `#e8b63f`, NOT orange glare.)
- **Aesthetic — "Twilight Sanctum, lit":** a diya burning in a dark sanctum, now
  allowed to actually *radiate*. Still mystical and hierarchical — glow earns its
  place, it isn't sprayed on every element — but lifelessness is the failure mode to
  avoid, not exuberance. DO NOT use flat design; DO NOT reintroduce neon-saffron
  (`#ff9933`).
- **Palette (single source of truth: `src/app/globals.css :root` + `tailwind.config.ts`):**
  - Base / page: **true OLED black `#000000`** (body) — the chat `VoidField` shader
    base is near-black `vec3(0.013,0.011,0.022)` and its CSS fallback ends in `#000`,
    so phone OLED pixels stay off. Do not paint chat surfaces grey (`#131313` was
    purged → `#000`).
  - Primary accent: **living amber-gold `#e8b63f`** (var `--gold`, Tailwind `saffron`).
    Highlight `#f6d27a` (`--gold-bright`); aged-brass borders `#c5912f` (`--gold-deep`).
  - Cool secondary: moonlit slate `#7e92b8` (`--slate`) — the ONLY cool accent.
  - Sacred text: sandalwood ivory `#e2d4b2` (`--ivory`).
  - Always use the tokens/`saffron` class, not raw hex, so the theme stays cohesive.
- **Text is housed in glass, not floating.** The chat answer sits in `.answer-glass`
  (blurred, gold-hairline, lit accent bar) and the question in `.question-chip`; each
  has an `--solid` variant (no `backdrop-filter`) for the iOS immersive path, because
  CSS `blur()` over the live WebGL orb is that WebView's worst perf trap. New text
  surfaces should follow this — give content a card/glass home with a soft glow.
- **Glow may radiate (focal points still get the most).** Use the `--glow-gold-*`
  tokens (now up to ~0.50 alpha) or `drop-shadow-[0_0_Npx_rgba(232,182,63,≤0.5)]`.
  Headings, emphasized words, and the bindu carry a soft gold radiance; build depth
  from layered tone AND glow. NOTE: Tailwind arbitrary values cannot
  contain spaces — write `rgba(203,164,85,0.3)` with no spaces inside `[...]`.
- **Typography:** 
  - Wordmarks, Headers, Titles: **Marcellus** (Temple-inscription style).
  - Body Text: **Inter** or **Geist**. No old display fonts like Cinzel, Yatra One.
- **Animations:** Animations should be incredibly smooth. For continuous loops (like the loader), use `requestAnimationFrame` to modify SVG `transform` attributes directly to achieve 60fps independent dual-axis rotation. Avoid React state for fast-looping properties to prevent linting errors and jank. 
  - *Reference:* See `YantraLoader.tsx` for the benchmark implementation.

## Voice & Darshan Architecture (2026-07-01)

### Darshan page (`src/app/darshan/page.tsx`)

The immersive voice-to-voice mode — seeker speaks, Guruji answers aloud. Three
input paths, each falling back to the next:

| Path | Trigger | STT | Failure fallback |
|------|---------|-----|-----------------|
| Hands-free VAD | Tap bindu, speak freely | WhisperSTT (350ms silence endpointing) | Error shown, use PTT or text |
| Push-to-talk | Hold mic button, release | MediaRecorder → /api/transcribe | Error shown, type |
| Text | Type + Enter | None | Always works |

State machine: `resting → listening → thinking → manifesting → listening → …`
Driven by `phaseRef` / `setPhaseSafe`. The bindu orb visual follows the phase.

Key refs: `voiceRef` (VoiceEngine), `speechRef` (useWhisperSTT), `specActiveRef`
/ `specDoneRef` / `specTokensRef` (speculative execution), `abortRef` (LLM abort).

### VoiceEngine (`src/lib/voiceEngine.ts`)

Streaming TTS engine — buffers SSE tokens, flushes at sentence boundaries
(20 chars first, 40 chars steady, 80-char fallback at last word break).
Pre-fetches next chunk while current plays → gapless.

**Provider cascade** (tried in order, falls through on any failure):

1. **ElevenLabs** — `<200ms` cold, `~300ms` warm. Requires `elKey` + `elVoiceId`.
   Uses `eleven_turbo_v2_5` model, mp3 44.1kHz output, decoded via Web Audio API.
2. **XTTS-v2** — local `:8123` or Modal GPU, 5-8s. Probed via `/health` only
   when ElevenLabs is not configured.
3. **Browser SpeechSynthesis** — `<50ms`, OS-dependent voice. English voice
   selected via `getVoices()` filter. 30s safety timer unblocks Chrome's
   dropped-`onend` bug.

Constructor takes an options object:
```ts
new VoiceEngine({
  voice?: string;              // "funguru" | "guruji" (default "funguru")
  lang?: string;               // ISO 639-1 (default "en")
  elevenlabsKey?: string;      // xi-api-key
  elevenlabsVoiceId?: string;  // Professional Voice Clone ID
})
```

Key methods: `enable()`, `pushToken(t)`, `flushFinal()`, `waitForDrain()`, `disable()`.

### Environment variables for voice

```
NEXT_PUBLIC_ELEVENLABS_API_KEY=sk_...     # ElevenLabs API key
NEXT_PUBLIC_ELEVENLABS_VOICE_ID=...        # Professional Voice Clone ID
OPENAI_API_KEY=sk-...                       # Used by /api/transcribe (gpt-4o-transcribe)
```

The ElevenLabs key is client-side (`NEXT_PUBLIC_`) because TTS calls go direct
from the browser. For production, both vars go in GitHub Secrets and are rendered
into the Docker build env.

### ElevenLabs setup

1. Creator plan ($99/month) — unlocks Professional Voice Clone
2. Upload Guruji reference audio from `gurugpt-next/tools/voice_clone/ref/`
   (`guruji_best.wav` + the 8-clip voiceprint)
3. Training takes 1-2 hours → returns a `voice_id`
4. Set `NEXT_PUBLIC_ELEVENLABS_VOICE_ID=<voice_id>` in `.env.local`

Until the voice ID is set, the cascade falls through to XTTS → browser.

### Backend: DARSHAN_DIRECTIVE

In `purangpt/backend/main.py` — injected when `mode == "darshan"`. Locks the
LLM into the heart-speaking register: short sentences, no markdown/headings/
`[N]` citations, scripture recited from memory. The full UNIFIED_SYSTEM prompt
still runs but the directive forces the spoken register exclusively.

### Speculative execution (ChatInterface + Darshan)

Interim STT transcripts ≥30 chars fire an early LLM call (throttled 1/2s).
Tokens are buffered — NOT spoken until the final transcript confirms a match
(prefix match or ≥70% shared words). On match: buffered tokens pushed to
VoiceEngine → instant audio (LLM time hidden). On mismatch: abort + restart.

### Known TTS latencies (measured 2026-07-01)

| Provider | Cold | Warm | Voice quality |
|----------|------|------|--------------|
| ElevenLabs | ~1.8s | **~0.3s** | Guruji clone (once trained) |
| XTTS Modal GPU | ~29s | 5-8s | Guruji clone (funguru/guruji) |
| Browser SpeechSynthesis | <50ms | <50ms | OS-dependent, English selected |

### Chat voice toggle

`ChatInterface.tsx` also creates a VoiceEngine (for the "Listen to response"
feature). It passes the same ElevenLabs config from env vars. Default voice:
"funguru" (XTTS-only), falls through to ElevenLabs if configured.

## Nuances & Gotchas
- **Next.js Config:** ESLint and TypeScript checks have been configured to be ignored during builds (`next.config.ts` and `eslint.config.mjs`) because strict linting previously blocked CI deployments to Hetzner. Keep these disabled for deployment stability.
- **Database Migrations:** If modifying embeddings or vector search, keep in mind all embeddings are 384-dimensional due to the switch from `text-embedding-3-small` to `all-MiniLM-L6-v2`.
- **Voice environment:** `NEXT_PUBLIC_ELEVENLABS_API_KEY` and `NEXT_PUBLIC_ELEVENLABS_VOICE_ID` must be set in GitHub Secrets for production voice to work. Without them, the cascade silently falls back to XTTS/browser.
