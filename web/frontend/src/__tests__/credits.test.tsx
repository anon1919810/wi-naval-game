import { revealClock, revealGeometry, revealing } from './reveal-fixture';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Portfolio from '../portfolio/Portfolio';
import { RailNav } from '../portfolio/RailNav';
import type { PreviewSound } from '../portfolio/previewAudio';
import { PUBLIC_CREDITS_HASH, PUBLIC_WORK_DETAIL_HASH, classifyHash } from '../portfolio/routes';
import { TRANSITION_MS } from '../portfolio/transitions';
import { railView } from '../portfolio/navPreview';
import * as api from '../api';

/**
 * Credits: a third public page, reached from the rail.
 *
 * The assertions here are about behaviour a visitor can observe — what a direct
 * address loads, which word the rail says is current, where focus lands, which
 * transition runs and what the ruler measures — rather than about the copy itself.
 */

vi.mock('../api', async importOriginal => ({
  ...await importOriginal<typeof import('../api')>(),
  authConfig: vi.fn(), me: vi.fn(), bootstrapAnonymous: vi.fn(), listProjects: vi.fn(),
}));

const listeners = new Map<string, Set<(event: MediaQueryListEvent) => void>>();
const preferences = new Map<string, boolean>();
const reducedQuery = '(prefers-reduced-motion: reduce)';
/** Reference bitmaps requested during the current test. */
let decoded: string[] = [];

/** The rail's own box for the long word, and the width its first glyph reports. */
const CREDITS_BOX = new DOMRect(1010, 312, 300, 60);
const GLYPH_Credits = 46;

beforeEach(() => {
  window.history.replaceState(null, '', '/');
  localStorage.clear();
  revealGeometry(); revealClock();
  decoded = [];
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
  // Every reference bitmap the shell asks the browser for, recorded by path. A page
  // that is not Work must decode none: the test asserts on the absence of work, not
  // only on the absence of an <img> in the markup.
  vi.stubGlobal('Image', class {
    src = '';
    decode = () => Promise.resolve();
    constructor() { decoded.push((this as unknown as { src: string }).src); }
  });
  vi.stubGlobal('scrollTo', vi.fn());
  Object.defineProperty(Range.prototype, 'getBoundingClientRect', {
    configurable: true, writable: true,
    value: function () {
      // The glyph is measured on the text node the range names, which for the split
      // word is the first character of the leading `Cred`.
      const link = (this as Range).startContainer.parentElement?.closest('.ff-rail-link');
      return new DOMRect(0, 0, link?.getAttribute('aria-label')?.startsWith('Credits') ? GLYPH_Credits : 70, 86);
    },
  });
  vi.mocked(api.authConfig).mockResolvedValue({ mode: 'anonymous' });
  vi.mocked(api.me).mockResolvedValue({ id: 'existing', email: 'existing@anonymous.invalid', theme: 'light', csrf_token: 'test', mode: 'anonymous', label: '本浏览器工作区' });
  vi.mocked(api.listProjects).mockResolvedValue([]);
});

afterEach(() => {
  cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks();
  delete (Range.prototype as { getBoundingClientRect?: unknown }).getBoundingClientRect;
  delete (document as { startViewTransition?: unknown }).startViewTransition;
});

const flush = () => act(async () => {});
const creditsPage = () => document.querySelector<HTMLElement>('.ff-credits');
/** The live content region, never the reveal's inert copy of the page leaving. */
const liveMain = () => document.querySelector<HTMLElement>('main.ff-main')!;
const credit = (name: string) => screen.getByRole('link', { name });
/**
 * A rail word, matched on its own painted text.
 *
 * The label is read back off the link rather than compared against the entry list,
 * so the test keeps working however the word is split into glyphs for the reveal.
 */
const wordBox = (label: string) => [...document.querySelectorAll<HTMLElement>('.ff-rail-word')]
  .find(node => node.closest('.ff-rail-link')!.getAttribute('aria-label')!.startsWith(label))!;

function open(hashValue: string) {
  act(() => { window.history.replaceState(null, '', `/${hashValue}`); window.dispatchEvent(new HashChangeEvent('hashchange')); });
}

/** A press the browser keeps, with the one hashchange it would raise. */
function press(name: string) {
  const link = name === 'VIEW PROJECT' ? viewProject() : credit(name);
  let allowed = false;
  window.addEventListener('click', event => { allowed = !event.defaultPrevented; event.preventDefault(); }, { once: true });
  fireEvent(link, new MouseEvent('click', { bubbles: true, cancelable: true, button: 0 }));
  expect(allowed).toBe(true);
  if (window.location.hash !== link.getAttribute('href')!) open(link.getAttribute('href')!);
}

/**
 * The exhibit's secondary entry into the detail.
 *
 * It is hidden until its own region is opened, exactly as it is for a visitor, so
 * it is found in the DOM rather than by role: querying by accessible name would be
 * asserting that it is visible when the test is about what happens when it is used.
 */
function viewProject() {
  fireEvent.focus(screen.getByRole('link', { name: 'Open Plimsoll' }));
  return document.querySelector<HTMLAnchorElement>('.ff-title-action')!;
}

function hover(name: string, clientX: number, clientY: number) {
  const event = new Event('pointerover', { bubbles: true });
  Object.assign(event, { pointerType: 'mouse', clientX, clientY, relatedTarget: null });
  fireEvent(credit(name), event);
}
function unhover(name: string) {
  const event = new Event('pointerout', { bubbles: true });
  Object.assign(event, { pointerType: 'mouse', relatedTarget: null });
  fireEvent(credit(name), event);
}

function layout() {
  Object.defineProperty(wordBox('Credits'), 'getBoundingClientRect', { configurable: true, value: () => CREDITS_BOX });
  act(() => { window.dispatchEvent(new Event('resize')); });
}

function media(query: string, matches: boolean) {
  act(() => {
    preferences.set(query, matches);
    for (const listener of listeners.get(query) ?? []) listener({ matches } as MediaQueryListEvent);
  });
}

describe('credits routing', () => {
  it('is a public view of its own, with its own hash and its own rail word', () => {
    expect(classifyHash('#/credits')).toEqual({ kind: 'public', view: 'credits' });
    expect(classifyHash(`#${PUBLIC_CREDITS_HASH}`)).toEqual({ kind: 'public', view: 'credits' });
    // A first segment, exactly as About is: it claims its own sub-paths rather
    // than falling through to Work, so the two reading pages cannot differ here.
    expect(classifyHash('#/credits/extra')).toEqual({ kind: 'public', view: 'credits' });
    expect(classifyHash('#/about/extra')).toEqual({ kind: 'public', view: 'about' });
    // The application's own first segments are untouched.
    for (const hashValue of ['#/plimsoll', '#/projects', '#/runs', '#/reports']) {
      expect(classifyHash(hashValue)).toEqual({ kind: 'app' });
    }
    expect(railView('credits')).toBe('credits');
  });

  it('opens straight from a direct address with no intro, no exhibit and no API call', async () => {
    open(`#${PUBLIC_CREDITS_HASH}`);
    render(<Portfolio />);
    // The address names Credits, so that is the page on screen and its own title.
    expect(creditsPage()).not.toBeNull();
    expect(document.title).toBe('Credits — Y’s Formfield');
    expect(screen.getByRole('heading', { level: 1 })).toBeVisible();
    // Not a visit to the exhibit: no opening, and no workspace either.
    expect(screen.queryByRole('status', { name: 'Opening Y’s Formfield' })).toBeNull();
    expect(document.querySelector('.ff-tool-shell')).toBeNull();
    // The exhibit stays mounted but hidden, exactly as it does behind About: what
    // matters is that nothing of it is on screen and that no reference bitmap was
    // asked for on this route.
    expect(screen.queryByRole('group', { name: /Interactive top-view/ })).toBeNull();
    expect(document.querySelector('img')).toBeNull();
    // The exhibit's own compass field is not mounted: Credits borrows the shell's.
    expect(document.querySelector('.ff-field--work')).toBeNull();
    expect(document.querySelector('.ff-field--shell')).not.toBeNull();
    expect(decoded).toEqual([]);
    await flush();
    expect(api.authConfig).not.toHaveBeenCalled();
    expect(api.me).not.toHaveBeenCalled();
    expect(api.bootstrapAnonymous).not.toHaveBeenCalled();
    expect(api.listProjects).not.toHaveBeenCalled();
  });


});

describe('the third rail entry', () => {
  it('is a native, semantically named link that takes its own current state', () => {
    render(<Portfolio introEnabled={false} />);
    const nav = screen.getByRole('navigation', { name: 'Main navigation' });
    const credits = credit('Credits');
    expect(credits).toHaveAttribute('href', '#/credits');
    expect(credits).not.toHaveAttribute('role');
    expect(credits).not.toHaveAttribute('tabindex');
    expect(credits).not.toHaveAttribute('target');
    // Exactly one accessible name: the blue duplicate is decoration and says so.
    expect(screen.getAllByRole('link', { name: 'Credits' })).toHaveLength(1);
    expect(credits.querySelector('.ff-rail-dup')).toHaveAttribute('aria-hidden', 'true');
    // Work is the current page to begin with, and neither of the others claims it.
    expect(credit('Work 01')).toHaveAttribute('aria-current', 'page');
    expect(credit('About')).not.toHaveAttribute('aria-current');
    expect(credits).not.toHaveAttribute('aria-current');
    expect(nav).toBeInTheDocument();
  });

  it('gives Credits its own current state while Work keeps the detail', () => {
    open(`#${PUBLIC_CREDITS_HASH}`);
    render(<Portfolio introEnabled={false} />);
    expect(credit('Credits')).toHaveAttribute('aria-current', 'page');
    expect(credit('Work 01')).not.toHaveAttribute('aria-current');
    // The detail belongs to Work, so Credits and Work never both claim the route.
    open(`#${PUBLIC_WORK_DETAIL_HASH}`);
    expect(credit('Work 01')).toHaveAttribute('aria-current', 'page');
    expect(credit('Credits')).not.toHaveAttribute('aria-current');
  });

  it('turns the dot red for a pointer preview and takes it back on leave', () => {
    const dotState = () => credit('Credits').getAttribute('data-ff-dot');
    render(<RailNav current="home" sound={sound()} onCurrentPagePress={vi.fn()} />);
    layout();
    // Work is the page on screen, so Credits is a destination and nothing more.
    expect(dotState()).toBe('idle');
    // A pointer over it is an intention to go there: the dot answers.
    hover('Credits', 1020, 330);
    expect(dotState()).toBe('preview');
    unhover('Credits');
    expect(dotState()).toBe('idle');
    // So does the keyboard, and leaving it takes the answer with it.
    fireEvent.keyDown(credit('Credits'), { key: 'Tab' });
    fireEvent.focus(credit('Credits'));
    expect(dotState()).toBe('preview');
    fireEvent.blur(credit('Credits'));
    expect(dotState()).toBe('idle');
  });

  it('holds the dot red for the whole of a move it asked for, then releases it', async () => {
    vi.useFakeTimers(); revealClock(); native();
    render(<Portfolio introEnabled={false} />);
    layout();
    const dotState = () => credit('Credits').getAttribute('data-ff-dot');
    hover('Credits', 1020, 330);
    press('Credits');
    expect(dotState()).toBe('preview');
    // The pointer drifts onto Work while Credits' own cut is still running. The hold
    // outranks it, so Credits keeps the word it was asked for and the dot with it.
    unhover('Credits');
    hover('Work 01', 1020, 130);
    expect(credit('Credits')).toHaveAttribute('data-ff-nav', 'selected');
    expect(credit('Work 01')).toHaveAttribute('data-ff-nav', 'rest');
    expect(dotState()).toBe('preview');
    // The move ends at 500 ms and the hold is released with it: the pointer leads
    // again, and the dot is no longer an answer about anywhere in particular.
    await act(async () => { vi.advanceTimersByTime(TRANSITION_MS.page + 100); });
    expect(credit('Credits')).not.toHaveAttribute('data-ff-nav-held');
    expect(credit('Work 01')).toHaveAttribute('data-ff-nav', 'selected');
    unhover('Work 01');
    expect(credit('Credits')).toHaveAttribute('data-ff-nav', 'selected');
    expect(dotState()).toBe('idle');
  });

  it('leaves the dot the accent colour on the page that is actually current', () => {
    render(<Portfolio introEnabled={false} />);
    layout();
    open(`#${PUBLIC_CREDITS_HASH}`);
    layout();
    // Selected is where the visitor is, not where they are going, so the dot is not
    // a preview signal here — the same distinction Work's badge makes.
    expect(credit('Credits')).toHaveAttribute('aria-current', 'page');
    expect(credit('Credits')).toHaveAttribute('data-ff-dot', 'idle');
    hover('Credits', 1020, 330);
    expect(credit('Credits')).toHaveAttribute('data-ff-dot', 'preview');
  });

  it('keeps the resting underline on the first glyph of the split word', () => {
    render(<Portfolio introEnabled={false} />);
    layout();
    // The glyph measured is the first character of the leading `Cred`, found by
    // walking to the first text node rather than assuming it is the element's own
    // first child — the split puts a wrapper in between.
    const ink = wordBox('Credits').querySelector('.ff-rail-ink')!;
    expect(ink.firstElementChild!.textContent).toBe('Cred');
    expect(ink.firstElementChild!.firstChild!.nodeType).toBe(Node.TEXT_NODE);
    // At rest the rule is held to that glyph against the word's own box, which is
    // only measurable because the walk found the text rather than the span.
    // The stub reports the first glyph of `Cred` as 46px against a 300px word, so
    // the rule is held to that fraction rather than to the whole word.
    expect(Number.parseFloat(wordBox('Credits').style.getPropertyValue('--ff-nav-rule')))
      .toBeCloseTo(GLYPH_Credits / CREDITS_BOX.width, 5);
    // While the word is selected the rule spans all of it, the same as the others.
    hover('Credits', 1020, 330);
    expect(wordBox('Credits').style.getPropertyValue('--ff-nav-rule')).toBe('1');
  });

  it('previews Credits from the pointer and hands it back on leave, without moving the route', () => {
    render(<Portfolio introEnabled={false} />);
    layout();
    expect(credit('Credits')).toHaveAttribute('data-ff-nav', 'rest');
    // Its own circle opens from where the pointer entered the word.
    hover('Credits', 1020, 330);
    expect(credit('Credits')).toHaveAttribute('data-ff-nav', 'selected');
    expect(wordBox('Credits').style.getPropertyValue('--ff-nav-x')).toBe('10px');
    expect(Number.parseFloat(wordBox('Credits').style.getPropertyValue('--ff-nav-radius'))).toBeGreaterThan(0);
    // Work, the page on screen, keeps the truth and answers nothing about Credits.
    expect(credit('Work 01')).toHaveAttribute('data-ff-nav', 'rest');
    expect(credit('Work 01')).toHaveAttribute('aria-current', 'page');
    expect(window.location.hash).toBe('');
    unhover('Credits');
    expect(credit('Credits')).toHaveAttribute('data-ff-nav', 'rest');
    expect(credit('Work 01')).toHaveAttribute('data-ff-nav', 'selected');
  });

  it('answers a reversal mid-reveal by resuming, not restarting', () => {
    render(<RailNav current="home" sound={sound()} onCurrentPagePress={vi.fn()} />);
    layout();
    hover('Credits', 1020, 330);
    const opened = {
      x: wordBox('Credits').style.getPropertyValue('--ff-nav-x'),
      y: wordBox('Credits').style.getPropertyValue('--ff-nav-y'),
      radius: wordBox('Credits').style.getPropertyValue('--ff-nav-radius'),
    };
    expect(Number.parseFloat(opened.radius)).toBeGreaterThan(0);
    // Back onto Work before the circle has finished: Work's own circle opens.
    hover('Work 01', 1020, 130);
    expect(credit('Work 01')).toHaveAttribute('data-ff-nav', 'selected');
    // Credits keeps the origin it had and is simply aimed closed again.
    expect(wordBox('Credits').style.getPropertyValue('--ff-nav-x')).toBe(opened.x);
    expect(wordBox('Credits').style.getPropertyValue('--ff-nav-y')).toBe(opened.y);
    expect(wordBox('Credits').style.getPropertyValue('--ff-nav-radius')).toBe('0px');
  });

  it('answers keyboard focus and the preview tap with About’s voice, not a new one', () => {
    const tapped: string[] = [];
    const sound: PreviewSound = {
      muted: false, unlocked: true, unlock: vi.fn(),
      tap: vi.fn((voice?: string) => { tapped.push(String(voice)); return true; }),
      setMuted: vi.fn(), dispose: vi.fn(),
    };
    render(<RailNav current="home" sound={sound} onCurrentPagePress={vi.fn()} />);
    layout();
    fireEvent.keyDown(screen.getByRole('link', { name: 'Credits' }), { key: 'Tab' });
    fireEvent.focus(credit('Credits'));
    expect(credit('Credits')).toHaveAttribute('data-ff-nav', 'selected');
    // The circle opens from the middle of the word: a key has no entry point.
    expect(wordBox('Credits').style.getPropertyValue('--ff-nav-x')).toBe('150px');
    expect(tapped).toEqual(['about']);
  });

  it('leaves a modified press to the browser and holds no local state with it', () => {
    render(<RailNav current="home" sound={sound()} onCurrentPagePress={vi.fn()} />);
    layout();
    hover('Credits', 1020, 330);
    for (const detail of [{ metaKey: true }, { ctrlKey: true }, { shiftKey: true }, { altKey: true }, { button: 1 }]) {
      const click = new MouseEvent('click', { bubbles: true, cancelable: true, ...detail });
      fireEvent(credit('Credits'), click);
      expect(click.defaultPrevented).toBe(false);
    }
    expect(credit('Credits')).not.toHaveAttribute('data-ff-nav-held');
    unhover('Credits');
    expect(credit('Credits')).toHaveAttribute('data-ff-nav', 'rest');
  });
});

describe('moving to Credits', () => {
  it('claims the focus with its own heading only when the rail does not hold it', async () => {
    const vt = native();
    render(<Portfolio introEnabled={false} />);
    layout();
    // A press from the rail: the rail keeps focus, as it always has, so the new
    // page must not take it just because it arrived.
    const credits = credit('Credits');
    credits.focus();
    press('Credits');
    expect(creditsPage()).not.toBeNull();
    expect(credit('Credits')).toHaveAttribute('aria-current', 'page');
    expect(document.activeElement).toBe(credits);
    // The reveal is ours, so the browser was never asked for a capture.
    expect(vt.captures).toHaveLength(0);
  });

  it('claims its own heading when the control that was pressed is gone', async () => {
    const vt = native();
    render(<Portfolio introEnabled={false} />);
    await flush();
    // The exhibit's own view-project entry is the control that strands: it lives
    // inside the section Credits replaces, so nothing visible holds the focus by the
    // time the move commits and Credits' heading takes it. It is revealed by focus,
    // the way a keyboard or a visitor reaches it.
    const stranded = viewProject();
    stranded.focus();
    expect(document.activeElement).toBe(stranded);
    press('VIEW PROJECT');
    const enter = vt.last();
    expect(enter.kind).toBe('detail');
    await enter.capture(); await enter.finish();
    expect(creditsPage()).toBeNull();
    expect(document.activeElement).not.toBe(document.body);
    // Now the detail's own tool link, which the next route unmounts.
    const detailCta = screen.getByRole('link', { name: 'Open Plimsoll' });
    detailCta.focus();
    open(`#${PUBLIC_CREDITS_HASH}`);
    expect(creditsPage()).not.toBeNull();
    expect(document.activeElement).toBe(screen.getByRole('heading', { level: 1 }));
  });

  it('measures Credits as three sections and keeps every mark reachable', async () => {
    render(<Portfolio introEnabled={false} />);
    await flush();
    open(`#${PUBLIC_CREDITS_HASH}`);
    const ruler = screen.getByRole('navigation', { name: 'Reading position' });
    const marks = [...ruler.querySelectorAll<HTMLButtonElement>('.ff-ruler-mark')];
    // One mark per declared section, no more and no fewer, so every section is a
    // destination and none is a mark that points nowhere.
    expect(marks).toHaveLength(3);
    const sections = [...creditsPage()!.querySelectorAll<HTMLElement>('[data-ff-section]')];
    for (const [index, mark] of marks.entries()) {
      expect(mark).toHaveAttribute('type', 'button');
      // The mark names its own section, in the ruler's own words, and is placed on
      // the section rather than beside a guess of it.
      expect(mark.getAttribute('title')!.toUpperCase()).toContain(sections[index].dataset.ffSection!.toUpperCase());
      expect(mark.style.top).toMatch(/%$/);
    }
    // Every mark is a real button in the tab order that reaches its own heading, so
    // all three are usable however long the page is.
    for (const [index, mark] of marks.entries()) {
      fireEvent.click(mark);
      expect(document.activeElement).toBe(sections[index].querySelector('h2'));
    }
  });

  it('reaches Credits at once under reduced motion and still answers a preview', () => {
    preferences.set(reducedQuery, true);
    native();
    render(<Portfolio introEnabled={false} />);
    layout();
    hover('Credits', 1020, 330);
    expect(credit('Credits')).toHaveAttribute('data-ff-nav', 'selected');
    press('Credits');
    // No attribute, no clip and no rim: the page is simply there.
    expect(revealing()).toBeUndefined();
    expect(creditsPage()).not.toBeNull();
    expect(credit('Credits')).toHaveAttribute('aria-current', 'page');
    expect(credit('Credits')).not.toHaveAttribute('data-ff-nav-held');
    unhover('Credits');
    expect(credit('Credits')).toHaveAttribute('data-ff-nav', 'selected');
  });
});

describe('credits and the circular reveal', () => {
  it('uses the reveal from Work and hands it back, holding the word that was asked for', async () => {
    vi.useFakeTimers(); revealClock();
    // The controller only reaches for the reveal where the browser can snapshot at
    // all; without it the page is simply committed at once, which is the fallback
    // and not what this test is about.
    native();
    render(<Portfolio introEnabled={false} />);
    layout();
    hover('Credits', 1020, 330);
    const attained = wordBox('Credits').style.getPropertyValue('--ff-nav-radius');
    press('Credits');
    // The reveal is running and Credits is already the page under it.
    expect(revealing()).toMatch(/^circle\(/);
    expect(creditsPage()).not.toBeNull();
    expect(credit('Credits')).toHaveAttribute('data-ff-nav-held', 'true');
    expect(credit('Credits')).toHaveAttribute('aria-current', 'page');
    // The preview is not restarted by the move: the word keeps the blue it had.
    expect(wordBox('Credits').style.getPropertyValue('--ff-nav-radius')).toBe(attained);
    await act(async () => { vi.advanceTimersByTime(500); });
    expect(revealing()).toBeUndefined();
    expect(credit('Credits')).not.toHaveAttribute('data-ff-nav-held');
  });

  it('reveals Credits from the work detail without morphing the artwork', async () => {
    vi.useFakeTimers(); revealClock();
    const vt = native();
    open(`#${PUBLIC_WORK_DETAIL_HASH}`);
    render(<Portfolio introEnabled={false} />);
    await flush();
    const before = vt.captures.length;
    open(`#${PUBLIC_CREDITS_HASH}`);
    // The reveal, and nothing that names the artwork for a cut: no capture, no
    // attribute, and the detail's own drawing has gone with the detail.
    expect(revealing()).toMatch(/^circle\(/);
    expect(vt.captures).toHaveLength(before);
    expect(document.documentElement.dataset.ffTransition).toBeUndefined();
    expect(creditsPage()).not.toBeNull();
    // Read the live region by identity, not by class: while the reveal runs it
    // holds a copy of the page it departed, and that copy legitimately still shows
    // the detail. Only the region actually in the document has moved on.
    expect(liveMain().querySelector('.ff-detail-slot')).toBeNull();
    await act(async () => { vi.advanceTimersByTime(500); });
    expect(revealing()).toBeUndefined();
    const afterReveal = vt.captures.length;
    // The way back is the reveal as well: the drawing lives on Work, so a move that
    // starts on Credits has nothing to morph it with.
    open(`#${PUBLIC_WORK_DETAIL_HASH}`);
    expect(revealing()).toMatch(/^circle\(/);
    expect(vt.captures).toHaveLength(afterReveal);
    expect(document.documentElement.dataset.ffTransition).toBeUndefined();
    await act(async () => { vi.advanceTimersByTime(500); });
    // And with Credits left behind, the exhibit and its detail morph once more.
    open('#/work');
    await flush();
    press('VIEW PROJECT');
    expect(vt.last().kind).toBe('detail');
  });

  it('keeps the artwork morph for the move that does own it', async () => {
    const vt = native();
    render(<Portfolio introEnabled={false} />);
    await flush();
    press('VIEW PROJECT');
    const enter = vt.last();
    // Exhibit to detail is still the shared artwork morph, untouched by Credits.
    expect(enter.kind).toBe('detail');
    await enter.capture(); await enter.finish();
    expect(document.querySelector('.ff-detail-slot')).not.toBeNull();
    expect(document.querySelector('.ff-credits')).toBeNull();
  });
});

function sound(): PreviewSound {
  return { muted: true, unlocked: false, unlock: vi.fn(), tap: vi.fn().mockReturnValue(false), setMuted: vi.fn(), dispose: vi.fn() };
}

interface Capture { kind: string; skipped: boolean; capture: () => Promise<void>; finish: () => Promise<void> }

/**
 * The browser's own view transitions, captured rather than run.
 *
 * Only the moves that still use them — the artwork morph and the workspace — go
 * through `startViewTransition`; the circular reveal never does. So a move that
 * must commit under this stub is driven with `capture()`, which is what a real
 * capture would do: call the update callback.
 */
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
      update(); reject(new Error('skipped')); finish();
    } };
  });
  return { captures, last: () => captures[captures.length - 1] };
}
