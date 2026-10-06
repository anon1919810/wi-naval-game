import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import * as api from '../api';
import { clearLeaveGuard, pushHash, setLeaveGuard } from '../leaveGuard';
import App from '../App';
import type { ProjectDocument, ProjectView, UserSession } from '../types';

/**
 * Leaving an unsaved project, in a real hash sequence.
 *
 * The properties that matter are about history, not about a dialog: a refused
 * Back must come back to the page without rewriting the entry it was refused at,
 * because that entry is the project library the reader was trying to reach. So
 * these tests drive `history.back()` / `history.forward()` for real and assert
 * the address, the stack length and the surviving addresses afterwards — a
 * `replaceState` "fix" would pass a weaker test and still destroy the entry.
 */

vi.mock('../api', async importOriginal => {
  const actual = await importOriginal<typeof import('../api')>();
  return { ...actual, authConfig: vi.fn(), me: vi.fn(), bootstrapAnonymous: vi.fn(), listProjects: vi.fn(),
    createProject: vi.fn(), getProject: vi.fn(), listRuns: vi.fn(), saveProject: vi.fn(), enqueueRun: vi.fn(),
    getRun: vi.fn(), setTheme: vi.fn(), logout: vi.fn() };
});

const UNSAVED = '当前舰船有未保存的修改，离开会丢失这些修改。是否离开？';

const session: UserSession = {
  id: 'a-1', email: 'anonymous-abc@anonymous.invalid', theme: 'light',
  csrf_token: 'csrf-1', mode: 'anonymous', label: '本浏览器工作区',
};

const box: ProjectDocument = {
  schema: 'plimsoll-project-1', id: 'p1', name: '解析方箱', revision: 1,
  hull: { length_m: 90, beam_m: 20, draft_m: 4 }, geometry: null,
  weight_groups: [], loading_conditions: [{ id: 'loaded', label: '满载' }],
};

/** Traversal events are queued by the environment; let them all arrive. */
async function settle() {
  for (let round = 0; round < 5; round += 1) await act(async () => { await new Promise(resolve => setTimeout(resolve, 20)); });
}

beforeEach(() => {
  cleanup();
  vi.restoreAllMocks();
  window.history.replaceState({}, '', '/#/projects/library');
  window.location.hash = '#/projects/library';
  vi.mocked(api.authConfig).mockResolvedValue({ mode: 'anonymous' });
  vi.mocked(api.me).mockResolvedValue(session);
  vi.mocked(api.listProjects).mockResolvedValue([]);
  vi.mocked(api.listRuns).mockResolvedValue([]);
  vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 1, project: box } as ProjectView);
});

afterEach(() => { cleanup(); clearLeaveGuard(); vi.restoreAllMocks(); });

/** A library entry followed by a project entry, both stamped by the guard. */
function sequence(): number {
  pushHash('#/projects');
  pushHash('#/projects/p1');
  return window.history.length;
}

/** Mirrors App's retained shownHash, which does not follow a refused URL. */
function guardShownPage() {
  const shown = window.location.hash;
  setLeaveGuard(() => ({ message: UNSAVED, current: shown }));
}

describe('a refused traversal', () => {
  it('comes back to the page, leaves every entry intact, and lets the next Back through', async () => {
    const ask = vi.spyOn(window, 'confirm');
    const length = sequence();
    guardShownPage();

    ask.mockReturnValue(false);
    window.history.back();
    await settle();
    expect(ask).toHaveBeenCalledTimes(1);
    expect(ask).toHaveBeenCalledWith(UNSAVED);
    // The address the reader was refused is the address they still have.
    expect(window.location.hash).toBe('#/projects/p1');
    // Nothing was rewritten, added or duplicated on the way.
    expect(window.history.length).toBe(length);

    ask.mockReturnValue(true);
    window.history.back();
    await settle();
    expect(ask).toHaveBeenCalledTimes(2);
    // The original target, still the entry it always was.
    expect(window.location.hash).toBe('#/projects');
    expect(window.history.length).toBe(length);

    window.history.forward();
    await settle();
    expect(window.location.hash).toBe('#/projects/p1');
    expect(window.history.length).toBe(length);
  });

  it('measures a multi-step traversal and undoes all of it', async () => {
    const ask = vi.spyOn(window, 'confirm');
    pushHash('#/projects');
    pushHash('#/projects/p1');
    pushHash('#/runs/run-1');
    const length = window.history.length;
    guardShownPage();

    ask.mockReturnValue(false);
    window.history.go(-2);
    await settle();
    expect(window.location.hash).toBe('#/runs/run-1');
    expect(window.history.length).toBe(length);

    ask.mockReturnValue(true);
    window.history.go(-2);
    await settle();
    expect(window.location.hash).toBe('#/projects');
    expect(window.history.length).toBe(length);
  });

  it('undoes a refused Forward as well, without stranding the reader', async () => {
    const ask = vi.spyOn(window, 'confirm');
    const length = sequence();
    window.history.back();
    await settle();
    expect(window.location.hash).toBe('#/projects');
    guardShownPage();

    ask.mockReturnValue(false);
    window.history.forward();
    await settle();
    expect(window.location.hash).toBe('#/projects');
    expect(window.history.length).toBe(length);

    ask.mockReturnValue(true);
    window.history.forward();
    await settle();
    expect(window.location.hash).toBe('#/projects/p1');
  });

  it('answers before any listener registered after it, so one refusal commits nothing', async () => {
    const ask = vi.spyOn(window, 'confirm');
    sequence();
    // Stands in for both route listeners, which mount after this module.
    const committed: string[] = [];
    const later = () => committed.push(window.location.hash);
    window.addEventListener('popstate', later);
    window.addEventListener('hashchange', later);
    guardShownPage();

    ask.mockReturnValue(false);
    window.history.back();
    await settle();
    expect(ask).toHaveBeenCalledTimes(1);
    expect(committed).not.toContain('#/projects');
    expect(window.location.hash).toBe('#/projects/p1');
    window.removeEventListener('popstate', later);
    window.removeEventListener('hashchange', later);
  });

  it('asks nothing for a navigation that is not a navigation', () => {
    const ask = vi.spyOn(window, 'confirm').mockReturnValue(false);
    sequence();
    guardShownPage();
    expect(pushHash('#/projects/p1')).toBe(false);
    expect(ask).not.toHaveBeenCalled();
    expect(window.location.hash).toBe('#/projects/p1');
  });

  it('refuses a plain left click on a link without ever creating its entry', () => {
    const ask = vi.spyOn(window, 'confirm').mockReturnValue(false);
    sequence();
    const length = window.history.length;
    guardShownPage();
    const link = document.createElement('a');
    link.href = '#/work';
    link.textContent = 'public site';
    document.body.append(link);
    const event = new MouseEvent('click', { bubbles: true, cancelable: true, button: 0 });
    fireEvent(link, event);
    expect(event.defaultPrevented).toBe(true);
    expect(window.location.hash).toBe('#/projects/p1');
    expect(window.history.length).toBe(length);
    link.remove();
  });

  it('warns about closing the tab only while a draft is unsaved', () => {
    sequence();
    const clean = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(clean);
    expect(clean.defaultPrevented).toBe(false);

    guardShownPage();
    const dirty = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(dirty);
    expect(dirty.defaultPrevented).toBe(true);

    clearLeaveGuard();
    const saved = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(saved);
    expect(saved.defaultPrevented).toBe(false);
  });

  it('confirms an accepted native link only once across its popstate and hashchange', async () => {
    const ask = vi.spyOn(window, 'confirm').mockReturnValue(true);
    sequence();
    guardShownPage();
    const link = document.createElement('a');
    link.href = '#/work';
    document.body.append(link);
    link.click();
    await settle();
    expect(window.location.hash).toBe('#/work');
    expect(ask).toHaveBeenCalledTimes(1);
    link.remove();
  });

  it('restores the right occurrence of a repeated URL and drops a Forward branch on a new push', async () => {
    pushHash('#/projects');
    pushHash('#/projects/p1');
    pushHash('#/runs/run-1');
    pushHash('#/projects/p1');
    const ask = vi.spyOn(window, 'confirm').mockReturnValue(false);
    guardShownPage();
    window.history.back();
    await settle();
    expect(window.location.hash).toBe('#/projects/p1');
    expect(ask).toHaveBeenCalledTimes(1);
    clearLeaveGuard();
    window.history.back();
    await settle();
    expect(window.location.hash).toBe('#/runs/run-1');
    pushHash('#/projects/p2');
    window.history.forward();
    await settle();
    expect(window.location.hash).toBe('#/projects/p2');
    window.history.back();
    await settle();
    expect(window.location.hash).toBe('#/runs/run-1');
  });
});

describe('the guard in the assembled application', () => {
  async function openDirtyProject() {
    window.location.hash = '#/projects/p1';
    render(<App returnHref="#/work" />);
    fireEvent.click(await screen.findByRole('button', { name: '船型与几何' }));
    const length = await screen.findByLabelText('船长');
    fireEvent.change(length, { target: { value: '91' } });
    await screen.findByText('未保存修改');
    return length;
  }

  it('keeps the draft, the chapter and the address when the way back is refused', async () => {
    const ask = vi.spyOn(window, 'confirm').mockReturnValue(false);
    await openDirtyProject();
    const length = screen.getByLabelText('船长');

    fireEvent.click(screen.getByRole('button', { name: '← 项目库' }));
    expect(ask).toHaveBeenCalledTimes(1);

    expect(window.location.hash).toBe('#/projects/p1');
    expect(screen.getByLabelText('船长')).toHaveValue(91);
    expect(screen.getByRole('heading', { level: 1, name: 'Hull & Geometry' })).toBeVisible();
    expect(screen.getByText('未保存修改')).toBeVisible();

    // The refusal is not sticky: the very next attempt still asks, and works.
    ask.mockReturnValue(true);
    fireEvent.click(screen.getByRole('button', { name: '← 项目库' }));
    await screen.findByRole('heading', { level: 1, name: /^Projects/ });
    expect(window.location.hash).toBe('#/projects');
    expect(length).not.toBeNull();
  });

  it('refuses the public way out too, and keeps the address where it was', async () => {
    const ask = vi.spyOn(window, 'confirm').mockReturnValue(false);
    await openDirtyProject();
    const event = new MouseEvent('click', { bubbles: true, cancelable: true, button: 0 });
    fireEvent(screen.getByRole('link', { name: '↖ Y’s Formfield' }), event);
    expect(ask).toHaveBeenCalledTimes(1);
    expect(event.defaultPrevented).toBe(true);
    expect(window.location.hash).toBe('#/projects/p1');
    expect(screen.getByLabelText('船长')).toHaveValue(91);
  });

  it('restores the assembled project after Back with a single question, then reaches the original library', async () => {
    sequence();
    const ask = vi.spyOn(window, 'confirm').mockReturnValue(false);
    await openDirtyProject();
    const size = window.history.length;
    window.history.back();
    await settle();
    expect(ask).toHaveBeenCalledTimes(1);
    expect(window.location.hash).toBe('#/projects/p1');
    expect(screen.getByLabelText('船长')).toHaveValue(91);
    expect(window.history.length).toBe(size);

    ask.mockReturnValue(true);
    window.history.back();
    await settle();
    expect(ask).toHaveBeenCalledTimes(2);
    expect(await screen.findByRole('heading', { level: 1, name: /^Projects/ })).toBeVisible();
    expect(window.location.hash).toBe('#/projects');
    expect(window.history.length).toBe(size);
  });

  it('asks nothing for a chapter, a Trace field or a display unit', async () => {
    const ask = vi.spyOn(window, 'confirm').mockReturnValue(false);
    await openDirtyProject();
    // A chapter, a traced field's provenance and a display unit are all view
    // state: they never leave the project, so nothing is at risk and no one is
    // asked.
    fireEvent.click(screen.getByRole('button', { name: '查看 船长 的来源与估算状态' }));
    expect(await screen.findByRole('heading', { level: 2, name: '船长' })).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: '重量与载荷' }));
    expect(await screen.findByRole('heading', { level: 1, name: 'Weights & Loading' })).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: '概览' }));
    expect(await screen.findByRole('heading', { level: 1, name: '解析方箱' })).toBeVisible();
    expect(ask).not.toHaveBeenCalled();
    expect(window.location.hash).toBe('#/projects/p1');
  });

  it('releases the guard once the reader has really left', async () => {
    const ask = vi.spyOn(window, 'confirm');
    ask.mockReturnValue(false);
    await openDirtyProject();
    fireEvent.click(screen.getByRole('button', { name: '← 项目库' }));
    expect(ask).toHaveBeenCalledTimes(1);

    ask.mockReturnValue(true);
    fireEvent.click(screen.getByRole('button', { name: '← 项目库' }));
    await screen.findByRole('heading', { level: 1, name: /^Projects/ });

    // A new project has no unsaved draft, so leaving it must ask nothing.
    ask.mockClear();
    vi.mocked(api.createProject).mockResolvedValue({ project_id: 'p1', revision: 1, project: box });
    fireEvent.click(await screen.findByRole('button', { name: /解析方箱/ }));
    await screen.findByRole('heading', { level: 1, name: '解析方箱' });
    expect(screen.getByText('与已保存修订一致')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: '← 项目库' }));
    expect(await screen.findByRole('heading', { level: 1, name: /^Projects/ })).toBeVisible();
    expect(ask).not.toHaveBeenCalled();
  });
});
