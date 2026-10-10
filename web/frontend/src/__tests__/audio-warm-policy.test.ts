import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SOUND_FILES } from '../audio/interactionAudio';

/**
 * Cluster: when the audition files may be fetched at all.
 *
 * A page that fetches five WAVs the moment it mounts has spent the visitor's
 * bandwidth and data before they have asked for a single sound — and it does it
 * even to someone who has muted sound. These tests drive the *installed*
 * controller, through a fresh module graph each time, because that is where the
 * policy was wrong. Which cue plays, and when `unlock()` itself may load, are
 * covered in interaction-audio.test.ts; this file is only about the request.
 *
 * The shared singleton reads through the browser `fetch`, so stubbing `fetch`
 * observes the real network path rather than an injected loader.
 */

beforeEach(() => { localStorage.clear(); });
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

/** A fresh controller and singleton, so nothing is cached from a previous test. */
async function freshController() {
  vi.resetModules();
  const feedback = await import('../audio/feedback');
  const audio = await import('../audio/interactionAudio');
  const toggle = await import('../audio/SoundToggle');
  return { feedback, audio, toggle };
}

/** Records every audition URL the page asks the browser for. */
function recordFetches() {
  const requests: string[] = [];
  const fetchStub = vi.fn(async (input: RequestInfo | URL) => {
    requests.push(String(input));
    return { ok: true, arrayBuffer: async () => new ArrayBuffer(8) } as Response;
  });
  vi.stubGlobal('fetch', fetchStub);
  return { requests, fetchStub };
}

/** jsdom has no Web Audio; a minimal running context exercises the real path. */
function stubAudioContext() {
  vi.stubGlobal('AudioContext', function () {
    return {
      state: 'running', currentTime: 0, destination: {},
      resume: async () => undefined, close: async () => undefined,
      decodeAudioData: async () => ({}),
      createBufferSource: () => ({
        buffer: null, connect: (node: unknown) => node, disconnect: () => {},
        start: () => {}, stop: () => {}, onended: null,
      }),
      createGain: () => ({
        connect: () => {}, disconnect: () => {},
        gain: {
          value: 1, cancelScheduledValues: () => {},
          setValueAtTime: () => {}, linearRampToValueAtTime: () => {},
        },
      }),
    };
  });
}

/** Let every promise chain the installer starts run to completion. */
async function settle() {
  for (let index = 0; index < 20; index++) await Promise.resolve();
  await new Promise(resolve => setTimeout(resolve, 0));
}

describe('mounting the feedback controller fetches nothing', () => {
  it.each([null, 'muted'])('with a stored sound preference of %s', async stored => {
    const { feedback, audio } = await freshController();
    if (stored === 'muted') localStorage.setItem('formfield-preview-sound', stored);
    const { requests, fetchStub } = recordFetches();
    audio.interactionAudio.dispose();

    const remove = feedback.installInteractionFeedback();
    try {
      await settle();
      expect(requests).toEqual([]);
      expect(fetchStub).not.toHaveBeenCalled();
      // Mounting is not consent, and it is not an audio context either.
      expect(audio.interactionAudio.unlocked).toBe(false);
    } finally {
      remove();
      audio.interactionAudio.dispose();
    }
  });

  it('fetches nothing for a scripted gesture, because it is not a real one', async () => {
    const { feedback, audio } = await freshController();
    const { requests } = recordFetches();
    stubAudioContext();
    audio.interactionAudio.dispose();

    const remove = feedback.installInteractionFeedback();
    try {
      await settle();
      document.body.dispatchEvent(new Event('pointerdown', { bubbles: true }));
      document.body.dispatchEvent(new Event('keydown', { bubbles: true }));
      await settle();
      expect(requests).toEqual([]);
    } finally {
      remove();
      audio.interactionAudio.dispose();
    }
  });
});

describe('a muted visitor is never asked to pay for sound', () => {
  it('fetches nothing while muted, and fetches only when sound is turned on', async () => {
    const { feedback, audio, toggle } = await freshController();
    const { act } = await import('@testing-library/react');
    const { createRoot } = await import('react-dom/client');
    const { createElement } = await import('react');

    const { requests } = recordFetches();
    stubAudioContext();
    // The visitor has said no.
    localStorage.setItem('formfield-preview-sound', 'muted');
    audio.interactionAudio.dispose();

    const remove = feedback.installInteractionFeedback();
    const host = document.createElement('div');
    document.body.append(host);
    const root = createRoot(host);
    await act(async () => { root.render(createElement(toggle.SoundToggle)); });
    try {
      expect(audio.interactionAudio.muted).toBe(true);
      await settle();
      expect(requests).toEqual([]);

      // Turning sound on is the enabling decision, and only then may it load.
      const button = host.querySelector('button')!;
      await act(async () => { button.click(); });
      await settle();
      expect(audio.interactionAudio.muted).toBe(false);
      expect(new Set(requests)).toEqual(new Set(Object.values(SOUND_FILES)));
      expect(requests).toHaveLength(Object.keys(SOUND_FILES).length);
    } finally {
      await act(async () => { root.unmount(); });
      host.remove();
      remove();
      audio.interactionAudio.dispose();
    }
  });
});
