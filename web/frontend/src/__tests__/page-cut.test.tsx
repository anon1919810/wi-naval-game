import { MAIN, RAIL, revealClock, revealGeometry, revealing } from './reveal-fixture';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Portfolio from '../portfolio/Portfolio';
import * as transitions from '../portfolio/transitions';
import { TRANSITION_MS, transitionsActive } from '../portfolio/transitions';
import * as api from '../api';

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
  revealGeometry({ railWords: true }); revealClock();
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
  cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks();
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

function pressOnly(name: string) {
  fireEvent(screen.getByRole('link', { name }), new MouseEvent('click', { bubbles: true, cancelable: true, button: 0 }));
}

const page = revealing;
const main = () => document.querySelector<HTMLElement>('.ff-main')!;
/** The circle the reveal has actually written on `main`. */
const clipOf = (node: HTMLElement) => {
  const match = node.style.clipPath.match(/^circle\(([\d.]+)px at (-?[\d.]+)px (-?[\d.]+)px\)$/);
  if (!match) throw new Error(`no circle on ${node.style.clipPath}`);
  return { radius: Number(match[1]), x: Number(match[2]), y: Number(match[3]) };
};
const homeVisible = () => !document.querySelector<HTMLElement>('.ff-home')!.hidden;
const aboutVisible = () => screen.queryByRole('heading', { name: /A field for/ }) !== null;

function expectNoCover() {
  expect(document.documentElement.dataset.ffCover).toBeUndefined();
  expect(document.querySelector('.ff-cover')).toBeNull();
  expect(document.querySelector('.ff-cover-sheet')).toBeNull();
}

describe('Work/About circular reveal', async () => {
  it('owns 500 ms for the page reveal, and no cover constants at all', async () => {
    expect(TRANSITION_MS.page).toBe(500);
    expect(Object.keys(transitions).filter(name => /cover/i.test(name))).toEqual([]);
  });

  it('commits the destination synchronously under the outgoing copy', async () => {
    vi.useFakeTimers(); revealClock(); native();
    render(<Portfolio introEnabled={false} />);
    expect(homeVisible()).toBe(true);
    expect(aboutVisible()).toBe(false);
    follow('About');
    expect(page()).toMatch(/^circle\(/);
    expect(aboutVisible()).toBe(true);
    expect(homeVisible()).toBe(false);
    expectNoCover();
    expect(document.querySelectorAll('.ff-reveal-out')).toHaveLength(1);
    expect(main().style.zIndex).toBe('2');
    await act(async () => { vi.advanceTimersByTime(TRANSITION_MS.page - 1); });
    expect(page()).toMatch(/^circle\(/);
    await act(async () => { vi.advanceTimersByTime(1); });
    expect(page()).toBeUndefined();
    expect(transitionsActive()).toBe(false);
  });

  it('covers the whole width main spans, including the arc that reaches the rail', async () => {
    vi.useFakeTimers(); revealClock(); native();
    render(<Portfolio introEnabled={false} />);
    const field = main().querySelector('.ff-field--work')!;
    expect(field).not.toBeNull();
    // The drawing is a child of `main`, not of the Work section: it needs the
    // width main spans — rail included — so the arc can run out past the reading
    // column rather than being cut off at it.
    expect(field.parentElement).toBe(main());
    expect(main().querySelector('.ff-home')!.contains(field)).toBe(false);

    follow('About');
    // The circle opens at the About word, which sits in the rail — to the right
    // of main's own left edge, so the origin is written in region-local
    // coordinates and is positive.
    expect(clipOf(main()).x).toBeGreaterThan(0);
    // The reveal's own bounds are the shared region, never wider than the page.
    const copy = document.querySelector<HTMLElement>('.ff-reveal-out');
    expect(copy).not.toBeNull();
    const span = Number.parseFloat(copy!.style.left) + Number.parseFloat(copy!.style.width);
    expect(span).toBeLessThanOrEqual(MAIN.left + MAIN.width);

    // Partway through, the circle is genuinely crossing the rail column: the
    // opening word is there, and the drawing reaches further right still, which
    // is only true because `main` is no longer cut off at the reading column.
    await act(async () => { vi.advanceTimersByTime(TRANSITION_MS.page / 2); });
    const opened = clipOf(main());
    expect(opened.radius).toBeGreaterThan(0);
    // The origin is the rail word's own centre, read from the rail's own box.
    const railCentre = RAIL.left + RAIL.width / 2 - MAIN.left;
    expect(opened.x).toBeCloseTo(railCentre, 0);
    // The rim travels the same number the clip does, on every frame.
    const rim = document.querySelector('.ff-reveal-rim circle')!;
    expect(Number(rim.getAttribute('r'))).toBeCloseTo(opened.radius, 2);
    // Partway through it is still travelling across the page from the rail, and
    // by the end it has covered the far side — the distance that only exists
    // because main spans the whole width, rail included.
    expect(opened.radius).toBeGreaterThan(railCentre / 2);
    // The circle keeps opening and grows monotonically to the far side of the
    // page, a distance that only exists because main spans the rail as well.
    let last = opened.radius;
    for (let step = 0; step < 6; step += 1) {
      await act(async () => { vi.advanceTimersByTime(TRANSITION_MS.page / 12); });
      const next = clipOf(main()).radius;
      expect(next).toBeGreaterThanOrEqual(last);
      last = next;
    }
    // Well past the rail itself: the circle reaches the far side of the content
    // column, not just across the navigation.
    expect(last).toBeGreaterThan(MAIN.width - RAIL.width - RAIL.gap);
    await act(async () => { vi.advanceTimersByTime(TRANSITION_MS.page); });
    expect(page()).toBeUndefined();
  });

  it('runs the same reveal the other way from About to Work', async () => {
    vi.useFakeTimers(); revealClock(); native();
    window.history.replaceState(null, '', '/#/about');
    render(<Portfolio introEnabled={false} />);
    expect(aboutVisible()).toBe(true);
    follow('Work 01');
    expect(page()).toMatch(/^circle\(/);
    expect(homeVisible()).toBe(true);
    expect(aboutVisible()).toBe(false);
    expectNoCover();
    await act(async () => { vi.advanceTimersByTime(TRANSITION_MS.page - 1); });
    expect(page()).toMatch(/^circle\(/);
    await act(async () => { vi.advanceTimersByTime(1); });
    expect(page()).toBeUndefined();
    expect(transitionsActive()).toBe(false);
  });

  it('moves content only: the chrome is outside the column, never captured, never wrapped', async () => {
    vi.useFakeTimers(); revealClock(); native();
    const { container } = render(<Portfolio introEnabled={false} />);
    follow('About');
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
    expect(main().querySelectorAll('.ff-cover, .ff-cover-sheet')).toHaveLength(0);
    await act(async () => { vi.advanceTimersByTime(TRANSITION_MS.page); });
    expectNoCover();
  });

  it('removes the visual layers and the pending move when a second navigation supersedes it', async () => {
    vi.useFakeTimers(); revealClock(); native();
    render(<Portfolio introEnabled={false} />);
    follow('About');
    expect(page()).toMatch(/^circle\(/);
    follow('Work 01');
    expect(page()).toMatch(/^circle\(/);
    expect(homeVisible()).toBe(true);
    expect(aboutVisible()).toBe(false);
    await act(async () => { vi.advanceTimersByTime(TRANSITION_MS.page - 1); });
    expect(page()).toMatch(/^circle\(/);
    await act(async () => { vi.advanceTimersByTime(1); });
    expect(page()).toBeUndefined();
    expect(transitionsActive()).toBe(false);
    expectNoCover();
  });

  it('cancels a pending obsolete reveal when the page already on screen is pressed', async () => {
    vi.useFakeTimers(); revealClock(); native();
    render(<Portfolio introEnabled={false} />);
    follow('About');
    expect(page()).toMatch(/^circle\(/);
    pressOnly('About');
    expect(page()).toBeUndefined();
    await act(async () => { vi.advanceTimersByTime(TRANSITION_MS.page); });
    expect(page()).toBeUndefined();
    expect(aboutVisible()).toBe(true);
    expect(homeVisible()).toBe(false);
    expect(transitionsActive()).toBe(false);
    expectNoCover();
  });

  it('settles on the requested address through Back, Forward and a hurried pair', async () => {
    vi.useFakeTimers(); revealClock(); native();
    render(<Portfolio introEnabled={false} />);
    hash('#/about');
    hash('#/work');
    await act(async () => { vi.advanceTimersByTime(TRANSITION_MS.page); });
    expect(aboutVisible()).toBe(false);
    expect(homeVisible()).toBe(true);
    hash('#/about');
    await act(async () => { vi.advanceTimersByTime(TRANSITION_MS.page); });
    expect(aboutVisible()).toBe(true);
    expect(page()).toBeUndefined();
    hash('#/work');
    await act(async () => { vi.advanceTimersByTime(TRANSITION_MS.page); });
    expect(homeVisible()).toBe(true);
    expect(aboutVisible()).toBe(false);
    hash('#/about'); hash('#/work'); hash('#/about');
    await act(async () => { vi.advanceTimersByTime(TRANSITION_MS.page); });
    expect(aboutVisible()).toBe(true);
    expect(page()).toBeUndefined();
    expect(window.location.hash).toBe('#/about');
  });

  it('removes the visual layers on unmount, and leaves no timer behind', async () => {
    vi.useFakeTimers(); revealClock(); native();
    const { unmount } = render(<Portfolio introEnabled={false} />);
    follow('About');
    expect(page()).toMatch(/^circle\(/);
    unmount();
    expect(page()).toBeUndefined();
    await act(async () => { vi.advanceTimersByTime(TRANSITION_MS.page); });
    expect(page()).toBeUndefined();
    expect(transitionsActive()).toBe(false);
    expect(api.listProjects).not.toHaveBeenCalled();
  });

  it.each([
    ['no view transitions at all', async () => { delete (document as { startViewTransition?: unknown }).startViewTransition; }],
    ['reduced motion requested', async () => { preferences.set(reducedQuery, true); native(); }],
  ])('reaches the page at once with %s', async (_label, arrange) => {
    arrange();
    render(<Portfolio introEnabled={false} />);
    await flush();
    follow('About');
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