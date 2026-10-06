import { Profiler, StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Portfolio from '../portfolio/Portfolio';
import { diagonalClip, introFrame, INTRO_DURATION } from '../portfolio/motion';
import { classifyHash } from '../portfolio/routes';
import { PLAN_SHEETS, sheetTone, sheetViewBox } from '../portfolio/plans';
import { lensFrame, LENS_MAGNIFICATION, samplePoint } from '../portfolio/lens';
import { THEME_KEY } from '../portfolio/theme';
import { IMAGE_TIMEOUT } from '../portfolio/images';
import * as api from '../api';

vi.mock('../api', async importOriginal => ({
  ...await importOriginal<typeof import('../api')>(),
  authConfig: vi.fn(), me: vi.fn(), bootstrapAnonymous: vi.fn(), listProjects: vi.fn(),
}));

type MediaHandler = (event: MediaQueryListEvent) => void;
const mediaListeners = new Map<string, Set<MediaHandler>>();

function media(reduced = false, dark = false) {
  mediaListeners.clear();
  vi.stubGlobal('matchMedia', vi.fn((query: string) => {
    const handlers = mediaListeners.get(query) ?? new Set<MediaHandler>();
    mediaListeners.set(query, handlers);
    return {
      matches: query.includes('reduced-motion') ? reduced : dark,
      media: query,
      addEventListener: (_: string, handler: MediaHandler) => { handlers.add(handler); },
      removeEventListener: (_: string, handler: MediaHandler) => { handlers.delete(handler); },
    };
  }));
}

/** Flip a media query and notify its listeners, the way a browser does. */
function changeMedia(query: string, matches: boolean) {
  act(() => { for (const handler of mediaListeners.get(query) ?? []) handler({ matches } as MediaQueryListEvent); });
}

beforeEach(() => {
  window.history.replaceState(null, '', '/');
  localStorage.clear();
  vi.clearAllMocks();
  media();
  vi.stubGlobal('Image', class { src = ''; decode = () => Promise.resolve(); });
  vi.stubGlobal('scrollTo', vi.fn());
  vi.mocked(api.authConfig).mockResolvedValue({ mode: 'anonymous' });
  vi.mocked(api.me).mockResolvedValue({ id: 'existing', email: 'existing@anonymous.invalid', theme: 'light', csrf_token: 'test', mode: 'anonymous', label: '本浏览器工作区' });
  vi.mocked(api.listProjects).mockResolvedValue([]);
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); });

function follow(name: string) {
  const link = screen.getByRole('link', { name });
  fireEvent.click(link);
  // jsdom schedules anchor navigation; apply the observed href before notifying React.
  act(() => {
    window.location.hash = link.getAttribute('href')!;
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  });
}

describe('public portfolio boundary', () => {
  it('browses references, themes and About without creating or fetching a workspace', async () => {
    render(<Portfolio introEnabled={false} />);
    fireEvent.click(screen.getByRole('button', { name: 'Reference sheet 03' }));
    // A reference only settles once its bitmap has decoded.
    await act(async () => {});
    fireEvent.click(screen.getByRole('button', { name: 'Switch to dark theme' }));
    follow('About');
    expect(screen.getByRole('heading', { name: /A field for\s*useful ideas\./ })).toBeVisible();
    follow('Work 01');
    expect(screen.getByRole('button', { name: 'Reference sheet 03' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.queryByRole('status', { name: 'Opening Y’s Formfield' })).toBeNull();
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(localStorage.getItem(THEME_KEY)).toBe('dark');
    // Let effects/microtasks run before checking the API boundary.
    await act(async () => {});
    expect(api.authConfig).not.toHaveBeenCalled();
    expect(api.me).not.toHaveBeenCalled();
    expect(api.bootstrapAnonymous).not.toHaveBeenCalled();
    expect(api.listProjects).not.toHaveBeenCalled();
  });

  it('opens the real app explicitly, and preserves the exhibit on return', async () => {
    render(<Portfolio introEnabled={false} />);
    fireEvent.click(screen.getByRole('button', { name: 'Reference sheet 02' }));
    await act(async () => {});
    follow('OPEN PLIMSOLL');
    await waitFor(() => expect(api.authConfig).toHaveBeenCalledTimes(1));
    expect(await screen.findByTitle('本浏览器工作区')).toBeVisible();
    expect(document.documentElement.dataset.formfieldSurface).toBe('app');
    follow('↖ Y’s Formfield');
    expect(await screen.findByRole('heading', { name: 'Plimsoll' })).toBeVisible();
    expect(screen.getByRole('button', { name: 'Reference sheet 02' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.queryByRole('status', { name: 'Opening Y’s Formfield' })).toBeNull();
    expect(api.bootstrapAnonymous).not.toHaveBeenCalled();
    expect(document.documentElement.lang).toBe('en');
    expect(document.documentElement.dataset.formfieldSurface).toBe('public');
  });

  it('supports keyboard exploration, reset and geometry visibility', () => {
    const { container } = render(<Portfolio introEnabled={false} />);
    const exhibit = screen.getByRole('group', { name: /Interactive top-view/ });
    const vessel = () => container.querySelector('.ff-layer-vessel')!;
    const plate = () => container.querySelector('.ff-layer-geometry')!;
    const resting = vessel().getAttribute('transform');
    const restingPlate = plate().getAttribute('transform');
    fireEvent.keyDown(exhibit, { key: 'ArrowRight' });
    // The construction plate floats at GEOMETRY_PARALLAX of the vessel's pan.
    expect(vessel().getAttribute('transform')).toBe('translate(815 350) rotate(-12) scale(1) translate(-800 -350)');
    expect(plate().getAttribute('transform')).toBe('translate(806.75 350) rotate(-12) scale(1) translate(-800 -350)');
    // The deck mask tracks the vessel's actual position in plate coordinates.
    expect(container.querySelector('.ff-mask-track')!.getAttribute('transform')).toBe('translate(8.07 1.72)');
    fireEvent.keyDown(exhibit, { key: 'Home' });
    expect(vessel().getAttribute('transform')).toBe(resting);
    expect(plate().getAttribute('transform')).toBe(restingPlate);
    expect(screen.queryByRole('button', { name: /Geometry/ })).toBeNull();
    expect(Number(plate().firstElementChild!.getAttribute('opacity'))).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: 'Inspect Off' }));
    expect(screen.getByRole('button', { name: 'Inspect On' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('keeps the drawing controls inside the exhibit and the construction plate always visible', async () => {
    const { container } = render(<Portfolio introEnabled={false} />);
    await act(async () => {});
    const exhibit = screen.getByRole('group', { name: /Interactive top-view/ });
    for (const name of ['Inspect Off', 'Reset view', ...PLAN_SHEETS.map(sheet => sheet.label)]) {
      expect(exhibit).toContainElement(screen.getByRole('button', { name }));
    }
    expect(container.querySelector('.ff-work-controls')).toBeNull();
    expect(container.querySelector('.ff-exhibit-tools')).toBeNull();
    expect(screen.queryByRole('button', { name: /Geometry/ })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: PLAN_SHEETS[1].label }));
    await act(async () => {});
    fireEvent.click(screen.getByRole('button', { name: 'Switch to dark theme' }));
    expect(Number(container.querySelector('.ff-layer-geometry > g')!.getAttribute('opacity'))).toBeGreaterThan(0);
  });

  it('isolates control keys and pointer capture from drawing exploration', () => {
    const { container } = render(<Portfolio introEnabled={false} />);
    const exhibit = screen.getByRole('group', { name: /Interactive top-view/ });
    vi.spyOn(exhibit, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 0, 800, 350));
    const capture = vi.fn();
    Object.defineProperty(exhibit, 'setPointerCapture', { value: capture, configurable: true });
    const transform = () => container.querySelector('.ff-layer-vessel')!.getAttribute('transform');
    const pointer = (target: Element, type: string, pointerType = 'mouse') => {
      const event = new Event(type, { bubbles: true });
      Object.assign(event, { pointerType, pointerId: 7, buttons: 1, clientX: 30, clientY: 20 });
      fireEvent(target, event);
    };
    fireEvent.keyDown(exhibit, { key: 'ArrowRight' });
    const kept = transform();
    const inspect = screen.getByRole('button', { name: 'Inspect Off' });
    for (const key of ['ArrowRight', 'Home', 'Escape', 'Enter', ' ']) fireEvent.keyDown(inspect, { key });
    pointer(inspect.querySelector('svg')!, 'pointerdown', 'touch');
    pointer(inspect, 'pointermove');
    expect(capture).not.toHaveBeenCalled();
    expect(transform()).toBe(kept);
    fireEvent.click(inspect);
    const lens = container.querySelector<HTMLElement>('.ff-lens')!;
    pointer(exhibit, 'pointerover');
    expect(lens.hidden).toBe(false);
    pointer(screen.getByRole('button', { name: 'Reset view' }), 'pointermove');
    expect(lens.hidden).toBe(true);
    expect(transform()).toBe(kept);
    const sample = container.querySelector('.ff-lens-view')!.getAttribute('viewBox');
    for (const key of ['ArrowLeft', 'Home', 'Escape']) fireEvent.keyDown(screen.getByRole('button', { name: 'Inspect On' }), { key });
    expect(container.querySelector('.ff-lens-view')).toHaveAttribute('viewBox', sample);
    expect(screen.getByRole('button', { name: 'Inspect On' })).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(screen.getByRole('button', { name: 'Reset view' }));
    expect(transform()).not.toBe(kept);
    fireEvent.keyDown(exhibit, { key: 'Tab' });
    expect(lens.hidden).toBe(true);
  });

  it('shows the blueprint cursor inside the exhibit for mouse pointers only', () => {
    const { container } = render(<Portfolio introEnabled={false} />);
    const exhibit = screen.getByRole('group', { name: /Interactive top-view/ });
    const cursor = () => container.querySelector<HTMLDivElement>('.ff-cursor')!;
    expect(cursor().hidden).toBe(true);
    const over = new Event('pointerover', { bubbles: true });
    Object.assign(over, { pointerType: 'mouse', clientX: 20, clientY: 20 });
    fireEvent(exhibit, over);
    expect(cursor().hidden).toBe(false);
    const out = new Event('pointerout', { bubbles: true });
    Object.assign(out, { pointerType: 'mouse' });
    fireEvent(exhibit, out);
    expect(cursor().hidden).toBe(true);
  });

  it('resolves the system preference locally and restores a saved theme', () => {
    media(false, true);
    localStorage.setItem(THEME_KEY, 'system');
    render(<Portfolio introEnabled={false} />);
    expect(screen.getByRole('button', { name: 'Switch to light theme' })).toBeInTheDocument();
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(api.authConfig).not.toHaveBeenCalled();
  });

  it('offers a compact System entry that follows the OS and yields to the primary toggle', () => {
    render(<Portfolio introEnabled={false} />);
    const system = screen.getByRole('button', { name: 'SYSTEM' });
    fireEvent.click(system);
    expect(system).toHaveAttribute('title', 'Follow system theme');
    expect(system).toHaveAttribute('aria-pressed', 'true');
    expect(localStorage.getItem(THEME_KEY)).toBe('system');
    // Following the OS means following it live, with no reload and no workspace.
    changeMedia('(prefers-color-scheme: dark)', true);
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(screen.getByRole('button', { name: 'Switch to light theme' })).toBeInTheDocument();
    changeMedia('(prefers-color-scheme: dark)', false);
    expect(document.documentElement.dataset.theme).toBe('light');
    // The explicit toggle leaves system mode behind and persists the choice.
    fireEvent.click(screen.getByRole('button', { name: 'Switch to dark theme' }));
    expect(system).toHaveAttribute('aria-pressed', 'false');
    expect(localStorage.getItem(THEME_KEY)).toBe('dark');
    expect(document.documentElement.dataset.theme).toBe('dark');
    // System re-enters on demand; pressing it while following pins what the
    // system resolves to right now, not the opposite of it.
    fireEvent.click(system);
    expect(system).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(system);
    expect(system).toHaveAttribute('aria-pressed', 'false');
    expect(localStorage.getItem(THEME_KEY)).toBe('light');
    changeMedia('(prefers-color-scheme: dark)', true);
    fireEvent.click(system);
    expect(system).toHaveAttribute('aria-pressed', 'true');
    expect(document.documentElement.dataset.theme).toBe('dark');
    fireEvent.click(system);
    expect(system).toHaveAttribute('aria-pressed', 'false');
    expect(localStorage.getItem(THEME_KEY)).toBe('dark');
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(api.authConfig).not.toHaveBeenCalled();
    expect(api.listProjects).not.toHaveBeenCalled();
  });

  it('does not collapse the splash into a hidden exhibit on a direct About link', () => {
    window.history.replaceState(null, '', '/#/about');
    render(<Portfolio />);
    expect(screen.getByRole('heading', { name: /A field for\s*useful ideas\./ })).toBeVisible();
    expect(screen.queryByRole('status', { name: 'Opening Y’s Formfield' })).toBeNull();
  });
});

function controlledImage() {
  let resolve!: () => void, reject!: (error: Error) => void;
  const pending = new Promise<void>((yes, no) => { resolve = yes; reject = no; });
  const decode = vi.fn(() => pending);
  vi.stubGlobal('Image', class { src = ''; decode = decode; });
  return { resolve, reject, decode };
}
/**
 * One decode gate per href, so a test can hold a specific reference open while
 * others resolve, which is what makes "the old drawing stays until the target
 * decodes" observable rather than instantaneous.
 */
function deferredImages() {
  const pending = new Map<string, { resolve: () => void; reject: (error: Error) => void }>();
  vi.stubGlobal('Image', class {
    private url = '';
    decode = () => new Promise<void>((resolve, reject) => {
      const gate = pending.get(this.url)!;
      gate.resolve = resolve; gate.reject = reject;
    });
    set src(value: string) { this.url = value; if (!pending.has(value)) pending.set(value, { resolve: () => {}, reject: () => {} }); }
    get src() { return this.url; }
  });
  return {
    async release(href: string) { await act(async () => { pending.get(href)!.resolve(); }); },
    async fail(href: string) { await act(async () => { pending.get(href)!.reject(new Error('decode failed')); }); },
  };
}
function fakeFrames() {
  vi.useFakeTimers();
  vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => window.setTimeout(() => cb(performance.now()), 16));
  vi.stubGlobal('cancelAnimationFrame', (id: number) => window.clearTimeout(id));
}

describe('opening lifecycle', () => {
  it('bypasses both waiting and motion for reduced motion, including replay', () => {
    media(true); controlledImage();
    const { unmount } = render(<StrictMode><Portfolio /></StrictMode>);
    expect(screen.queryByRole('status')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'REPLAY INTRO' }));
    expect(screen.queryByRole('status')).toBeNull();
    expect(document.body.style.overflow).not.toBe('hidden');
    unmount();
  });

  it('waits for decoding before the full intro and does not rerender each animation frame', async () => {
    fakeFrames();
    const image = controlledImage();
    const commits = vi.fn();
    document.body.style.overflow = 'auto';
    render(<StrictMode><Profiler id="portfolio" onRender={commits}><Portfolio /></Profiler></StrictMode>);
    expect(screen.getByRole('status', { name: 'Loading reference' })).toBeVisible();
    expect(document.body.style.overflow).toBe('hidden');
    act(() => { vi.advanceTimersByTime(3000); });
    expect(screen.queryByRole('status', { name: 'Opening Y’s Formfield' })).toBeNull();
    expect(image.decode).toHaveBeenCalledTimes(1);
    await act(async () => { image.resolve(); });
    expect(screen.getByRole('status', { name: 'Opening Y’s Formfield' })).toHaveAttribute('data-phase', 'black');
    const before = commits.mock.calls.length;
    act(() => { vi.advanceTimersByTime(1000); });
    expect(commits.mock.calls.length).toBe(before);
    expect(screen.getByRole('status', { name: 'Opening Y’s Formfield' })).toHaveAttribute('data-phase', 'hold');
    await act(async () => { vi.advanceTimersByTime(1532); });
    expect(screen.queryByRole('status')).toBeNull();
    expect(document.body.style.overflow).toBe('auto');
    follow('About'); follow('Work 01');
    expect(screen.queryByRole('status')).toBeNull();
    expect(api.authConfig).not.toHaveBeenCalled();
    document.body.style.overflow = '';
  });

  it.each(['reject', 'timeout'] as const)('releases the page on image %s without scanning empty artwork', async mode => {
    fakeFrames(); const image = controlledImage();
    render(<Portfolio />);
    await act(async () => { if (mode === 'reject') image.reject(new Error('network')); else vi.advanceTimersByTime(IMAGE_TIMEOUT + 1); });
    expect(screen.queryByRole('status')).toBeNull();
    expect(screen.getByRole('alert')).toHaveTextContent('could not be loaded');
    expect(document.body.style.overflow).not.toBe('hidden');
  });

  it('ignores a stale decode after leaving home and restores scroll on unmount', async () => {
    const image = controlledImage();
    const { unmount } = render(<Portfolio />);
    follow('About');
    await act(async () => { image.resolve(); });
    expect(screen.queryByRole('status')).toBeNull();
    expect(document.body.style.overflow).not.toBe('hidden');
    fireEvent.click(screen.getByRole('button', { name: 'REPLAY INTRO' }));
    unmount();
    expect(document.body.style.overflow).not.toBe('hidden');
  });

  it('allows Escape to skip waiting without a later decode restarting the intro', async () => {
    const image = controlledImage(); render(<Portfolio />);
    fireEvent.keyDown(window, { key: 'Escape' });
    await act(async () => { image.resolve(); });
    expect(screen.queryByRole('status')).toBeNull();
    expect(document.body.style.overflow).not.toBe('hidden');
  });

  it('coalesces pointer movement without React commits and resets on keyboard Home', async () => {
    fakeFrames(); const commits = vi.fn();
    const { container } = render(<Profiler id="portfolio" onRender={commits}><Portfolio introEnabled={false} /></Profiler>);
    await act(async () => {});
    const exhibit = screen.getByRole('group', { name: /Interactive top-view/ });
    vi.spyOn(exhibit, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 0, 800, 400));
    const art = container.querySelector('.ff-layer-vessel')!;
    const plate = container.querySelector('.ff-layer-geometry')!;
    const initial = art.getAttribute('transform');
    const initialPlate = plate.getAttribute('transform');
    const before = commits.mock.calls.length;
    for (let i = 0; i < 20; i++) {
      const event = new Event('pointermove', { bubbles: true });
      Object.assign(event, { pointerType: 'mouse', clientX: 700, clientY: 300 });
      fireEvent(exhibit, event);
    }
    expect(art.getAttribute('transform')).toBe(initial);
    act(() => { vi.advanceTimersByTime(16); });
    expect(art.getAttribute('transform')).not.toBe(initial);
    expect(plate.getAttribute('transform')).not.toBe(initialPlate);
    expect(plate.getAttribute('transform')).not.toBe(art.getAttribute('transform'));
    expect(commits.mock.calls.length).toBe(before);
    fireEvent.keyDown(exhibit, { key: 'Home' });
    expect(art.getAttribute('transform')).toBe(initial);
  });

  it('updates public chrome colors and restores previous metadata on exit', async () => {
    const meta = document.createElement('meta'); meta.name = 'theme-color'; meta.content = '#abcdef'; document.head.append(meta);
    document.documentElement.style.colorScheme = 'normal';
    const { unmount } = render(<Portfolio introEnabled={false} />);
    fireEvent.click(screen.getByRole('button', { name: 'Switch to dark theme' }));
    expect(meta.content).toBe('#101110');
    expect(document.documentElement.style.colorScheme).toBe('dark');
    follow('OPEN PLIMSOLL');
    expect(meta.content).toBe('#abcdef');
    expect(document.documentElement.style.colorScheme).toBe('normal');
    // Clicking an anchor queues a navigation in jsdom. Let it land inside this
    // test, so the next one cannot inherit the application route.
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });
    unmount(); meta.remove(); document.documentElement.style.colorScheme = '';
  });
});
describe('routing and visual contracts', () => {
  it.each(['#/plimsoll', '#/projects', '#/projects/p1', '#/runs/r1', '#/reports/r1'])('preserves the existing app bookmark %s', hash => {
    expect(classifyHash(hash)).toEqual({ kind: 'app' });
  });

  it('treats the root and unknown hashes as public work', () => {
    expect(classifyHash('')).toEqual({ kind: 'public', view: 'home' });
    expect(classifyHash('#/unknown')).toEqual({ kind: 'public', view: 'home' });
  });

  it('keeps the agreed 2.5-second choreography and final slight diagonal', () => {
    expect(INTRO_DURATION).toBe(2500);
    expect(introFrame(0)).toMatchObject({ phase: 'black', reveal: 0, reverse: 0 });
    expect(introFrame(500)).toMatchObject({ phase: 'reveal', reveal: .5 });
    expect(introFrame(1000)).toMatchObject({ phase: 'hold', reveal: 1, reverse: 0 });
    expect(introFrame(1450)).toMatchObject({ phase: 'reverse', reverse: .5 });
    expect(introFrame(2000).phase).toBe('settle');
    expect(introFrame(2500)).toMatchObject({ phase: 'done', angle: -12, scale: 1, settle: 1 });
  });

  it('reveals from the upper-left and reverses from the lower-right with sharp cuts', () => {
    expect(diagonalClip(.25)).toBe('polygon(0% 0%, 50% 0%, 0% 50%)');
    expect(diagonalClip(.25, true)).toBe('polygon(50% 100%, 100% 50%, 100% 100%)');
    expect(diagonalClip(1)).toContain('100% 100%');
    expect(diagonalClip(1, true)).toContain('0% 0%');
  });

  it('retains the lower plan band metadata of every archived reference sheet', () => {
    for (const sheet of PLAN_SHEETS) {
      expect(sheet.crop.y).toBeGreaterThan(sheet.sourceHeight / 2);
      expect(sheet.crop.width).toBe(sheet.sourceWidth);
      expect(sheet.crop.y + sheet.crop.height).toBeLessThanOrEqual(sheet.sourceHeight);
      expect(sheet.crop.height / sheet.crop.width).toBeLessThan(.2);
    }
  });

  it('embeds each original reference sheet cropped to its metadata, without geometric redraw', async () => {
    const { container } = render(<Portfolio introEnabled={false} />);
    const seen = new Set<string>();
    for (const sheet of PLAN_SHEETS) {
      fireEvent.click(screen.getByRole('button', { name: sheet.label }));
      // Selection is decode-gated: the swap happens on the microtask after the
      // press, so the artwork is settled before it is inspected.
      await act(async () => {});
      const drawing = container.querySelector('.ff-vessel')!;
      expect(drawing).toHaveAttribute('data-study', sheet.id);
      // The nested crop window is the source sheet's own coordinates.
      const viewport = drawing.querySelector('.ff-vessel-sheet')!;
      expect(viewport).toHaveAttribute('viewBox', sheetViewBox(sheet));
      expect(viewport).toHaveAttribute('preserveAspectRatio', 'xMidYMid meet');
      // The full original bitmap is placed at its intrinsic size, never traced.
      const image = drawing.querySelector('image')!;
      expect(image).toHaveAttribute('href', sheet.href);
      expect(image).toHaveAttribute('width', String(sheet.sourceWidth));
      expect(image).toHaveAttribute('height', String(sheet.sourceHeight));
      expect(image.getAttribute('clip-path')).toMatch(/^url\(#.+-crop\)$/);
      const clip = drawing.querySelector('clipPath rect')!;
      expect(clip.getAttribute('x')).toBe(String(sheet.crop.x));
      expect(clip.getAttribute('y')).toBe(String(sheet.crop.y));
      expect(clip.getAttribute('width')).toBe(String(sheet.crop.width));
      expect(clip.getAttribute('height')).toBe(String(sheet.crop.height));
      expect(drawing.querySelector('path')).toBeNull();
      expect(container.querySelector('img')).toBeNull();
      seen.add(image.getAttribute('href')!);
    }
    expect(seen.size).toBe(PLAN_SHEETS.length);
    for (const sheet of PLAN_SHEETS) expect(seen.has(sheet.href)).toBe(true);
  });

  it('marks the pressed reference immediately while the old drawing stays on the exhibit', async () => {
    const gate = deferredImages();
    const { container } = render(<Portfolio introEnabled={false} />);
    await act(async () => {});
    const study = () => container.querySelector('.ff-layer-vessel .ff-vessel')!.getAttribute('data-study');
    expect(study()).toBe(PLAN_SHEETS[0].id);

    const target = PLAN_SHEETS[1];
    fireEvent.click(screen.getByRole('button', { name: target.label }));
    // The button answers at once; the artwork has not decoded, so it cannot move.
    expect(screen.getByRole('button', { name: target.label })).toHaveAttribute('aria-pressed', 'true');
    expect(study()).toBe(PLAN_SHEETS[0].id);

    await gate.release(target.href);
    expect(study()).toBe(target.id);
    // The mark settles onto the sheet that is actually displayed.
    expect(screen.getByRole('button', { name: target.label })).toHaveAttribute('aria-pressed', 'true');
    expect(api.listProjects).not.toHaveBeenCalled();
  });

  it('lets the newest press win and never runs an abandoned selection', async () => {
    const gate = deferredImages();
    const { container } = render(<Portfolio introEnabled={false} />);
    await act(async () => {});
    const study = () => container.querySelector('.ff-layer-vessel .ff-vessel')!.getAttribute('data-study');
    const [first, second] = [PLAN_SHEETS[1], PLAN_SHEETS[2]];
    fireEvent.click(screen.getByRole('button', { name: first.label }));
    fireEvent.click(screen.getByRole('button', { name: second.label }));
    // The first request was retired by the second press, so its late decode is
    // never allowed to commit: only the newest press decides what is shown.
    await gate.release(first.href);
    expect(study()).toBe(PLAN_SHEETS[0].id);
    await gate.release(second.href);
    expect(study()).toBe(second.id);
    expect(screen.getByRole('button', { name: first.label })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('button', { name: second.label })).toHaveAttribute('aria-pressed', 'true');
  });

  it('keeps the current drawing and offers a retry when a new reference fails', async () => {
    const gate = deferredImages();
    const { container } = render(<Portfolio introEnabled={false} />);
    await act(async () => {});
    const study = () => container.querySelector('.ff-layer-vessel .ff-vessel')!.getAttribute('data-study');
    const target = PLAN_SHEETS[2];
    fireEvent.click(screen.getByRole('button', { name: target.label }));
    await gate.fail(target.href);
    // A failed switch is never a blank exhibit: the old drawing is untouched
    // and the alert names both the failure and the way out.
    expect(study()).toBe(PLAN_SHEETS[0].id);
    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent('could not be loaded');
    expect(alert).toHaveTextContent(`${PLAN_SHEETS[0].shortLabel} stays on the exhibit`);
    expect(screen.getByRole('button', { name: 'Reference sheet 03' })).toHaveAttribute('aria-pressed', 'false');
    // Retry re-requests the same sheet and succeeds.
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: /RETRY/ })); });
    await gate.release(target.href);
    expect(study()).toBe(target.id);
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('cancels a pending request when the displayed reference is pressed again', async () => {
    const gate = deferredImages();
    const { container } = render(<Portfolio introEnabled={false} />);
    await act(async () => {});
    const study = () => container.querySelector('.ff-layer-vessel .ff-vessel')!.getAttribute('data-study');
    const shown = screen.getByRole('button', { name: PLAN_SHEETS[0].label });
    fireEvent.click(screen.getByRole('button', { name: PLAN_SHEETS[1].label }));
    expect(shown).toHaveAttribute('aria-pressed', 'false');
    // Pressing the sheet that is already on the exhibit withdraws the request
    // rather than doing nothing, so a late decode cannot still swap it in.
    fireEvent.click(shown);
    expect(shown).toHaveAttribute('aria-pressed', 'true');
    await gate.release(PLAN_SHEETS[1].href);
    expect(study()).toBe(PLAN_SHEETS[0].id);
    expect(screen.getByRole('button', { name: PLAN_SHEETS[1].label })).toHaveAttribute('aria-pressed', 'false');
  });

  it('clears its own transition attribute when a pending switch is cancelled', async () => {
    const gates = new Map<string, () => void>();
    vi.stubGlobal('Image', class {
      private url = '';
      set src(value: string) { this.url = value; if (!gates.has(value)) gates.set(value, () => {}); }
      get src() { return this.url; }
      decode = () => new Promise<void>(resolve => { gates.set(this.url, resolve); });
    });
    const skipped = vi.fn();
    let settle!: () => void;
    const finished = new Promise<void>(resolve => { settle = resolve; });
    const started = vi.fn(() => ({ ready: new Promise<void>(() => {}), finished, skipTransition: skipped }));
    const surface = document as { startViewTransition?: unknown };
    surface.startViewTransition = started;
    try {
      const { unmount } = render(<Portfolio introEnabled={false} />);
      await act(async () => {});
      fireEvent.click(screen.getByRole('button', { name: PLAN_SHEETS[1].label }));
      await act(async () => { gates.get(PLAN_SHEETS[1].href)!(); });
      expect(started).toHaveBeenCalledTimes(1);
      expect(document.documentElement.dataset.ffTransition).toBe('sheet');
      // Unmounting cancels the snapshot and takes its attribute with it, even
      // though the browser still runs the update callback and resolves after.
      unmount();
      expect(skipped).toHaveBeenCalledTimes(1);
      expect(document.documentElement.dataset.ffTransition).toBeUndefined();
      await act(async () => { settle(); });
      expect(document.documentElement.dataset.ffTransition).toBeUndefined();
    } finally {
      delete surface.startViewTransition;
    }
  });

  it('drops a pending reference request when the visitor leaves the exhibit', async () => {
    const gate = deferredImages();
    const { container } = render(<Portfolio introEnabled={false} />);
    await act(async () => {});
    const study = () => container.querySelector('.ff-layer-vessel .ff-vessel')!.getAttribute('data-study');
    fireEvent.click(screen.getByRole('button', { name: 'Reference sheet 02' }));
    follow('About');
    await gate.release(PLAN_SHEETS[1].href);
    follow('Work 01');
    // Coming back shows the sheet the exhibit settled on, never the late one.
    expect(study()).toBe(PLAN_SHEETS[0].id);
    expect(screen.getByRole('button', { name: 'Reference sheet 02' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('themes the scan with tonal cleanup only, never convolution or edge detection', () => {
    const { container } = render(<Portfolio introEnabled={false} />);
    const drawing = container.querySelector('.ff-vessel')!;
    const filter = drawing.getAttribute('filter')!;
    expect(filter).toMatch(/^url\(#.+\)$/);
    const target = container.querySelector(`${filter.slice(4, -1)}`)!;
    const stages = [...target.children].map(node => node.tagName.toLowerCase());
    // grayscale -> alpha, mild cleanup, alpha bound to the source, flood ink.
    expect(stages).toEqual(['fecolormatrix', 'fecomponenttransfer', 'fecomposite', 'feflood', 'fecomposite']);
    for (const forbidden of ['feConvolveMatrix', 'feGaussianBlur', 'feMorphology', 'feEdgeDetect', 'feTile', 'feDisplacementMap']) {
      expect(target.querySelector(forbidden)).toBeNull();
    }
    const curve = target.querySelectorAll('feComponentTransfer feFuncA');
    // One function per channel: a second feFuncA would replace it, not follow it.
    expect(curve).toHaveLength(1);
    expect(curve[0]).toHaveAttribute('type', 'gamma');
    // Sheet 01 keeps the values it shipped with: gamma 1, 1.2/-0.05 in light.
    expect(Number(curve[0].getAttribute('exponent'))).toBe(1);
    expect(Number(curve[0].getAttribute('amplitude'))).toBeCloseTo(1.2);
    expect(Number(curve[0].getAttribute('offset'))).toBeCloseTo(-0.05);
    fireEvent.click(screen.getByRole('button', { name: 'Switch to dark theme' }));
    const darkDrawing = container.querySelector('.ff-vessel')!;
    const darkTarget = container.querySelector(`${darkDrawing.getAttribute('filter')!.slice(4, -1)}`)!;
    const darkCurve = darkTarget.querySelectorAll('feComponentTransfer feFuncA');
    expect(darkCurve).toHaveLength(1);
    expect(Number(darkCurve[0].getAttribute('exponent'))).toBe(1);
    expect(Number(darkCurve[0].getAttribute('amplitude'))).toBeCloseTo(1.08);
    expect(Number(darkCurve[0].getAttribute('offset'))).toBeCloseTo(-0.035);
    expect(container.querySelectorAll('image').length).toBeGreaterThan(0);
  });

  it('shares one tonal profile per sheet between the exhibit and the lens', async () => {
    for (const sheet of PLAN_SHEETS) {
      for (const theme of ['light', 'dark'] as const) {
        const profile = sheetTone(sheet, theme === 'dark');
        // Monotone, non-destructive controls: no geometry, no new detail.
        expect(profile.gamma).toBeGreaterThan(0);
        expect(profile.slope).toBeGreaterThan(0);
        expect(profile.opacity).toBeGreaterThan(0);
        expect(profile.opacity).toBeLessThanOrEqual(1);
      }
    }
    // Sheet 01 is the reference appearance and must not move.
    expect(sheetTone(PLAN_SHEETS[0], false)).toMatchObject({ slope: 1.2, intercept: -0.05, gamma: 1 });
    expect(sheetTone(PLAN_SHEETS[0], true)).toMatchObject({ slope: 1.08, intercept: -0.035, gamma: 1 });
    // 02 carries the dense deck hatch, so its midtones are pulled down hardest,
    // and 03's flat gray fills are eased to sit in the same hierarchy.
    const reference = sheetTone(PLAN_SHEETS[0], true);
    const dense = sheetTone(PLAN_SHEETS[1], true);
    const filled = sheetTone(PLAN_SHEETS[2], true);
    expect(dense.gamma).toBeGreaterThan(reference.gamma);
    expect(dense.slope).toBeLessThan(reference.slope);
    expect(filled.gamma).toBeGreaterThan(reference.gamma);
    expect(sheetTone(PLAN_SHEETS[1], false).gamma).toBeGreaterThan(reference.gamma);
    expect(sheetTone(PLAN_SHEETS[2], false).gamma).toBeGreaterThan(reference.gamma);
    const { container } = render(<Portfolio introEnabled={false} />);
    fireEvent.click(screen.getByRole('button', { name: 'Inspect Off' }));
    const filters = () => [...container.querySelectorAll('.ff-vessel')].map(node => node.getAttribute('filter')!);
    const params = () => filters().map(id => {
      const func = container.querySelector(`${id.slice(4, -1)} feComponentTransfer feFuncA`)!;
      return [func.getAttribute('type'), func.getAttribute('amplitude'), func.getAttribute('exponent'), func.getAttribute('offset')];
    });
    for (const sheet of PLAN_SHEETS) {
      fireEvent.click(screen.getByRole('button', { name: sheet.label }));
      await act(async () => {});
      // Exhibit and lens carry the same curve, and no third copy is invented.
      expect(filters()).toHaveLength(2);
      expect(params()[0]).toEqual(params()[1]);
      const [type, amplitude, exponent, offset] = params()[0];
      expect(type).toBe('gamma');
      expect(Number(amplitude)).toBe(sheetTone(sheet, false).slope);
      expect(Number(exponent)).toBe(sheetTone(sheet, false).gamma);
      expect(Number(offset)).toBe(sheetTone(sheet, false).intercept);
    }
    fireEvent.click(screen.getByRole('button', { name: 'Switch to dark theme' }));
    const last = PLAN_SHEETS[PLAN_SHEETS.length - 1];
    expect(params()[0]).toEqual([ 'gamma', String(sheetTone(last, true).slope), String(sheetTone(last, true).gamma), String(sheetTone(last, true).intercept) ]);
  });
});

describe('inspection lens', () => {
  it('samples the composition under the pointer, letterboxing included', () => {
    // 800x350 is exactly 16:7, so the frame fills the exhibit and the mapping is
    // the plain scale: half across 400 CSS px is composition 800.
    expect(samplePoint({ left: 0, top: 0, width: 800, height: 350 }, .5, .5)).toMatchObject({ x: 800, y: 350 });
    expect(samplePoint({ left: 0, top: 0, width: 800, height: 350 }, .5, .25)).toMatchObject({ x: 800, y: 175 });
    // 1600x900 is wider than 16:7: `meet` letterboxes 100px top and bottom, so a
    // quarter down the rectangle is composition y=125 rather than y=225.
    expect(samplePoint({ left: 0, top: 0, width: 1600, height: 900 }, .5, .25)).toMatchObject({ x: 800, y: 125 });
  });

  it('magnifies exactly twice and centres the circle on the sample at every edge and corner', () => {
    expect(LENS_MAGNIFICATION).toBe(2);
    const frame = { left: 0, top: 0, width: 800, height: 350 };
    const centred = lensFrame(frame, .5, .5);
    // 200px of lens at 2x over a 0.5 scale shows 200/2/0.5 = 200 composition units.
    expect(centred).toMatchObject({ viewBox: '700 250 200 200', span: 200, size: 200, cx: 400, cy: 175 });
    // Letterboxed exhibit: scale 1, so 200px of lens at 2x shows 100 units.
    expect(lensFrame({ left: 0, top: 0, width: 1600, height: 900 }, .5, .25)).toMatchObject({ viewBox: '750 75 100 100', size: 200, cx: 800, cy: 225 });
    // The circle is never pushed back inside the board: at every edge and corner
    // its centre is the sampled point itself, and the board clips what hangs out.
    const square: [number, number][] = [[0, 0], [1, 0], [0, 1], [1, 1], [0, .5], [.5, 0], [1, .5], [.5, 1], [.25, .75]];
    for (const [fx, fy] of square) {
      const lens = lensFrame(frame, fx, fy);
      expect(lens.cx).toBe(fx * 800);
      expect(lens.cy).toBe(fy * 350);
      expect(lens.size).toBe(200);
    }
    // Corner viewBoxes still centre on the sample: 800 ± 100, 350 ± 100.
    expect(lensFrame(frame, 0, 0)).toMatchObject({ viewBox: '-100 -100 200 200', cx: 0, cy: 0 });
    expect(lensFrame(frame, 1, 1)).toMatchObject({ viewBox: '1500 600 200 200', cx: 800, cy: 350 });
    expect(lensFrame(frame, 0, .5)).toMatchObject({ viewBox: '-100 250 200 200', cx: 0, cy: 175 });
    expect(lensFrame(frame, 1, .5)).toMatchObject({ viewBox: '1500 250 200 200', cx: 800, cy: 175 });
    // A letterboxed board samples above and below the artwork itself, and the
    // circle still sits exactly on the pointer rather than on the artwork's edge.
    const letterboxed: [number, number, string][] = [
      [0, 0, '-50 -150 100 100'],
      [1, 1, '1550 750 100 100'],
      [.5, 1, '750 750 100 100'],
      [0, .5, '-50 300 100 100'],
    ];
    for (const [fx, fy, viewBox] of letterboxed) {
      const lens = lensFrame({ left: 0, top: 0, width: 1600, height: 900 }, fx, fy);
      expect(lens.viewBox).toBe(viewBox);
      expect(lens.cx).toBe(fx * 1600);
      expect(lens.cy).toBe(fy * 900);
    }
    // An exhibit smaller than the lens shrinks it rather than overflowing, and
    // it is still centred on the sample.
    expect(lensFrame({ left: 0, top: 0, width: 160, height: 90 }, .5, .5)).toMatchObject({ size: 90, cx: 80, cy: 45, viewBox: '575 125 450 450' });
    // Unmeasured (zero) rectangles fall back to the resting view instead of NaN.
    expect(lensFrame({ left: 0, top: 0, width: 0, height: 0 }, .5, .5).viewBox).toBe('400 -50 800 800');
  });

  it('paints the lens over the sample rather than pulled back inside the board', () => {
    fakeFrames();
    const { container } = render(<Portfolio introEnabled={false} />);
    const exhibit = screen.getByRole('group', { name: /Interactive top-view/ });
    const rect = vi.spyOn(exhibit, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 0, 800, 350));
    fireEvent.click(screen.getByRole('button', { name: 'Inspect Off' }));
    const lens = container.querySelector<HTMLElement>('.ff-lens')!;
    const view = () => container.querySelector('.ff-lens-view')!.getAttribute('viewBox');
    const move = (clientX: number, clientY: number) => {
      const event = new Event('pointermove', { bubbles: true });
      Object.assign(event, { pointerType: 'mouse', clientX, clientY });
      fireEvent(exhibit, event);
      act(() => { vi.advanceTimersByTime(16); });
    };
    // The middle: the circle is centred on the sample, so the transform puts the
    // lens half its size above and to the left of it.
    move(400, 175);
    expect(lens.style.width).toBe('200px');
    expect(lens.style.transform).toBe('translate(300px, 75px)');
    // The top-left corner: the circle stays on the sample and a quarter of it
    // hangs over the board, which is what the exhibit's own clipping cuts.
    move(0, 0);
    expect(lens.style.transform).toBe('translate(-100px, -100px)');
    expect(view()).toBe('-100 -100 200 200');
    // The bottom-right corner, in a board that letterboxes: the sample is off the
    // artwork, and the lens is still exactly where the pointer is.
    rect.mockReturnValue(new DOMRect(0, 0, 1600, 900));
    move(1600, 900);
    expect(lens.style.transform).toBe('translate(1500px, 800px)');
    expect(view()).toBe('1550 750 100 100');
  });

  it('magnifies the registered scan, moves by keyboard and leaves on Escape', () => {
    const { container } = render(<Portfolio introEnabled={false} />);
    const exhibit = screen.getByRole('group', { name: /Interactive top-view/ });
    vi.spyOn(exhibit, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 0, 800, 350));
    fireEvent.click(screen.getByRole('button', { name: 'Inspect Off' }));
    const lens = container.querySelector<HTMLElement>('.ff-lens')!;
    const view = container.querySelector<SVGElement>('.ff-lens-view')!;
    // A local window onto the same Artwork, tone and all: two copies, not two renderers.
    const scans = container.querySelectorAll('.ff-vessel');
    expect(scans.length).toBe(2);
    expect(scans[0].getAttribute('data-study')).toBe(scans[1].getAttribute('data-study'));
    const filters = [...scans].map(node => node.getAttribute('filter')!);
    // Two copies, two filter ids: the lens never shares the exhibit's defs.
    expect(new Set(filters).size).toBe(2);
    for (const filter of filters) {
      expect(container.querySelector(`${filter.slice(4, -1)} feComponentTransfer feFuncA`)).toHaveAttribute('type', 'gamma');
    }
    expect(container.querySelectorAll('image').length).toBe(2);
    // The lens keeps the frame's own pixel box, so 1 unit = 1 CSS px inside it
    // and the outer viewBox window alone decides the 2x.
    const lensArt = lens.querySelector('.ff-artwork')!;
    expect(lensArt).toHaveAttribute('width', '1600');
    expect(lensArt).toHaveAttribute('height', '700');
    const layers = () => [...container.querySelectorAll('.ff-layer-vessel')].map(node => node.getAttribute('transform'));
    // Keyboard alone brings the lens up, and the arrows move the sample, not the pan.
    const resting = layers()[0];
    fireEvent.keyDown(exhibit, { key: 'ArrowRight' });
    expect(lens.hidden).toBe(false);
    // 4% of 800px is 32 CSS px, which is 64 composition units at scale 0.5.
    expect(view.getAttribute('viewBox')).toBe('764 250 200 200');
    expect(layers()[0]).toBe(resting);
    expect(layers()[0]).toBe(layers()[1]);
    fireEvent.keyDown(exhibit, { key: 'Home' });
    expect(view.getAttribute('viewBox')).toBe('700 250 200 200');
    // Escape leaves inspection; the exhibit keeps its normal explore keys.
    fireEvent.keyDown(exhibit, { key: 'Escape' });
    expect(screen.getByRole('button', { name: 'Inspect Off' })).toHaveAttribute('aria-pressed', 'false');
    expect(container.querySelector('.ff-lens')).toBeNull();
    fireEvent.keyDown(exhibit, { key: 'ArrowRight' });
    expect(layers()[0]).not.toBe(resting);
  });

  it('shows the lens only while the pointer or the keyboard asks for it', () => {
    const { container } = render(<Portfolio introEnabled={false} />);
    const exhibit = screen.getByRole('group', { name: /Interactive top-view/ });
    vi.spyOn(exhibit, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 0, 800, 350));
    const pointer = (type: string) => { const event = new Event(type, { bubbles: true }); Object.assign(event, { pointerType: 'mouse' }); fireEvent(exhibit, event); };
    fireEvent.click(screen.getByRole('button', { name: 'Inspect Off' }));
    const lens = container.querySelector<HTMLElement>('.ff-lens')!;
    expect(lens.hidden).toBe(true);
    pointer('pointerover');
    expect(lens.hidden).toBe(false);
    pointer('pointerout');
    expect(lens.hidden).toBe(true);
    // Focus alone is not consent: a key is, and losing focus takes it back.
    fireEvent.keyDown(exhibit, { key: 'Home' });
    expect(lens.hidden).toBe(false);
    // A real pointer movement takes over from keyboard inspection. Leaving
    // afterwards must hide the lens even if the exhibit still has focus.
    const move = new Event('pointermove', { bubbles: true });
    Object.assign(move, { pointerType: 'mouse', clientX: 300, clientY: 150 });
    fireEvent(exhibit, move);
    pointer('pointerout');
    expect(lens.hidden).toBe(true);
    fireEvent.keyDown(exhibit, { key: 'Home' });
    expect(lens.hidden).toBe(false);
    fireEvent.focusOut(exhibit);
    expect(lens.hidden).toBe(true);
    // Explore mode keeps the stable cursor instead, never both at once.
    fireEvent.click(screen.getByRole('button', { name: 'Inspect On' }));
    expect(container.querySelector('.ff-lens')).toBeNull();
    const cursor = container.querySelector<HTMLElement>('.ff-cursor')!;
    pointer('pointerover');
    expect(cursor.hidden).toBe(false);
    pointer('pointerout');
    expect(cursor.hidden).toBe(true);
  });

  it('keeps hover-pan still under reduced motion while inspection still samples', () => {
    media(true); fakeFrames();
    const { container } = render(<Portfolio introEnabled={false} />);
    const exhibit = screen.getByRole('group', { name: /Interactive top-view/ });
    vi.spyOn(exhibit, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 0, 800, 350));
    fireEvent.click(screen.getByRole('button', { name: 'Inspect Off' }));
    const art = container.querySelector('.ff-layer-vessel')!;
    const view = container.querySelector('.ff-lens-view')!;
    const resting = art.getAttribute('transform');
    const move = new Event('pointermove', { bubbles: true });
    Object.assign(move, { pointerType: 'mouse', clientX: 700, clientY: 300 });
    fireEvent(exhibit, move);
    act(() => { vi.advanceTimersByTime(16); });
    // The hover pan is frozen...
    expect(art.getAttribute('transform')).toBe(resting);
    // ...but the lens still samples the pointer: (700,300)px is composition (1400,600).
    expect(view.getAttribute('viewBox')).toBe('1300 500 200 200');
    // In inspect mode the arrows are the sample's, and Escape hands panning back.
    fireEvent.keyDown(exhibit, { key: 'ArrowRight' });
    expect(view.getAttribute('viewBox')).toBe('1364 500 200 200');
    expect(art.getAttribute('transform')).toBe(resting);
    fireEvent.keyDown(exhibit, { key: 'Escape' });
    fireEvent.keyDown(exhibit, { key: 'ArrowRight' });
    expect(art.getAttribute('transform')).not.toBe(resting);
  });

  it('repaints the lens per frame without React commits', async () => {
    fakeFrames();
    const commits = vi.fn();
    const { container } = render(<Profiler id="portfolio" onRender={commits}><Portfolio introEnabled={false} /></Profiler>);
    const exhibit = screen.getByRole('group', { name: /Interactive top-view/ });
    vi.spyOn(exhibit, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 0, 800, 350));
    fireEvent.click(screen.getByRole('button', { name: 'Inspect Off' }));
    await act(async () => {});
    const view = container.querySelector<SVGElement>('.ff-lens-view')!;
    // Let the decode gate settle before measuring steady-state frames.
    act(() => { vi.advanceTimersByTime(16); });
    const before = commits.mock.calls.length;
    for (let i = 0; i < 20; i++) {
      const event = new Event('pointermove', { bubbles: true });
      Object.assign(event, { pointerType: 'mouse', clientX: 300, clientY: 120 });
      fireEvent(exhibit, event);
    }
    expect(view.getAttribute('viewBox')).toBe('700 250 200 200');
    expect(commits.mock.calls.length).toBe(before);
    const looped = commits.mock.calls.length;
    act(() => { vi.advanceTimersByTime(16); });
    // The sample sits at (300,120) CSS px = composition (600,240) at scale 0.5.
    expect(view.getAttribute('viewBox')).toBe('500 140 200 200');
    // Painting the frame must not reach React: any phase here is a commit.
    expect(commits.mock.calls.slice(looped).map(call => call[1])).toEqual([]);
  });
});
