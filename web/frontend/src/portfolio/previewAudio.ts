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
 *   is longer than the longest of the two voices, so two taps can never sound at
 *   once, and a pointer that swings between the two words cannot machine-gun.
 * - **The voice says which way it is.** Work's is shorter, lower and more exact;
 *   About's is the same quiet register for a little longer. Both peaks sit inside
 *   one narrow range, so neither destination can be louder than the other.
 * - **Nothing here can break the page.** A missing context, a refused resume or a
 *   throwing node marks the sound dead for the session and returns; the visual
 *   preview and the navigation are untouched.
 */

export const PREVIEW_SOUND_KEY = 'formfield-preview-sound';

/**
 * One voice per destination, so the tap says which way the visitor is going.
 *
 * Work is the shorter, lower, more exact of the two — a small closed tap, a
 * steeper fall, a shorter attack. About is the same quiet register for a little
 * longer, a touch softer and rounder. Both peaks stay inside one narrow range
 * below a fifth of full scale, so neither can be louder than the other and
 * neither can become a chime.
 */
export type PreviewVoice = 'work' | 'about';

interface TapProfile {
  /** Peak gain: a tap under a conversation, never a chime. */
  readonly peak: number;
  /** Length of the tap, in milliseconds. */
  readonly ms: number;
  /** Attack time, in seconds — long enough to sound soft, short enough to snap. */
  readonly attack: number;
  /** A small downward glide takes the edge off the onset. */
  readonly fromHz: number;
  readonly toHz: number;
  /** Nothing above this is worth hearing for a tap. */
  readonly cutoffHz: number;
}

export const PREVIEW_TAP: Readonly<Record<PreviewVoice, TapProfile>> = {
  work: { peak: 0.05, ms: 84, attack: 0.004, fromHz: 540, toHz: 440, cutoffHz: 2600 },
  about: { peak: 0.046, ms: 124, attack: 0.009, fromHz: 620, toHz: 500, cutoffHz: 2000 },
};

/** The envelope, in the units the Web Audio API actually takes. */
export const PREVIEW_TAP_DEFAULT: PreviewVoice = 'work';

/** Longer than the longest voice, so two taps can never overlap. */
export const PREVIEW_SOUND_THROTTLE_MS = 200;

/** The longest voice in the set: the throttle and any lifetime must exceed it. */
export function longestVoiceMs(): number {
  return Math.max(...Object.values(PREVIEW_TAP).map(profile => profile.ms));
}

/** The loudest voice in the set: nothing may exceed it. */
export function loudestVoicePeak(): number {
  return Math.max(...Object.values(PREVIEW_TAP).map(profile => profile.peak));
}

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
  /**
   * One tap for one destination. Silent until unlocked, silent while muted,
   * throttled, never throws. Returns whether it actually sounded, which is what
   * tells a caller that a silent preview must not count as one that happened.
   */
  tap(voice?: PreviewVoice): boolean;
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

  const tap = (which: PreviewVoice = PREVIEW_TAP_DEFAULT): boolean => {
    if (broken || muted || !context) return false;
    const stamp = now();
    // The window is longer than the longest voice, so this also rules out any overlap.
    if (stamp - last < PREVIEW_SOUND_THROTTLE_MS) return false;
    last = stamp;
    silence();
    const profile = PREVIEW_TAP[which] ?? PREVIEW_TAP[PREVIEW_TAP_DEFAULT];
    const seconds = profile.ms / 1000;
    try {
      const at = context.currentTime;
      const source = context.createOscillator();
      voice = { source, nodes: [source] };
      const filter = context.createBiquadFilter();
      voice.nodes.push(filter);
      const gain = context.createGain();
      voice.nodes.push(gain);
      source.type = 'sine';
      source.frequency.setValueAtTime(profile.fromHz, at);
      source.frequency.exponentialRampToValueAtTime(profile.toHz, at + seconds);
      filter.type = 'lowpass';
      filter.frequency.setValueAtTime(profile.cutoffHz, at);
      // Never from silence to full: an exponential ramp from zero is not a ramp.
      gain.gain.setValueAtTime(0.0001, at);
      gain.gain.exponentialRampToValueAtTime(profile.peak, at + profile.attack);
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
      // A tap that could not be built did not sound, and saying otherwise would
      // let a caller believe it never has to try again.
      return false;
    }
    return true;
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
