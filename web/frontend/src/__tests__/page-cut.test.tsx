import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Portfolio from '../portfolio/Portfolio';
import * as transitions from '../portfolio/transitions';
import { TRANSITION_MS, transitionsActive } from '../portfolio/transitions';
import * as api from '../api';

/**
 * The Work/About move, as it now stands.
 *
 * This file replaces the exhibition-sheet cover suite that was implemented and
 * then rejected: it covered the content column with a paper sheet for 520 ms and
 * deferred the content change to a timer. That candidate is gone from the source
 * — no `.ff-cover`, no `data-ff-cover`, no deferred commit — and these are the
 * regressions that keep the restored 260 ms content-only cut honest.
 */

vi.mock('../api', async importOriginal => ({
  ...await importOriginal<typeof import('../api')>(),
  authConfig: vi.fn(), me: vi.fn(), bootstrapAnonymous: vi.fn(), listProjects: vi.fn(),
}));

const listeners = new Map<string, Set<(event: MediaQueryListEvent) => void>>();
const preferences = new Map<string, boolean>();
const reducedQuery = '(prefers-reduced-motion: reduce)';

beforeEach(() => {
  window.history.replaceState(null, '', '/');
  localStorage.clear();
  vi.clearAllMocks();
  listeners.clear(); preferences.clear();
  delete (document as { startViewTransition?: unknown }).startViewTransition;
  vi.stubGlobal('matchMedia', (query: string) => {
    const handlers = listeners.get(query) ?? new Set<(event: MediaQueryListEvent) => void>();
    listeners.set(query, handlers);
    return {
      get matches() { return preferences.get(query) ?? false; }, media: query,
      addEventListener: (_: string, handler: (event: MediaQueryListEvent) => void) => handlers.add(handler),
      removeEventListener: (_: string, handler: (event: MediaQueryListEvent) => void) => handlers.delete(handler),
    };
  });
  vi.stubGlobal('Image', class { src = ''; decode = () => Promise.resolve(); });
  vi.stubGlobal('scrollTo', vi.fn());
  vi.mocked(api.authConfig).mockResolvedValue({ mode: 'anonymous' });
  vi.mocked(api.me).mockResolvedValue({ id: 'existing', email: 'existing@anonymous.invalid', theme: 'light', csrf_token: 'test', mode: 'anonymous', label: '本浏览器工作区' });
  vi.mocked(api.listProjects).mockResolvedValue([]);
});

afterEach(() => {
  cleanup(); vi.useRealTimers(); vi.unstubAllGlobals();
  delete (document as { startViewTransition?: unknown }).startViewTransition;
});

const flush = () => act(async () => {});

function native() {
  const captures: { kind: string; skipped: boolean; capture: () => Promise<void>; finish: () => Promise<void> }[] = [];
  (document as { startViewTransition?: unknown }).startViewTransition = vi.fn((update: () => void) => {
    let ready!: () => void, reject!: (reason: unknown) => void, finish!: () => void;
    const readyPromise = new Promise<void>((yes, no) => { ready = yes; reject = no; });
    const finished = new Promise<void>(yes => { finish = yes; });
    const capture = {
      kind: document.documentElement.dataset.ffTransition!, skipped: false,
      capture: () => act(async () => { update(); ready(); }),
      finish: () => act(async () => { finish(); }),
    };
    captures.push(capture);
    return { ready: readyPromise, finished, skipTransition: () => { capture.skipped = true; update(); reject(new Error('skipped')); finish(); } };
  });
  return { captures, last: () => captures[captures.length - 1] };
}

function hash(value: string) {
  act(() => { window.history.replaceState(null, '', `/${value}`); window.dispatchEvent(new HashChangeEvent('hashchange')); });
}

function follow(name: string) {
  const link = screen.getByRole('link', { name });
  let allowed = false;
  window.addEventListener('click', event => { allowed = !event.defaultPrevented; event.preventDefault(); }, { once: true });
  fireEvent(link, new MouseEvent('click', { bubbles: true, cancelable: true, button: 0 }));
  expect(allowed).toBe(true);
  hash(link.getAttribute('href')!);
}

/** A press on a link without the navigation a browser would raise after it. */
function pressOnly(name: string) {
  fireEvent(screen.getByRole('link', { name }), new MouseEvent('click', { bubbles: true, cancelable: true, button: 0 }));
}

const page = () => document.documentElement.dataset.ffPage;
const main = () => document.querySelector<HTMLElement>('.ff-main')!;
const homeVisible = () => !document.querySelector<HTMLElement>('.ff-home')!.hidden;
const aboutVisible = () => screen.queryByRole('heading', { name: /A field for/ }) !== null;

/**
 * Nothing of the rejected cover exists anywhere: no attribute on the root, no
 * element in the column, no sheet node. `data-ff-page` is the *restored* cut and
 * is deliberately not asserted here — it is present while a cut runs.
 */
function expectNoCover() {
  expect(document.documentElement.dataset.ffCover).toBeUndefined();
  expect(document.querySelector('.ff-cover')).toBeNull();
  expect(document.querySelector('.ff-cover-sheet')).toBeNull();
}

describe('Work/About content cut', () => {
  it('owns 260 ms for the page cut, and no cover constants at all', () => {
    expect(TRANSITION_MS.page).toBe(260);
    // The rejected candidate's numbers are gone from the module, not merely unused.
    expect(Object.keys(transitions).filter(name => /cover/i.test(name))).toEqual([]);
  });

  it('swaps the page in the same step that sets the attribute, and holds nothing back', () => {
    vi.useFakeTimers(); native();
    render(<Portfolio introEnabled={false} />);
    expect(homeVisible()).toBe(true);
    expect(aboutVisible()).toBe(false);
    follow('About');
    // One synchronous step: the attribute is set and the content has changed. There
    // is no sheet over the column and no instant at which the outgoing page is
    // still the page while a timer has not yet fired.
    expect(page()).toBe('in');
    expect(aboutVisible()).toBe(true);
    expect(homeVisible()).toBe(false);
    expectNoCover();
    act(() => vi.advanceTimersByTime(TRANSITION_MS.page - 1));
    expect(page()).toBe('in');
    act(() => vi.advanceTimersByTime(1));
    expect(page()).toBeUndefined();
    expect(transitionsActive()).toBe(false);
  });

  it('runs the same cut the other way from About to Work', () => {
    vi.useFakeTimers(); native();
    window.history.replaceState(null, '', '/#/about');
    render(<Portfolio introEnabled={false} />);
    expect(aboutVisible()).toBe(true);
    follow('Work 01');
    // The same immediate swap and the same 260 ms, entering from the other side.
    expect(page()).toBe('out');
    expect(homeVisible()).toBe(true);
    expect(aboutVisible()).toBe(false);
    expectNoCover();
    act(() => vi.advanceTimersByTime(TRANSITION_MS.page - 1));
    expect(page()).toBe('out');
    act(() => vi.advanceTimersByTime(1));
    expect(page()).toBeUndefined();
    expect(transitionsActive()).toBe(false);
  });

  it('moves content only: the chrome is outside the column, never captured, never wrapped', () => {
    vi.useFakeTimers(); native();
    const { container } = render(<Portfolio introEnabled={false} />);
    follow('About');
    // The header, the rail and the footer are siblings of the column, so the cut
    // cannot move them, cannot make them unclickable and cannot capture them.
    for (const chrome of ['.ff-header', '.ff-rail', '.ff-footer']) {
      const node = container.querySelector<HTMLElement>(chrome)!;
      expect(node).toBeInTheDocument();
      expect(main().contains(node)).toBe(false);
    }
    const about = screen.getByRole('link', { name: 'About' });
    expect(about).not.toBeDisabled();
    expect(about.closest('[inert]')).toBeNull();
    expect(container.querySelector('.ff-rail')!.closest('[inert]')).toBeNull();
    expect(container.querySelector('.ff-header button')!.closest('[inert]')).toBeNull();
    // Nothing is layered over the column: the cut is the attribute and the CSS
    // animation on the section that appeared, nothing else.
    expect(main().querySelectorAll('.ff-cover, .ff-cover-sheet')).toHaveLength(0);
    act(() => vi.advanceTimersByTime(TRANSITION_MS.page));
    expectNoCover();
  });

  it('drops the attribute and the pending move when a second navigation supersedes it', () => {
    vi.useFakeTimers(); native();
    render(<Portfolio introEnabled={false} />);
    follow('About');
    expect(page()).toBe('in');
    // Work is asked for while the cut is still running. About is already committed,
    // so this is an ordinary second route, and the newest one is the one that stands.
    follow('Work 01');
    expect(page()).toBe('out');
    expect(homeVisible()).toBe(true);
    expect(aboutVisible()).toBe(false);
    act(() => vi.advanceTimersByTime(TRANSITION_MS.page - 1));
    expect(page()).toBe('out');
    act(() => vi.advanceTimersByTime(1));
    // The superseded cut left nothing behind: one attribute, one release, no cover.
    expect(page()).toBeUndefined();
    expect(transitionsActive()).toBe(false);
    expectNoCover();
  });

  it('cancels a pending obsolete cut when the page already on screen is pressed', () => {
    vi.useFakeTimers(); native();
    render(<Portfolio introEnabled={false} />);
    follow('About');
    expect(page()).toBe('in');
    // About is the committed page now, so this press raises no address and
    // therefore no route. It is answered by dropping the attribute the cut still
    // holds, and the About that is on screen is left exactly where it is.
    pressOnly('About');
    expect(page()).toBeUndefined();
    act(() => vi.advanceTimersByTime(TRANSITION_MS.page));
    expect(page()).toBeUndefined();
    expect(aboutVisible()).toBe(true);
    expect(homeVisible()).toBe(false);
    expect(transitionsActive()).toBe(false);
    expectNoCover();
  });

  it('settles on the requested address through Back, Forward and a hurried pair', () => {
    vi.useFakeTimers(); native();
    render(<Portfolio introEnabled={false} />);
    // Forward asked for before the cut finished: the requested address is Work,
    // which is where we already are, so nothing is left behind.
    hash('#/about');
    hash('#/work');
    act(() => vi.advanceTimersByTime(TRANSITION_MS.page));
    expect(aboutVisible()).toBe(false);
    expect(homeVisible()).toBe(true);
    // Back again, given its full 260 ms this time.
    hash('#/about');
    act(() => vi.advanceTimersByTime(TRANSITION_MS.page));
    expect(aboutVisible()).toBe(true);
    expect(page()).toBeUndefined();
    // The detail-less pair, in the other direction.
    hash('#/work');
    act(() => vi.advanceTimersByTime(TRANSITION_MS.page));
    expect(homeVisible()).toBe(true);
    expect(aboutVisible()).toBe(false);
    // And the last of three hurried requests is the one that stands.
    hash('#/about'); hash('#/work'); hash('#/about');
    act(() => vi.advanceTimersByTime(TRANSITION_MS.page));
    expect(aboutVisible()).toBe(true);
    expect(page()).toBeUndefined();
    expect(window.location.hash).toBe('#/about');
  });

  it('releases the attribute on unmount, and leaves no timer behind', () => {
    vi.useFakeTimers(); native();
    const { unmount } = render(<Portfolio introEnabled={false} />);
    follow('About');
    expect(page()).toBe('in');
    unmount();
    expect(page()).toBeUndefined();
    act(() => vi.advanceTimersByTime(TRANSITION_MS.page));
    expect(page()).toBeUndefined();
    expect(transitionsActive()).toBe(false);
    expect(api.listProjects).not.toHaveBeenCalled();
  });

  it.each([
    ['no view transitions at all', () => { delete (document as { startViewTransition?: unknown }).startViewTransition; }],
    ['reduced motion requested', () => { preferences.set(reducedQuery, true); native(); }],
  ])('reaches the page at once with %s', async (_label, arrange) => {
    arrange();
    render(<Portfolio introEnabled={false} />);
    await flush();
    follow('About');
    // The same contract as before this move existed: an immediate, un-animated
    // commit, with no attribute and nothing layered over the column.
    expect(aboutVisible()).toBe(true);
    expect(page()).toBeUndefined();
    expectNoCover();
    expect(transitionsActive()).toBe(false);
    follow('Work 01');
    expect(homeVisible()).toBe(true);
    expect(page()).toBeUndefined();
    expectNoCover();
  });
});