import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Portfolio from '../portfolio/Portfolio';
import { classifyHash, PUBLIC_WORK_DETAIL_HASH, publicHref } from '../portfolio/routes';
import { REPORT_IMAGE } from '../portfolio/ProjectDetail';
import { CONTACT_EMAIL, CONTACT_PROFILE } from '../portfolio/Contact';
import { TRANSITION_MS, transitionsActive } from '../portfolio/transitions';
import { PLAN_SHEETS } from '../portfolio/plans';
import * as api from '../api';

vi.mock('../api', async importOriginal => ({
  ...await importOriginal<typeof import('../api')>(),
  authConfig: vi.fn(), me: vi.fn(), bootstrapAnonymous: vi.fn(), listProjects: vi.fn(),
}));

const mediaListeners = new Map<string, Set<(event: MediaQueryListEvent) => void>>();
const preferences = new Map<string, boolean>();
const reducedQuery = '(prefers-reduced-motion: reduce)';
const animations: { keyframes: unknown; options: KeyframeAnimationOptions }[] = [];

function media(reduced = false, dark = false) {
  mediaListeners.clear(); preferences.clear();
  preferences.set(reducedQuery, reduced);
  preferences.set('(prefers-color-scheme: dark)', dark);
  vi.stubGlobal('matchMedia', vi.fn((query: string) => {
    const handlers = mediaListeners.get(query) ?? new Set<(event: MediaQueryListEvent) => void>();
    mediaListeners.set(query, handlers);
    return {
      get matches() { return preferences.get(query) ?? false; }, media: query,
      addEventListener: (_: string, handler: (event: MediaQueryListEvent) => void) => { handlers.add(handler); },
      removeEventListener: (_: string, handler: (event: MediaQueryListEvent) => void) => { handlers.delete(handler); },
    };
  }));
}

beforeEach(() => {
  window.history.replaceState(null, '', '/');
  localStorage.clear();
  vi.clearAllMocks();
  animations.length = 0;
  delete (document as { startViewTransition?: unknown }).startViewTransition;
  media();
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
  cleanup(); vi.useRealTimers(); vi.unstubAllGlobals();
  delete (Element.prototype as { animate?: unknown }).animate;
  delete (document as { startViewTransition?: unknown }).startViewTransition;
});

const flush = () => act(async () => {});
/** replaceState avoids jsdom queuing a second, duplicate hashchange. */
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
/** A real anchor navigation the browser would have raised, observed the way a browser does. */
function open(hashValue: string) { window.history.replaceState(null, '', `/${hashValue}`); window.dispatchEvent(new HashChangeEvent('hashchange')); }

const detail = () => document.querySelector<HTMLElement>('.ff-detail-slot')!;
const homeVisible = () => !document.querySelector<HTMLElement>('.ff-home')!.hidden;
/** The detail and About mount only while they are the visible view. */
const detailVisible = () => detail() !== null;

describe('work detail routing', () => {
  it('owns exactly one public detail and leaves every application hash alone', () => {
    expect(classifyHash('#/work/plimsoll')).toEqual({ kind: 'public', view: 'project' });
    expect(classifyHash(`#${PUBLIC_WORK_DETAIL_HASH}`)).toEqual({ kind: 'public', view: 'project' });
    expect(PUBLIC_WORK_DETAIL_HASH).toBe('/work/plimsoll');
    // The detail must not swallow the application's own first segment, nor be
    // reachable by a first-segment match of its own.
    for (const hashValue of ['#/plimsoll', '#/projects', '#/projects/p1', '#/runs/r1', '#/reports/r1']) {
      expect(classifyHash(hashValue)).toEqual({ kind: 'app' });
    }
    // `#/work` stays the exhibit; an unknown sub-path of it falls back to Work
    // rather than resolving to a detail that does not exist.
    expect(classifyHash('#/work')).toEqual({ kind: 'public', view: 'home' });
    expect(classifyHash('#/work/plimsoll/extra')).toEqual({ kind: 'public', view: 'home' });
    expect(classifyHash('#/works')).toEqual({ kind: 'public', view: 'home' });
    expect(classifyHash('#/about')).toEqual({ kind: 'public', view: 'about' });
    expect(publicHref('project')).toBe('#/work/plimsoll');
  });

  it('offers the detail as a secondary entry and keeps the direct tool entry', async () => {
    render(<Portfolio introEnabled={false} />);
    await flush();
    const view = screen.getByRole('link', { name: /VIEW PROJECT/ });
    expect(view).toHaveAttribute('href', '#/work/plimsoll');
    // The two ways out stay visibly different classes, and only the framed block
    // carries the tool behaviour.
    expect(view).toHaveClass('ff-project-link');
    expect(view).not.toHaveClass('ff-explore-link');
    const open = screen.getByRole('link', { name: 'OPEN PLIMSOLL' });
    expect(open).toHaveClass('ff-explore-link');
    expect(open).toHaveAttribute('href', '#/plimsoll');
    expect(view.closest('.ff-work-entries')).toContainElement(open);
  });

  it('opens the detail from a deep link without the intro, the tool or any API call', async () => {
    open(`#${PUBLIC_WORK_DETAIL_HASH}`);
    render(<Portfolio />);
    expect(detailVisible()).toBe(true);
    expect(screen.getByRole('heading', { level: 1, name: 'Plimsoll' })).toBeVisible();
    // A direct deep link is not a visit to the exhibit, so the opening never runs.
    expect(screen.queryByRole('status', { name: 'Opening Y’s Formfield' })).toBeNull();
    expect(screen.queryByRole('status', { name: 'Loading reference' })).toBeNull();
    expect(document.querySelector('.ff-tool-shell')).toBeNull();
    expect(document.title).toBe('Plimsoll — Y’s Formfield');
    // Work stays the current rail item: the detail belongs to Work, not to About.
    expect(screen.getByRole('link', { name: 'Work 01' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: 'About' })).not.toHaveAttribute('aria-current');
    await flush();
    expect(api.authConfig).not.toHaveBeenCalled();
    expect(api.me).not.toHaveBeenCalled();
    expect(api.bootstrapAnonymous).not.toHaveBeenCalled();
    expect(api.listProjects).not.toHaveBeenCalled();
  });
});

describe('work detail content', () => {
  beforeEach(async () => {
    open(`#${PUBLIC_WORK_DETAIL_HASH}`);
    render(<Portfolio />);
    await flush();
  });

  it('reads as numbered editorial sections with the report screenshot in the workflow', () => {
    const heads = screen.getAllByRole('heading', { level: 2 }).map(node => node.textContent);
    expect(heads.filter(text => /^\d\d/.test(text ?? ''))).toEqual(['01Overview', '02Capabilities', '03Workflow', '04Technology', '05Methods & Limits']);
    // The real report, at the file's own intrinsic size and with real alt text.
    const image = screen.getByRole('img', { name: /Plimsoll calculation report/ }) as HTMLImageElement;
    expect(image.getAttribute('src')).toBe(REPORT_IMAGE.src);
    expect(REPORT_IMAGE.src).toBe('/portfolio/plimsoll-report.jpg');
    expect(image).toHaveAttribute('width', String(REPORT_IMAGE.width));
    expect(image).toHaveAttribute('height', String(REPORT_IMAGE.height));
    expect(image.getAttribute('alt')).toBeTruthy();
    // The caption claims the screenshot honestly and exposes no file path.
    const caption = document.querySelector('.ff-report figcaption')!.textContent!;
    expect(caption).toMatch(/captured on 4 October 2026/);
    expect(caption).toMatch(/without recalculating/);
    expect(caption).not.toMatch(/docs\/|\.jpg/);
    // No visitor-visible file paths anywhere on the page.
    expect(detail().textContent).not.toMatch(/docs\/plimsoll|\.json|\.py\b/);
  });

  it('states the manifest stack, the capabilities and the method limits without overclaiming', () => {
    const text = detail().textContent!;
    // Technology: what the actual manifests declare, each with its use.
    for (const row of ['A React and TypeScript interface built with Vite', 'Python calculation core', 'FastAPI serves the application; SQLAlchemy manages stored data, and Alembic versions the database schema.', 'PostgreSQL', 'Independent worker']) {
      expect(text).toContain(row);
    }
    // Capabilities, in the approved wording.
    expect(text).toContain('Draft, trim and heel calculations with liquid-load effects, GM and sampled GZ curves, including opening-immersion checks.');
    expect(text).toContain('Edit the ship’s inputs while retaining source and estimate information. Missing data stays explicit.');
    expect(text).toMatch(/Taylor-Gertler, Schoenherr, Holtrop-Mennen/);
    // Limits are stated, not implied.
    expect(text).toContain('Not a full SPS reproduction');
    expect(text).toMatch(/no armour penetration, no explosion and no CFD/);
    expect(text).toContain('Full seakeeping, structural strength, historical cost and combat damage simulation are not modelled.');
    expect(text).toContain('Not a certified design tool');
    // The Overview no longer repeats a negative SPS claim, and nothing on the
    // page claims equivalence, certification or a repository.
    const overview = document.querySelector('#ff-detail-01')!.parentElement!.textContent!;
    expect(overview).not.toMatch(/SPS/);
    expect(text).not.toMatch(/github\.com\/anon1919810|certified by|ISO|class-approved|exceeds SPS/);
    // The negative SPS claim lives in exactly one row of one section, counted
    // here so a future edit cannot quietly repeat it across the page.
    const limits = document.querySelector('#ff-detail-05')!.parentElement!.textContent!;
    expect(limits.match(/SPS/g)).toHaveLength(3);
    for (const other of ['01', '02', '03', '04']) {
      expect(document.querySelector(`#ff-detail-${other}`)!.parentElement!.textContent).not.toMatch(/SPS/);
    }
  });

  it('reuses the exhibit’s selected drawing as its hero, and the sheet picker still drives it', async () => {
    // The hero really is the same composition the exhibit shows, not a redraw.
    const hero = detail().querySelector('.ff-art-scene')!;
    expect(hero.querySelector('.ff-vessel')!.getAttribute('data-study')).toBe(PLAN_SHEETS[0].id);
    expect(hero.querySelectorAll('image')).toHaveLength(1);
    expect(hero.querySelector('image')!.getAttribute('href')).toBe(PLAN_SHEETS[0].href);
    expect(detail().textContent).toContain(`REFERENCE ${PLAN_SHEETS[0].id} / SAME DRAWING AS THE EXHIBIT`);
  });

  it('keeps a working way into the tool and a way back to the exhibit', async () => {
    const back = screen.getByRole('link', { name: /BACK TO WORK/ });
    expect(back).toHaveAttribute('href', '#/work');
    const cta = screen.getByRole('link', { name: 'OPEN PLIMSOLL' });
    expect(cta).toHaveAttribute('href', '#/plimsoll');
    expect(cta).toHaveClass('ff-explore-link');
    // The detail's own CTA warms the chunk on hover without mounting anything.
    fireEvent.pointerEnter(cta); fireEvent.focus(cta); await flush();
    expect(document.querySelector('.ff-tool-shell')).toBeNull();
    expect(api.authConfig).not.toHaveBeenCalled();
    // And a modified click is left to the browser.
    for (const extra of [{ metaKey: true }, { button: 1 }]) {
      const click = new MouseEvent('click', { bubbles: true, cancelable: true, button: 0, ...extra });
      fireEvent(cta, click);
      expect(click.defaultPrevented).toBe(false);
    }
  });
});

describe('home and detail navigation', () => {
  interface Capture { kind: string; skipped: boolean; capture: () => Promise<void>; finish: () => Promise<void> }
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
  const pan = () => document.querySelector('.ff-layer-vessel')!.getAttribute('transform');
  const sample = () => document.querySelector('.ff-lens-view')?.getAttribute('viewBox');

  it('does not cancel a pending tool entry when the same link is activated twice', async () => {
    const vt = native();
    render(<Portfolio introEnabled={false} />);
    await flush();
    follow('OPEN PLIMSOLL');
    const entry = vt.last();
    // A second anchor activation at the same hash raises no hashchange.
    window.addEventListener('click', event => event.preventDefault(), { once: true });
    fireEvent.click(screen.getByRole('link', { name: 'OPEN PLIMSOLL' }));
    expect(entry.skipped).toBe(false);
    await entry.capture(); await entry.finish();
    await screen.findByTitle('本浏览器工作区');
    expect(window.location.hash).toBe('#/plimsoll');
    expect(document.querySelector('.ff-tool-shell')).toBeVisible();
  });

  it.each(['theme', 'system', 'reduced motion', 'OS theme'])('settles requested navigation when %s interrupts its capture', async mode => {
    if (mode === 'OS theme') localStorage.setItem('formfield-theme', 'system');
    const vt = native();
    render(<Portfolio introEnabled={false} />);
    await flush();
    follow('VIEW PROJECT');
    const enter = vt.last();
    expect(homeVisible()).toBe(true);
    if (mode === 'theme') fireEvent.click(screen.getByRole('button', { name: 'Switch to dark theme' }));
    else if (mode === 'system') fireEvent.click(screen.getByRole('button', { name: /system/i }));
    else {
      const query = mode === 'reduced motion' ? reducedQuery : '(prefers-color-scheme: dark)';
      preferences.set(query, true);
      act(() => mediaListeners.get(query)?.forEach(listener => listener({ matches: true } as MediaQueryListEvent)));
    }
    expect(window.location.hash).toBe('#/work/plimsoll');
    expect(detailVisible()).toBe(true);
    await enter.capture(); await enter.finish();
    if (vt.last() !== enter) { await vt.last().capture(); await vt.last().finish(); }
    expect(detailVisible()).toBe(true);
    expect(homeVisible()).toBe(false);
    expect(api.authConfig).not.toHaveBeenCalled();
  });

  it('morphs the shared artwork for 400 ms and names only a visible node', async () => {
    const vt = native();
    render(<Portfolio introEnabled={false} />);
    await flush();
    // Only the visible view is mounted, so there is exactly one artwork node and
    // no hidden copy that could take the same view-transition-name.
    const scenes = () => [...document.querySelectorAll<HTMLElement>('.ff-art-scene')].filter(node => !node.closest('[hidden]'));
    expect(scenes()).toHaveLength(1);
    expect(scenes()[0].closest('.ff-home')).not.toBeNull();

    follow('VIEW PROJECT');
    const enter = vt.last();
    expect(enter.kind).toBe('detail');
    expect(TRANSITION_MS.detail).toBe(400);
    // The attribute exists for the whole transition, which is what the scoped
    // view-transition-name rules key off.
    expect(document.documentElement.dataset.ffTransition).toBe('detail');
    await enter.capture();
    expect(detailVisible()).toBe(true);
    expect(homeVisible()).toBe(false);
    // After the swap the one scene is the detail's, and it is the same drawing the
    // exhibit was showing: the morph travels between two instances of one image.
    expect(scenes()).toHaveLength(1);
    expect(scenes()[0].closest('.ff-detail-slot')).not.toBeNull();
    expect(scenes()[0].querySelector('.ff-vessel')!.getAttribute('data-study')).toBe(PLAN_SHEETS[0].id);
    expect(scenes()[0].querySelector('image')!.getAttribute('href')).toBe(PLAN_SHEETS[0].href);
    // One body group, and only the detail has one.
    expect(document.querySelectorAll('.ff-detail-body')).toHaveLength(1);
    expect(document.querySelectorAll('.ff-home .ff-detail-body')).toHaveLength(0);
    await enter.finish();
    expect(document.documentElement.dataset.ffTransition).toBeUndefined();
    expect(transitionsActive()).toBe(false);
    // No JS keyframes drive this cut: the morph is the browser's own, so the Web
    // Animations API is not used for it.
    expect(animations).toHaveLength(0);
  });

  it('preserves exploration, settings and scroll across home to detail and back', async () => {
    const vt = native();
    render(<Portfolio introEnabled={false} />);
    await flush();
    fireEvent.click(screen.getByRole('button', { name: PLAN_SHEETS[1].label }));
    await flush();
    await vt.last().capture(); await vt.last().finish();
    fireEvent.click(screen.getByRole('button', { name: 'Geometry On' }));
    fireEvent.click(screen.getByRole('button', { name: 'Inspect Off' }));
    const exhibit = screen.getByRole('group', { name: /Interactive top-view/ });
    vi.spyOn(exhibit, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 0, 800, 350));
    fireEvent.keyDown(exhibit, { key: 'ArrowRight' });
    const keptPan = pan();
    fireEvent.keyDown(exhibit, { key: 'ArrowRight' });
    const keptSample = sample();
    vi.mocked(window.scrollTo as ReturnType<typeof vi.fn>).mockClear();
    Object.defineProperty(window, 'scrollY', { value: 240, configurable: true, writable: true });

    follow('VIEW PROJECT');
    await vt.last().capture(); await vt.last().finish();
    // A long page must not leave the reader halfway down it.
    expect(window.scrollTo).toHaveBeenLastCalledWith({ top: 0, behavior: 'auto' });
    // The drawing the visitor chose is the one the hero shows.
    expect(detail().querySelector('.ff-vessel')!.getAttribute('data-study')).toBe(PLAN_SHEETS[1].id);

    follow('BACK TO WORK');
    await vt.last().capture(); await vt.last().finish();
    expect(homeVisible()).toBe(true);
    expect(detailVisible()).toBe(false);
    // The exhibit came back exactly as it was left.
    expect(screen.getByRole('button', { name: PLAN_SHEETS[1].label })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'Geometry Off' })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('button', { name: 'Inspect On' })).toHaveAttribute('aria-pressed', 'true');
    expect(pan()).toBe(keptPan);
    expect(sample()).toBe(keptSample);
    // And its own scroll position, not the top of the page.
    expect(window.scrollTo).toHaveBeenLastCalledWith({ top: 240, behavior: 'auto' });
    expect(api.listProjects).not.toHaveBeenCalled();
  });

  it('keeps Back and Forward working through the detail', async () => {
    const vt = native();
    render(<Portfolio introEnabled={false} />);
    await flush();
    follow('VIEW PROJECT');
    await vt.last().capture(); await vt.last().finish();
    expect(detailVisible()).toBe(true);
    // Back, as the browser raises it: one hashchange, one transition, one commit.
    hash('#/work');
    const back = vt.last();
    expect(back.kind).toBe('detail');
    await back.capture(); await back.finish();
    expect(homeVisible()).toBe(true);
    expect(detailVisible()).toBe(false);
    // Forward again.
    hash(`#${PUBLIC_WORK_DETAIL_HASH}`);
    const forward = vt.last();
    expect(forward.kind).toBe('detail');
    await forward.capture(); await forward.finish();
    expect(detailVisible()).toBe(true);
    expect(document.title).toBe('Plimsoll — Y’s Formfield');
    expect(screen.getByRole('link', { name: 'Work 01' })).toHaveAttribute('aria-current', 'page');
  });

  it('retires a superseded detail cut so a late callback cannot strand the page', async () => {
    const vt = native();
    render(<Portfolio introEnabled={false} />);
    await flush();
    follow('VIEW PROJECT');
    const first = vt.last();
    // A second navigation before the first finished: latest wins.
    follow('About');
    expect(first.skipped).toBe(true);
    expect(document.documentElement.dataset.ffTransition).toBeUndefined();
    await first.capture(); await first.finish();
    // The abandoned cut never committed, so About is the page on screen and the
    // detail never appeared at all — not even its hidden section.
    expect(screen.getByRole('heading', { name: /A field for/ })).toBeVisible();
    expect(detailVisible()).toBe(false);
    await vt.last().capture(); await vt.last().finish();
    // The detail cut left no attribute of its own. The page cut owns a short
    // timer of its own, and it releases itself when it expires.
    expect(document.documentElement.dataset.ffTransition).toBeUndefined();
    await waitFor(() => expect(document.documentElement.dataset.ffPage).toBeUndefined());
    expect(transitionsActive()).toBe(false);
  });

  it('claims focus only when the clicked control is hidden by the new page', async () => {
    const vt = native();
    render(<Portfolio introEnabled={false} />);
    await flush();
    // Work/About is the content-only cut: it sets one attribute and never starts a
    // view transition, so there is no capture to drive here.
    const about = screen.getByRole('link', { name: 'About' });
    about.focus();
    follow('About');
    expect(document.documentElement.dataset.ffPage).toBe('in');
    expect(vt.captures).toHaveLength(0);
    // The rail is a sibling of main, so it keeps its own focus across the change.
    expect(document.activeElement).toBe(about);
    // Coming back through the exhibit, nothing visible took the rail away, so
    // focus is still there and the exhibit does not steal it.
    follow('Work 01');
    expect(document.documentElement.dataset.ffPage).toBe('out');
    expect(document.activeElement).toBe(about);
    // Entering the detail from the exhibit does strand the VIEW PROJECT link — it
    // is inside the section that gets hidden — so the new page's heading takes it.
    screen.getByRole('link', { name: /VIEW PROJECT/ }).focus();
    expect(document.activeElement).not.toBe(document.body);
    follow('VIEW PROJECT');
    await vt.last().capture(); await vt.last().finish();
    expect(document.activeElement).toBe(screen.getByRole('heading', { level: 1, name: 'Plimsoll' }));
  });

  it('returns from the tool to the page the visitor actually left', async () => {
    const vt = native();
    render(<Portfolio introEnabled={false} />);
    await flush();
    follow('VIEW PROJECT');
    await vt.last().capture(); await vt.last().finish();
    follow('OPEN PLIMSOLL');
    await vt.last().capture(); await vt.last().finish();
    await screen.findByTitle('本浏览器工作区');
    // The way out points at the detail, not at a hardcoded exhibit.
    const back = screen.getByRole('link', { name: '↖ Y’s Formfield' });
    expect(back).toHaveAttribute('href', '#/work/plimsoll');
    follow('↖ Y’s Formfield');
    await vt.last().capture(); await vt.last().finish();
    expect(detailVisible()).toBe(true);
    expect(document.documentElement.dataset.formfieldSurface).toBe('public');
    // Focus is never left invisible: whatever holds it is on the page that came
    // back, and the public shell is showing again.
    const held = document.activeElement as HTMLElement;
    expect(held.closest('[hidden]')).toBeNull();
    expect(detail().contains(held)).toBe(true);
    // Returning to a public page never replays the opening.
    expect(screen.queryByRole('status', { name: 'Opening Y’s Formfield' })).toBeNull();
    expect(screen.queryByRole('status', { name: 'Loading reference' })).toBeNull();
  });

  it('restores the way out of the exhibit when the tool is left with nothing else holding focus', async () => {
    const vt = native();
    render(<Portfolio introEnabled={false} />);
    await flush();
    follow('OPEN PLIMSOLL');
    await vt.last().capture(); await vt.last().finish();
    await screen.findByTitle('本浏览器工作区');
    // A return that leaves the page without a visible focus holder is the case the
    // controller has to repair: the CTA becomes the focus so the visitor can go
    // straight back in.
    (document.activeElement as HTMLElement | null)?.blur();
    expect(document.activeElement).toBe(document.body);
    follow('↖ Y’s Formfield');
    await vt.last().capture(); await vt.last().finish();
    expect(document.activeElement).toBe(screen.getByRole('link', { name: 'OPEN PLIMSOLL' }));
  });

  it('navigates immediately under reduced motion and leaves nothing named behind', async () => {
    preferences.set(reducedQuery, true);
    const vt = native();
    render(<Portfolio introEnabled />);
    await flush();
    expect(screen.queryByRole('status')).toBeNull();
    follow('VIEW PROJECT');
    // The feature is available, but the preference is not ignored.
    expect(vt.captures).toHaveLength(0);
    expect(detailVisible()).toBe(true);
    expect(document.documentElement.dataset.ffTransition).toBeUndefined();
    follow('BACK TO WORK');
    expect(homeVisible()).toBe(true);
    expect(document.documentElement.dataset.ffTransition).toBeUndefined();
    expect(animations).toHaveLength(0);
  });

  it('commits the detail immediately where the browser has no view transitions', async () => {
    // No startViewTransition at all: the fallback must still reach the same page.
    render(<Portfolio introEnabled={false} />);
    await flush();
    follow('VIEW PROJECT');
    expect(detailVisible()).toBe(true);
    expect(document.documentElement.dataset.ffTransition).toBeUndefined();
    expect(transitionsActive()).toBe(false);
    follow('BACK TO WORK');
    expect(homeVisible()).toBe(true);
    await waitFor(() => expect(api.authConfig).not.toHaveBeenCalled());
    expect(api.me).not.toHaveBeenCalled();
    expect(api.bootstrapAnonymous).not.toHaveBeenCalled();
  });
});

describe('about and contact', () => {
  it('keeps the existing About heading and intro on the same public primitives', async () => {
    // The existing suites match this heading and the shared primitives it uses, so
    // the extraction must not rename them or restyle them into something else.
    open('#/about');
    const { container } = render(<Portfolio />);
    await flush();
    const about = container.querySelector('.ff-about')!;
    expect(about.tagName).toBe('ARTICLE');
    // `.ff-about`, `.ff-eyebrow` and `.ff-about-work` are the shell's own classes
    // and are declared in portfolio.css, not re-declared here.
    expect(about.querySelector('.ff-eyebrow')).not.toBeNull();
    expect(about.querySelector('.ff-about-work')).not.toBeNull();
    expect(about.parentElement).toHaveClass('ff-about-slot');
    expect(about.querySelector('h1')!.textContent).toBe('A field foruseful ideas.');
    // The new content hangs off the same article rather than replacing it.
    expect(about.querySelector('.ff-about-author')).not.toBeNull();
    expect(about.querySelector('.ff-about-built')).not.toBeNull();
    expect(about.querySelector('.ff-contact')).not.toBeNull();
  });

  it('names the author, the direction, what this site is built from, and a real contact route', async () => {
    open('#/about');
    render(<Portfolio />);
    await flush();
    const text = (document.querySelector('.ff-about-slot') as HTMLElement).textContent!;
    expect(text).toContain('Yang Duanming');
    expect(text).toContain('tools and experiments');
    expect(text).toMatch(/Built with/i);
    expect(text).toContain('Space Grotesk');
    expect(text).toContain('Inter');
    // The honest boundary about what this site does: it never reaches the tool.
    expect(text).toMatch(/No API on this site/i);
    expect(text).toMatch(/never call the Plimsoll service and never create a workspace/);
    // The work entry now reads the project first.
    const project = screen.getByRole('link', { name: /VIEW THE PROJECT/ });
    expect(project).toHaveAttribute('href', '#/work/plimsoll');
    // No invented biography and no contact form.
    expect(text).not.toMatch(/<form|form action|President|University|PhD|founded in \d{4}/i);
  });

  it('reaches the author by a real mailto and the public profile, whatever the clipboard does', async () => {
    open('#/about');
    render(<Portfolio />);
    await flush();
    const mail = screen.getByRole('link', { name: CONTACT_EMAIL });
    expect(mail).toHaveAttribute('href', `mailto:${CONTACT_EMAIL}`);
    expect(CONTACT_EMAIL).toBe('youxiang051110@163.com');
    const profile = screen.getByRole('link', { name: /GITHUB/ });
    expect(profile).toHaveAttribute('href', CONTACT_PROFILE);
    expect(CONTACT_PROFILE).toBe('https://github.com/anon1919810');
    expect(profile).toHaveAttribute('rel', expect.stringContaining('noopener'));
  });

  it.each([
    ['resolves', () => vi.fn().mockResolvedValue(undefined), true],
    ['rejects', () => vi.fn().mockRejectedValue(new Error('denied')), false],
  ])('shows copied only after the clipboard write %s', async (mode, factory, copied) => {
    const writeText = factory();
    vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText } });
    open('#/about');
    render(<Portfolio />);
    await flush();
    // Nothing is claimed before the visitor asks for it.
    expect(screen.queryByRole('status')).toBeNull();
    expect(screen.queryByRole('alert')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'COPY EMAIL' }));
    await act(async () => {});
    expect(writeText).toHaveBeenCalledWith(CONTACT_EMAIL);
    if (copied) {
      expect(screen.getByRole('status')).toHaveTextContent(`COPIED — ${CONTACT_EMAIL} is on your clipboard.`);
      expect(screen.queryByRole('alert')).toBeNull();
    } else {
      // A rejected write must never claim success, and the way out stays the link.
      expect(screen.queryByRole('status')).toBeNull();
      const alert = screen.getByRole('alert');
      expect(alert).toHaveTextContent('NOT COPIED');
      expect(alert).toHaveTextContent('did not give the page clipboard access');
      expect(screen.getByRole('link', { name: CONTACT_EMAIL })).toBeVisible();
    }
  });

  it('survives a browser with no clipboard API and can be retried', async () => {
    vi.stubGlobal('navigator', { ...navigator, clipboard: undefined });
    open('#/about');
    render(<Portfolio />);
    await flush();
    fireEvent.click(screen.getByRole('button', { name: 'COPY EMAIL' }));
    await act(async () => {});
    expect(screen.getByRole('alert')).toHaveTextContent('NOT COPIED');
    // Retrying with a working clipboard is allowed and is the only way to get Copied.
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText } });
    fireEvent.click(screen.getByRole('button', { name: 'COPY EMAIL' }));
    await act(async () => {});
    expect(screen.getByRole('status')).toHaveTextContent('COPIED');
    expect(screen.queryByRole('alert')).toBeNull();
  });
});
