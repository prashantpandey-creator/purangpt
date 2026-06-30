/**
 * VoiceEngine — streams TTS in sync with the SSE token flow.
 *
 * Provider cascade (tried in order, falls through on any failure):
 *   1. ElevenLabs Professional Voice Clone — <200ms, Guruji's actual voice
 *   2. XTTS-v2 (local :8123 or Modal GPU) — 5-8s, high quality
 *   3. Browser SpeechSynthesis — <50ms, OS-dependent voice
 *
 * Usage:
 *   const engine = new VoiceEngine({ elevenlabsKey, elevenlabsVoiceId });
 *   engine.enable();
 *   engine.pushToken(token);   // on each SSE token
 *   engine.flushFinal();       // stream done
 *   engine.disable();          // stop / interrupt
 */
import { TTS_BASE } from "@/lib/ttsBase";

type Chunk =
  | { kind: "browser"; text: string }
  | { kind: "xtts"; buffer: AudioBuffer }
  | { kind: "elevenlabs"; buffer: AudioBuffer };

export interface VoiceEngineOpts {
  ttsBase?: string;
  voice?: string;
  lang?: string;
  elevenlabsKey?: string;
  elevenlabsVoiceId?: string;
}

export class VoiceEngine {
  private buf = "";
  private queue: Promise<void> = Promise.resolve();
  private audioCtx: AudioContext | null = null;
  private _enabled = false;
  private localOk: boolean | null = null;
  private readonly ttsBase: string;
  private readonly voice: string;
  private readonly lang: string;
  private readonly elKey?: string;
  private readonly elVoiceId?: string;

  private static readonly MIN_CHARS = 40;
  private static readonly FIRST_MIN_CHARS = 20;
  private firstFlushDone = false;
  private static readonly RE_PARA = /^([\s\S]*?)\n\n+/;
  private static readonly RE_SENTENCE =
    /^([\s\S]*?[.!?…])\s+(?=[A-Z“”‘’"'])/;

  constructor(opts: VoiceEngineOpts = {}) {
    this.ttsBase = opts.ttsBase ?? TTS_BASE;
    this.voice = opts.voice ?? "funguru";
    this.lang = opts.lang ?? "en";
    this.elKey = opts.elevenlabsKey;
    this.elVoiceId = opts.elevenlabsVoiceId;
  }

  get enabled() { return this._enabled; }

  enable() {
    this._enabled = true;
    this.firstFlushDone = false;
    this.localOk = null; // re-probe XTTS health each session
  }

  disable() {
    this._enabled = false;
    this.buf = "";
    this.firstFlushDone = false;
    // Drain queue then close context so no orphaned audio plays.
    this.queue = this.queue.then(() => {
      this.audioCtx?.close();
      this.audioCtx = null;
    });
  }

  /** Resolves when all queued audio has finished playing. */
  async waitForDrain(): Promise<void> {
    await this.queue;
  }

  /** Feed each SSE token here as it arrives. */
  pushToken(token: string) {
    if (!this._enabled) return;
    this.buf += token;
    this._drain();
  }

  /** Call once when the stream is fully done to flush remaining text. */
  flushFinal() {
    if (!this._enabled || !this.buf.trim()) return;
    const text = this.buf.trim();
    this.buf = "";
    this._enqueue(text);
  }

  private _drain() {
    const minChars = this.firstFlushDone ? VoiceEngine.MIN_CHARS : VoiceEngine.FIRST_MIN_CHARS;
    // Prefer whole paragraphs — most natural, prosody spans the sentences.
    let m = this.buf.match(VoiceEngine.RE_PARA);
    if (m) {
      const chunk = m[1].trim();
      this.buf = this.buf.slice(m[0].length);
      if (chunk) { this.firstFlushDone = true; this._enqueue(chunk); }
      this._drain(); // recurse — there may be more paragraphs already buffered
      return;
    }
    // No paragraph break yet, but the run is long enough — flush at a sentence
    // end so audio starts without waiting for the whole paragraph.
    m = this.buf.match(VoiceEngine.RE_SENTENCE);
    if (m && m[1].trim().length >= minChars) {
      const chunk = m[1].trim();
      this.buf = this.buf.slice(m[0].length);
      this.firstFlushDone = true;
      this._enqueue(chunk);
      this._drain();
      return;
    }
    // No punctuation boundary yet but the buffer is long — flush at the last
    // word break so audio starts without waiting for a period that may never
    // arrive (LLM streaming tokens don't always end with . ! ?).
    if (this.buf.length >= 80) {
      const lastSpace = this.buf.lastIndexOf(" ");
      if (lastSpace > minChars) {
        const chunk = this.buf.slice(0, lastSpace).trim();
        this.buf = this.buf.slice(lastSpace + 1);
        if (chunk) { this.firstFlushDone = true; this._enqueue(chunk); }
        this._drain();
      }
    }
  }

  private _enqueue(text: string) {
    if (!text.trim()) return;
    // Pre-fetch: start synthesis NOW so the next chunk is ready before the
    // current one finishes — gapless playback, no dead air between chunks.
    const audioP = this._synth(text);
    this.queue = this.queue.then(() =>
      this._enabled ? this._play(audioP) : Promise.resolve()
    );
  }

  /** Synthesise text → decoded audio buffer, cascading through providers. */
  private async _synth(text: string): Promise<Chunk> {
    // 1. ElevenLabs Professional Voice Clone — <200ms, Guruji's actual voice
    if (this.elKey && this.elVoiceId) {
      try {
        const buf = await this._synthElevenLabs(text);
        if (buf) return { kind: "elevenlabs", buffer: buf };
      } catch { /* fall through to XTTS */ }
    }

    // 2. XTTS-v2 (local or Modal GPU) — 5-8s, high quality
    try {
      const useLocal = await this._checkLocal();
      if (useLocal) {
        let r: Response;
        try {
          r = await fetch(`${this.ttsBase}/tts`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text, lang: this.lang, voice: this.voice }),
            signal: AbortSignal.timeout(15_000),
          });
        } catch (err) {
          if (!(err instanceof DOMException && err.name === "TimeoutError")) {
            this.localOk = false;
          }
          throw err; // fall through to browser
        }
        if (r.ok) {
          const arrayBuf = await r.arrayBuffer();
          if (!this._enabled) return { kind: "browser", text };
          const ctx = this._ctx();
          const buffer = await ctx.decodeAudioData(arrayBuf);
          return { kind: "xtts", buffer };
        }
      }
    } catch { /* fall through to browser */ }

    // 3. Browser SpeechSynthesis — <50ms, OS-dependent voice (last resort)
    return { kind: "browser", text };
  }

  /** Call ElevenLabs streaming TTS. Returns decoded AudioBuffer or null. */
  private async _synthElevenLabs(text: string): Promise<AudioBuffer | null> {
    if (!this.elKey || !this.elVoiceId) return null;
    const r = await fetch(
      `https://api.elevenlabs.io/v1/text-to-speech/${this.elVoiceId}/stream?output_format=mp3_44100_128`,
      {
        method: "POST",
        headers: {
          "xi-api-key": this.elKey,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          text,
          model_id: "eleven_turbo_v2_5",
          voice_settings: { stability: 0.5, similarity_boost: 0.78 },
        }),
        signal: AbortSignal.timeout(15_000),
      },
    );
    if (!r.ok) return null;
    const arrayBuf = await r.arrayBuffer();
    if (!this._enabled) return null;
    const ctx = this._ctx();
    return ctx.decodeAudioData(arrayBuf);
  }

  private async _play(audioP: Promise<Chunk>): Promise<void> {
    let a: Chunk;
    try { a = await audioP; } catch { return; }
    if (!a || !this._enabled) return;
    if (a.kind === "browser") return this._playBrowser(a.text);

    // Gapless XTTS / ElevenLabs playback — Web Audio API BufferSource,
    // no trailing pause; natural breath is baked into the clip.
    const ctx = this._ctx();
    await new Promise<void>((resolve) => {
      const src = ctx.createBufferSource();
      src.buffer = (a as { buffer: AudioBuffer }).buffer;
      src.connect(ctx.destination);
      src.onended = () => resolve();
      src.start();
    });
  }

  private async _checkLocal(): Promise<boolean> {
    // ElevenLabs is primary — skip the XTTS health probe entirely
    if (this.elKey && this.elVoiceId) return false;
    if (this.localOk !== null) return this.localOk;
    try {
      const r = await fetch(`${this.ttsBase}/health`, {
        // The Modal CUDA endpoint can COLD-START for ~30s; a short timeout
        // mislabels a warming clone as "down" → robot for the whole answer.
        // 12s catches a warm or warming container.
        signal: AbortSignal.timeout(12000),
      });
      // Only a definitive non-ok response latches us off the clone. A timeout
      // (cold start / slow) is NOT cached as false — the next chunk re-probes,
      // so once the container warms the real voice takes over.
      this.localOk = r.ok ? true : false;
    } catch {
      return false;
    }
    return this.localOk;
  }

  private _playBrowser(text: string): Promise<void> {
    return new Promise<void>((resolve) => {
      if (typeof window === "undefined" || !window.speechSynthesis) {
        resolve();
        return;
      }
      const utt = new SpeechSynthesisUtterance(text);
      utt.rate = 0.86;
      utt.pitch = 0.88;

      // Pick an English voice explicitly — on systems where the primary language
      // is not English (Chinese, Hindi, Russian…), the default voice will read
      // English text in the wrong accent, making it sound garbled or foreign.
      // getVoices() may be empty on first call (async load in Chrome); we try
      // synchronously first, then re-check after voiceschanged fires.
      const pickVoice = () => {
        const voices = window.speechSynthesis.getVoices();
        // Prefer an English voice matching our lang prefix
        const prefix = (this.lang || "en").split("-")[0];
        const match = voices.find((v) => v.lang.startsWith(prefix));
        if (match) utt.voice = match;
      };
      pickVoice();
      if (!utt.voice) {
        // Voices haven't loaded yet — listen for them (Chrome loads async)
        const onVoices = () => { pickVoice(); window.speechSynthesis.removeEventListener("voiceschanged", onVoices); };
        window.speechSynthesis.addEventListener("voiceschanged", onVoices);
      }

      // Chrome can drop onend for long utterances or backgrounded tabs → the
      // queue hangs, the mic never re-arms, darshan is stuck. A generous safety
      // timer unbricks the turn regardless.
      const safety = setTimeout(() => resolve(), 30_000);
      const done = () => { clearTimeout(safety); resolve(); };
      utt.onend = done;
      utt.onerror = done;
      try {
        window.speechSynthesis.speak(utt);
      } catch {
        // speak() can throw if the string is absurdly long or the autoplay
        // policy blocks speech — resolve immediately so the queue continues.
        clearTimeout(safety);
        resolve();
      }
    });
  }

  private _ctx(): AudioContext {
    if (!this.audioCtx || this.audioCtx.state === "closed") {
      this.audioCtx = new AudioContext();
      // Browsers created outside a direct user gesture start suspended (autoplay
      // policy). Resume immediately — if it stays suspended, getByteFrequencyData
      // returns silence and decodeAudioData fails silently.
      void this.audioCtx.resume().catch(() => {});
    }
    return this.audioCtx;
  }
}
