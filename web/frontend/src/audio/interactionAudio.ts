/** The approved audition files, shared by the portfolio and workspace. */
export const SOUND_KEY = 'formfield-preview-sound';
export const SOUND_FILES = {
  touch: '/audio/touch.wav', detent: '/audio/detent.wav',
  passage: '/audio/passage-a-02.wav', resolve: '/audio/complete.wav', hold: '/audio/failure.wav',
} as const;
export type SoundCue = keyof typeof SOUND_FILES;
export type SoundGroup = 'preview' | 'reading' | 'command' | 'transition' | 'result';
const PRIORITY: Record<SoundGroup, number> = { preview: 0, reading: 0, command: 1, transition: 2, result: 3 };
export function storedMuted(): boolean {
  try { return localStorage.getItem(SOUND_KEY) === 'muted'; } catch { return false; }
}
interface PlayOptions { group?: SoundGroup; volume?: number }
interface Voice { source: AudioBufferSourceNode; gain: GainNode; group: SoundGroup }
interface AudioOptions {
  muted?: boolean; create?: () => AudioContext; load?: (url: string) => Promise<ArrayBuffer>;
  now?: () => number; hidden?: () => boolean;
}
export interface InteractionAudio {
  readonly muted: boolean;
  readonly unlocked: boolean;
  warm(): void;
  /** Only real gesture handlers call this; fetching never creates a context. */
  unlock(): void;
  play(cue: SoundCue, options?: PlayOptions): boolean;
  stop(group?: SoundGroup): void;
  setMuted(muted: boolean): void;
  subscribe(listener: () => void): () => void;
  dispose(): void;
}
export function createInteractionAudio(options: AudioOptions = {}): InteractionAudio {
  const now = options.now ?? (() => performance.now());
  const hidden = options.hidden ?? (() => document.hidden);
  const load = options.load ?? (async url => {
    const response = await fetch(url);
    if (!response.ok) throw new Error('Sound unavailable');
    return response.arrayBuffer();
  });
  const create = options.create ?? (() => {
    const scope = window as unknown as { AudioContext?: typeof AudioContext; webkitAudioContext?: typeof AudioContext };
    const Constructor = scope.AudioContext ?? scope.webkitAudioContext;
    if (!Constructor) throw new Error('Audio unavailable');
    return new Constructor();
  });
  let muted = options.muted ?? storedMuted(), broken = false;
  let context: AudioContext | null = null;
  let lifetime = 0, last = -Infinity, lastPriority = -1;
  let pending: { cue: SoundCue; group: SoundGroup; volume: number; at: number } | null = null;
  let voice: Voice | null = null;
  const voices = new Set<Voice>();
  const listeners = new Set<() => void>();
  const files = new Map<SoundCue, Promise<ArrayBuffer | null>>();
  const buffers = new Map<SoundCue, AudioBuffer>();
  const decoding = new Map<SoundCue, Promise<void>>();
  const file = (cue: SoundCue) => {
    let promise = files.get(cue);
    if (!promise) {
      promise = Promise.resolve().then(() => load(SOUND_FILES[cue])).catch(() => null);
      files.set(cue, promise);
    }
    return promise;
  };
  const warm = () => { for (const cue of Object.keys(SOUND_FILES) as SoundCue[]) void file(cue); };
  const release = (old: Voice) => {
    if (!voices.delete(old)) return;
    try { old.source.disconnect(); old.gain.disconnect(); } catch { /* Already released. */ }
    if (voice === old) voice = null;
  };
  const silence = (group?: SoundGroup) => {
    if (pending && (!group || pending.group === group)) pending = null;
    if (!voice || (group && voice.group !== group)) return;
    const old = voice; voice = null;
    try {
      const at = context?.currentTime ?? 0;
      old.gain.gain.cancelScheduledValues(at);
      old.gain.gain.setValueAtTime(old.gain.gain.value, at);
      old.gain.gain.linearRampToValueAtTime(0, at + .012);
      old.source.stop(at + .013);
    } catch { release(old); }
  };
  const start = (cue: SoundCue, group: SoundGroup, volume: number): boolean => {
    const buffer = buffers.get(cue);
    if (!context || context.state !== 'running' || !buffer || muted || broken || hidden()) return false;
    silence();
    let source: AudioBufferSourceNode | undefined, gain: GainNode | undefined;
    try {
      source = context.createBufferSource(); gain = context.createGain(); source.buffer = buffer;
      // Same default gain as the audition; reading deliberately uses less.
      gain.gain.value = .5 * Math.max(0, Math.min(1, volume));
      source.connect(gain).connect(context.destination);
      const current = { source, gain, group }; voice = current; voices.add(current);
      source.onended = () => release(current);
      source.start(context.currentTime + .014);
      return true;
    } catch {
      try { source?.disconnect(); gain?.disconnect(); } catch { /* Partial graph. */ }
      if (voice) voices.delete(voice);
      voice = null; broken = true; return false;
    }
  };
  const decode = (cue: SoundCue, opened: AudioContext, ticket: number) => {
    if (decoding.has(cue)) return;
    const work = file(cue).then(async bytes => {
      if (!bytes || context !== opened || ticket !== lifetime) return;
      const buffer = await opened.decodeAudioData(bytes.slice(0));
      if (context !== opened || ticket !== lifetime) return;
      buffers.set(cue, buffer);
      const request = pending;
      if (request?.cue === cue) {
        pending = null;
        if (now() - request.at <= 180) start(cue, request.group, request.volume);
      }
    }).catch(() => { /* Failed audio never delays UI. */ });
    decoding.set(cue, work);
  };
  const unlock = () => {
    if (muted || broken || hidden()) return;
    try {
      if (!context) context = create();
      const opened = context, ticket = lifetime;
      const ready = opened.state === 'suspended' ? opened.resume() : Promise.resolve();
      void ready.then(() => {
        if (context !== opened || ticket !== lifetime) return;
        for (const cue of Object.keys(SOUND_FILES) as SoundCue[]) decode(cue, opened, ticket);
      }).catch(() => { if (context === opened) { broken = true; silence(); } });
    } catch { broken = true; silence(); }
  };
  const play = (cue: SoundCue, settings: PlayOptions = {}): boolean => {
    if (muted || broken || !context || hidden()) return false;
    const group = settings.group ?? 'command', priority = PRIORITY[group], stamp = now();
    const elapsed = stamp - last;
    if ((priority < lastPriority && elapsed < 280) || (priority === 0 && elapsed < 160)) return false;
    last = stamp; lastPriority = priority;
    const volume = settings.volume ?? 1;
    if (buffers.has(cue) && context.state === 'running') return start(cue, group, volume);
    // Cold clicks wait at most 180 ms; cold previews/ticks are dropped, never queued.
    if (priority > 0) { silence(); pending = { cue, group, volume, at: stamp }; }
    return false;
  };
  const setMuted = (next: boolean) => {
    if (muted === next) return;
    muted = next;
    if (next) silence();
    try { if (next) localStorage.setItem(SOUND_KEY, 'muted'); else localStorage.removeItem(SOUND_KEY); } catch { /* Session preference survives. */ }
    for (const listener of listeners) listener();
  };
  const dispose = () => {
    silence(); const closing = context; context = null; lifetime++;
    for (const old of voices) release(old);
    buffers.clear(); decoding.clear(); last = -Infinity; lastPriority = -1; broken = false;
    try { void closing?.close().catch(() => {}); } catch { /* Already closed. */ }
  };
  return {
    get muted() { return muted; }, get unlocked() { return context !== null && !broken; },
    warm, unlock, play, stop: silence, setMuted, dispose,
    subscribe(listener) { listeners.add(listener); return () => { listeners.delete(listener); }; },
  };
}
export const interactionAudio = createInteractionAudio();
const requestedRuns = new Set<string>();
export function expectRunResult(id: string): void {
  if (requestedRuns.size >= 20) requestedRuns.delete(requestedRuns.values().next().value!);
  requestedRuns.add(id);
}
export function consumeRunRequest(id: string): boolean { return requestedRuns.delete(id); }
