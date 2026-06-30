/**
 * audioLevels — pure spectrum→bar math for the mic waveform.
 *
 * The visual job: turn a live FFT magnitude spectrum (from a Web Audio
 * AnalyserNode) into a handful of bar heights that actually breathe with the
 * seeker's voice — tall on a vowel, flat on a pause — instead of animating on a
 * fixed timer. The Web Audio plumbing (getUserMedia, AudioContext, rAF) lives in
 * MicWaveform.tsx; THIS file is the deterministic core, deliberately free of DOM
 * and Web Audio so the band mapping is unit-testable without a real microphone.
 */

export interface BarLevelOpts {
  /** Lowest FFT bin sampled — skips DC offset and sub-bass room rumble. */
  minBin?: number;
  /** Highest FFT bin sampled — human voice energy dies long before Nyquist. */
  maxBin?: number;
  /** Resting floor in [0,1] so bars shimmer faintly instead of dying flat. */
  floor?: number;
  /** Gain on normalized band energy before clamping — lifts quiet speech. */
  gain?: number;
}

/**
 * Map an FFT magnitude spectrum to `barCount` normalized heights in
 * `[floor, 1]`. Each bar averages a contiguous band of bins across the
 * voice-relevant range `[minBin, maxBin]`, so mid-frequency formants (the body
 * of speech) naturally drive the centre bars hardest.
 *
 * @param freq    AnalyserNode.getByteFrequencyData output (0..255 per bin), or
 *                any array-like of bin magnitudes.
 * @param barCount how many bars to produce.
 * @returns       one normalized height per bar, each clamped to `[floor, 1]`.
 */
export function computeBarLevels(
  freq: Uint8Array | number[],
  barCount: number,
  opts: BarLevelOpts = {},
): number[] {
  if (barCount <= 0) return [];

  const floor = clamp01(opts.floor ?? 0.1);
  const gain = opts.gain ?? 1.4;
  const n = freq.length;

  // No spectrum (e.g. analyser not ready) → resting shimmer, never a dead bar.
  if (n === 0) return new Array(barCount).fill(floor);

  // Clamp the sampling window into the actual spectrum. Default top bin caps at
  // 64 (≈ voice band on a 256-point FFT) but never exceeds what we were given.
  const lo = Math.max(0, Math.min(opts.minBin ?? 2, n - 1));
  const hi = Math.max(lo + 1, Math.min(opts.maxBin ?? 64, n));
  const span = hi - lo;

  const out = new Array<number>(barCount);
  for (let b = 0; b < barCount; b++) {
    // Contiguous, gap-free band for this bar. Guarantee ≥1 bin even when the
    // window is narrower than barCount (bands then overlap rather than vanish).
    const start = lo + Math.floor((b * span) / barCount);
    const end = Math.max(start + 1, lo + Math.floor(((b + 1) * span) / barCount));

    let sum = 0;
    let count = 0;
    for (let i = start; i < end && i < n; i++) {
      sum += freq[i];
      count++;
    }
    const avg = count > 0 ? sum / count : 0;
    // 0..255 → 0..1, lift with gain, then clamp into [floor, 1].
    const level = (avg / 255) * gain;
    out[b] = Math.max(floor, Math.min(1, level));
  }
  return out;
}

function clamp01(v: number): number {
  return v < 0 ? 0 : v > 1 ? 1 : v;
}
