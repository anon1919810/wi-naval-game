import { revealClock, revealGeometry, revealing } from './reveal-fixture';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Portfolio from '../portfolio/Portfolio';
import { PLAN_SHEETS } from '../portfolio/plans';
import { TRANSITION_MS, transitionsActive } from '../portfolio/transitions';
import * as api from '../api';

vi.mock('../api', async original => ({
  ...await original<typeof import('../api')>(),
  authConfig: vi.fn(), me: vi.fn(), bootstrapAnonymous: vi.fn(), listProjects: vi.fn(), setTheme: vi.fn(), logout: vi.fn(),
}));
vi.mock('../pages/Workbench', () => ({ Workbench: () => <main>Outgoing project sentinel</main> }));

const listeners = new Map<string, Set<(event: MediaQueryListEvent) => void>>();
const preferences = new Map<string, boolean>();
const reducedQuery = '(prefers-reduced-motion: reduce)';
const darkQuery = '(prefers-color-scheme: dark)';
const animations: { keyframes: unknown; options: KeyframeAnimationOptions }[] = [];

beforeEach(() => {
  window.history.replaceState(null, '', '/');
  localStorage.clear();
  revealGeometry(); revealClock();
  vi.clearAllMocks();
  listeners.clear(); preferences.clear(); animations.length = 0;
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
  Element.prototype.animate = vi.fn((keyframes, options) => {
    animations.push({ keyframes, options: options as KeyframeAnimationOptions });
    return { finished: Promise.resolve(), cancel: () => {} } as unknown as Animation;
  });
  vi.mocked(api.authConfig).mockResolvedValue({ mode: 'anonymous' });
  vi.mocked(api.me).mockResolvedValue({ id: 'existing', email: 'existing@anonymous.invalid', theme: 'light', csrf_token: 'test', mode: 'anonymous', label: '本浏览器工作区' });
  vi.mocked(api.listProjects).mockResolvedValue([]);
});
afterEach(() => {
  cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks();
  delete (Element.prototype as { animate?: unknown }).animate;
  delete (document as { startViewTransition?: unknown }).startViewTransition;
});

const flush = () => act(async () => {});
function hash(value: string) {
  act(() => {
    // replaceState avoids jsdom scheduling a second, duplicate hashchange.
    window.history.replaceState(null, '', `/${value}`);
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  });
}
function follow(name: string) {
  const link = screen.getByRole('link', { name });
  const click = new MouseEvent('click', { bubbles: true, cancelable: true, button: 0 });
  let allowed = false;
  // React's root handler runs before this window listener. Assert that it left
  // navigation available, then suppress jsdom's queued navigation because the
  // test below supplies the one deterministic hashchange instead.
  window.addEventListener('click', event => {
    allowed = !event.defaultPrevented;
    event.preventDefault();
  }, { once: true });
  fireEvent(link, click);
  // Do not silently simulate a navigation that the handler prevented.
  expect(allowed).toBe(true);
  hash(link.getAttribute('href')!);
}
function media(query: string, matches: boolean) {
  act(() => {
    preferences.set(query, matches);
    for (const listener of listeners.get(query) ?? []) listener({ matches } as MediaQueryListEvent);
  });
}
interface Capture {
  kind: string;
  skipped: boolean;
  capture: () => Promise<void>;
  finish: () => Promise<void>;
}
function native() {
  const captures: Capture[] = [];
  (document as { startViewTransition?: unknown }).startViewTransition = vi.fn((update: () => void) => {
    let ready!: () => void, reject!: (reason: unknown) => void, finish!: () => void;
    const readyPromise = new Promise<void>((yes, no) => { ready = yes; reject = no; });
    const finished = new Promise<void>(yes => { finish = yes; });
    const capture: Capture = {
      kind: document.documentElement.dataset.ffTransition!, skipped: false,
      capture: () => act(async () => { update(); ready(); }),
      finish: () => act(async () => { finish(); }),
    };
    captures.push(capture);
    return { ready: readyPromise, finished, skipTransition: () => {
      capture.skipped = true;
      // MDN: skipTransition still invokes the update callback.
      update(); reject(new Error('skipped')); finish();
    } };
  });
  return { captures, last: () => captures[captures.length - 1] };
}
const study = () => document.querySelector('.ff-layer-vessel .ff-vessel')!.getAttribute('data-study');
const transform = () => document.querySelector('.ff-layer-vessel')!.getAttribute('transform');

describe('desktop transitions', async () => {
  it('prefetches on hover/focus without mounting the app or calling its API', async () => {
    const vt = native(); render(<Portfolio introEnabled={false} />); await flush();
    const entry = screen.getByRole('link', { name: 'Open Plimsoll' });
    fireEvent.pointerEnter(entry); fireEvent.focus(entry); await flush();
    expect(vt.captures).toHaveLength(0);
    expect(document.querySelector('.ff-tool-shell')).toBeNull();
    expect(api.authConfig).not.toHaveBeenCalled(); expect(api.me).not.toHaveBeenCalled();
    expect(api.bootstrapAnonymous).not.toHaveBeenCalled(); expect(api.listProjects).not.toHaveBeenCalled();
  });

  it('uses the anchor navigation and retains the tool transition until it finishes', async () => {
    const vt = native(); render(<Portfolio introEnabled={false} />); await flush();
    follow('Open Plimsoll'); const entry = vt.last();
    expect(entry.kind).toBe('tool'); expect(api.authConfig).not.toHaveBeenCalled();
    await entry.capture();
    expect(document.documentElement.dataset.ffTransition).toBe('tool');
    expect(document.querySelector('.ff-workspace')).toBeInTheDocument();
    await screen.findByTitle('本浏览器工作区');
    const fades = animations.filter(call => call.options.pseudoElement !== '::view-transition-new(root)');
    expect(fades).toHaveLength(3);
    expect(fades.every(call => call.options.fill === 'both')).toBe(true);
    const arrival = fades.find(call => call.options.pseudoElement === '::view-transition-new(ff-frame)')!;
    expect(arrival.keyframes).toEqual({ opacity: [0, 1] }); expect(arrival.options.delay).toBe(140);
    expect(arrival.options.duration).toBe(240);
    await entry.finish();
    expect(document.documentElement.dataset.ffTransition).toBeUndefined(); expect(transitionsActive()).toBe(false);
    expect(api.authConfig).toHaveBeenCalledTimes(1);
  });

  it('returns with the reverse frame move, preserves reference/settings/pan/sample and focuses the CTA', async () => {
    const vt = native(); render(<Portfolio introEnabled={false} />); await flush();
    fireEvent.click(screen.getByRole('button', { name: PLAN_SHEETS[1].label })); await flush();
    const sheet = vt.last(); await sheet.capture(); await sheet.finish();
    expect(screen.queryByRole('button', { name: /Geometry/ })).toBeNull();
    const exhibit = screen.getByRole('group', { name: /Interactive top-view/ });
    fireEvent.keyDown(exhibit, { key: 'ArrowRight' }); const pan = transform();
    fireEvent.click(screen.getByRole('button', { name: 'Inspect Off' }));
    fireEvent.keyDown(exhibit, { key: 'ArrowRight' });
    const sample = document.querySelector('.ff-lens-view')!.getAttribute('viewBox');
    follow('Open Plimsoll'); await vt.last().capture(); await vt.last().finish();
    await screen.findByTitle('本浏览器工作区');
    follow('↖ Y’s Formfield'); const back = vt.last();
    expect(back.kind).toBe('tool-back'); await back.capture(); await back.finish();
    const arrival = animations.find(call => call.options.pseudoElement === '::view-transition-new(ff-scan)')!;
    expect(arrival.options.fill).toBe('both'); expect(arrival.options.delay).toBe(140);
    expect(screen.getByRole('button', { name: PLAN_SHEETS[1].label })).toHaveAttribute('aria-pressed', 'true');
    expect(Number(document.querySelector('.ff-layer-geometry > g')!.getAttribute('opacity'))).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: 'Inspect On' })).toHaveAttribute('aria-pressed', 'true');
    expect(transform()).toBe(pan); expect(document.querySelector('.ff-lens-view')!.getAttribute('viewBox')).toBe(sample);
    expect(screen.queryByRole('status', { name: 'Opening Y’s Formfield' })).toBeNull();
    expect(document.activeElement).toBe(screen.getByRole('link', { name: 'Open Plimsoll' }));
  });

  it('animates Work/About content for 500 ms while keeping persistent navigation focus', async () => {
    vi.useFakeTimers(); revealClock(); const vt = native(); render(<Portfolio introEnabled={false} />); await flush();
    const nav = screen.getByRole('navigation', { name: 'Main navigation' });
    const about = screen.getByRole('link', { name: 'About' }); about.focus();
    follow('About'); expect(revealing()).toMatch(/^circle\(/);
    // The content changes in the same synchronous step that sets the attribute:
    // there is no deferred commit and nothing covers the column while it settles.
    expect(screen.getByRole('heading', { name: /A field for/ })).toBeVisible(); expect(document.activeElement).toBe(about);
    await act(async () => { vi.advanceTimersByTime(TRANSITION_MS.page - 1); }); expect(revealing()).toMatch(/^circle\(/);
    await act(async () => { vi.advanceTimersByTime(1); }); expect(revealing()).toBeUndefined();
    follow('Work 01'); expect(revealing()).toMatch(/^circle\(/);
    expect(screen.getByRole('heading', { name: 'Plimsoll' })).toBeVisible(); expect(nav).toBeInTheDocument();
    // No sheet, no paper and no overlay exist anywhere on the public shell.
    expect(vt.captures).toHaveLength(0);
    expect(document.querySelector('.ff-cover')).toBeNull();
    expect(document.documentElement.dataset.ffCover).toBeUndefined();
  });

  it('protects a newer theme from a skipped callback and late cleanup', async () => {
    const vt = native(); render(<Portfolio introEnabled={false} />); await flush();
    fireEvent.click(screen.getByRole('button', { name: 'Switch to dark theme' })); const old = vt.last();
    follow('About'); expect(old.skipped).toBe(true); await old.capture(); await old.finish();
    expect(document.documentElement.dataset.theme).toBe('light');
    fireEvent.click(screen.getByRole('button', { name: 'Switch to dark theme' })); const current = vt.last();
    await old.finish(); expect(document.documentElement.dataset.ffTransition).toBe('theme');
    await current.capture();
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(animations.find(call => call.options.pseudoElement === '::view-transition-new(root)')!.options.duration).toBe(560);
    await current.finish(); expect(document.documentElement.dataset.ffTransition).toBeUndefined();
  });

  it.each(['theme', 'reduced'] as const)('clears a requested sheet interrupted before capture by %s', async interruption => {
    const vt = native(); render(<Portfolio introEnabled={false} />); await flush();
    fireEvent.click(screen.getByRole('button', { name: PLAN_SHEETS[2].label })); await flush();
    const sheet = vt.last(); expect(study()).toBe(PLAN_SHEETS[0].id);
    if (interruption === 'theme') fireEvent.click(screen.getByRole('button', { name: 'Switch to dark theme' }));
    else media(reducedQuery, true);
    expect(sheet.skipped).toBe(true); await sheet.capture(); await sheet.finish();
    expect(study()).toBe(PLAN_SHEETS[0].id);
    expect(screen.getByRole('button', { name: PLAN_SHEETS[0].label })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: PLAN_SHEETS[2].label })).toHaveAttribute('aria-pressed', 'false');
    if (interruption === 'theme') { await vt.last().capture(); await vt.last().finish(); }
    expect(document.querySelector('.ff-shell')).toHaveAttribute('data-switching', 'false');
  });

  it('ignores OS theme changes during a running sheet capture', async () => {
    localStorage.setItem('formfield-theme', 'system');
    const vt = native(); render(<Portfolio introEnabled={false} />); await flush();
    fireEvent.click(screen.getByRole('button', { name: PLAN_SHEETS[1].label })); await flush();
    const sheet = vt.last(); media(darkQuery, true); await sheet.capture(); await sheet.finish();
    expect(sheet.skipped).toBe(false); expect(study()).toBe(PLAN_SHEETS[1].id);
    expect(document.documentElement.dataset.theme).toBe('light');
  });

  it('cancels a pending tool entry when history returns to the already committed public route', async () => {
    const vt = native(); render(<Portfolio introEnabled={false} />); await flush();
    follow('Open Plimsoll'); const entry = vt.last(); hash('#/work');
    expect(entry.skipped).toBe(true); await entry.capture(); await entry.finish();
    expect(api.authConfig).not.toHaveBeenCalled(); expect(document.querySelector('.ff-tool-shell')).toBeNull();
    expect(document.documentElement.dataset.ffTransition).toBeUndefined();
  });

  it.each([false, true])('uses immediate navigation when reduced motion is %s and no native animation is needed', async reduced => {
    if (reduced) { preferences.set(reducedQuery, true); native(); }
    render(<Portfolio introEnabled={reduced} />); await flush();
    if (reduced) expect(screen.queryByRole('status', { name: 'Opening Y’s Formfield' })).toBeNull();
    follow('About'); follow('Work 01'); follow('Open Plimsoll');
    await screen.findByTitle('本浏览器工作区'); follow('↖ Y’s Formfield'); await flush();
    expect(document.documentElement.dataset.formfieldSurface).toBe('public');
    expect(revealing()).toBeUndefined(); expect(document.documentElement.dataset.ffTransition).toBeUndefined();
    expect(animations).toHaveLength(0);
  });

  it('keeps modified and middle clicks available to the browser', async () => {
    const vt = native(); render(<Portfolio introEnabled={false} />); await flush();
    const link = screen.getByRole('link', { name: 'Open Plimsoll' });
    for (const detail of [{ metaKey: true, button: 0 }, { ctrlKey: true, button: 0 }, { button: 1 }]) {
      const click = new MouseEvent('click', { bubbles: true, cancelable: true, ...detail });
      fireEvent(link, click); expect(click.defaultPrevented).toBe(false);
    }
    expect(vt.captures).toHaveLength(0); expect(api.authConfig).not.toHaveBeenCalled();
  });

  it('releases a running capture on unmount without committing stale content', async () => {
    const vt = native(); const { unmount } = render(<Portfolio introEnabled={false} />); await flush();
    fireEvent.click(screen.getByRole('button', { name: PLAN_SHEETS[1].label })); await flush();
    const sheet = vt.last(); unmount(); await sheet.capture(); await sheet.finish();
    expect(sheet.skipped).toBe(true); expect(transitionsActive()).toBe(false);
    expect(document.documentElement.dataset.ffTransition).toBeUndefined();
  });
});

describe('application isolation', async () => {
  it('does not bootstrap after a pending identity lookup returns 401 following exit', async () => {
    const vt = native(); window.history.replaceState(null, '', '/#/plimsoll');
    let reject!: (cause: unknown) => void;
    vi.mocked(api.me).mockReturnValue(new Promise((_, no) => { reject = no; }));
    render(<Portfolio />); await flush();
    expect(api.me).toHaveBeenCalledTimes(1);
    follow('↖ Y’s Formfield'); await vt.last().capture(); await vt.last().finish();
    await act(async () => { reject(new api.ApiError(401, 'unauthorized')); });
    expect(api.bootstrapAnonymous).not.toHaveBeenCalled(); expect(api.me).toHaveBeenCalledTimes(1);
  });

  it('keeps outgoing project content until tool-back capture rather than loading Library', async () => {
    const vt = native(); window.history.replaceState(null, '', '/#/projects/project-id');
    render(<Portfolio />); await screen.findByText('Outgoing project sentinel');
    follow('↖ Y’s Formfield');
    expect(screen.getByText('Outgoing project sentinel')).toBeVisible(); expect(api.listProjects).not.toHaveBeenCalled();
    await vt.last().capture(); await vt.last().finish();
    expect(screen.queryByText('Outgoing project sentinel')).toBeNull(); expect(api.listProjects).not.toHaveBeenCalled();
    expect(document.documentElement.dataset.formfieldSurface).toBe('public');
  });

  it('ignores a pending application theme save after return', async () => {
    const vt = native(); window.history.replaceState(null, '', '/#/plimsoll');
    let release!: () => void;
    vi.mocked(api.setTheme).mockReturnValue(new Promise(resolve => { release = () => resolve({ theme: 'dark' }); }));
    render(<Portfolio />); await screen.findByTitle('本浏览器工作区');
    fireEvent.click(screen.getByRole('button', { name: '切换到深色主题' }));
    follow('↖ Y’s Formfield'); await vt.last().capture(); await vt.last().finish();
    // Public preference remains light; a late save may not repaint it dark.
    await act(async () => release()); expect(document.documentElement.dataset.theme).toBe('light');
  });
});
