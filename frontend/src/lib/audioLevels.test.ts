/**
 * Tests for computeBarLevels — the pure spectrum→bar math behind MicWaveform.
 * Run with Node's native TypeScript stripping (Node ≥ 23.6):
 *   node src/lib/audioLevels.test.ts
 * Exits 0 on success; throws (non-zero) on the first failed assertion.
 */
import assert from "node:assert/strict";
import { computeBarLevels } from "./audioLevels.ts";

let passed = 0;
function check(name: string, fn: () => void) {
  fn();
  passed++;
  console.log(`  ok  ${name}`);
}

// ── shape & guards ─────────────────────────────────────────────────────────
check("barCount<=0 returns empty array", () => {
  assert.deepEqual(computeBarLevels(new Uint8Array(128), 0), []);
  assert.deepEqual(computeBarLevels(new Uint8Array(128), -3), []);
});

check("returns exactly barCount entries", () => {
  for (const c of [1, 3, 5, 12]) {
    assert.equal(computeBarLevels(new Uint8Array(128), c).length, c);
  }
});

check("empty spectrum → every bar at floor", () => {
  const out = computeBarLevels(new Uint8Array(0), 5, { floor: 0.2 });
  assert.deepEqual(out, [0.2, 0.2, 0.2, 0.2, 0.2]);
});

// ── range invariants ───────────────────────────────────────────────────────
check("silence (all zero) → every bar exactly at floor", () => {
  const out = computeBarLevels(new Uint8Array(128), 5, { floor: 0.1 });
  for (const v of out) assert.equal(v, 0.1);
});

check("full blast (all 255) → every bar clamps to 1", () => {
  const freq = new Uint8Array(128).fill(255);
  const out = computeBarLevels(freq, 5, { gain: 1.4 });
  for (const v of out) assert.equal(v, 1);
});

check("all outputs stay within [floor, 1] for arbitrary data", () => {
  const freq = new Uint8Array(128);
  for (let i = 0; i < freq.length; i++) freq[i] = (i * 37) % 256;
  const floor = 0.1;
  const out = computeBarLevels(freq, 7, { floor, gain: 2.5 });
  for (const v of out) {
    assert.ok(v >= floor - 1e-9, `under floor: ${v}`);
    assert.ok(v <= 1 + 1e-9, `over 1: ${v}`);
  }
});

// ── the spectrum actually drives the right bars ────────────────────────────
check("energy in a band lifts only that bar above floor", () => {
  // Put energy ONLY in bins ~26-29. With minBin=2,maxBin=64,barCount=5 the
  // span is 62 → ~12.4 bins/bar; bin 26-29 lands in bar index 1 (bins 14..26)
  // and bar 2 (bins 26..38). Bars 0 and 4 must remain at floor.
  const freq = new Uint8Array(128);
  for (let i = 26; i < 30; i++) freq[i] = 220;
  const out = computeBarLevels(freq, 5, { floor: 0.1 });
  assert.equal(out[0], 0.1, "lowest band should be silent");
  assert.equal(out[4], 0.1, "highest band should be silent");
  assert.ok(out[1] > 0.1 || out[2] > 0.1, "a mid band should be lifted");
});

check("louder input → taller bar (monotonic in amplitude)", () => {
  const mk = (amp: number) => {
    const f = new Uint8Array(128);
    for (let i = 2; i < 64; i++) f[i] = amp;
    return computeBarLevels(f, 5, { floor: 0.05, gain: 1.0 })[2];
  };
  const quiet = mk(40);
  const mid = mk(120);
  const loud = mk(200);
  assert.ok(quiet < mid, `quiet ${quiet} !< mid ${mid}`);
  assert.ok(mid < loud, `mid ${mid} !< loud ${loud}`);
});

check("narrow window (maxBin-minBin < barCount) still yields barCount bars", () => {
  // 3-bin window, 5 bars → bands overlap but none vanish.
  const freq = new Uint8Array(128).fill(255);
  const out = computeBarLevels(freq, 5, { minBin: 10, maxBin: 13 });
  assert.equal(out.length, 5);
  for (const v of out) assert.equal(v, 1);
});

check("accepts plain number[] as well as Uint8Array", () => {
  const out = computeBarLevels([0, 0, 255, 255, 255, 255], 2, { minBin: 0, maxBin: 6, floor: 0 });
  assert.equal(out.length, 2);
  assert.ok(out[1] > out[0], "second half is louder");
});

console.log(`\n${passed} checks passed.`);
