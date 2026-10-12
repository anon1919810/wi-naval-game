import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react';
import { renderZh as render } from './locale';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import App from '../App';
import { ApiError } from '../api';
import { Library } from '../pages/Library';
import { Workbench } from '../pages/Workbench';
import * as api from '../api';
import type { ProjectDocument, ProjectSummary, ProjectView, UserSession } from '../types';

vi.mock('../api', async importOriginal => {
  const actual = await importOriginal<typeof import('../api')>();
  return {
    ...actual,
    authConfig: vi.fn(),
    me: vi.fn(),
    bootstrapAnonymous: vi.fn(),
    listProjects: vi.fn(),
    getProject: vi.fn(),
    enqueueRun: vi.fn(),
    listRuns: vi.fn(),
    createProject: vi.fn(),
    exportUrl: vi.fn(),
    logout: vi.fn(),
  };
});

const anonymousSession: UserSession = {
  id: 'a-1', email: 'anonymous-abc123@anonymous.invalid', theme: 'light',
  csrf_token: 'csrf-1', mode: 'anonymous', label: '本浏览器工作区',
};

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
  window.location.hash = '';
  vi.mocked(api.listProjects).mockResolvedValue([]);
});

afterEach(() => { cleanup(); });

describe('anonymous browser workspace', () => {
  it('bootstraps once, keeps projects and hides the misleading logout', async () => {
    vi.mocked(api.authConfig).mockResolvedValue({ mode: 'anonymous' });
    vi.mocked(api.me).mockRejectedValue(new ApiError(401, 'login required'));
    vi.mocked(api.bootstrapAnonymous).mockResolvedValue(anonymousSession);

    render(<App />);

    expect((await screen.findAllByText('本浏览器工作区')).length).toBeGreaterThan(1);
    expect(screen.getByTitle('本浏览器工作区')).toBeVisible();
    expect(api.bootstrapAnonymous).toHaveBeenCalledTimes(1);
    expect(api.me).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('button', { name: '退出' })).toBeNull();
    expect(screen.getByText(/仅当前浏览器可见/)).toBeVisible();
    fireEvent.click(screen.getByText('保存与恢复说明'));
    expect(screen.getByText(/清除 Cookie/)).toBeVisible();
    expect(screen.queryByLabelText('邮箱地址')).toBeNull();
  });

  it('reuses an existing cookie instead of minting another workspace', async () => {
    vi.mocked(api.authConfig).mockResolvedValue({ mode: 'anonymous' });
    vi.mocked(api.me).mockResolvedValue(anonymousSession);

    render(<App />);

    expect(await screen.findByTitle('本浏览器工作区')).toBeVisible();
    expect(api.bootstrapAnonymous).not.toHaveBeenCalled();
  });

  it('reports a lost connection without retrying into new identities', async () => {
    vi.mocked(api.authConfig).mockResolvedValue({ mode: 'anonymous' });
    vi.mocked(api.me).mockRejectedValue(new ApiError(401, 'login required'));
    vi.mocked(api.bootstrapAnonymous).mockRejectedValue(new ApiError(503, 'mail delivery unavailable'));

    render(<App />);

    expect(await screen.findByText('暂时无法连接工作空间，请稍后刷新页面重试。')).toBeVisible();
    expect(api.bootstrapAnonymous).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('button', { name: '退出' })).toBeNull();
  });

  it('never shows the email form in anonymous mode', async () => {
    vi.mocked(api.authConfig).mockResolvedValue({ mode: 'anonymous' });
    vi.mocked(api.me).mockRejectedValue(new ApiError(401, 'login required'));
    vi.mocked(api.bootstrapAnonymous).mockRejectedValue(new Error('network down'));

    render(<App />);

    await waitFor(() => expect(api.bootstrapAnonymous).toHaveBeenCalled());
    expect(screen.queryByLabelText('邮箱地址')).toBeNull();
    expect(screen.queryByRole('button', { name: '发送验证码' })).toBeNull();
  });

  it('keeps the email-code entry point in email mode', async () => {
    vi.mocked(api.authConfig).mockResolvedValue({ mode: 'email' });
    vi.mocked(api.me).mockRejectedValue(new ApiError(401, 'login required'));

    render(<App />);

    expect(await screen.findByLabelText('邮箱地址')).toBeVisible();
    expect(api.bootstrapAnonymous).not.toHaveBeenCalled();
    expect(screen.queryByText('暂时无法连接工作空间，请稍后刷新页面重试。')).toBeNull();
  });
});

describe('library workspace note', () => {
  it('separates the project document from report exports', async () => {
    render(<Library onOpen={vi.fn()} anonymous />);
    expect(await screen.findByText('本浏览器工作区')).toBeVisible();
    expect(screen.getByText(/运行页导出的 JSON\/CSV 是计算报告，不是项目备份/)).not.toBeVisible();
    fireEvent.click(screen.getByText('保存与恢复说明'));
    expect(screen.getByText(/「下载项目 JSON」/)).toBeVisible();
    expect(screen.getByText(/运行页导出的 JSON\/CSV 是计算报告，不是项目备份/)).toBeVisible();
  });

  it('omits the caveat for an identified account', () => {
    render(<Library onOpen={vi.fn()} />);
    expect(screen.queryByText('本浏览器工作区')).toBeNull();
  });
});

describe('library filter', () => {
  const summaries: ProjectSummary[] = [
    { project_id: 'p1', name: '解析方箱', revision: 1, updated_at: '2026-10-11T00:00:00Z' },
    { project_id: 'p2', name: 'HMS Queen Mary', revision: 3, updated_at: '2026-10-11T00:00:00Z' },
    { project_id: 'p3', name: '通用试验船', revision: 2, updated_at: '2026-10-11T00:00:00Z' },
  ];
  /** The names the saved list actually renders, in order. */
  const listed = () => Array.from(document.querySelectorAll('.project-row strong')).map(node => node.textContent);

  it('narrows the list already read by name, counts the matches, and clears', async () => {
    vi.mocked(api.listProjects).mockResolvedValue(summaries);
    render(<Library onOpen={vi.fn()} />);
    await waitFor(() => expect(listed().length).toBe(3));

    const filter = screen.getByLabelText('按名称筛选项目');
    // One rule covers a Latin name and a Chinese one: matching is on the stored
    // name itself, case-insensitively, not on a transliteration of it.
    fireEvent.change(filter, { target: { value: 'queen' } });
    expect(listed()).toEqual(['HMS Queen Mary']);
    expect(screen.getByText('匹配 1 / 3')).toBeVisible();

    fireEvent.change(filter, { target: { value: '方箱' } });
    expect(listed()).toEqual(['解析方箱']);
    expect(screen.getByText('匹配 1 / 3')).toBeVisible();

    // A longer name is matched on any part of it, not only its start.
    fireEvent.change(filter, { target: { value: '试验' } });
    expect(listed()).toEqual(['通用试验船']);

    fireEvent.click(screen.getByRole('button', { name: '清除筛选' }));
    expect(listed().length).toBe(3);
    expect(screen.getByText('3 个项目')).toBeVisible();
    // The whole narrowing was a view of one read: it never became a second one.
    expect(api.listProjects).toHaveBeenCalledTimes(1);
  });

  it('separates "no match" from an empty library and offers the way back', async () => {
    vi.mocked(api.listProjects).mockResolvedValue(summaries);
    render(<Library onOpen={vi.fn()} />);
    await waitFor(() => expect(listed().length).toBe(3));

    fireEvent.change(screen.getByLabelText('按名称筛选项目'), { target: { value: '不存在的船' } });
    // Not the empty-library state: this library holds three projects, and the
    // reader is only being shown none of them.
    expect(screen.queryByText('还没有舰船项目')).toBeNull();
    expect(screen.getByText('没有匹配的舰船')).toBeVisible();
    expect(screen.getByText(/不存在的船/)).toBeVisible();
    expect(screen.getByText('匹配 0 / 3')).toBeVisible();
    expect(listed().length).toBe(0);

    fireEvent.click(screen.getByRole('button', { name: '显示全部项目' }));
    expect(listed().length).toBe(3);
    expect(screen.queryByText('没有匹配的舰船')).toBeNull();
  });

  it('offers no filter where there is nothing to sift', async () => {
    render(<Library onOpen={vi.fn()} />);
    await screen.findByText('还没有舰船项目');
    // An empty library says so once, rather than also offering a control whose
    // only possible result is "no match".
    expect(screen.queryByLabelText('按名称筛选项目')).toBeNull();
  });
});

describe('first-use guide', () => {
  // The one shape `createProject` answers with; the created document itself is
  // irrelevant to these tests, only the identity and revision are.
  const created: ProjectView = { project_id: 'p-new', revision: 1, project: {} as ProjectDocument };
  beforeEach(() => { vi.mocked(api.createProject).mockResolvedValue(created); });

  it('recommends the sample project and creates it only when pressed', async () => {
    const onOpen = vi.fn();
    render(<Library onOpen={onOpen} anonymous />);
    await screen.findByText('还没有舰船项目');

    // Open on a confirmed empty library, because there is nothing else to read
    // yet — but it is a disclosure that stays available, not a modal.
    const guide = screen.getByText('第一次使用').closest('details')!;
    expect(guide).toHaveAttribute('open');
    // Opening it, or reading it, creates nothing by itself.
    expect(api.createProject).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /从通用试验船开始/ }));
    await waitFor(() => expect(api.createProject).toHaveBeenCalledTimes(1));
    // It reuses the one guarded creation, so it creates the documented sample
    // rather than a second, differently seeded project.
    expect(vi.mocked(api.createProject).mock.calls[0]).toEqual(['generic_steamer', '通用试验船']);
    await waitFor(() => expect(onOpen).toHaveBeenCalledWith('p-new'));
  });

  it('keeps the recommended creation behind the same guard as every other one', async () => {
    let release!: (value: ProjectView) => void;
    vi.mocked(api.createProject).mockReturnValue(new Promise(resolve => { release = resolve; }));
    const onOpen = vi.fn();
    render(<Library onOpen={onOpen} anonymous />);
    await screen.findByText('还没有舰船项目');

    const cta = screen.getByRole('button', { name: /从通用试验船开始/ });
    fireEvent.click(cta);
    await waitFor(() => expect(cta).toBeDisabled());

    // One creation at a time across the whole page: while it is in flight the
    // guide's own button, the templates and the blank form are all refused, so
    // a reader cannot start two projects from two different entry points.
    expect(cta).toBeDisabled();
    for (const card of screen.getAllByRole('button', { name: /建立项目/ })) expect(card).toBeDisabled();
    expect(screen.getByRole('button', { name: /创建空白项目/ })).toBeDisabled();
    // And a second press on the guide cannot start a second project.
    fireEvent.click(cta);
    expect(api.createProject).toHaveBeenCalledTimes(1);

    release({ project_id: 'p-1', revision: 1, project: {} as ProjectDocument });
    await waitFor(() => expect(onOpen).toHaveBeenCalledWith('p-1'));
  });

  it('reports a failed recommended creation beside the entries that can be retried', async () => {
    vi.mocked(api.createProject).mockRejectedValue(new Error('名称已存在'));
    render(<Library onOpen={vi.fn()} anonymous />);
    await screen.findByText('还没有舰船项目');
    fireEvent.click(screen.getByRole('button', { name: /从通用试验船开始/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent('名称已存在');
    // Nothing was opened, and the page is still usable.
    expect(screen.getByRole('button', { name: /从通用试验船开始/ })).toBeEnabled();
  });
});

const box: ProjectDocument = {
  schema: 'plimsoll-project-1', id: 'p1', name: '解析方箱', revision: 1,
  hull: { length_m: 90, beam_m: 20, draft_m: 4 },
  geometry: null, weight_groups: [{ id: 'lightship', label: '空船', items: [{ id: 'steel', label: '船体钢', mass_t: 2100 }] }],
  loading_conditions: [{ id: 'loaded', label: '满载' }],
};

describe('project document download', () => {
  it('writes the editable project document, never a report payload', async () => {
    let blob: Blob | null = null;
    const revoked: string[] = [];
    const createObjectURL = vi.fn((value: Blob) => { blob = value; return 'blob:plimsoll/1'; });
    const revokeObjectURL = vi.fn((url: string) => { revoked.push(url); });
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL });
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 3, project: box });
    vi.mocked(api.listRuns).mockResolvedValue([]);

    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '下载项目 JSON' }));

    expect(revoked).toEqual(['blob:plimsoll/1']);
    expect(api.exportUrl).not.toHaveBeenCalled();
    const document_ = JSON.parse(await blob!.text()) as ProjectDocument;
    expect(document_.schema).toBe('plimsoll-project-1');
    expect(document_.name).toBe('解析方箱');
    expect(document_.hull).toEqual(box.hull);
    expect(document_.weight_groups[0].items[0]).toEqual(box.weight_groups[0].items[0]);
    expect(document_).not.toHaveProperty('stages');
    expect(document_).not.toHaveProperty('request_fingerprint');

    click.mockRestore();
    vi.unstubAllGlobals();
  });
});

describe('unknown auth mode stays offline instead of showing email login', () => {
  it('never offers the email form when auth/config cannot be read', async () => {
    vi.mocked(api.authConfig).mockRejectedValue(new ApiError(503, 'service unavailable'));
    vi.mocked(api.me).mockRejectedValue(new ApiError(401, 'login required'));

    render(<App />);

    expect(await screen.findByText('暂时无法连接工作空间，请稍后刷新页面重试。')).toBeVisible();
    expect(screen.queryByLabelText('邮箱地址')).toBeNull();
    expect(screen.queryByRole('button', { name: '发送验证码' })).toBeNull();
    expect(api.bootstrapAnonymous).not.toHaveBeenCalled();
  });
});
