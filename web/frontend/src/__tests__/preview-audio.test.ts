import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createPreviewSound, PREVIEW_SOUND_KEY, PREVIEW_SOUND_THROTTLE_MS, PREVIEW_TAP } from '../portfolio/previewAudio';

const param = () => ({ setValueAtTime: vi.fn(), exponentialRampToValueAtTime: vi.fn() });
function audio(state = 'running') {
  const source = { connect: vi.fn(), disconnect: vi.fn(), start: vi.fn(), stop: vi.fn(), frequency: param(), type: '', onended: null as (() => void) | null };
  const filter = { connect: vi.fn(), disconnect: vi.fn(), frequency: param(), type: '' };
  const gain = { connect: vi.fn(), disconnect: vi.fn(), gain: param() };
  const context = { state, currentTime: 12, destination: {}, resume: vi.fn().mockResolvedValue(undefined), close: vi.fn().mockResolvedValue(undefined),
    createOscillator: vi.fn(() => source), createBiquadFilter: vi.fn(() => filter), createGain: vi.fn(() => gain) };
  return { source, filter, gain, context, create: vi.fn(() => context as unknown as AudioContext) };
}
beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());

describe('preview tap lifecycle', () => {
  it('distinguishes silent attempts and uses a lower, shorter Work voice', () => {
    const graph = audio(); let time = 0;
    const sound = createPreviewSound({ create: graph.create, now: () => time });
    expect(sound.tap('about')).toBe(false);
    sound.unlock();
    expect(sound.tap('work')).toBe(true);
    expect(graph.source.frequency.setValueAtTime).toHaveBeenLastCalledWith(PREVIEW_TAP.work.fromHz, 12);
    expect(graph.source.stop).toHaveBeenLastCalledWith(12 + PREVIEW_TAP.work.ms / 1000);
    expect(sound.tap('about')).toBe(false);
    time = PREVIEW_SOUND_THROTTLE_MS;
    expect(sound.tap('about')).toBe(true);
    expect(graph.source.frequency.setValueAtTime).toHaveBeenLastCalledWith(PREVIEW_TAP.about.fromHz, 12);
    expect(PREVIEW_TAP.work.fromHz).toBeLessThan(PREVIEW_TAP.about.fromHz);
    expect(PREVIEW_TAP.work.ms).toBeLessThan(PREVIEW_TAP.about.ms);
    expect(PREVIEW_TAP.about.peak).toBeLessThan(PREVIEW_TAP.work.peak);
    expect(PREVIEW_SOUND_THROTTLE_MS).toBeGreaterThan(PREVIEW_TAP.about.ms);
    sound.dispose();
  });
  it('stays silent until a gesture unlocks it, then throttles repeated previews', () => {
    const graph = audio(); let time = 0;
    const sound = createPreviewSound({ create: graph.create, now: () => time });
    sound.tap();
    expect(graph.create).not.toHaveBeenCalled();
    sound.unlock(); sound.unlock(); sound.tap(); sound.tap();
    expect(graph.create).toHaveBeenCalledTimes(1);
    expect(graph.source.start).toHaveBeenCalledTimes(1);
    time = PREVIEW_SOUND_THROTTLE_MS; sound.tap();
    expect(graph.source.start).toHaveBeenCalledTimes(2);
    expect(graph.source.disconnect).toHaveBeenCalledTimes(1);
  });

  it.each(['ended', 'mute', 'dispose'] as const)('releases the whole graph on %s', reason => {
    const graph = audio(); const sound = createPreviewSound({ create: graph.create });
    sound.unlock(); sound.tap();
    if (reason === 'ended') graph.source.onended!();
    if (reason === 'mute') sound.setMuted(true);
    if (reason === 'dispose') sound.dispose();
    for (const node of [graph.source, graph.filter, graph.gain]) expect(node.disconnect).toHaveBeenCalledTimes(1);
    sound.dispose();
    for (const node of [graph.source, graph.filter, graph.gain]) expect(node.disconnect).toHaveBeenCalledTimes(1);
    expect(graph.context.close).toHaveBeenCalledTimes(1);
  });

  it('remembers mute and allows a later explicit unmute gesture', () => {
    localStorage.setItem(PREVIEW_SOUND_KEY, 'muted');
    const graph = audio(); const sound = createPreviewSound({ create: graph.create });
    sound.unlock(); sound.tap();
    expect(graph.create).not.toHaveBeenCalled();
    sound.setMuted(false); sound.unlock(); sound.tap();
    expect(graph.source.start).toHaveBeenCalledTimes(1);
    expect(localStorage.getItem(PREVIEW_SOUND_KEY)).toBeNull();
    sound.setMuted(true);
    expect(createPreviewSound().muted).toBe(true);
  });

  it('does not retry a refused resume or throw into navigation', async () => {
    const graph = audio('suspended'); graph.context.resume.mockRejectedValue(new Error('refused'));
    const sound = createPreviewSound({ create: graph.create });
    sound.unlock(); await Promise.resolve(); await Promise.resolve();
    sound.unlock(); sound.tap();
    expect(graph.context.resume).toHaveBeenCalledTimes(1);
    expect(graph.source.start).not.toHaveBeenCalled();
    expect(sound.unlocked).toBe(false);
  });

  it('disconnects partially constructed graphs when a node fails', () => {
    const graph = audio(); graph.context.createGain.mockImplementation(() => { throw new Error('node failure'); });
    const sound = createPreviewSound({ create: graph.create });
    sound.unlock(); expect(() => sound.tap()).not.toThrow();
    expect(graph.source.disconnect).toHaveBeenCalledTimes(1);
    expect(graph.filter.disconnect).toHaveBeenCalledTimes(1);
    sound.tap(); expect(graph.context.createGain).toHaveBeenCalledTimes(1);
  });

  it('tolerates unavailable audio and denied storage', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('denied'); });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('denied'); });
    const create = vi.fn(() => { throw new Error('missing'); });
    const sound = createPreviewSound({ create });
    expect(() => { sound.unlock(); sound.unlock(); sound.setMuted(true); sound.tap(); sound.dispose(); }).not.toThrow();
    expect(create).toHaveBeenCalledTimes(1);
  });
});
