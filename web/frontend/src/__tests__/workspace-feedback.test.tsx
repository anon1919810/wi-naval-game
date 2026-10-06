import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import App from '../App';
import * as api from '../api';
import { ReadPending, READ_SHIMMER_MS, READ_WAIT_MS } from '../components/ReadPending';
import { clearLeaveGuard, pushHash } from '../leaveGuard';
import { Library } from '../pages/Library';
import { ReportPage } from '../pages/Report';
import { Run } from '../pages/Run';
import { Workbench } from '../pages/Workbench';
import type { ProjectDocument, ProjectView, RunView, UserSession } from '../types';

/**
 * Cluster one: reads, submissions and recovery.
 *
 * What is asserted here is behaviour a reader depends on — that a failure ends
 * the waiting instead of replacing it, that one explicit retry recovers it, that
 * a slow answer to a question nobody is asking any more is ignored, that each
 * operation says what it is actually doing, and that a save never reports
 * itself as a run or loses the edits made while it was in flight.
 */

vi.mock('../api', async importOriginal => {
  const actual = await importOriginal<typeof import('../api')>();
  return { ...actual, authConfig: vi.fn(), me: vi.fn(), bootstrapAnonymous: vi.fn(), listProjects: vi.fn(),
    createProject: vi.fn(), getProject: vi.fn(), listRuns: vi.fn(), saveProject: vi.fn(), enqueueRun: vi.fn(),
    getRun: vi.fn(), cancelRun: vi.fn(), setTheme: vi.fn(), logout: vi.fn() };
});

const session: UserSession = {
  id: 'a-1', email: 'anonymous-abc@anonymous.invalid', theme: 'light',
  csrf_token: 'csrf-1', mode: 'anonymous', label: '本浏览器工作区',
};

const UNSAVED = '当前舰船有未保存的修改，离开会丢失这些修改。是否离开？';

const box: ProjectDocument = {
  schema: 'plimsoll-project-1', id: 'p1', name: '解析方箱', revision: 1,
  hull: { length_m: 90, beam_m: 20, draft_m: 4 }, geometry: null,
  weight_groups: [], loading_conditions: [{ id: 'loaded', label: '满载' }],
};

const view = (project = box, revision = 1): ProjectView => ({ project_id: 'p1', revision, project });
const summary = { project_id: 'p1', name: '解析方箱', revision: 1, updated_at: '2026-10-06T00:00:00Z' };

function runOf(patch: Partial<RunView> & { status: RunView['status'] }): RunView {
  return { id: 'run-1', project_id: 'p1', revision: 1, condition_id: 'loaded', request_fingerprint: 'rf',
    created_at: '2026-10-06T00:00:00Z', started_at: null, finished_at: null,
    cancel_requested: false, result: null, error: null, ...patch };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (cause: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
  window.location.hash = '';
  vi.mocked(api.authConfig).mockResolvedValue({ mode: 'anonymous' });
  vi.mocked(api.me).mockResolvedValue(session);
  vi.mocked(api.listProjects).mockResolvedValue([]);
  vi.mocked(api.listRuns).mockResolvedValue([]);
  vi.mocked(api.getProject).mockResolvedValue(view());
});
afterEach(() => { cleanup(); vi.useRealTimers(); clearLeaveGuard(); });

describe('shared reading feedback', () => {
  it('shows no decoration for a fast answer, and never delays the result', () => {
    vi.useFakeTimers();
    const { unmount } = render(<ReadPending scope="library" object="项目库" />);
    const status = screen.getByRole('status');
    expect(status).toHaveAttribute('aria-busy', 'true');
    expect(status).toHaveAttribute('aria-label', '正在读取项目库');
    expect(status).toHaveTextContent('正在读取项目库');
    expect(document.querySelector('.read-pending-lines')).toBeNull();
    act(() => { vi.advanceTimersByTime(READ_SHIMMER_MS); });
    // Only now does the shape appear, so a read answered in 80 ms shows nothing.
    expect(document.querySelector('.read-shape--rows')).toBeVisible();
    expect(document.querySelectorAll('.read-row')).toHaveLength(3);
    expect(screen.queryByText(/仍在等待/)).toBeNull();
    act(() => { vi.advanceTimersByTime(READ_WAIT_MS); });
    expect(screen.getByText(/仍在等待项目库的读取结果，已超过 2 秒/)).toBeVisible();
    unmount();
  });

  it('clears both timers on unmount, so a finished read leaves nothing pending', () => {
    vi.useFakeTimers();
    const { unmount } = render(<ReadPending scope="report" object="计算报告" />);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
    act(() => { vi.advanceTimersByTime(5000); });
    expect(document.body.textContent).toBe('');
  });
});

describe('project library · a failed read is not a failed creation', () => {
  it('ends the skeleton and the reading count, and keeps creation usable', async () => {
    vi.mocked(api.listProjects).mockRejectedValue(new Error('项目库暂时不可达'));
    render(<Library onOpen={vi.fn()} />);
    expect(await screen.findByText('无法读取项目库')).toBeVisible();
    expect(screen.getByText('项目库暂时不可达')).toBeVisible();
    expect(screen.queryByLabelText('正在读取项目库')).toBeNull();
    // The count stops reading as though it were still counting.
    expect(screen.queryByText('读取中')).toBeNull();
    expect(screen.getByText('读取失败')).toBeVisible();
    // Nothing about creating a project depends on being able to list the old ones.
    for (const label of ['解析方箱', '通用试验船', 'HMS Queen Mary']) {
      expect(screen.getByRole('button', { name: new RegExp(label) })).toBeEnabled();
    }
  });

  it('recovers in place with one explicit retry', async () => {
    vi.mocked(api.listProjects)
      .mockRejectedValueOnce(new Error('第一次读取失败'))
      .mockResolvedValueOnce([summary]);
    render(<Library onOpen={vi.fn()} />);
    expect(await screen.findByText('无法读取项目库')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: '重新读取项目库' }));
    expect(await screen.findByText('解析方箱')).toBeVisible();
    expect(screen.getByText('1 个项目')).toBeVisible();
    expect(screen.queryByText('无法读取项目库')).toBeNull();
  });

  it('ignores a read that answers for a page the reader has already left', async () => {
    const abandoned = deferred<typeof summary[]>();
    vi.mocked(api.listProjects).mockReturnValue(abandoned.promise);
    const { unmount } = render(<Library onOpen={vi.fn()} />);
    await screen.findByLabelText('正在读取项目库');
    unmount();
    await act(async () => { abandoned.resolve([summary]); await abandoned.promise; });
    // The list arrived for a page that is gone; it must not render anywhere.
    expect(document.body.textContent).toBe('');
  });

  it('reports a creation failure on its own, separately from any read', async () => {
    vi.mocked(api.listProjects).mockRejectedValue(new Error('项目库暂时不可达'));
    vi.mocked(api.createProject).mockRejectedValue(new Error('名称已被占用'));
    render(<Library onOpen={vi.fn()} />);
    expect(await screen.findByText('无法读取项目库')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: /解析方箱/ }));
    expect(await screen.findByText('创建失败：名称已被占用')).toBeVisible();
    // The template that failed is offered again rather than left disabled.
    expect(screen.getByRole('button', { name: /解析方箱/ })).toBeEnabled();
    // The read failure is still its own message, and the read still has not
    // silently turned into a project list.
    expect(screen.getByText('无法读取项目库')).toBeVisible();
    expect(screen.getByText('读取失败')).toBeVisible();
  });

  it('says it is establishing a blank project, in the same honest terms', async () => {
    vi.mocked(api.createProject).mockReturnValue(new Promise(() => {}));
    render(<Library onOpen={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('新项目名称'), { target: { value: '新船' } });
    fireEvent.click(screen.getByRole('button', { name: '创建空白项目' }));
    expect(await screen.findByRole('button', { name: '建立中…' })).toBeDisabled();
  });
});

describe('workspace entry · a retry re-reads the session, it does not mint one', () => {
  it('adopts an existing browser session on retry instead of creating another', async () => {
    vi.mocked(api.authConfig).mockRejectedValueOnce(new Error('网关不可达'));
    render(<App />);
    expect(await screen.findByText('暂时无法连接工作空间，请稍后刷新页面重试。')).toBeVisible();
    expect(api.bootstrapAnonymous).not.toHaveBeenCalled();
    // Nothing repeats on its own: the message waits for the reader.
    await new Promise(resolve => setTimeout(resolve, 20));
    expect(api.authConfig).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('button', { name: '重新连接' }));
    expect(await screen.findByTitle('本浏览器工作区')).toBeVisible();
    expect(api.me).toHaveBeenCalledTimes(1);
    expect(api.bootstrapAnonymous).not.toHaveBeenCalled();
  });

  it('creates a workspace only after /me answers 401, and only once per press', async () => {
    vi.mocked(api.authConfig).mockRejectedValueOnce(new Error('网关不可达'));
    vi.mocked(api.me).mockRejectedValueOnce(new api.ApiError(401, 'login required'));
    vi.mocked(api.bootstrapAnonymous).mockResolvedValue(session);
    render(<App />);
    expect(await screen.findByText('暂时无法连接工作空间，请稍后刷新页面重试。')).toBeVisible();
    // The first attempt never got as far as an identity lookup.
    expect(api.me).not.toHaveBeenCalled();
    expect(api.bootstrapAnonymous).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: '重新连接' }));
    expect(await screen.findByTitle('本浏览器工作区')).toBeVisible();
    // The reader's single press asked /me first, and only a 401 authorised one
    // creation. Nothing repeats on its own afterwards.
    expect(api.me).toHaveBeenCalledTimes(1);
    expect(api.bootstrapAnonymous).toHaveBeenCalledTimes(1);
    await new Promise(resolve => setTimeout(resolve, 20));
    expect(api.me).toHaveBeenCalledTimes(1);
    expect(api.bootstrapAnonymous).toHaveBeenCalledTimes(1);
  });

  it('refuses a real browser Back, keeps the draft and address, and lets the next Back through', async () => {
    // The address the guard is told comes from the committed route, so it is the
    // page the reader is on and not the destination they were refused. Spelling
    // this out matters: a wrong segment here would restore them to no page.
    const ask = vi.spyOn(window, 'confirm');
    // A real two-entry history, built through the guard's own push so every entry
    // carries its own position — otherwise Back cannot be measured.
    window.history.replaceState(null, '', '/#/plimsoll');
    pushHash('#/projects');
    pushHash('#/projects/p1');
    render(<App returnHref="#/work" />);
    fireEvent.click(await screen.findByRole('button', { name: '船型与几何' }));
    fireEvent.change(await screen.findByLabelText('船长'), { target: { value: '91' } });
    await screen.findByText('未保存修改');

    ask.mockReturnValue(false);
    window.history.back();
    for (let round = 0; round < 5; round += 1) await act(async () => { await new Promise(resolve => setTimeout(resolve, 20)); });
    expect(ask).toHaveBeenCalledTimes(1);
    expect(ask).toHaveBeenCalledWith(UNSAVED);
    // The draft and the address are both exactly where they were.
    expect(window.location.hash).toBe('#/projects/p1');
    expect(screen.getByLabelText('船长')).toHaveValue(91);
    expect(screen.getByText('未保存修改')).toBeVisible();

    // The library entry the reader was refused is still there to reach.
    ask.mockReturnValue(true);
    window.history.back();
    for (let round = 0; round < 5; round += 1) await act(async () => { await new Promise(resolve => setTimeout(resolve, 20)); });
    expect(window.location.hash).toBe('#/projects');
    expect(await screen.findByRole('heading', { level: 1, name: /Projects/ })).toBeVisible();
    expect(screen.queryByLabelText('船长')).toBeNull();
  });

  it('does not treat a same-project address change as leaving the project', async () => {
    const ask = vi.spyOn(window, 'confirm').mockReturnValue(false);
    window.history.replaceState(null, '', '/#/projects/p1');
    render(<App returnHref="#/work" />);
    fireEvent.click(await screen.findByRole('button', { name: '船型与几何' }));
    fireEvent.change(await screen.findByLabelText('船长'), { target: { value: '91' } });
    await screen.findByText('未保存修改');

    // A same-project address change is view state, not a departure.
    await act(async () => {
      window.history.pushState(null, '', '#/projects/p1');
      window.dispatchEvent(new HashChangeEvent('hashchange'));
    });
    await act(async () => { await Promise.resolve(); });
    expect(ask).not.toHaveBeenCalled();
    expect(screen.getByLabelText('船长')).toHaveValue(91);
  });

  it('abandons an attempt whose answer arrives after the reader left the application', async () => {
    vi.mocked(api.authConfig).mockResolvedValue({ mode: 'anonymous' });
    const late = deferred<UserSession>();
    vi.mocked(api.me).mockReturnValue(late.promise);
    const { unmount } = render(<App />);
    await waitFor(() => expect(api.me).toHaveBeenCalledTimes(1));
    unmount();
    await act(async () => {
      late.resolve({ ...session, theme: 'dark' });
      await late.promise;
    });
    // The public shell owns the root theme; a workspace that has already gone
    // must not repaint it behind the portfolio's back.
    expect(document.documentElement.dataset.theme).not.toBe('dark');
    expect(document.body.textContent).toBe('');
  });

  it('does not navigate a page that has already been left when a creation answers', async () => {
    const pending = deferred<ProjectView>();
    vi.mocked(api.createProject).mockReturnValue(pending.promise);
    const onOpen = vi.fn();
    const { unmount } = render(<Library onOpen={onOpen} />);
    await screen.findByLabelText('正在读取项目库');
    fireEvent.click(screen.getByRole('button', { name: /解析方箱/ }));
    await screen.findByText('建立中…');
    unmount();
    await act(async () => { pending.resolve(view()); await pending.promise; });
    // The project was really created, but nobody is here to open it.
    expect(onOpen).not.toHaveBeenCalled();
    expect(document.body.textContent).toBe('');
  });

  it('does not navigate to a queued run after the workbench has been left', async () => {
    vi.mocked(api.getProject).mockResolvedValue(view());
    const pending = deferred<RunView>();
    vi.mocked(api.enqueueRun).mockReturnValue(pending.promise);
    const onRun = vi.fn();
    const { unmount } = render(<Workbench projectId="p1" onBack={vi.fn()} onRun={onRun} />);
    await screen.findByRole('heading', { level: 1, name: '解析方箱' });
    fireEvent.click(screen.getByRole('button', { name: '运行计算 ↗' }));
    await screen.findByRole('button', { name: '正在启动计算…' });
    unmount();
    await act(async () => { pending.resolve(runOf({ status: 'queued' })); await pending.promise; });
    expect(onRun).not.toHaveBeenCalled();
    expect(document.body.textContent).toBe('');
  });

  it('ignores a save answer that arrives after the reader left the project', async () => {
    vi.mocked(api.getProject).mockResolvedValue(view());
    const pending = deferred<ProjectView>();
    vi.mocked(api.saveProject).mockReturnValue(pending.promise);
    const { unmount } = render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '船型与几何' }));
    fireEvent.change(await screen.findByLabelText('船长'), { target: { value: '91' } });
    fireEvent.click(screen.getByRole('button', { name: '保存修订' }));
    await screen.findByRole('button', { name: '保存中…' });
    unmount();
    await act(async () => { pending.resolve(view(box, 2)); await pending.promise; });
    expect(document.body.textContent).toBe('');
  });

  it('offers the public way out of a workspace that never connected', async () => {
    vi.mocked(api.authConfig).mockRejectedValue(new Error('网关不可达'));
    render(<App returnHref="#/work" />);
    expect(await screen.findByRole('button', { name: '返回总站' })).toBeVisible();
    expect(screen.getByRole('link', { name: '↖ Y’s Formfield' })).toHaveAttribute('href', '#/work');
  });
});

describe('workbench · one named operation at a time', () => {
  it('reports a load failure with one retry and the real way back', async () => {
    vi.mocked(api.getProject).mockRejectedValue(new Error('项目暂时不可达'));
    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
    expect(await screen.findByText('无法读取舰船 p1')).toBeVisible();
    expect(screen.getByText('项目暂时不可达')).toBeVisible();
    expect(screen.getByRole('button', { name: '← 返回项目库' })).toBeVisible();
  });

  it('ignores a project load that answers for a project the reader has left', async () => {
    // Two projects are opened in quick succession, so the first read is still out
    // when the second one commits.
    const abandoned = deferred<ProjectView>();
    vi.mocked(api.getProject).mockReturnValueOnce(abandoned.promise)
      .mockResolvedValueOnce(view({ ...box, id: 'p2', name: '第二艘舰' }, 4));
    const { rerender } = render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
    await screen.findByLabelText('正在读取舰船项目');
    rerender(<Workbench projectId="p2" onBack={vi.fn()} onRun={vi.fn()} />);
    expect(await screen.findByRole('heading', { level: 1, name: '第二艘舰' })).toBeVisible();

    // The superseded project answers last, with its own revision.
    await act(async () => { abandoned.resolve(view({ ...box, name: '过期舰船' }, 7)); await abandoned.promise; });
    expect(screen.queryByText('过期舰船')).toBeNull();
    expect(screen.getByRole('heading', { level: 1, name: '第二艘舰' })).toBeVisible();
    expect(screen.getAllByText('修订 4').length).toBeGreaterThan(0);
  });

  it('names a save as a save and never as a run, and keeps the edits made during it', async () => {
    vi.mocked(api.getProject).mockResolvedValue(view());
    const pending = deferred<ProjectView>();
    vi.mocked(api.saveProject).mockReturnValue(pending.promise);
    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '船型与几何' }));
    fireEvent.change(await screen.findByLabelText('船长'), { target: { value: '91' } });
    fireEvent.click(screen.getByRole('button', { name: '保存修订' }));

    expect(await screen.findByRole('button', { name: '保存中…' })).toBeDisabled();
    expect(screen.getByRole('status')).toHaveTextContent('正在保存修订…');
    // The run control still reads as a run: nothing here is computing anything.
    expect(screen.getByRole('button', { name: '运行计算 ↗' })).toBeDisabled();
    expect(screen.queryByText('正在提交计算请求…')).toBeNull();

    fireEvent.change(screen.getByLabelText('型宽'), { target: { value: '21' } });
    await act(async () => {
      pending.resolve(view({ ...box, hull: { ...box.hull, length_m: 91 } }, 2));
      await pending.promise;
    });
    expect(await screen.findByLabelText('型宽')).toHaveValue(21);
    expect(screen.getByText('未保存修改')).toBeVisible();
    expect(screen.getByRole('button', { name: '保存修订' })).toBeEnabled();
  });

  it('names a queued calculation, and a reload as a reload', async () => {
    vi.mocked(api.getProject).mockResolvedValue(view());
    const queued = deferred<RunView>();
    vi.mocked(api.enqueueRun).mockReturnValue(queued.promise);
    const onRun = vi.fn();
    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={onRun} />);
    await screen.findByRole('heading', { level: 1, name: '解析方箱' });
    fireEvent.click(screen.getByRole('button', { name: '运行计算 ↗' }));
    expect(await screen.findByRole('button', { name: '正在启动计算…' })).toBeDisabled();
    expect(screen.getByRole('status')).toHaveTextContent('正在提交计算请求…');
    expect(screen.queryByRole('button', { name: '保存中…' })).toBeNull();
    await act(async () => { queued.resolve(runOf({ status: 'queued' })); await queued.promise; });
    expect(onRun).toHaveBeenCalledWith('run-1');
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('keeps the 409 conflict copy and reload paths, now with their own label', async () => {
    vi.mocked(api.getProject).mockResolvedValue(view());
    vi.mocked(api.saveProject).mockRejectedValue(new api.ApiError(409, { current_revision: 2 }));
    const reloading = deferred<ProjectView>();
    vi.mocked(api.getProject).mockResolvedValueOnce(view());
    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '船型与几何' }));
    fireEvent.change(await screen.findByLabelText('船长'), { target: { value: '91' } });
    fireEvent.click(screen.getByRole('button', { name: '保存修订' }));
    expect(await screen.findByText(/服务器已有修订 2/)).toBeVisible();
    expect(screen.getByRole('button', { name: '复制我的修改' })).toBeVisible();

    // The reload is its own operation, reported as one.
    const second = vi.mocked(api.getProject).getMockImplementation();
    vi.mocked(api.getProject).mockImplementation(() => reloading.promise);
    fireEvent.click(screen.getByRole('button', { name: '重新载入' }));
    expect(await screen.findByRole('button', { name: '正在重新载入…' })).toBeDisabled();
    expect(screen.getByRole('status')).toHaveTextContent('正在重新载入项目…');
    await act(async () => { reloading.resolve(view(box, 2)); await reloading.promise; });
    expect(await screen.findByText('已保存')).toBeVisible();
    if (second) vi.mocked(api.getProject).mockImplementation(second);
  });
});

describe('run and report · the same honest reading feedback', () => {
  it('names what the run page is waiting for, and marks the real activity only', async () => {
    const running = runOf({ id: 'run-3', status: 'running' });
    vi.mocked(api.getRun).mockResolvedValue(running);
    render(<Run runId="run-3" onBack={vi.fn()} onReport={vi.fn()} />);
    expect(screen.getByLabelText('正在读取运行')).toBeVisible();
    await screen.findByRole('heading', { name: '计算中' });
    // The marker describes the state the server actually reported.
    expect(document.querySelector('.run-progress')).toHaveAttribute('data-status', 'running');
    expect(screen.getByText('计算正在后台执行，离开页面后可再打开此运行。')).toBeVisible();
  });

  it('discards a run read that answers after the reader moved to another run', async () => {
    const abandoned = deferred<RunView>();
    vi.mocked(api.getRun).mockReturnValueOnce(abandoned.promise).mockResolvedValue(runOf({ id: 'run-3', status: 'completed' }));
    const { rerender } = render(<Run runId="run-1" onBack={vi.fn()} onReport={vi.fn()} />);
    await screen.findByLabelText('正在读取运行');

    // A second run is opened while the first read is still out.
    rerender(<Run runId="run-3" onBack={vi.fn()} onReport={vi.fn()} />);
    expect(await screen.findByRole('heading', { name: '计算完成' })).toBeVisible();
    expect(document.querySelector('.run-identity')).toHaveTextContent('run-3');

    // The abandoned read answers with a completely different run. It is not the
    // run in front of the reader and must not appear.
    await act(async () => { abandoned.resolve(runOf({ id: 'run-1', status: 'failed', error: { code: 'stale', message: '过期响应' } })); await abandoned.promise; });
    expect(screen.queryByText('过期响应')).toBeNull();
    expect(screen.getByRole('heading', { name: '计算完成' })).toBeVisible();
    expect(document.querySelector('.run-identity')).toHaveTextContent('run-3');
  });

  it('drops the activity marker once the run has actually ended', async () => {
    vi.mocked(api.getRun).mockResolvedValue(runOf({ status: 'completed' }));
    render(<Run runId="run-1" onBack={vi.fn()} onReport={vi.fn()} />);
    await screen.findByRole('heading', { name: '计算完成' });
    expect(document.querySelector('.run-progress')).toBeNull();
  });

  it('recovers a failed report read in place, and ignores an earlier answer', async () => {
    const first = deferred<RunView>();
    vi.mocked(api.getRun).mockReturnValueOnce(first.promise).mockResolvedValue(runOf({ status: 'completed' }));
    render(<ReportPage runId="run-1" onBack={vi.fn()} />);
    expect(screen.getByLabelText('正在读取计算报告')).toBeVisible();
    await act(async () => { first.reject(new Error('报告暂时不可达')); await first.promise.catch(() => {}); });
    expect(await screen.findByText('无法读取报告 run-1')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: '重新读取报告' }));
    await waitFor(() => expect(api.getRun).toHaveBeenCalledTimes(2));
    expect(screen.queryByText('无法读取报告 run-1')).toBeNull();
  });

  it('keeps the alert to one region while the workspace is reading', async () => {
    vi.mocked(api.getProject).mockRejectedValue(new Error('项目暂时不可达'));
    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
    const alert = await screen.findByRole('alert');
    expect(within(alert).getByText('无法读取舰船 p1')).toBeVisible();
    expect(screen.getAllByRole('alert')).toHaveLength(1);
  });
});