/**
 * One quiet, synthesised tap for a navigation preview.
 *
 * The sound is original: a single sine oscillator with a falling pitch and a
 * damped envelope, run through a low-pass and straight out. There is no file to
 * fetch, no decode to wait for and nothing that can fail on a slow connection —
 * if the buffer did not exist yet, the preview would still be on time.
 *
 * Three rules keep it from becoming an annoyance:
 *
 * - **A real gesture unlocks it, and only a real gesture.** No `AudioContext` is
 *   constructed before the visitor has actually pressed or keyed something, so
 *   the first hover is silent and there is no autoplay, no retry loop and no
 *   other way around the browser's own gesture requirement.
 * - **Once per destination, throttled, never overlapping.** The throttle window
 *   is longer than the tap itself, so two taps can never sound at once, and a
 *   pointer that swings between the two words cannot machine-gun.
 * - **Nothing here can break the page.** A missing context, a refused resume or a
 *   throwing node marks the sound dead for the session and returns; the visual
 *   preview and the navigation are untouched.
 */

export const PREVIEW_SOUND_KEY = 'formfield-preview-sound';

/** The envelope, in the units the Web Audio API actually takes. */
export const PREVIEW_TAP = {
  /** Peak gain: a tap under a conversation, never a chime. */
  peak: 0.05,
  /** Length of the tap, in milliseconds. */
  ms: 110,
  /** Attack time, in seconds — long enough to sound soft, short enough to snap. */
  attack: 0.006,
  /** A small downward glide takes the edge off the onset. */
  fromHz: 620,
  toHz: 520,
  /** Nothing above this is worth hearing for a tap. */
  cutoffHz: 2400,
} as const;

/** Longer than one tap, so two taps can never overlap. */
export const PREVIEW_SOUND_THROTTLE_MS = 140;

type AudioContextCtor = new () => AudioContext;

/** The browser's own context, or nothing at all. Never invented, never faked. */
function browserContext(): AudioContext {
  const scope = window as unknown as { AudioContext?: AudioContextCtor; webkitAudioContext?: AudioContextCtor };
  const ctor = scope.AudioContext ?? scope.webkitAudioContext;
  if (!ctor) throw new Error('No Web Audio support');
  return new ctor();
}

/** A refused `localStorage` must not cost the visitor their preference for the session. */
export function storedMuted(): boolean {
  try { return localStorage.getItem(PREVIEW_SOUND_KEY) === 'muted'; }
  catch { return false; }
}

export interface PreviewSound {
  readonly muted: boolean;
  /** True once a real gesture has produced a usable context. */
  readonly unlocked: boolean;
  setMuted(muted: boolean): void;
  /** Call from a real gesture handler and nowhere else. */
  unlock(): void;
  /** One tap. Silent until unlocked, silent while muted, throttled, never throws. */
  tap(): void;
  /** Release the voice and the context. The sound can be unlocked again later. */
  dispose(): void;
}

export interface PreviewSoundOptions {
  muted?: boolean;
  now?: () => number;
  /** Injected by tests; the browser's own constructor by default. */
  create?: () => AudioContext;
}

export function createPreviewSound(options: PreviewSoundOptions = {}): PreviewSound {
  const now = options.now ?? (() => performance.now());
  const create = options.create ?? browserContext;
  let muted = options.muted ?? storedMuted();
  let context: AudioContext | null = null;
  /** Every node of the one tap that may be sounding, so all of them are released. */
  let voice: { source: AudioScheduledSourceNode; nodes: AudioNode[] } | null = null;
  let last = Number.NEGATIVE_INFINITY;
  /** Set once the browser has refused us: no retries, no workarounds. */
  let broken = false;

  /**
   * Stop the tap and let go of the whole chain. Called when a new tap replaces it,
   * when the visitor mutes, when the shell goes away, when the node graph throws,
   * and by the source itself when the tap has run its course — so no node is ever
   * left connected to a destination it no longer has anything to say to.
   */
  const silence = () => {
    const sounding = voice;
    voice = null;
    if (!sounding) return;
    try { sounding.source.stop(); } catch { /* already stopped */ }
    for (const node of sounding.nodes) { try { node.disconnect(); } catch { /* already released */ } }
  };

  const resume = (opened: AudioContext) => {
    if (opened.state !== 'suspended' || typeof opened.resume !== 'function') return;
    try { void Promise.resolve(opened.resume()).catch(() => { broken = true; silence(); }); }
    catch { broken = true; silence(); }
  };

  const unlock = () => {
    if (broken || muted) return;
    if (context) { resume(context); return; }
    let opened: AudioContext;
    try { opened = create(); }
    catch { broken = true; return; }
    context = opened;
    resume(opened);
  };

  const tap = () => {
    if (broken || muted || !context) return;
    const stamp = now();
    // The window is longer than the tap, so this also rules out any overlap.
    if (stamp - last < PREVIEW_SOUND_THROTTLE_MS) return;
    last = stamp;
    silence();
    const seconds = PREVIEW_TAP.ms / 1000;
    try {
      const at = context.currentTime;
      const source = context.createOscillator();
      voice = { source, nodes: [source] };
      const filter = context.createBiquadFilter();
      voice.nodes.push(filter);
      const gain = context.createGain();
      voice.nodes.push(gain);
      source.type = 'sine';
      source.frequency.setValueAtTime(PREVIEW_TAP.fromHz, at);
      source.frequency.exponentialRampToValueAtTime(PREVIEW_TAP.toHz, at + seconds);
      filter.type = 'lowpass';
      filter.frequency.setValueAtTime(PREVIEW_TAP.cutoffHz, at);
      // Never from silence to full: an exponential ramp from zero is not a ramp.
      gain.gain.setValueAtTime(0.0001, at);
      gain.gain.exponentialRampToValueAtTime(PREVIEW_TAP.peak, at + PREVIEW_TAP.attack);
      gain.gain.exponentialRampToValueAtTime(0.0001, at + seconds);
      source.connect(filter);
      filter.connect(gain);
      gain.connect(context.destination);
      source.start(at);
      source.stop(at + seconds);
      // The tap ends itself: releasing on `ended` is what keeps a long session
      // from holding on to nodes it has no further use for.
      source.onended = () => { if (voice?.source === source) silence(); };
    } catch {
      broken = true;
      silence();
    }
  };

  const setMuted = (next: boolean) => {
    muted = next;
    // Muting is immediate, and a voice already in flight stops with it.
    if (muted) silence();
    try {
      if (muted) localStorage.setItem(PREVIEW_SOUND_KEY, 'muted');
      else localStorage.removeItem(PREVIEW_SOUND_KEY);
    } catch { /* A refused store only costs the preference, never the session. */ }
  };

  const dispose = () => {
    silence();
    const closing = context;
    context = null;
    // Not a one-way door: a later gesture may unlock a fresh context, which is
    // what keeps this correct under StrictMode's mount/unmount/mount rehearsal.
    if (closing) { try { void Promise.resolve(closing.close?.()).catch(() => {}); } catch { /* already closed */ } }
  };

  return {
    get muted() { return muted; },
    get unlocked() { return context !== null && !broken; },
    setMuted, unlock, tap, dispose,
  };
}
