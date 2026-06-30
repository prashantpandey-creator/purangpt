// ─────────────────────────────────────────────────────────────────────────
//  binduPulse — the single "intelligence" signal that drives BOTH the visual
//  field (VoidField) and the audio (CosmicHum) from one clock.
//
//  Asymmetric envelope: fast attack (~0.4s) so the field brightens the instant
//  a query fires; slow release (~2.5s) so it lingers after the answer settles.
//  Everything reads getPulse() — no per-component timers, no drift.
// ─────────────────────────────────────────────────────────────────────────

export interface Pulse {
  /** 0 = resting, 1 = thinking. Asymmetric envelope (fast attack, slow release). */
  intensity: number;
  /** Shared slow breathing, 0..1. */
  breath: number;
  /** Raw breath phase in radians. */
  phase: number;
  /** Consume-flight progress 0→1 during a query dissolve. Zero at rest. */
  flight: number;
}

const BREATH_HZ = 0.052; // ~19s inhale→exhale — meditative, soothing
const ATTACK  = 0.4;    // seconds — instant feel when thought fires
const RELEASE = 2.5;    // seconds — field lingers after answer settles

const state = {
  target: 0,
  intensity: 0,
  phase: 0,
  flight: 0,
};

let running = false;
let last = 0;

function tick(now: number) {
  if (!running) return;
  const dt = last ? Math.min(0.1, (now - last) * 0.001) : 0;
  last = now;

  // Asymmetric envelope: different time-constant for rising vs falling.
  const tc = state.intensity < state.target ? ATTACK : RELEASE;
  const k = 1 - Math.exp(-dt / tc);
  state.intensity += (state.target - state.intensity) * k;

  // Breathing speeds up a touch when the mind is active.
  const hz = BREATH_HZ * (1 + state.intensity * 0.6);
  state.phase = (state.phase + dt * hz * Math.PI * 2) % (Math.PI * 2);

  requestAnimationFrame(tick);
}

function ensureRunning() {
  if (running || typeof window === "undefined") return;
  running = true;
  last = 0;
  requestAnimationFrame(tick);
}

/** Set how awake the mind is (0 resting → 1 thinking). Drives light + sound together. */
export function setIntelligence(level: number) {
  state.target = Math.max(0, Math.min(1, level));
  ensureRunning();
}

/** Drive the consume-flight progress (0→1) from ConsumeFibers. */
export function setFlight(progress: number) {
  state.flight = Math.max(0, Math.min(1, progress));
}

/** Read the current shared pulse. Call inside your own rAF / audio loop. */
export function getPulse(): Pulse {
  ensureRunning();
  return {
    intensity: state.intensity,
    breath: 0.5 + 0.5 * Math.sin(state.phase),
    phase: state.phase,
    flight: state.flight,
  };
}
