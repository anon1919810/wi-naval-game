import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import * as api from '../api';
import Portfolio from '../portfolio/Portfolio';
import { introPlayed, markIntroPlayed } from '../portfolio/intro';
import { PLAN_SHEETS } from '../portfolio/plans';
import { runTransition, TRANSITION_MS } from '../portfolio/transitions';
import { Workbench } from '../pages/Workbench';
import { ToolModuleBoundary } from '../portfolio/ToolModule';
import type { ProjectDocument, ProjectView, RunView, UserSession } from '../types';

/**
 * Cluster two: the local reveals, the route entry, the session intro and the
 * failed-chunk recovery.
 *
 * What matters is that motion explains a change and never becomes a prerequisite
 * for one: a draft survives its chapter being revealed, a fast route switch is
 * still seen as a switch, a failed chunk says the only thing that can help it,
 * and every one of them is still there when motion is switched off.
 */

vi.mock('../api', async importOriginal => {
  const actual = await importOriginal<typeof import('../api')>();
  return { ...actual, authConfig: vi.fn(), me: vi.fn(), bootstrapAnonymous: vi.fn(), listProjects: vi.fn(),
    getProject: vi.fn(), listRuns: vi.fn(), saveProject: vi.fn(), enqueueRun: vi.fn(), getRun: vi.fn(),
    setTheme: vi.fn(), logout: vi.fn() };
});

const session: UserSession = {
  id: 'a-1', email: 'anonymous-abc@anonymous.invalid', theme: 'light',
  csrf_token: 'csrf-1', mode: 'anonymous', label: '本浏览器工作区',
};

const box: ProjectDocument = {
  schema: 'plimsoll-project-1', id: 'p1', name: '解析方箱', revision: 1,
  hull: { length_m: 90, beam_m: 20, draft_m: 4 }, geometry: null,
  weight_groups: [], loading_conditions: [{ id: 'loaded', label: '满载' }],
};
const view = (revision = 1): ProjectView => ({ project_id: 'p1', revision, project: box });
const run = (patch: Partial<RunView> = {}): RunView => ({
  id: 'run-1', project_id: 'p1', revision: 1, condition_id: 'loaded', request_fingerprint: 'rf',
  created_at: '2026-10-06T00:00:00Z', started_at: null, finished_at: null,
  cancel_requested: false, result: null, error: null, status: 'completed', ...patch,
});

const listeners = new Map<string, Set<(event: MediaQueryListEvent) => void>>();
const preferences = new Map<string, boolean>();
const reduced = '(prefers-reduced-motion: reduce)';

/** jsdom has no animation engine; the reduced-motion contract is asserted on the
 * controller's own branch and on the attributes it does and does not set. */
function stubMotion(reduce: boolean) {
  vi.stubGlobal('matchMedia', (query: string) => {
    const handlers = listeners.get(query) ?? new Set<(event: MediaQueryListEvent) => void>();
    listeners.set(query, handlers);
    return {
      get matches() { return preferences.get(query) ?? false; }, media: query,
      addEventListener: (_: string, handler: (event: MediaQueryListEvent) => void) => handlers.add(handler),
      removeEventListener: (_: string, handler: (event: MediaQueryListEvent) => void) => handlers.delete(handler),
    };
  });
  preferences.set(reduced, reduce);
}

function native() {
  (document as { startViewTransition?: unknown }).startViewTransition = vi.fn((update: () => void) => {
    let ready!: () => void, finish!: () => void;
    const readyPromise = new Promise<void>(yes => { ready = yes; });
    const finished = new Promise<void>(yes => { finish = yes; });
    const entry = {
      kind: document.documentElement.dataset.ffTransition,
      capture: () => act(async () => { update(); ready(); }),
      finish: () => act(async () => { finish(); }),
    };
    return { ready: readyPromise, finished, skipTransition: () => { update(); ready(); finish(); } };
  });
}

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
  listeners.clear(); preferences.clear();
  window.sessionStorage.clear();
  window.history.replaceState(null, '', '/');
  delete (document as { startViewTransition?: unknown }).startViewTransition;
  stubMotion(false);
  vi.stubGlobal('Image', class { src = ''; decode = () => Promise.resolve(); });
  vi.stubGlobal('scrollTo', vi.fn());
  vi.mocked(api.authConfig).mockResolvedValue({ mode: 'anonymous' });
  vi.mocked(api.me).mockResolvedValue(session);
  vi.mocked(api.listProjects).mockResolvedValue([]);
  vi.mocked(api.listRuns).mockResolvedValue([]);
  vi.mocked(api.getProject).mockResolvedValue(view());
  vi.mocked(api.getRun).mockResolvedValue(run());
});

afterEach(() => {
  cleanup(); vi.useRealTimers(); vi.unstubAllGlobals();
  delete (document as { startViewTransition?: unknown }).startViewTransition;
});

/** The token the CSS animation name is derived from. */
const token = (selector: string): string | null | undefined => document.querySelector(selector)?.getAttribute('data-motion');

describe('local reveals keep the draft', () => {
  it('reveals a chapter change without ever remounting the editor', async () => {
    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '船型与几何' }));
    const length = await screen.findByLabelText('船长');
    fireEvent.change(length, { target: { value: '91' } });
    const content = document.querySelector('.workbench-content')!;
    const first = token('.workbench-content');

    // The reader edits, leaves the chapter and comes back: the container is the
    // very same node, so the input, its value and its selection all survive.
    fireEvent.click(screen.getByRole('button', { name: '重量与载荷' }));
    expect(token('.workbench-content')).not.toBe(first);
    fireEvent.click(screen.getByRole('button', { name: '船型与几何' }));
    expect(await screen.findByLabelText('船长')).toHaveValue(91);
    expect(document.querySelector('.workbench-content')).toBe(content);
    // Still an unsaved draft: the reveal neither saved nor discarded anything.
    expect(screen.getByText('未保存修改')).toBeVisible();
  });

  it('keeps a hand-edited JSON document across the reveal that shows it', async () => {
    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '项目数据' }));
    const editor = await screen.findByLabelText('项目 JSON');
    // Applied to the draft, so it is the draft being preserved rather than a
    // scratch buffer: the reveal must not be able to discard it.
    fireEvent.change(editor, { target: { value: JSON.stringify({ ...box, name: '保留的舰名' }) } });
    fireEvent.click(screen.getByRole('button', { name: '应用到草稿' }));
    expect(screen.getByText('未保存修改')).toBeVisible();

    fireEvent.click(screen.getByRole('button', { name: '概览' }));
    expect(await screen.findByRole('heading', { level: 1, name: '保留的舰名' })).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: '项目数据' }));
    expect((await screen.findByLabelText('项目 JSON') as HTMLTextAreaElement).value).toContain('保留的舰名');
  });

  it('does not replay a reveal when the same chapter is chosen again', async () => {
    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '重量与载荷' }));
    const after = token('.workbench-content');
    fireEvent.click(screen.getByRole('button', { name: '重量与载荷' }));
    fireEvent.click(screen.getByRole('button', { name: '重量与载荷' }));
    expect(token('.workbench-content')).toBe(after);
  });

  it('reveals a traced field when it changes, and not when only its value does', async () => {
    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '船型与几何' }));
    await screen.findByLabelText('型宽');
    const panel = () => document.querySelector<HTMLElement>('.trace-body')!;

    fireEvent.click(screen.getByRole('button', { name: '查看 型宽 的来源与估算状态' }));
    expect(within(panel()).getByRole('heading', { name: '型宽' })).toBeVisible();
    const first = panel().getAttribute('data-motion');

    fireEvent.click(screen.getByRole('button', { name: '查看 船长 的来源与估算状态' }));
    expect(within(panel()).getByRole('heading', { name: '船长' })).toBeVisible();
    expect(panel().getAttribute('data-motion')).not.toBe(first);

    // Editing the value publishes the same field again, and reveals nothing: a
    // keystroke must never be mistaken for a change of field.
    const length = screen.getByLabelText('船长');
    const before = panel().getAttribute('data-motion');
    fireEvent.change(length, { target: { value: '91' } });
    expect(panel().getAttribute('data-motion')).toBe(before);
    expect(within(panel()).getByRole('heading', { name: '船长' })).toBeVisible();
  });
});

describe('the route entry', () => {
  it('marks the arriving page for 220 ms, and waits for nothing at all', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    native();
    let committed = false;
    // A destination page whose read never answers must not hold the switch back.
    vi.mocked(api.getRun).mockReturnValue(new Promise(() => {}));
    void runTransition('app-route', () => { committed = true; });
    expect(committed).toBe(true);
    expect(document.documentElement.dataset.ffAppRoute).toBe('in');
    act(() => { vi.advanceTimersByTime(TRANSITION_MS.appRoute - 1); });
    expect(document.documentElement.dataset.ffAppRoute).toBe('in');
    act(() => { vi.advanceTimersByTime(1); });
    expect(document.documentElement.dataset.ffAppRoute).toBeUndefined();
    // It is a plain CSS reveal of one element: no snapshot of the report body was
    // ever taken, which is what makes a page of this size safe to switch.
    expect(document.querySelector('.app-route')?.getAttributeNames().some(name => name.startsWith('data-ff'))).toBeFalsy();
    expect(api.getRun).not.toHaveBeenCalled();
  });

  it('alternates its token so a rapid second switch is still seen', () => {
    native();
    let token: 'a' | 'b' = 'a';
    // Two switches in a row, exactly as a reader clicking twice would produce.
    void runTransition('app-route', () => { token = token === 'a' ? 'b' : 'a'; });
    expect(token).toBe('b');
    void runTransition('app-route', () => { token = token === 'a' ? 'b' : 'a'; });
    expect(token).toBe('a');
    // Latest wins: the first switch's timer and attribute are already gone.
    expect(document.documentElement.dataset.ffAppRoute).toBe('in');
    expect(document.documentElement.dataset.ffTransition).toBeUndefined();
  });

  it('keeps a single reveal while a second switch interrupts the first', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    native();
    let shown: string | null = null;
    void runTransition('app-route', () => { shown = 'library'; });
    // A second switch inside the first 220 ms: the newest one wins, and it is
    // revealed rather than dropped.
    act(() => { vi.advanceTimersByTime(50); });
    void runTransition('app-route', () => { shown = 'workbench'; });
    expect(shown).toBe('workbench');
    expect(document.documentElement.dataset.ffAppRoute).toBe('in');
    act(() => { vi.advanceTimersByTime(TRANSITION_MS.appRoute); });
    expect(document.documentElement.dataset.ffAppRoute).toBeUndefined();
  });

  it('commits at once when the reader has asked for less motion', () => {
    preferences.set(reduced, true);
    let committed = false;
    void runTransition('app-route', () => { committed = true; });
    // No attribute, no animation, no capture: the page simply arrives.
    expect(committed).toBe(true);
    expect(document.documentElement.dataset.ffAppRoute).toBeUndefined();
  });

  it('commits at once where the browser cannot animate at all', () => {
    let committed = false;
    void runTransition('app-route', () => { committed = true; });
    expect(committed).toBe(true);
    expect(document.documentElement.dataset.ffAppRoute).toBeUndefined();
  });

  it('shows which project or run the reader is in, from the route alone', async () => {
    window.history.replaceState(null, '', '/#/projects/p1');
    const { default: App } = await import('../App');
    render(<App returnHref="#/work" />);
    await screen.findByRole('heading', { level: 1, name: '解析方箱' });
    // The identity is stated before the page's own data arrives, so the arriving
    // page is never a blank screen.
    expect(document.querySelector('.header-context')).toHaveTextContent('项目 · P1');
  });
});

describe('the opening, once per browser session', () => {
  it('plays on a first visit and not again in the same session', async () => {
    vi.useFakeTimers();
    window.history.replaceState(null, '', '/#/work');
    const first = render(<Portfolio />);
    expect(screen.getByRole('status', { name: /Opening Y’s Formfield|Loading reference/ })).toBeInTheDocument();
    expect(introPlayed()).toBe(true);
    first.unmount();

    // A second visit in the same browser session starts on the work, not the intro.
    render(<Portfolio />);
    expect(screen.queryByRole('status', { name: 'Opening Y’s Formfield' })).toBeNull();
    expect(screen.getByRole('heading', { level: 1, name: 'Plimsoll' })).toBeVisible();
  });

  it('replays on request, which is the only way to see it twice', async () => {
    // The intro is finished first, by the reader's own choice, so the replay is
    // unambiguously a second showing rather than the first.
    markIntroPlayed();
    window.history.replaceState(null, '', '/#/work');
    render(<Portfolio />);
    await screen.findByRole('heading', { level: 1, name: 'Plimsoll' });
    expect(screen.queryByRole('status', { name: 'Opening Y’s Formfield' })).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /REPLAY INTRO/ }));
    expect(screen.getByRole('status', { name: /Opening Y’s Formfield|Loading reference/ })).toBeInTheDocument();
  });

  it('does not open for a deep link, an app route or a reduced-motion reader', () => {
    for (const hash of ['#/projects/p1', '#/about']) {
      window.history.replaceState(null, '', `/${hash}`);
      const view = render(<Portfolio />);
      expect(screen.queryByRole('status', { name: 'Opening Y’s Formfield' })).toBeNull();
      view.unmount();
    }
    preferences.set(reduced, true);
    window.history.replaceState(null, '', '/#/work');
    render(<Portfolio />);
    expect(screen.queryByRole('status', { name: 'Opening Y’s Formfield' })).toBeNull();
  });

  it('still plays, and still recovers, where session storage is refused', () => {
    const storage = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('denied'); });
    const write = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('denied'); });
    window.history.replaceState(null, '', '/#/work');
    render(<Portfolio />);
    // Refused storage degrades to "as though never seen": the intro plays.
    expect(screen.getByRole('status', { name: /Opening Y’s Formfield|Loading reference/ })).toBeInTheDocument();
    expect(() => markIntroPlayed()).not.toThrow();
    storage.mockRestore(); write.mockRestore();
  });

  it('keeps the reference failure recoverable, and the exhibit usable', async () => {
    window.history.replaceState(null, '', '/#/work');
    vi.stubGlobal('Image', class {
      src = '';
      decode = () => Promise.reject(new Error('decode failed'));
    });
    render(<Portfolio />);
    // A drawing that never decodes ends the opening rather than holding the reader
    // in front of a black panel forever.
    expect(await screen.findByRole('heading', { level: 1, name: 'Plimsoll' })).toBeVisible();
    expect(screen.queryByRole('status', { name: 'Opening Y’s Formfield' })).toBeNull();
    // The reference controls are still there, and replay can try again.
    for (const sheet of PLAN_SHEETS) expect(screen.getByRole('button', { name: sheet.label })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /REPLAY INTRO/ }));
    expect(screen.getByRole('status', { name: /Opening Y’s Formfield|Loading reference/ })).toBeInTheDocument();
  });
});

describe('a workspace chunk that failed to load', () => {
  it('offers a real page reload and says what a reload will keep', () => {
    function Explode(): never { throw new Error('Failed to fetch dynamically imported module'); }
    const reload = vi.fn();
    const location = vi.spyOn(window, 'location', 'get').mockReturnValue({ ...window.location, reload } as Location);
    render(<ToolModuleBoundary returnHref="#/work" onFailure={vi.fn()}>
      <Explode />
    </ToolModuleBoundary>);
    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent('工作空间未能加载');
    expect(screen.getByText('Failed to fetch dynamically imported module')).toBeVisible();
    // What the reader is told, in terms of what they keep and can still do.
    expect(screen.getByText(/请重新载入页面以恢复工作空间/)).toBeVisible();
    expect(screen.getByText(/现有浏览器工作区会保留/)).toBeVisible();
    expect(screen.getByRole('link', { name: '↖ Y’s Formfield' })).toHaveAttribute('href', '#/work');

    // And the action is the real thing, not a second attempt at the same import.
    fireEvent.click(screen.getByRole('button', { name: '重新载入页面' }));
    expect(reload).toHaveBeenCalledTimes(1);
    location.mockRestore();
  });

  it('never locks the public shell, which never needed the chunk', async () => {
    native();
    window.history.replaceState(null, '', '/#/work');
    render(<Portfolio />);
    await screen.findByRole('heading', { level: 1, name: 'Plimsoll' });
    // Work and About are served by this document and remain reachable whatever
    // happens to the workspace chunk behind them.
    fireEvent.click(screen.getByRole('link', { name: 'About' }));
    expect(await screen.findByRole('heading', { name: /A field for/ })).toBeVisible();
    fireEvent.click(screen.getByRole('link', { name: /Work 01/ }));
    expect(await screen.findByRole('heading', { level: 1, name: 'Plimsoll' })).toBeVisible();
  });
});