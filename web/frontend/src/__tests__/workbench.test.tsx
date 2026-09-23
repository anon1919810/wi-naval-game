import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { FactField } from '../components/FactField';
import { Library } from '../pages/Library';
import { Login } from '../pages/Login';
import { Workbench } from '../pages/Workbench';
import * as api from '../api';
import type { ProjectDocument } from '../types';

vi.mock('../api', async importOriginal => {
  const actual = await importOriginal<typeof import('../api')>();
  return { ...actual, listProjects: vi.fn(), requestCode: vi.fn(), getProject: vi.fn(), saveProject: vi.fn() };
});

const box: ProjectDocument = {
  schema: 'plimsoll-project-1', id: 'p1', name: '解析方箱', revision: 1,
  hull: { length_m: 90, beam_m: 20, draft_m: 4 },
  geometry: null, weight_groups: [], loading_conditions: [{ id: 'loaded', label: '满载' }],
};

beforeEach(() => { cleanup(); vi.clearAllMocks(); });

describe('workbench entry', () => {
  it('distinguishes unknown from a real zero', () => {
    render(<><FactField label="装甲甲板覆盖率" value={null} unit="%" status="unknown" />
      <FactField label="横倾角" value={0} unit="°" status="known" /></>);
    expect(screen.getByText('未知')).toBeVisible();
    expect(screen.getByText('0 °')).toBeVisible();
    expect(screen.queryByText('0 %')).toBeNull();
  });

  it('shows an honest empty library and Queen Mary proxy label', async () => {
    vi.mocked(api.listProjects).mockResolvedValue([]);
    render(<Library onOpen={vi.fn()} />);
    expect(await screen.findByText('还没有舰船项目')).toBeVisible();
    expect(screen.getByText(/史实未认证代理/)).toBeVisible();
  });

  it('shows an email-code error without losing the entry form', async () => {
    vi.mocked(api.requestCode).mockRejectedValue(new Error('邮件服务暂不可用'));
    render(<Login onAuthenticated={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('邮箱地址'), { target: { value: 'alice@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: '发送验证码' }));
    expect(await screen.findByText('邮件服务暂不可用')).toBeVisible();
    expect(screen.getByLabelText('邮箱地址')).toBeVisible();
  });

  it('saves an edited dimension and presents a stale revision conflict', async () => {
    vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 1, project: box });
    vi.mocked(api.saveProject).mockRejectedValue(new api.ApiError(409, { current_revision: 2 }));
    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '船型与几何' }));
    const length = await screen.findByLabelText(/船长 · m/);
    fireEvent.change(length, { target: { value: '91' } });
    expect(screen.getByText('未保存修改')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: '保存修订' }));
    expect(await screen.findByText(/服务器已有修订 2/)).toBeVisible();
    expect(screen.getByRole('button', { name: '复制我的修改' })).toBeVisible();
    expect(screen.getByRole('button', { name: '重新载入' })).toBeVisible();
    await waitFor(() => expect(api.saveProject).toHaveBeenCalledWith('p1', expect.objectContaining({ base_revision: 1 })));
  });

  it('preserves edits made while a save response is pending', async () => {
    vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 1, project: box });
    let finishSave!: (value: { project_id: string; revision: number; project: ProjectDocument }) => void;
    vi.mocked(api.saveProject).mockImplementation(() => new Promise(resolve => { finishSave = resolve; }));
    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '船型与几何' }));
    fireEvent.change(screen.getByLabelText(/船长 · m/), { target: { value: '91' } });
    fireEvent.click(screen.getByRole('button', { name: '保存修订' }));
    await waitFor(() => expect(api.saveProject).toHaveBeenCalled());
    fireEvent.change(screen.getByLabelText(/型宽 · m/), { target: { value: '21' } });
    finishSave({ project_id: 'p1', revision: 2, project: { ...box, hull: { ...box.hull, length_m: 91 } } });
    await waitFor(() => expect(screen.getByLabelText(/型宽 · m/)).toHaveValue(21));
    expect(screen.getByText('未保存修改')).toBeVisible();
  });

  it('rejects incomplete project JSON before replacing the visible draft', async () => {
    vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 1, project: box });
    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '项目数据' }));
    fireEvent.change(screen.getByLabelText('项目 JSON'), { target: { value: '{"id":"p1"}' } });
    fireEvent.click(screen.getByRole('button', { name: '应用到草稿' }));
    expect(screen.getByRole('alert')).toHaveTextContent(/缺少|无效/);
    expect(screen.getByRole('heading', { name: '解析方箱' })).toBeVisible();
    fireEvent.change(screen.getByLabelText('项目 JSON'), { target: { value: JSON.stringify({
      ...box, loading_conditions: [{ id: 'loaded', label: { invalid: true } }],
    }) } });
    fireEvent.click(screen.getByRole('button', { name: '应用到草稿' }));
    expect(screen.getByRole('alert')).toHaveTextContent('工况 loading_conditions');
  });
});
