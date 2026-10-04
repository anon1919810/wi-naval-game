import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Portfolio from '../portfolio/Portfolio';
import { diagonalClip, introFrame, INTRO_DURATION } from '../portfolio/motion';
import { classifyHash } from '../portfolio/routes';
import { PLAN_SHEETS, sheetViewBox } from '../portfolio/plans';
import { THEME_KEY } from '../portfolio/theme';
import * as api from '../api';

vi.mock('../api', async importOriginal => ({
  ...await importOriginal<typeof import('../api')>(),
  authConfig: vi.fn(), me: vi.fn(), bootstrapAnonymous: vi.fn(), listProjects: vi.fn(),
}));

function media(reduced = false, dark = false) {
  vi.stubGlobal('matchMedia', vi.fn((query: string) => ({
    matches: query.includes('reduced-motion') ? reduced : dark,
    media: query, addEventListener: vi.fn(), removeEventListener: vi.fn(),
  })));
}

beforeEach(() => {
  window.history.replaceState(null, '', '/');
  localStorage.clear();
  vi.clearAllMocks();
  media();
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
    fireEvent.change(screen.getByLabelText('Color theme'), { target: { value: 'dark' } });
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
    follow('EXPLORE PROJECT');
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
    const composition = () => container.querySelector('.ff-artwork > g')!;
    const resting = composition().getAttribute('transform');
    fireEvent.keyDown(exhibit, { key: 'ArrowRight' });
    expect(composition().getAttribute('transform')).not.toBe(resting);
    fireEvent.keyDown(exhibit, { key: 'Home' });
    expect(composition().getAttribute('transform')).toBe(resting);
    fireEvent.click(screen.getByRole('button', { name: 'Geometry On' }));
    expect(composition().firstElementChild).toHaveAttribute('opacity', '0');
    fireEvent.click(screen.getByRole('button', { name: 'Inspect Off' }));
    expect(screen.getByRole('button', { name: 'Inspect On' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('resolves the system preference locally and restores a saved theme', () => {
    media(false, true);
    localStorage.setItem(THEME_KEY, 'system');
    render(<Portfolio introEnabled={false} />);
    expect(screen.getByLabelText('Color theme')).toHaveValue('system');
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(api.authConfig).not.toHaveBeenCalled();
  });

  it('does not collapse the splash into a hidden exhibit on a direct About link', () => {
    window.history.replaceState(null, '', '/#/about');
    render(<Portfolio />);
    expect(screen.getByRole('heading', { name: /A field for\s*useful ideas\./ })).toBeVisible();
    expect(screen.queryByRole('status', { name: 'Opening Y’s Formfield' })).toBeNull();
  });
});

describe('opening lifecycle', () => {
  it('bypasses motion immediately for a reduced-motion preference', () => {
    media(true);
    render(<StrictMode><Portfolio /></StrictMode>);
    expect(screen.queryByRole('status', { name: 'Opening Y’s Formfield' })).toBeNull();
    expect(screen.getByRole('heading', { name: 'Plimsoll' })).toBeVisible();
  });

  it('starts without JS image loading, finishes under StrictMode, and internal return does not replay', () => {
    vi.useFakeTimers();
    // The exhibit draws the scan with <image>, which the browser fetches without
    // the Image constructor; this guards against reintroducing a JS preload path.
    const imageConstructor = vi.fn(() => { throw new Error('The intro must not preload bitmaps through JS'); });
    vi.stubGlobal('Image', imageConstructor);
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => window.setTimeout(() => cb(performance.now()), 16));
    vi.stubGlobal('cancelAnimationFrame', (id: number) => window.clearTimeout(id));
    render(<StrictMode><Portfolio /></StrictMode>);
    expect(screen.getByRole('status', { name: 'Opening Y’s Formfield' })).toBeInTheDocument();
    act(() => { vi.advanceTimersByTime(INTRO_DURATION + 32); });
    expect(screen.queryByRole('status', { name: 'Opening Y’s Formfield' })).toBeNull();
    expect(imageConstructor).not.toHaveBeenCalled();
    follow('About'); follow('Work 01');
    expect(screen.queryByRole('status', { name: 'Opening Y’s Formfield' })).toBeNull();
    expect(api.authConfig).not.toHaveBeenCalled();
  });

  it('allows Escape to skip the introduction', () => {
    render(<Portfolio />);
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(screen.queryByRole('status', { name: 'Opening Y’s Formfield' })).toBeNull();
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

  it('embeds each original reference sheet cropped to its metadata, without geometric redraw', () => {
    const { container } = render(<Portfolio introEnabled={false} />);
    const seen = new Set<string>();
    for (const sheet of PLAN_SHEETS) {
      fireEvent.click(screen.getByRole('button', { name: sheet.label }));
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
    const clean = target.querySelector('feComponentTransfer feFuncA')!;
    expect(clean).toHaveAttribute('type', 'linear');
    expect(Number(clean.getAttribute('slope'))).toBeCloseTo(1.08);
    expect(Number(clean.getAttribute('intercept'))).toBeCloseTo(-0.035);
    expect(container.querySelectorAll('image').length).toBeGreaterThan(0);
  });
});
