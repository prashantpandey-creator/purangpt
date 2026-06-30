// ─────────────────────────────────────────────────────────────────────────
//  humControl — a tiny persisted store for the Nāda (cosmic hum) on/off state.
//  The Nāda is OFF by default — the seeker must explicitly click to sound it.
//  Once booted, the toggle flips on/off; the choice persists to localStorage.
//  Plain module state + subscribers — no React context overhead.
// ─────────────────────────────────────────────────────────────────────────

const KEY = "purangpt-naad";

let enabled = false; // OFF by default — seeker explicitly clicks to activate
let booted = false;
const listeners = new Set<(v: boolean) => void>();
const bootCallbacks: Array<() => void> = [];

if (typeof window !== "undefined") {
  try {
    const saved = window.localStorage.getItem(KEY);
    // Only restore "on" — if they chose it before, respect it. Still requires
    // a fresh boot gesture (browser AudioContext policy).
    if (saved === "on") enabled = true;
  } catch {
    /* localStorage may be blocked — default to off */
  }
}

export function getHumEnabled() {
  return enabled;
}

export function setHumEnabled(v: boolean) {
  enabled = v;
  try {
    window.localStorage.setItem(KEY, v ? "on" : "off");
  } catch { /* ignore */ }
  listeners.forEach((cb) => cb(v));
}

export function toggleHum() {
  setHumEnabled(!enabled);
  return enabled;
}

export function subscribeHum(cb: (v: boolean) => void) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

/** Register a one-shot boot callback — fired on the next requestHumBoot()
 *  (which the UI must call inside a user gesture so the AudioContext is
 *  allowed). Safe to call after boot via a no-op guard. */
export function onHumBoot(cb: () => void) {
  if (booted) return; // already running — don't accumulate callbacks
  bootCallbacks.push(cb);
}

/** One-shot completion warp trigger. Fires when the answer arrives —
 *  the hum should end meaningfully (pitch sweep up + dissolve) instead
 *  of cutting abruptly. */
let completionCallbacks: Array<() => void> = [];

export function onHumComplete(cb: () => void) {
  completionCallbacks.push(cb);
}

export function triggerHumCompletion() {
  const cbs = completionCallbacks.splice(0);
  cbs.forEach((cb) => cb());
}

/** Call from a click handler to boot the Nāda audio engine. Sets enabled=true,
 *  fires all registered boot callbacks (within the user-gesture window), then
 *  clears them. Subsequent calls are no-ops — audio is already alive. */
export function requestHumBoot() {
  if (booted) return;
  booted = true;
  setHumEnabled(true);
  const cbs = bootCallbacks.splice(0);
  cbs.forEach((cb) => cb());
}
