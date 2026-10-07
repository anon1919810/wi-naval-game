import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Portfolio from '../portfolio/Portfolio';
import { classifyHash } from '../portfolio/routes';
import { storedTheme, THEME_KEY } from '../portfolio/theme';
import * as api from '../api';

/**
 * Cluster: the entry into the tool, and the header that carries it.
 *
 * What is checked here is behaviour a reader can lose: that the title really is
 * the link and the heading still says Plimsoll, that the action beside it appears
 * only for a reason and cannot swallow a press while hidden, that a pointer
 * crossing the gap keeps the title's own circle, that a modified press takes
 * nothing with it, and that there is no longer a SYSTEM mode, a footer replay or
 * a footer address.
 */

vi.mock('../api', async importOriginal => ({
  ...await importOriginal<typeof import('../api')>(),
  authConfig: vi.fn(), me: vi.fn(), bootstrapAnonymous: vi.fn(), listProjects: vi.fn(),
}));

const listeners = new Map<string, Set<(event: MediaQueryListEvent) => void>>();
const preferences = new Map<string, boolean>();

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
  // jsdom lays nothing out, so the two measurements the title entry depends on
  // are stated once and overridden per test: the word's box, and the real width
  // of its first glyph. A quarter of the word means the rule sits on the P.
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 0, 200, 60));
  vi.spyOn(document, 'createRange').mockReturnValue({
    setStart: () => {}, setEnd: () => {}, getBoundingClientRect: () => new DOMRect(0, 0, 50, 60),
  } as unknown as Range);
  vi.mocked(api.authConfig).mockResolvedValue({ mode: 'anonymous' });
  vi.mocked(api.me).mockResolvedValue({ id: 'existing', email: 'existing@anonymous.invalid', theme: 'light', csrf_token: 'test', mode: 'anonymous', label: '本浏览器工作区' });
  vi.mocked(api.listProjects).mockResolvedValue([]);
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

const flush = () => act(async () => {});
function hash(value: string) {
  act(() => { window.history.replaceState(null, '', `/${value}`); window.dispatchEvent(new HashChangeEvent('hashchange')); });
}
function follow(name: string) {
  const link = screen.getByRole('link', { name });
  const click = new MouseEvent('click', { bubbles: true, cancelable: true, button: 0 });
  let allowed = false;
  window.addEventListener('click', event => { allowed = !event.defaultPrevented; event.preventDefault(); }, { once: true });
  fireEvent(link, click);
  expect(allowed).toBe(true);
  hash(link.getAttribute('href')!);
}
/**
 * A pointer gesture, as the browser reports one.
 *
 * Entering and leaving are raised as `pointerover`/`pointerout`, which is what
 * React turns into its own enter/leave pair; the component then checks the
 * pointer type itself, exactly as it does for a real mouse.
 */
function enter(node: Element, extra: Record<string, unknown> = {}) {
  const event = new Event('pointerover', { bubbles: true });
  Object.assign(event, { pointerType: 'mouse', clientX: 40, clientY: 20, ...extra });
  fireEvent(node, event);
}
function leave(node: Element, extra: Record<string, unknown> = {}) {
  const event = new Event('pointerout', { bubbles: true });
  Object.assign(event, { pointerType: 'mouse', clientX: 400, clientY: 300, ...extra });
  fireEvent(node, event);
}

const titleLink = () => screen.getByRole('link', { name: 'Open Plimsoll' });
/**
 * The action while it is closed.
 *
 * `visibility: hidden` puts it out of the accessibility tree entirely, which is
 * the point — a hidden link with a name is a tab stop nobody can see. So while it
 * is closed it is addressed by its own node, and it is only ever queried by role
 * once the region has actually opened.
 */
const actionHidden = () => document.querySelector('.ff-title-action') as HTMLAnchorElement;
const actionLink = () => screen.getByRole('link', { name: 'VIEW PROJECT' });
const region = () => document.querySelector('.ff-title-region')!;
const wordOf = (link: HTMLElement) => link.querySelector('.ff-title-word') as HTMLElement;
const dupOf = (link: HTMLElement) => link.querySelector('.ff-title-dup') as HTMLElement;

describe('the title is the entry', () => {
  it('keeps the heading named Plimsoll and the link named Open Plimsoll', async () => {
    render(<Portfolio introEnabled={false} />);
    await flush();
    const heading = screen.getByRole('heading', { level: 1, name: 'Plimsoll' });
    expect(heading).toContainElement(titleLink());
    expect(titleLink()).toHaveAttribute('href', '#/plimsoll');
    // The visible spelling is unchanged: the accessible name adds a verb, the
    // word on the page is the word that was always there.
    expect(titleLink().textContent).toContain('Plimsoll');
    // Neither standalone button survives: there is one entry, not two.
    expect(screen.queryByRole('link', { name: /OPEN PLIMSOLL/ })).toBeNull();
    expect(document.querySelector('.ff-explore-link')).toBeNull();
    expect(document.querySelector('.ff-work-entries')).toBeNull();
    expect(api.authConfig).not.toHaveBeenCalled();
  });

  it('offers the detail on Work only, and the detail has no self-link', async () => {
    render(<Portfolio introEnabled={false} />);
    await flush();
    expect(actionHidden()).toHaveAttribute('href', '#/work/plimsoll');
    expect(actionHidden()).not.toContainElement(titleLink());
    // Open the region, so the action is in the accessibility tree to be followed.
    enter(region());
    follow('VIEW PROJECT');
    // On the detail the tool entry is the title, and there is nothing to offer
    // beside it: this page is already the detail.
    expect(titleLink()).toHaveAttribute('href', '#/plimsoll');
    expect(document.querySelector('.ff-detail .ff-title-action')).toBeNull();
  });

  it('warms the chunk on pointer and focus without mounting the tool', async () => {
    render(<Portfolio introEnabled={false} />);
    await flush();
    fireEvent.pointerEnter(titleLink()); fireEvent.focus(titleLink());
    await flush();
    expect(document.querySelector('.ff-tool-shell')).toBeNull();
    expect(api.authConfig).not.toHaveBeenCalled();
    expect(api.me).not.toHaveBeenCalled();
  });

  it('leaves a modified or middle press to the browser, holding nothing', async () => {
    render(<Portfolio introEnabled={false} />);
    await flush();
    const link = titleLink();
    for (const detail of [{ metaKey: true }, { ctrlKey: true }, { shiftKey: true }, { button: 1 }]) {
      const click = new MouseEvent('click', { bubbles: true, cancelable: true, button: 0, ...detail });
      fireEvent(link, click);
      expect(click.defaultPrevented).toBe(false);
    }
    // A tab opening elsewhere must not leave this tab's title accent behind.
    expect(link).not.toHaveAttribute('data-ff-title-held');
    expect(dupOf(link).style.opacity).toBe('');
  });

  it('holds its own preview for the move it asked for, and lets the address end it', async () => {
    const finished = new Promise<void>(() => {});
    (document as unknown as { startViewTransition: unknown }).startViewTransition = vi.fn(() => ({ ready: Promise.resolve(), finished, skipTransition: () => {} }));
    render(<Portfolio introEnabled={false} />);
    await flush();
    const link = titleLink();
    fireEvent.click(link);
    expect(link).toHaveAttribute('data-ff-title-held', 'true');
    // The address still names the tool, so the hold belongs to that move.
    hash('#/plimsoll');
    expect(link).toHaveAttribute('data-ff-title-held', 'true');
    // An address that goes somewhere else abandons the request at once.
    hash('#/about');
    expect(link).not.toHaveAttribute('data-ff-title-held');
  });
});

describe('the title preview', () => {
  it('opens from where the pointer went in and reverses on the way out', async () => {
    vi.useFakeTimers();
    render(<Portfolio introEnabled={false} />);
    await flush();
    const word = wordOf(titleLink());
    vi.spyOn(word, 'getBoundingClientRect').mockReturnValue(new DOMRect(10, 100, 200, 60));
    enter(region(), { clientX: 60, clientY: 110 });
    // The origin is the pointer's own entry point, in the word's own box.
    expect(word.style.getPropertyValue('--ff-title-x')).toBe('50px');
    expect(word.style.getPropertyValue('--ff-title-y')).toBe('10px');
    // The radius covers the far corner of the word, so the reveal ends exactly
    // when the word is accent, and the rule spans the whole word with it.
    expect(Number.parseFloat(word.style.getPropertyValue('--ff-title-radius'))).toBeGreaterThan(100);
    expect(word.style.getPropertyValue('--ff-title-rule')).toBe('1');
    leave(region());
    act(() => { vi.advanceTimersByTime(200); });
    expect(word.style.getPropertyValue('--ff-title-radius')).toBe('0px');
    expect(word.style.getPropertyValue('--ff-title-rule')).toBe('0.25');
  });

  it('shortens the rule onto the first glyph at rest, measured on the real text', async () => {
    render(<Portfolio introEnabled={false} />);
    await flush();
    // A quarter of the word: the rule sits on the first glyph, not the whole word.
    expect(wordOf(titleLink()).style.getPropertyValue('--ff-title-rule')).toBe('0.25');
  });

  it('keeps the origin and radius it has when a reversal is interrupted', async () => {
    render(<Portfolio introEnabled={false} />);
    await flush();
    const word = wordOf(titleLink());
    vi.spyOn(word, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 0, 200, 60));
    enter(region(), { clientX: 40, clientY: 20 });
    expect(word.style.getPropertyValue('--ff-title-x')).toBe('40px');
    // A circle that is already open: the preview is mid-flight.
    vi.spyOn(window, 'getComputedStyle').mockReturnValue({ clipPath: 'circle(120px at 40px 20px)' } as CSSStyleDeclaration);
    enter(region(), { clientX: 180, clientY: 50 });
    // The reversal aims the radius back from the origin it already has rather
    // than snapping to a new one: an interrupted preview must not jump.
    expect(word.style.getPropertyValue('--ff-title-x')).toBe('40px');
    expect(word.style.getPropertyValue('--ff-title-y')).toBe('20px');
    expect(Number.parseFloat(word.style.getPropertyValue('--ff-title-radius'))).toBeGreaterThan(100);
  });

  it('opens from the middle of the word for the keyboard', async () => {
    render(<Portfolio introEnabled={false} />);
    await flush();
    const word = wordOf(titleLink());
    vi.spyOn(word, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 0, 200, 60));
    fireEvent.focus(titleLink());
    expect(word.style.getPropertyValue('--ff-title-x')).toBe('100px');
    expect(word.style.getPropertyValue('--ff-title-y')).toBe('30px');
    // A key is a preview, and the region opens with it so the action is reachable.
    expect(region()).toHaveAttribute('data-ff-title-region', 'open');
  });

  it('only reddens the dot of the isolated i', async () => {
    render(<Portfolio introEnabled={false} />);
    await flush();
    const letters = titleLink().querySelectorAll('.ff-title-ink > span');
    // The word is split so the dot can be addressed; the rest of the letters are
    // in plain spans and are never given the band.
    expect(letters[1]).toHaveClass('ff-title-i');
    expect(letters[0]).not.toHaveClass('ff-title-i');
    expect(letters[2]).not.toHaveClass('ff-title-i');
    // The duplicate is where the band is, so the ink on the page never changes.
    const duplicate = dupOf(titleLink());
    expect(duplicate.querySelector('.ff-title-i')).not.toBeNull();
    expect(duplicate).toHaveAttribute('aria-hidden', 'true');
    expect(titleLink().querySelector('.ff-title-ink .ff-title-i')).toBeInTheDocument();
  });
});

describe('the action beside the title', () => {
  it('keeps the action visible while either keyboard focus or the pointer remains inside', async () => {
    vi.useFakeTimers();
    render(<Portfolio introEnabled={false} />);
    await flush();
    enter(region());
    act(() => actionHidden().focus());
    leave(region());
    act(() => vi.advanceTimersByTime(160));
    expect(document.activeElement).toBe(actionHidden());
    expect(actionHidden().style.visibility).toBe('visible');
    enter(region());
    act(() => actionHidden().blur());
    act(() => vi.advanceTimersByTime(160));
    expect(actionHidden().style.visibility).toBe('visible');
    leave(region());
    act(() => vi.advanceTimersByTime(160));
    expect(actionHidden().style.visibility).toBe('hidden');
  });

  it('is hidden at rest, out of the tab order and off the pointer', async () => {
    render(<Portfolio introEnabled={false} />);
    await flush();
    const action = actionHidden();
    // `visibility: hidden` is what removes it from the tab order and from hit
    // testing; it is not a zero-size box that can still swallow a press, and it
    // carries no accessible name while it is closed.
    expect(action.style.visibility).toBe('hidden');
    expect(screen.queryByRole('link', { name: 'VIEW PROJECT' })).toBeNull();
    // Open it, and it is an ordinary link with an ordinary name.
    enter(region());
    expect(action.style.visibility).toBe('visible');
    expect(screen.getByRole('link', { name: 'VIEW PROJECT' })).toBe(action);
  });

  it('appears for the pointer and for the keyboard, and disappears again', async () => {
    vi.useFakeTimers();
    render(<Portfolio introEnabled={false} />);
    await flush();
    const action = actionHidden();
    enter(region());
    expect(action.style.visibility).toBe('visible');
    // Leaving the whole region closes it after a delay, not on the same frame:
    // crossing the gap must not drop the title's own preview.
    leave(region());
    expect(action.style.visibility).toBe('visible');
    act(() => { vi.advanceTimersByTime(200); });
    expect(action.style.visibility).toBe('hidden');
  });

  it('retains the title preview while the pointer is over the action', async () => {
    render(<Portfolio introEnabled={false} />);
    await flush();
    const title = wordOf(titleLink());
    const actionWord = wordOf(actionHidden());
    vi.spyOn(title, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 0, 200, 60));
    vi.spyOn(actionWord, 'getBoundingClientRect').mockReturnValue(new DOMRect(240, 0, 120, 40));
    enter(region(), { clientX: 10, clientY: 30 });
    const held = title.style.getPropertyValue('--ff-title-radius');
    leave(titleLink(), { clientX: 250, clientY: 20, relatedTarget: actionHidden() });
    // The title's circle is untouched, and the action has its own: from its own
    // entry point (250-240, 20-0) to the far corner of a 120×40 word, hypot(110,20).
    expect(title.style.getPropertyValue('--ff-title-radius')).toBe(held);
    expect(Number.parseFloat(wordOf(actionHidden()).style.getPropertyValue('--ff-title-radius'))).toBeCloseTo(Math.hypot(110, 20), 2);
    expect(actionHidden()).toHaveAttribute('data-ff-title-action', 'preview');
  });

  it('previews from the middle of the word when the action is reached by keyboard', async () => {
    render(<Portfolio introEnabled={false} />);
    await flush();
    const action = actionHidden();
    const actionWord = wordOf(action);
    vi.spyOn(actionWord, 'getBoundingClientRect').mockReturnValue(new DOMRect(240, 0, 120, 40));
    fireEvent.focus(action);
    expect(actionWord.style.getPropertyValue('--ff-title-x')).toBe('60px');
    fireEvent.blur(action);
    expect(action).toHaveAttribute('data-ff-title-action', 'rest');
  });

  it('still reaches the detail through a press of its own', async () => {
    render(<Portfolio introEnabled={false} />);
    await flush();
    enter(region());
    follow('VIEW PROJECT');
    expect(classifyHash('#/work/plimsoll')).toEqual({ kind: 'public', view: 'project' });
    expect(document.querySelector('.ff-detail-slot')).not.toBeNull();
    expect(api.authConfig).not.toHaveBeenCalled();
  });
});

describe('the header', () => {
  it('draws the sound as a speaker and states its pressed truth', async () => {
    render(<Portfolio introEnabled={false} />);
    await flush();
    const sound = screen.getByRole('button', { name: 'Preview sound' });
    expect(sound).toHaveAttribute('aria-pressed', 'true');
    // A geometric speaker with one wave and a slash for mute: no text box.
    expect(sound.querySelector('svg')).not.toBeNull();
    expect(sound.textContent).toBe('');
    expect(sound.querySelector('.ff-preview-sound-slash')).not.toBeNull();
    fireEvent.click(sound);
    expect(screen.getByRole('button', { name: 'Preview sound' })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('button', { name: 'Preview sound' })).toHaveAttribute('title', 'Turn preview sound on');
  });

  it('offers one replay control in the header and none in the footer', async () => {
    render(<Portfolio introEnabled={false} />);
    await flush();
    const replay = screen.getByRole('button', { name: 'Replay intro' });
    expect(replay).toHaveAttribute('title', 'Replay intro');
    expect(replay.querySelector('svg')).not.toBeNull();
    expect(screen.getAllByRole('button', { name: 'Replay intro' })).toHaveLength(1);
    // The footer keeps only its two lines: the address lives in About, once.
    expect(document.querySelector('.ff-footer')!.textContent).toBe('BUILT BY YANG DUANMINGPRECISE. MODERN. INTERACTIVE.');
    expect(document.querySelector('.ff-footer a')).toBeNull();
    expect(document.querySelector('.ff-footer button')).toBeNull();
  });

  it('still replays the opening from the header control', async () => {
    render(<Portfolio />);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Replay intro' })).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'Replay intro' }));
    expect(screen.getByRole('status', { name: /Opening Y’s Formfield|Loading reference/ })).toBeInTheDocument();
  });

  it('has no SYSTEM mode, and a legacy stored one resolves to light', async () => {
    preferences.set('(prefers-color-scheme: dark)', true);
    localStorage.setItem(THEME_KEY, 'system');
    render(<Portfolio introEnabled={false} />);
    await flush();
    // Following the OS is gone: the preference is chosen here and kept.
    expect(screen.queryByRole('button', { name: /system/i })).toBeNull();
    expect(storedTheme()).toBe('light');
    expect(document.documentElement.dataset.theme).toBe('light');
    fireEvent.click(screen.getByRole('button', { name: 'Switch to dark theme' }));
    expect(localStorage.getItem(THEME_KEY)).toBe('dark');
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(api.authConfig).not.toHaveBeenCalled();
  });

  it('keeps a manual choice across a reload of the shell', async () => {
    localStorage.setItem(THEME_KEY, 'dark');
    const first = render(<Portfolio introEnabled={false} />);
    await flush();
    expect(document.documentElement.dataset.theme).toBe('dark');
    first.unmount();
    render(<Portfolio introEnabled={false} />);
    await flush();
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(screen.getByRole('button', { name: 'Switch to light theme' })).toBeInTheDocument();
  });
});
