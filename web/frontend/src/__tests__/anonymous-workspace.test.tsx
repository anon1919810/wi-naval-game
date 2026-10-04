import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import App from '../App';
import { ApiError } from '../api';
import { Library } from '../pages/Library';
import { Workbench } from '../pages/Workbench';
import * as api from '../api';
import type { ProjectDocument, UserSession } from '../types';

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
    expect(screen.getByText(/下载项目 JSON/)).toBeVisible();
    expect(screen.getByText(/运行页导出的 JSON\/CSV 是计算报告，不是项目备份/)).toBeVisible();
  });

  it('omits the caveat for an identified account', () => {
    render(<Library onOpen={vi.fn()} />);
    expect(screen.queryByText('本浏览器工作区')).toBeNull();
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
