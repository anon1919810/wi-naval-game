import { revealClock, revealGeometry, revealing } from './reveal-fixture';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Portfolio from '../portfolio/Portfolio';
import { RailNav } from '../portfolio/RailNav';
import type { PreviewSound } from '../portfolio/previewAudio';
import { TRANSITION_MS } from '../portfolio/transitions';
import { entryPoint, previewTarget, railView, revealRadius, wordCentre, NAV_PREVIEW_EASE, NAV_PREVIEW_MS } from '../portfolio/navPreview';
import * as api from '../api';

vi.mock('../api', async importOriginal => ({
  ...await importOriginal<typeof import('../api')>(),
  authConfig: vi.fn(), me: vi.fn(), bootstrapAnonymous: vi.fn(), listProjects: vi.fn(),
}));

const listeners = new Map<string, Set<(event: MediaQueryListEvent) => void>>();
const preferences = new Map<string, boolean>();
const reducedQuery = '(prefers-reduced-motion: reduce)';

/** Desktop rail geometry: two words in the fixed grid slot, beside the column. */
const WORK_BOX = new DOMRect(1000, 120, 300, 86);
const ABOUT_BOX = new DOMRect(1000, 216, 340, 86);
/** The real painted width of each word's first glyph, at the rail's display size. */
const GLYPH: Record<string, number> = { Work: 74, About: 70 };

beforeEach(() => {
  window.history.replaceState(null, '', '/');
  localStorage.clear();
  revealGeometry(); revealClock();
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
  // jsdom lays nothing out, and a range over the first character is how the real
  // first-glyph width is measured. Both are geometry the component reads, so both
  // are given a truth here rather than a zero the tests would have to work around.
  Object.defineProperty(Range.prototype, 'getBoundingClientRect', {
    configurable: true, writable: true,
    value: function () {
      const word = (this as Range).startContainer.parentElement?.closest('.ff-rail-word')?.querySelector('.ff-rail-ink')?.textContent ?? '';
      return new DOMRect(0, 0, GLYPH[word] ?? 0, 86);
    },
  });
  vi.mocked(api.authConfig).mockResolvedValue({ mode: 'anonymous' });
  vi.mocked(api.me).mockResolvedValue({ id: 'existing', email: 'existing@anonymous.invalid', theme: 'light', csrf_token: 'test', mode: 'anonymous', label: '本浏览器工作区' });
  vi.mocked(api.listProjects).mockResolvedValue([]);
});

afterEach(() => {
  cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); vi.restoreAllMocks();
  delete (Range.prototype as { getBoundingClientRect?: unknown }).getBoundingClientRect;
  delete (document as { startViewTransition?: unknown }).startViewTransition;
});

const flush = () => act(async () => {});

describe('Work badge preview', () => {
  it('answers only Work hover and restores on leave without changing the route', () => {
    render(<Portfolio introEnabled={false} />);
    layout();
    const work = screen.getByRole('link', { name: 'Work 01' });
    expect(work).toHaveAttribute('data-ff-badge', 'idle');
    hover('About', 1020, 240);
    expect(work).toHaveAttribute('data-ff-badge', 'idle');
    unhover('About');
    hover('Work 01', 1020, 145);
    expect(work).toHaveAttribute('data-ff-badge', 'preview');
    expect(work).toHaveAttribute('aria-current', 'page');
    unhover('Work 01');
    expect(work).toHaveAttribute('data-ff-badge', 'idle');
  });
  it('answers keyboard focus under reduced motion', () => {
    media(reducedQuery, true);
    render(<Portfolio introEnabled={false} />);
    const work = screen.getByRole('link', { name: 'Work 01' });
    key('Work 01'); fireEvent.focus(work);
    expect(work).toHaveAttribute('data-ff-badge', 'preview');
    fireEvent.blur(work);
    expect(work).toHaveAttribute('data-ff-badge', 'idle');
  });
  it('keeps a held Work preview red when the pointer moves to About', async () => {
    native();
    window.history.replaceState(null, '', '/#/about');
    render(<Portfolio introEnabled={false} />);
    layout();
    hover('Work 01', 1020, 145);
    press('Work 01');
    unhover('Work 01'); hover('About', 1020, 240);
    const work = screen.getByRole('link', { name: 'Work 01' });
    expect(work).toHaveAttribute('data-ff-nav-held', 'true');
    expect(work).toHaveAttribute('data-ff-badge', 'preview');
    await flush();
  });
});

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

/** An ordinary press: the browser's own navigation, then the hashchange it raises. */
function press(name: string) {
  const link = screen.getByRole('link', { name });
  let allowed = false;
  window.addEventListener('click', event => { allowed = !event.defaultPrevented; event.preventDefault(); }, { once: true });
  fireEvent(link, new MouseEvent('click', { bubbles: true, cancelable: true, button: 0 }));
  expect(allowed).toBe(true);
  // A press at the address already shown raises no hashchange, exactly as in a
  // browser: that is the whole difference between a press and a repeat.
  if (window.location.hash !== link.getAttribute('href')!) hash(link.getAttribute('href')!);
}

/** A press the browser keeps: a new tab, a new window, a download. */
function modifiedPress(name: string, detail: Partial<MouseEventInit> = { metaKey: true }) {
  const link = screen.getByRole('link', { name });
  const click = new MouseEvent('click', { bubbles: true, cancelable: true, button: 0, ...detail });
  fireEvent(link, click);
  return click;
}

function media(query: string, matches: boolean) {
  act(() => {
    preferences.set(query, matches);
    for (const listener of listeners.get(query) ?? []) listener({ matches } as MediaQueryListEvent);
  });
}

/** Give both words the geometry a 1440-wide desktop rail would give them. */
function layout() {
  for (const word of document.querySelectorAll<HTMLElement>('.ff-rail-word')) {
    const label = word.querySelector('.ff-rail-ink')!.textContent!;
    Object.defineProperty(word, 'getBoundingClientRect', { configurable: true, value: () => label === 'Work' ? WORK_BOX : ABOUT_BOX });
  }
  // The shell measured an empty document on its way in; a resize is what a real
  // viewport does anyway, and it re-measures both words against the real rail.
  act(() => { window.dispatchEvent(new Event('resize')); });
}

const word = (label: string) => [...document.querySelectorAll<HTMLElement>('.ff-rail-word')]
  .find(node => node.querySelector('.ff-rail-ink')!.textContent === label)!;
const dupOf = (label: string) => word(label).querySelector<HTMLElement>('.ff-rail-dup')!;
const radius = (label: string) => word(label).style.getPropertyValue('--ff-nav-radius');
const rule = (label: string) => word(label).style.getPropertyValue('--ff-nav-rule');
const origin = (label: string) => ({
  x: word(label).style.getPropertyValue('--ff-nav-x'),
  y: word(label).style.getPropertyValue('--ff-nav-y'),
});
const state = (name: string) => screen.getByRole('link', { name }).getAttribute('data-ff-nav');
const held = (name: string) => screen.getByRole('link', { name }).getAttribute('data-ff-nav-held');

/** React turns `pointerover`/`pointerout` into its own enter and leave. */
function hover(name: string, clientX: number, clientY: number) {
  const event = new Event('pointerover', { bubbles: true });
  Object.assign(event, { pointerType: 'mouse', clientX, clientY, relatedTarget: null });
  fireEvent(screen.getByRole('link', { name }), event);
}
function unhover(name: string) {
  const event = new Event('pointerout', { bubbles: true });
  Object.assign(event, { pointerType: 'mouse', relatedTarget: null });
  fireEvent(screen.getByRole('link', { name }), event);
}
function glide(name: string, clientX: number, clientY: number) {
  const event = new Event('pointermove', { bubbles: true });
  Object.assign(event, { pointerType: 'mouse', clientX, clientY });
  fireEvent(screen.getByRole('link', { name }), event);
}
function down(name: string) {
  fireEvent(screen.getByRole('link', { name }), new Event('pointerdown', { bubbles: true }));
}
function key(name: string, value = 'Tab') {
  fireEvent.keyDown(screen.getByRole('link', { name }), { key: value });
}

describe('navigation preview geometry', async () => {
  it('reads the entry point, the word centre and the far corner as three separate things', async () => {
    expect(entryPoint({ left: 1000, top: 216, width: 340, height: 86 }, 1010, 260)).toEqual({ x: 10, y: 44 });
    // A pointer outside the word is clamped into it rather than opening the circle
    // from somewhere the visitor cannot see.
    expect(entryPoint({ left: 1000, top: 216, width: 340, height: 86 }, 900, 400)).toEqual({ x: 0, y: 86 });
    expect(wordCentre({ left: 0, top: 0, width: 340, height: 86 })).toEqual({ x: 170, y: 43 });
    // The radius is the furthest corner from the origin, whatever that origin is.
    const square = { left: 0, top: 0, width: 200, height: 200 };
    expect(revealRadius(square, { x: 0, y: 0 })).toBeCloseTo(Math.hypot(200, 200), 2);
    expect(revealRadius(square, { x: 100, y: 100 })).toBeCloseTo(Math.hypot(100, 100), 2);
    const box = { left: 0, top: 0, width: 300, height: 86 };
    expect(revealRadius(box, { x: 10, y: 44 })).toBeCloseTo(Math.hypot(290, 44), 1);
    expect(revealRadius(box, { x: 150, y: 43 })).toBeCloseTo(Math.hypot(150, 43), 2);
    expect(revealRadius({ left: 0, top: 0, width: 0, height: 0 }, { x: 0, y: 0 })).toBe(0);
  });

  it('puts authority in a fixed order, so a pointer, a key and a press each win', async () => {
    // Work owns the detail, so any public view that is not About is Work.
    expect(railView('home')).toBe('home');
    expect(railView('project')).toBe('home');
    expect(railView('about')).toBe('about');
    // Idle: the route decides.
    expect(previewTarget('home', null, null, null)).toBe('home');
    // A pointer outranks a focus ring left behind by an earlier press.
    expect(previewTarget('home', 'about', 'home', null)).toBe('about');
    // Focus is what a keyboard gets.
    expect(previewTarget('home', null, 'about', null)).toBe('about');
    // A pressed destination outranks both, because the sheet needs it to hold.
    expect(previewTarget('home', 'home', 'home', 'about')).toBe('about');
  });

  it('hands over in one damped move, with no bounce to interrupt it', async () => {
    expect(NAV_PREVIEW_MS).toBe(300);
    // A monotonic easing: every control point inside the unit square, so the value
    // never overshoots and the handover cannot bounce back.
    const control = NAV_PREVIEW_EASE.replace(/cubic-bezier\(|\)/g, '').split(',').map(Number);
    expect(control).toHaveLength(4);
    expect(control.every(value => value >= 0 && value <= 1)).toBe(true);
  });
});

describe('work and about navigation', async () => {
  it('stays native, semantic and keyboard reachable, with one honest name each', async () => {
    render(<Portfolio introEnabled={false} />);
    const nav = screen.getByRole('navigation', { name: 'Main navigation' });
    const work = screen.getByRole('link', { name: 'Work 01' });
    const about = screen.getByRole('link', { name: 'About' });
    expect(work).toHaveAttribute('href', '#/work');
    expect(about).toHaveAttribute('href', '#/about');
    // Nothing about either entry is taken away from the browser: no role
    // overrides, no tabindex, no target, and the badge is inside the link.
    for (const link of [work, about]) {
      expect(link).not.toHaveAttribute('role');
      expect(link).not.toHaveAttribute('tabindex');
      expect(link).not.toHaveAttribute('target');
      expect(link.querySelector('.ff-rail-badge, .ff-rail-word')).not.toBeNull();
    }
    // Work owns the exhibit and its detail, and the count says there is one work.
    expect(work.querySelector('.ff-rail-badge')!.textContent).toBe('01');
    // Exactly one accessible name per link, and the blue duplicate contributes
    // nothing to it: it is decoration, and it says so.
    expect(screen.getAllByRole('link', { name: 'Work 01' })).toHaveLength(1);
    expect(screen.getAllByRole('link', { name: 'About' })).toHaveLength(1);
    for (const node of document.querySelectorAll('.ff-rail-dup')) expect(node).toHaveAttribute('aria-hidden', 'true');
    // The truthful page is named as current, and the other one is not.
    expect(work).toHaveAttribute('aria-current', 'page');
    expect(about).not.toHaveAttribute('aria-current');
    expect(nav).toBeInTheDocument();
  });

  it('paints the page on screen blue with a full rule, and every other word ink with the rule on its first glyph', async () => {
    render(<Portfolio introEnabled={false} />);
    layout();
    // The current word's circle is already open before the first paint: measured in
    // a layout effect, so the page never shows a resting Work that turns blue.
    expect(state('Work 01')).toBe('selected');
    expect(radius('Work')).toBe('156.04px');
    expect(rule('Work')).toBe('1');
    // Any other word is ink, with one rule, held to the real width of its first
    // glyph: 70 of About's 340 pixels.
    expect(state('About')).toBe('rest');
    expect(radius('About')).toBe('0px');
    expect(rule('About')).toBe(String(GLYPH.About / 340));
    // The base word is ink in both cases: the blue is only ever the duplicate,
    // which is what makes the reveal a reveal and not a cross-fade.
    expect(word('About').querySelector('.ff-rail-ink')!.className).toBe('ff-rail-ink');
  });

  it('opens the circle from the pointer entry point, closing it first so only the radius moves', async () => {
    render(<Portfolio introEnabled={false} />);
    layout();
    hover('About', 1010, 260);
    expect(origin('About')).toEqual({ x: '10px', y: '44px' });
    expect(dupOf('About').hasAttribute('data-ff-nav-armed')).toBe(false);
    expect(radius('About')).toBe(`${revealRadius({ left: 0, top: 0, width: 340, height: 86 }, { x: 10, y: 44 })}px`);
    expect(state('About')).toBe('selected');
    expect(state('Work 01')).toBe('rest');
    // And the page on screen keeps its own truth: still current, still named so.
    expect(screen.getByRole('link', { name: 'Work 01' })).toHaveAttribute('aria-current', 'page');
  });

  it('never moves the origin while the pointer moves inside the same word', async () => {
    render(<Portfolio introEnabled={false} />);
    layout();
    hover('About', 1010, 260);
    const entered = origin('About');
    glide('About', 1200, 250);
    glide('About', 1330, 240);
    expect(origin('About')).toEqual(entered);
    expect(radius('About')).toBe(`${revealRadius({ left: 0, top: 0, width: 340, height: 86 }, { x: 10, y: 44 })}px`);
  });

  it('resumes an open circle on a reversal rather than starting it again', async () => {
    render(<Portfolio introEnabled={false} />);
    layout();
    hover('About', 1010, 260);
    const opened = { origin: origin('About'), radius: radius('About') };
    expect(Number.parseFloat(opened.radius)).toBeGreaterThan(0);
    // Back onto Work, which is the page already on screen.
    hover('Work 01', 1010, 130);
    // Work's own circle is opened the same way: closed first, origin installed,
    // then radius alone to its far corner.
    expect(origin('Work')).toEqual({ x: '10px', y: '10px' });
    expect(radius('Work')).toBe(`${revealRadius({ left: 0, top: 0, width: 300, height: 86 }, { x: 10, y: 10 })}px`);
    // About's origin is exactly where it was, and its radius is aimed back at
    // closed: the circle closes from wherever it had opened to, with no new origin
    // and nothing to slide across.
    expect(origin('About')).toEqual(opened.origin);
    expect(radius('About')).toBe('0px');
    expect(dupOf('About').hasAttribute('data-ff-nav-armed')).toBe(false);
    // Coming back to About re-aims its radius from its own origin, still.
    const computed = window.getComputedStyle.bind(window);
    vi.spyOn(window, 'getComputedStyle').mockImplementation((node, pseudo) => node === dupOf('About')
      ? { clipPath: 'circle(100px at 10px 44px)' } as CSSStyleDeclaration : computed(node, pseudo));
    hover('About', 1330, 230);
    expect(origin('About')).toEqual(opened.origin);
    expect(radius('About')).toBe(opened.radius);
  });

  it('accepts keyboard focus arriving from outside after pointer input', async () => {
    render(<Portfolio introEnabled={false} />);
    layout();
    fireEvent.pointerDown(screen.getByRole('button', { name: 'Preview sound' }));
    fireEvent.keyDown(window, { key: 'Tab', shiftKey: true });
    fireEvent.focus(screen.getByRole('link', { name: 'About' }));
    expect(state('About')).toBe('selected');
    expect(origin('About')).toEqual({ x: '170px', y: '43px' });
  });

  it('keeps a held destination silent when the route commits under it', async () => {
    const sound: PreviewSound = { muted: false, unlocked: true, unlock: vi.fn(), tap: vi.fn().mockReturnValue(true), setMuted: vi.fn(), dispose: vi.fn() };
    const props = { sound, onCurrentPagePress: vi.fn() };
    const view = render(<RailNav current="home" {...props} />);
    layout();
    hover('About', 1010, 260);
    expect(sound.tap).toHaveBeenCalledTimes(1);
    press('About');
    hover('Work 01', 1010, 130);
    view.rerender(<RailNav current="about" {...props} />);
    expect(held('About')).toBe('true');
    expect(state('Work 01')).toBe('rest');
    expect(sound.tap).toHaveBeenCalledTimes(1);
  });

  it('answers a real click after a cold silent hover', async () => {
    const sound: PreviewSound = { muted: false, unlocked: false, unlock: vi.fn(), tap: vi.fn().mockReturnValueOnce(false).mockReturnValue(true), setMuted: vi.fn(), dispose: vi.fn() };
    render(<RailNav current="home" sound={sound} onCurrentPagePress={vi.fn()} />);
    layout();
    hover('About', 1010, 260);
    down('About');
    press('About');
    expect(sound.unlock).toHaveBeenCalled();
    expect(sound.tap).toHaveBeenCalledTimes(2);
    expect(sound.tap).toHaveBeenLastCalledWith('about');
  });

  it('releases the requested word when native transition startup throws', async () => {
    window.history.replaceState(null, '', '/#/work/plimsoll');
    (document as { startViewTransition?: unknown }).startViewTransition = vi.fn(() => { throw new Error('unavailable'); });
    render(<Portfolio introEnabled={false} />);
    layout();
    press('About');
    expect(screen.getByRole('heading', { name: /A field for/ })).toBeVisible();
    expect(held('About')).toBeNull();
    hover('Work 01', 1010, 130);
    expect(state('Work 01')).toBe('selected');
  });

  it('unlocks sound on the same click that unmutes a cold stored preference', async () => {
    localStorage.setItem('formfield-preview-sound', 'muted');
    const opened = vi.fn();
    vi.stubGlobal('AudioContext', class {
      state = 'running'; close = vi.fn();
      constructor() { opened(); }
    });
    render(<Portfolio introEnabled={false} />);
    expect(opened).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Preview sound' }));
    expect(opened).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button', { name: 'Preview sound' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('restores the truthful route when the pointer leaves, including from About', async () => {
    window.history.replaceState(null, '', '/#/about');
    render(<Portfolio introEnabled={false} />);
    layout();
    expect(state('About')).toBe('selected');
    expect(screen.getByRole('link', { name: 'About' })).toHaveAttribute('aria-current', 'page');
    hover('Work 01', 1200, 130);
    expect(state('Work 01')).toBe('selected');
    expect(state('About')).toBe('rest');
    expect(radius('About')).toBe('0px');
    // The preview never touched the truth: About is still the current page.
    expect(screen.getByRole('link', { name: 'About' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: 'Work 01' })).not.toHaveAttribute('aria-current');
    // Leaving puts it back exactly where it was, with the rule on the first glyph.
    unhover('Work 01');
    expect(state('About')).toBe('selected');
    expect(state('Work 01')).toBe('rest');
    expect(rule('Work')).toBe(String(GLYPH.Work / 300));
    expect(Number.parseFloat(radius('About'))).toBeGreaterThan(0);
  });

  it('previews from the middle of the word for a key, and stops when the focus goes', async () => {
    render(<Portfolio introEnabled={false} />);
    layout();
    const about = screen.getByRole('link', { name: 'About' });
    // Tabbing to a destination is an intention to look at it, and a key has no
    // entry point, so the circle opens from the middle of the word.
    key('About'); fireEvent.focus(about);
    expect(origin('About')).toEqual({ x: '170px', y: '43px' });
    expect(radius('About')).toBe(`${revealRadius({ left: 0, top: 0, width: 340, height: 86 }, { x: 170, y: 43 })}px`);
    expect(state('About')).toBe('selected');
    fireEvent.blur(about);
    expect(state('About')).toBe('rest');
    expect(radius('About')).toBe('0px');
    // Leaving the rail with the keyboard takes the preview with it.
    key('About'); fireEvent.focus(about);
    expect(state('About')).toBe('selected');
    fireEvent.focusOut(about);
    expect(state('About')).toBe('rest');
  });

  it('does not let a click’s own focus outlive the pointer that caused it', async () => {
    render(<Portfolio introEnabled={false} />);
    layout();
    const about = screen.getByRole('link', { name: 'About' });
    down('About');
    hover('About', 1010, 260);
    fireEvent.focus(about);
    // The pointer's entry point survives the click's focus: nothing re-aims it.
    expect(origin('About')).toEqual({ x: '10px', y: '44px' });
    unhover('About');
    // And the focus the click left behind holds no word blue afterwards.
    expect(state('About')).toBe('rest');
    expect(radius('About')).toBe('0px');
    // A genuine key after the same press takes over again.
    key('About'); fireEvent.focus(about);
    expect(state('About')).toBe('selected');
    expect(origin('About')).toEqual({ x: '170px', y: '43px' });
  });

  it('leaves a modified press to the browser, and locks no local state with it', async () => {
    render(<Portfolio introEnabled={false} />);
    layout();
    hover('About', 1010, 260);
    for (const detail of [{ metaKey: true }, { ctrlKey: true }, { shiftKey: true }, { altKey: true }, { button: 1 }]) {
      expect(modifiedPress('About', detail).defaultPrevented).toBe(false);
    }
    expect(held('About')).toBeNull();
    expect(revealing()).toBeUndefined();
    unhover('About');
    // Nothing about a new tab follows this tab: no hold, no blue, no page cut.
    expect(state('About')).toBe('rest');
    expect(held('About')).toBeNull();
  });

  it('holds the requested destination for the whole page cut, and commits without a restart', async () => {
    vi.useFakeTimers(); revealClock(); native();
    render(<Portfolio introEnabled={false} />);
    layout();
    hover('About', 1010, 260);
    const attained = radius('About');
    press('About');
    // The content changes as the attribute is set, and the word it was asked for
    // keeps exactly the blue it had attained: the preview is not restarted, and the
    // requested page is already on screen while its entrance is still running.
    expect(revealing()).toMatch(/^circle\(/);
    expect(screen.getByRole('heading', { name: /A field for/ })).toBeVisible();
    expect(screen.getByRole('link', { name: 'About' })).toHaveAttribute('aria-current', 'page');
    expect(held('About')).toBe('true');
    expect(state('About')).toBe('selected');
    expect(radius('About')).toBe(attained);
    expect(state('Work 01')).toBe('rest');
    await act(async () => { vi.advanceTimersByTime(TRANSITION_MS.page - 1); });
    expect(revealing()).toMatch(/^circle\(/);
    expect(state('About')).toBe('selected');
    expect(radius('About')).toBe(attained);
    // Partway through the entrance the pointer drifts back onto the outgoing word.
    // The destination was asked for and is still on screen, so it keeps the blue.
    hover('Work 01', 1200, 130);
    expect(state('About')).toBe('selected');
    expect(radius('About')).toBe(attained);
    expect(state('Work 01')).toBe('rest');
    await act(async () => { vi.advanceTimersByTime(1); });
    // The move is over at 500 ms, so the hold is released and the pointer leads again.
    expect(revealing()).toBeUndefined();
    expect(held('About')).toBeNull();
    expect(state('Work 01')).toBe('selected');
  });

  it('releases the hold when the destination is pressed again once it is the committed page', async () => {
    vi.useFakeTimers(); revealClock(); native();
    render(<Portfolio introEnabled={false} />);
    layout();
    hover('About', 1010, 260);
    press('About');
    expect(held('About')).toBe('true');
    expect(screen.getByRole('link', { name: 'About' })).toHaveAttribute('aria-current', 'page');
    // About is committed already, so this press raises no address and therefore no
    // route. It is a press on the page already on screen, so the hold goes with it
    // and the cut it belonged to is retired rather than left to finish.
    press('About');
    expect(held('About')).toBeNull();
    expect(revealing()).toBeUndefined();
    await act(async () => { vi.advanceTimersByTime(TRANSITION_MS.page); });
    expect(revealing()).toBeUndefined();
    expect(state('About')).toBe('selected');
    expect(screen.getByRole('link', { name: 'About' })).toHaveAttribute('aria-current', 'page');
  });

  it('drops a hold the address has already abandoned', async () => {
    vi.useFakeTimers(); revealClock(); native();
    render(<Portfolio introEnabled={false} />);
    layout();
    hover('About', 1010, 260);
    press('About');
    expect(held('About')).toBe('true');
    // Back before the cut finished: the address says Work, so the requested
    // destination is abandoned rather than held on to.
    hash('#/work');
    await act(async () => { vi.advanceTimersByTime(TRANSITION_MS.page); });
    expect(held('About')).toBeNull();
    expect(screen.getByRole('link', { name: 'Work 01' })).toHaveAttribute('aria-current', 'page');
  });

  it('reaches the page at once under reduced motion, and still answers a preview', async () => {
    preferences.set(reducedQuery, true);
    native();
    render(<Portfolio introEnabled={false} />);
    layout();
    hover('About', 1010, 260);
    expect(state('About')).toBe('selected');
    expect(radius('About')).toBe(`${revealRadius({ left: 0, top: 0, width: 340, height: 86 }, { x: 10, y: 44 })}px`);
    press('About');
    // No attribute is ever set, so nothing animates: the page is simply there.
    expect(revealing()).toBeUndefined();
    expect(screen.getByRole('heading', { name: /A field for/ })).toBeVisible();
    expect(screen.getByRole('link', { name: 'About' })).toHaveAttribute('aria-current', 'page');
    expect(state('About')).toBe('selected');
    expect(held('About')).toBeNull();
    unhover('About');
    expect(state('About')).toBe('selected');
  });

  it('settles the requested route when the preference is turned on mid-cut', async () => {
    vi.useFakeTimers(); revealClock(); native();
    render(<Portfolio introEnabled={false} />);
    layout();
    press('About');
    expect(revealing()).toMatch(/^circle\(/);
    expect(screen.getByRole('heading', { name: /A field for/ })).toBeVisible();
    media(reducedQuery, true);
    // The requested URL is still the authority: the page stays, and the attribute
    // is released rather than left behind.
    expect(screen.getByRole('heading', { name: /A field for/ })).toBeVisible();
    expect(revealing()).toBeUndefined();
    await act(async () => { vi.advanceTimersByTime(TRANSITION_MS.page); });
    expect(revealing()).toBeUndefined();
    expect(screen.getByRole('heading', { name: /A field for/ })).toBeVisible();
    void flush();
  });
});
