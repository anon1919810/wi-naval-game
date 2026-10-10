import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Portfolio from '../portfolio/Portfolio';
import { PLAN_SHEETS } from '../portfolio/plans';
import * as api from '../api';

/**
 * Cluster: which reference bitmaps the page asks the browser for.
 *
 * There are three ~200 KB sheets and a visitor usually looks at one. Fetching
 * all three while the page is idle spends the visitor's data and connection for
 * drawings they may never open, and it does it before they have done anything.
 * These tests pin the policy: the selected sheet is loaded, and nothing else is
 * loaded until a sheet is actually selected.
 */

vi.mock('../api', async importOriginal => ({
  ...await importOriginal<typeof import('../api')>(),
  authConfig: vi.fn(), me: vi.fn(), bootstrapAnonymous: vi.fn(), listProjects: vi.fn(),
}));

/** Every bitmap URL the browser was asked to decode, in request order. */
let requested: string[] = [];
/** Idle callbacks the shell scheduled, so the test can run them deliberately. */
let idle: Array<() => void> = [];

beforeEach(() => {
  window.history.replaceState(null, '', '/');
  localStorage.clear();
  requested = [];
  idle = [];
  vi.clearAllMocks();
  vi.stubGlobal('matchMedia', vi.fn(() => ({
    matches: false, media: '',
    addEventListener: vi.fn(), removeEventListener: vi.fn(),
  })));
  // The selected sheet's own decode resolves; everything else is held open, so
  // a prefetch of the alternatives would be plainly visible.
  vi.stubGlobal('Image', class {
    private url = '';
    set src(value: string) {
      this.url = value;
      requested.push(value);
    }
    get src() { return this.url; }
    decode() { return Promise.resolve(); }
  });
  // requestIdleCallback is the hook the idle prefetch used. Recording the
  // callback instead of running it makes "nothing else was loaded" checkable.
  vi.stubGlobal('requestIdleCallback', vi.fn((callback: () => void) => {
    idle.push(callback);
    return idle.length;
  }));
  vi.stubGlobal('cancelIdleCallback', vi.fn());
  vi.stubGlobal('scrollTo', vi.fn());
  vi.mocked(api.authConfig).mockResolvedValue({ mode: 'anonymous' });
  vi.mocked(api.me).mockResolvedValue({ id: 'existing', email: 'existing@anonymous.invalid', theme: 'light', csrf_token: 'test', mode: 'anonymous', label: '本浏览器工作区' });
  vi.mocked(api.listProjects).mockResolvedValue([]);
});

afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });

const flush = () => act(async () => {});
/** Run everything the shell deferred to an idle period. */
async function runIdle() {
  await act(async () => { for (const callback of idle) callback(); });
  await flush();
}

describe('reference bitmaps are loaded on selection, not in advance', () => {
  it('asks for the displayed sheet and nothing else, even after every idle period', async () => {
    vi.useFakeTimers();
    try {
      render(<Portfolio introEnabled={false} />);
      await flush();
      expect(requested).toEqual([PLAN_SHEETS[0].href]);

      // Two idle periods, and a timer long enough for the previous setTimeout
      // fallback to have fired as well.
      await runIdle();
      await runIdle();
      await act(async () => { vi.advanceTimersByTime(5000); });
      await flush();

      // The two alternatives are still not requested. They will be, when the
      // visitor selects one.
      expect(requested).toEqual([PLAN_SHEETS[0].href]);
      expect(requested).not.toContain(PLAN_SHEETS[1].href);
      expect(requested).not.toContain(PLAN_SHEETS[2].href);
    } finally {
      vi.useRealTimers();
    }
  });

  it('loads an alternative exactly when the visitor selects it', async () => {
    render(<Portfolio introEnabled={false} />);
    await flush();
    const target = PLAN_SHEETS[2];
    expect(requested).toEqual([PLAN_SHEETS[0].href]);

    fireEvent.click(screen.getByRole('button', { name: target.label }));
    await flush();

    // The press is the intent: the alternative is now requested, once.
    expect(requested).toContain(target.href);
    expect(requested.filter(href => href === target.href)).toHaveLength(1);
    // And the sheet that was never selected is still not requested.
    expect(requested).not.toContain(PLAN_SHEETS[1].href);
  });

  it('loads only the selected sheet on the work detail too', async () => {
    window.history.replaceState(null, '', '/#/work/plimsoll');
    act(() => { window.dispatchEvent(new HashChangeEvent('hashchange')); });
    render(<Portfolio introEnabled={false} />);
    await flush();
    await runIdle();
    expect(requested).toEqual([PLAN_SHEETS[0].href]);
  });

  it.each(['about', 'credits'])('mounts no bitmap resource on %s', async view => {
    window.history.replaceState(null, '', `/#/${view}`);
    render(<Portfolio />);
    await flush();
    await runIdle();
    expect(requested).toEqual([]);
    // A hidden SVG still fetches its href in a real browser; Image/decode
    // stubs alone cannot observe that second request path.
    expect(document.querySelector('image[href^="/portfolio/ship-plan-"]')).toBeNull();
  });
});
