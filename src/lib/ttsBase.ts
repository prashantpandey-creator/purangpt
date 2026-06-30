/**
 * TTS_BASE — where the cloned-voice server lives, resolved per environment.
 *
 *  - dev (localhost): the local XTTS server (serve.py on :8123)
 *  - prod: the Modal serverless CUDA endpoint — Guruji's denoised, per-sentence
 *    stitched voice (voice_clone/voice_modal.py)
 *
 * MODAL_TTS_URL is a PUBLIC endpoint, not a secret, so it lives safely in the
 * client bundle. Until it's filled, prod falls back to localhost (→ browser
 * SpeechSynthesis), i.e. a no-op — so this file is safe to ship before the URL
 * exists. Both voiceEngine.ts (chat) and darshan/page.tsx (voice) import it, so
 * there is one source of truth.
 */
const MODAL_TTS_URL = "https://fcpuru95--guruji-voice-voice-web.modal.run";

const isLocalHost =
  typeof window !== "undefined" &&
  ["localhost", "127.0.0.1"].includes(window.location.hostname);

export const TTS_BASE =
  !isLocalHost && MODAL_TTS_URL && !MODAL_TTS_URL.startsWith("__")
    ? MODAL_TTS_URL
    : "http://localhost:8123";

/**
 * prewarmVoice — wake the (scale-to-zero) Modal GPU EARLY, on voice intent, so
 * its ~30s cold start overlaps with latency the seeker is already spending.
 *
 * The clone voice never speaks first: it only synthesises AFTER the LLM has
 * thought + streamed a reply (seconds later), so firing this the moment voice
 * is enabled / darshan opens hides the spin-up entirely — no always-on GPU bill.
 *
 * Fire-and-forget: a GET /health, result ignored, errors swallowed. Throttled
 * to once per 4 min per page so re-toggling doesn't spam the endpoint (and
 * scaledown_window keeps it warm ~10 min after, covering the gap).
 */
let _lastPrewarm = 0;
export function prewarmVoice(): void {
  if (typeof window === "undefined") return;
  const now = Date.now();
  if (now - _lastPrewarm < 10 * 60 * 1000) return; // warm for 10 min (was 4)
  _lastPrewarm = now;
  try {
    void fetch(`${TTS_BASE}/health`, {
      method: "GET",
      // Long enough to actually trigger the cold boot; we don't await it.
      signal: AbortSignal.timeout(35_000),
    }).catch(() => {});
  } catch {
    /* AbortSignal.timeout unsupported — ignore; the real call will still work */
  }
}

/**
 * prewarmVoiceSynth — the deeper warm, for STRONG voice intent (toggle-on,
 * darshan open). A throwaway one-word `/tts` so the GPU not only wakes but also
 * runs RVC's lazy first-load (hubert + net_g + the rmvpe pipeline) NOW, in the
 * background, instead of on the seeker's first real reply.
 *
 * Why a synth and not the snapshot: RVC's Pipeline bakes the device into its F0
 * sub-models at construction, so it can't be pre-loaded into the CPU snapshot
 * and moved to GPU — warming it with a real (tiny) call is the robust path.
 * voice:"guruji" warms the full XTTS→RVC chain, which also covers chat's
 * (XTTS-only) funguru. Fire-and-forget; the audio is discarded.
 */
let _lastSynthWarm = 0;
export function prewarmVoiceSynth(): void {
  if (typeof window === "undefined") return;
  const now = Date.now();
  if (now - _lastSynthWarm < 10 * 60 * 1000) return; // warm for 10 min (was 4)
  _lastSynthWarm = now;
  _lastPrewarm = now; // a synth-warm is a superset of the /health wake
  try {
    void fetch(`${TTS_BASE}/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: "Om", lang: "en", voice: "guruji" }),
      // Generous: first synth pays the cold wake + RVC load. Don't abort early.
      signal: AbortSignal.timeout(60_000),
    }).catch(() => {});
  } catch {
    /* AbortSignal.timeout unsupported — ignore */
  }
}
