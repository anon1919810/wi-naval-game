import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createInteractionAudio, SOUND_FILES, SOUND_KEY } from '../audio/interactionAudio';

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(res => { resolve = res; });
  return { promise, resolve };
}
const flush = async () => { for (let i = 0; i < 10; i++) await Promise.resolve(); };
function graph(state: 'running' | 'suspended' = 'running') {
  const sources: Array<{ buffer: AudioBuffer | null; connect: ReturnType<typeof vi.fn>; disconnect: ReturnType<typeof vi.fn>;
    start: ReturnType<typeof vi.fn>; stop: ReturnType<typeof vi.fn>; onended: (() => void) | null }> = [];
  const gains: Array<{ connect: ReturnType<typeof vi.fn>; disconnect: ReturnType<typeof vi.fn>;
    gain: { value: number; cancelScheduledValues: ReturnType<typeof vi.fn>; setValueAtTime: ReturnType<typeof vi.fn>; linearRampToValueAtTime: ReturnType<typeof vi.fn> } }> = [];
  const context = {
    state, currentTime: 12, destination: {}, resume: vi.fn().mockImplementation(async () => { context.state = 'running'; }), close: vi.fn().mockResolvedValue(undefined),
    decodeAudioData: vi.fn(async (bytes: ArrayBuffer) => ({ id: new Uint8Array(bytes)[0] }) as unknown as AudioBuffer),
    createBufferSource: vi.fn(() => {
      const source = { buffer: null as AudioBuffer | null, connect: vi.fn(node => node), disconnect: vi.fn(), start: vi.fn(), stop: vi.fn(), onended: null as (() => void) | null };
      sources.push(source); return source;
    }),
    createGain: vi.fn(() => {
      const gain = { connect: vi.fn(), disconnect: vi.fn(), gain: { value: 1, cancelScheduledValues: vi.fn(), setValueAtTime: vi.fn(), linearRampToValueAtTime: vi.fn() } };
      gains.push(gain); return gain;
    }),
  };
  const load = vi.fn(async (url: string) => new Uint8Array([Object.values(SOUND_FILES).indexOf(url as never)]).buffer);
  return { context, sources, gains, load, create: vi.fn(() => context as unknown as AudioContext) };
}
beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());

describe('shared interaction audio', () => {
  it('fetches the approved files without creating a context or replaying a cold hover', async () => {
    const g = graph(); const sound = createInteractionAudio(g);
    sound.warm(); sound.warm();
    expect(sound.play('touch', { group: 'preview' })).toBe(false);
    await flush();
    expect(g.load.mock.calls.map(([url]) => url)).toEqual(Object.values(SOUND_FILES));
    expect(g.create).not.toHaveBeenCalled();
    sound.unlock(); await flush();
    expect(g.sources).toHaveLength(0);
    expect(sound.play('passage', { group: 'transition' })).toBe(true);
    expect(g.sources[0].buffer).toEqual({ id: 2 });
    expect(g.gains[0].gain.value).toBe(.5);
    sound.dispose();
  });

  it('throttles previews, lets confirmed outcomes supersede them, and retires prior tails', async () => {
    const g = graph(); let now = 0;
    const sound = createInteractionAudio({ ...g, now: () => now });
    sound.unlock(); await flush();
    expect(sound.play('touch', { group: 'preview' })).toBe(true);
    expect(sound.play('touch', { group: 'preview' })).toBe(false);
    expect(sound.play('passage', { group: 'transition' })).toBe(true);
    expect(sound.play('resolve', { group: 'result' })).toBe(true);
    expect(sound.play('touch')).toBe(false);
    expect(sound.play('detent', { group: 'reading' })).toBe(false);
    expect(g.sources).toHaveLength(3);
    expect(g.sources[0].stop).toHaveBeenCalledOnce();
    expect(g.sources[1].stop).toHaveBeenCalledOnce();
    now = 300;
    expect(sound.play('detent', { group: 'reading', volume: .32 })).toBe(true);
    expect(g.gains[3].gain.value).toBe(.16);
    // Ending an old source must not erase the current voice.
    g.sources[0].onended!(); sound.stop();
    expect(g.sources[3].stop).toHaveBeenCalledOnce();
    sound.dispose();
    for (const source of g.sources) expect(source.disconnect).toHaveBeenCalledOnce();
    for (const gain of g.gains) expect(gain.disconnect).toHaveBeenCalledOnce();
  });

  it.each(['mute', 'stop', 'dispose', 'expired', 'hidden'] as const)('drops a pending cold command on %s', async reason => {
    const g = graph(); const loading = deferred<ArrayBuffer>(); let now = 0, hidden = false;
    const sound = createInteractionAudio({ ...g, load: () => loading.promise, now: () => now, hidden: () => hidden });
    sound.unlock(); sound.play('passage', { group: 'transition' });
    if (reason === 'mute') sound.setMuted(true);
    if (reason === 'stop') sound.stop('transition');
    if (reason === 'dispose') sound.dispose();
    if (reason === 'expired') now = 181;
    if (reason === 'hidden') hidden = true;
    loading.resolve(new ArrayBuffer(4)); await flush();
    expect(g.sources).toHaveLength(0);
    sound.dispose();
  });

  it('keeps only the latest cold command, without allowing late preview audio', async () => {
    const g = graph(); const loading = deferred<ArrayBuffer>();
    const sound = createInteractionAudio({ ...g, load: () => loading.promise });
    sound.unlock(); sound.play('touch'); sound.play('passage', { group: 'transition' });
    sound.play('touch', { group: 'preview' });
    loading.resolve(new ArrayBuffer(4)); await flush();
    expect(g.sources).toHaveLength(1);
    sound.dispose();
  });

  it('restores persisted mute and only opens audio after explicit unmute', async () => {
    localStorage.setItem(SOUND_KEY, 'muted');
    const g = graph(); const sound = createInteractionAudio(g); const changed = vi.fn();
    sound.subscribe(changed); sound.unlock(); sound.play('touch');
    expect(g.create).not.toHaveBeenCalled();
    sound.setMuted(false); sound.unlock(); await flush(); sound.play('touch');
    expect(g.sources).toHaveLength(1);
    expect(localStorage.getItem(SOUND_KEY)).toBeNull();
    sound.setMuted(true); sound.setMuted(true);
    expect(changed).toHaveBeenCalledTimes(2);
    expect(g.sources[0].stop).toHaveBeenCalledOnce();
    sound.dispose(); sound.dispose();
    expect(g.context.close).toHaveBeenCalledOnce();
  });

  it('rejects stale decodes after disposal and can unlock a new context', async () => {
    const old = graph(), next = graph(); const decoding = deferred<AudioBuffer>();
    old.context.decodeAudioData.mockImplementation(() => decoding.promise);
    const create = vi.fn().mockReturnValueOnce(old.context).mockReturnValue(next.context);
    const sound = createInteractionAudio({ create, load: old.load });
    sound.unlock(); sound.play('touch'); await flush(); sound.dispose();
    sound.unlock(); await flush();
    decoding.resolve({} as AudioBuffer); await flush();
    expect(old.sources).toHaveLength(0);
    expect(sound.play('passage', { group: 'transition' })).toBe(true);
    expect(next.sources).toHaveLength(1);
    sound.dispose();
  });

  it('does not let blocked audio, failed fetches or denied storage interrupt controls', async () => {
    const g = graph('suspended'); g.context.resume.mockRejectedValue(new Error('blocked'));
    const sound = createInteractionAudio(g);
    sound.unlock(); await flush(); sound.unlock();
    expect(g.context.resume).toHaveBeenCalledOnce();
    expect(sound.play('touch')).toBe(false);
    expect(sound.unlocked).toBe(false); sound.dispose();
    const unavailable = createInteractionAudio({ ...graph(), load: async () => { throw new Error('404'); } });
    unavailable.unlock(); await flush(); expect(() => unavailable.play('passage')).not.toThrow(); unavailable.dispose();
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('denied'); });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('denied'); });
    const missing = createInteractionAudio({ create: () => { throw new Error('missing'); } });
    expect(() => { missing.unlock(); missing.setMuted(true); missing.dispose(); }).not.toThrow();
  });

  it('disconnects a partially constructed voice when a node fails', async () => {
    const g = graph(); g.context.createGain.mockImplementation(() => { throw new Error('node failure'); });
    const sound = createInteractionAudio(g); sound.unlock(); await flush();
    expect(sound.play('touch')).toBe(false);
    expect(g.sources[0].disconnect).toHaveBeenCalledOnce();
    expect(sound.play('touch')).toBe(false);
    expect(g.context.createGain).toHaveBeenCalledOnce(); sound.dispose();
  });
});
