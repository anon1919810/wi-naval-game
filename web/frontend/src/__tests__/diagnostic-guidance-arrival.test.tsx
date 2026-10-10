import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import * as api from '../api';
import { Workbench } from '../pages/Workbench';
import { diagnosticHref, readDiagnosticTarget } from '../components/diagnosticGuidance';
import type { AnalysisResult, ProjectDocument, RunView, StageEnvelope } from '../types';

/**
 * Arriving at the workspace from a diagnostic, and leaving it again.
 *
 * The two halves of the promise are tested here: a saved finding really does
 * reach its own control, and it never buys that focus with a save, a run, a
 * discarded draft or a wrong answer from a foreign run.
 */

vi.mock('../api', async original => ({ ...await original<typeof import('../api')>(),
  getProject: vi.fn(), saveProject: vi.fn(), listRuns: vi.fn(), enqueueRun: vi.fn(), getRun: vi.fn() }));

const project: ProjectDocument = {
  schema: 'plimsoll-project-1', id: 'p1', name: '解析方箱', revision: 1,
  hull: { loa_m: 90, beam_m: 20, draught_normal_m: 4 }, geometry: null,
  weight_groups: [{ id: 'lightship', label: '空船', items: [{ id: 'steamer-structure', mass_t: null, x_m: 35, source: 'yard plan' }] }],
  loading_conditions: [{ id: 'loaded', label: '满载' }, { id: 'deep', label: '深载' }],
  resistance_scenarios: [{ id: 'study', method: 'holtrop_mennen_1982' }],
};

function envelope(status: StageEnvelope['status'], requested: boolean, data: StageEnvelope['data'] = null,
  reason: string | null = null, diagnostics: StageEnvelope['diagnostics'] = []): StageEnvelope {
  return {
    status, requested, reason,
    validity: { complete: status === 'completed', converged: null, model_applicable: null, historical_validated: null },
    method_versions: {}, assumptions: [], diagnostics, data,
  };
}

const MASS_UNKNOWN = {
  code: 'loading.mass_unknown', severity: 'error', blocking: true, stage: 'loading',
  path: '$.weight_groups[0].items[0].mass_t', source_path: '$.weight_groups[0].items[0].mass_t',
  message: '账本条目 steamer-structure 的有效质量未知',
};

function savedRun(overrides: Partial<RunView> = {}, stages?: AnalysisResult['stages']): RunView {
  const result = {
    schema: 'plimsoll-analysis-1', status: 'partial', project_id: 'p1', condition_id: 'loaded',
    project_fingerprint: 'pf', input_fingerprint: 'if', request_fingerprint: 'rf',
    request: { stages: ['loading'], options: { stages: ['loading', 'equilibrium'] } },
    input_snapshot: project, units: {}, method_versions: {}, sources: {},
    diagnostics: [MASS_UNKNOWN],
    validity: { complete: false, converged: null, model_applicable: null, historical_validated: null },
    stages: stages ?? {
      loading: envelope('failed', true, null, '账本条目 steamer-structure 的有效质量未知', [MASS_UNKNOWN]),
      equilibrium: envelope('unavailable', true, null, '型线资料不足'),
    },
  } as unknown as AnalysisResult;
  return { id: 'run-a', project_id: 'p1', revision: 1, condition_id: 'loaded', status: 'partial',
    request_fingerprint: 'rf', created_at: '2026-10-10T00:00:00Z', started_at: null, finished_at: '2026-10-10T00:01:00Z',
    cancel_requested: false, result, error: null, ...overrides } as RunView;
}

let narrow = false;

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
  narrow = false;
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: /max-width:\s*1280px/.test(query) ? narrow : false,
    media: query, addEventListener: () => {}, removeEventListener: () => {},
  }));
  vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 1, project });
  vi.mocked(api.listRuns).mockResolvedValue([]);
  vi.mocked(api.getRun).mockRejectedValue(new Error('no stored run'));
  vi.mocked(api.saveProject).mockResolvedValue({ project_id: 'p1', revision: 2, project });
  vi.mocked(api.enqueueRun).mockResolvedValue(savedRun({ id: 'run-new' }) as unknown as RunView);
  window.history.replaceState(null, '', '/#/projects/p1');
});

afterEach(() => { vi.unstubAllGlobals(); cleanup(); });

async function open(hash?: string, onDirtyChange?: (dirty: boolean) => void) {
  if (hash) { window.history.replaceState(null, '', hash); }
  render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} onDirtyChange={onDirtyChange} />);
  await screen.findByRole('button', { name: '概览' });
  await waitFor(() => expect(api.listRuns).toHaveBeenCalled());
}

function readiness(): HTMLElement {
  return screen.getByRole('heading', { name: /计算就绪/ }).closest('.chapter-group') as HTMLElement;
}

/** The panel's own words, including the run id it keeps inside `<code>`. */
function said(panel: HTMLElement, selector: string): string {
  return (panel.querySelector(selector)?.textContent ?? '').replace(/\s+/g, ' ').trim();
}

function focusedLabel(): string | null {
  return document.activeElement?.getAttribute('aria-label') ?? null;
}

describe('what the overview says about calculation readiness', () => {
  it('names the stages of the current request and calls them unassessed before any run', async () => {
    await open();
    const panel = readiness();
    // The stages come from the request that is actually assembled on screen.
    expect(within(panel).getByText('载荷与重心')).toBeVisible();
    expect(within(panel).getByText('浮态平衡')).toBeVisible();
    expect(within(panel).getAllByText('未评估').length).toBeGreaterThan(4);
    expect(within(panel).getByText(/尚未评估/)).toBeVisible();
    expect(said(panel, '.readiness-attribution')).not.toContain('运行 run-');
  });

  it('keeps the previous check as evidence after a corrected revision is saved but not rerun', async () => {
    const oldRun = savedRun({ id: 'run-2', revision: 2 });
    vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 2, project });
    vi.mocked(api.listRuns).mockResolvedValue([oldRun]);
    vi.mocked(api.saveProject).mockResolvedValue({ project_id: 'p1', revision: 3, project: {
      ...project, weight_groups: [{ id: 'lightship', label: '空船', items: [
        { id: 'steamer-structure', mass_t: 2800, x_m: 35, source: 'yard plan' }] }],
    } });
    await open();
    await waitFor(() => expect(said(readiness(), '.readiness-attribution')).toContain('运行 run-2'));

    // The reader corrects the missing mass and saves a new revision. No run has
    // been queued, so the new revision has no result of its own.
    fireEvent.click(screen.getByRole('button', { name: '重量与载荷' }));
    fireEvent.change(await screen.findByLabelText('lightship steamer-structure 质量'), { target: { value: '2800' } });
    fireEvent.click(screen.getByRole('button', { name: '保存修订' }));
    await waitFor(() => expect(within(document.querySelector('.operation-bar') as HTMLElement).getByText('修订 3')).toBeVisible());
    fireEvent.click(screen.getByRole('button', { name: '概览' }));

    const panel = readiness();
    // The diagnostic the reader was following is still here, attributed to the
    // run and revision it came from, and never presented as the current result.
    expect(said(panel, '.readiness-attribution')).toContain('运行 run-2');
    expect(said(panel, '.readiness-attribution')).toContain('修订 2');
    expect(said(panel, '.readiness-history')).toContain('当前已保存修订是 3');
    expect(said(panel, '.readiness-history')).toContain('需要保存修订并重新运行');
    const action = within(panel).getByRole('button', { name: /steamer-structure/ });
    expect(action.textContent).toContain('质量');
    const result = screen.getByRole('heading', { name: /当前结果/ }).closest('.chapter-group') as HTMLElement;
    expect(within(result).getByText('尚无当前结果')).toBeVisible();
    expect(result.textContent).not.toContain('运行 run-2');
  });

  it('keeps that evidence across a fresh load of the same project', async () => {
    vi.mocked(api.listRuns).mockResolvedValue([savedRun({ id: 'run-2', revision: 2 })]);
    vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 3, project: {
      ...project, weight_groups: [{ id: 'lightship', label: '空船', items: [
        { id: 'steamer-structure', mass_t: 2800, x_m: 35, source: 'yard plan' }] }],
    } });
    await open();
    const panel = readiness();
    expect(said(panel, '.readiness-attribution')).toContain('运行 run-2');
    expect(said(panel, '.readiness-history')).toContain('当前已保存修订是 3');
    expect(within(panel).getByRole('button', { name: /steamer-structure/ })).toBeVisible();
    const result = screen.getByRole('heading', { name: /当前结果/ }).closest('.chapter-group') as HTMLElement;
    expect(within(result).getByText('尚无当前结果')).toBeVisible();
  });

  it('uses one saved-result read for the current result and its diagnostic history', async () => {
    const full = savedRun();
    vi.mocked(api.listRuns).mockResolvedValue([{ ...full, result: null }]);
    vi.mocked(api.getRun).mockResolvedValue(full);
    await open();
    await waitFor(() => expect(said(readiness(), '.readiness-attribution')).toContain('运行 run-a'));
    expect(within(readiness()).getByRole('button', { name: /steamer-structure/ })).toBeVisible();
    expect(api.getRun).toHaveBeenCalledTimes(1);
  });

  it('never describes a later saved revision as a previous check of the loaded revision', async () => {
    const past = savedRun({ id: 'past-check', revision: 2 });
    const future = savedRun({ id: 'future-check', revision: 4, created_at: '2026-10-11T00:00:00Z' });
    vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 3, project });
    vi.mocked(api.listRuns).mockResolvedValue([past, future]);
    await open();
    await waitFor(() => expect(said(readiness(), '.readiness-attribution')).toContain('past-check'));
    expect(said(readiness(), '.readiness-attribution')).not.toContain('future-check');
  });

  it('refuses historical diagnostic actions when the payload disagrees with the run identity', async () => {
    const wrong = savedRun({ revision: 1 });
    wrong.result!.condition_id = 'deep';
    vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 2, project });
    vi.mocked(api.listRuns).mockResolvedValue([wrong]);
    await open();
    expect(said(readiness(), '.readiness-attribution')).not.toContain('run-a');
    expect(within(readiness()).queryByRole('button', { name: /steamer-structure/ })).toBeNull();
  });

  it('lists a valid flooding selection exactly as the queued request', async () => {
    const source = { kind: 'analytic_fixture' };
    const scenario = {
      schema: 'plimsoll-flooding-scenario-1', id: 'flooding_1', duration_s: 1, time_step_s: .25,
      source, estimate: false,
      sea: { id: 'sea', fluid_density_t_m3: 1.025, source, estimate: false },
      tanks: [{ id: 'centre', length_m: 4, beam_m: 2, height_m: 4, x_m: 0, y_m: 0,
        keel_to_bottom_m: 0, permeability: 1, initial_volume_m3: 8, free_surface: true,
        fluid_density_t_m3: 1.025, source, estimate: false }],
      connections: [{ id: 'sea-inlet', from: 'sea', to: 'centre', x_m: 0, y_m: 0, z_m: .1,
        area_m2: .1, discharge_coefficient: .6, fluid_density_t_m3: 1.025, open: true, source, estimate: false }],
      openings: [],
    };
    vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 1,
      project: { ...project, flooding_scenarios: [scenario] } });
    await open();
    fireEvent.click(screen.getByRole('button', { name: '破损研究' }));
    fireEvent.change(await screen.findByLabelText('请求破损场景'), { target: { value: 'flooding_1' } });
    fireEvent.click(screen.getByRole('button', { name: '概览' }));
    const row = within(readiness()).getByText('破损进水').closest('li')!;
    expect(within(row).getByText('本次请求已选择')).toBeVisible();
    expect(within(readiness()).queryByText('本次请求无效，不会提交')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '运行计算 ↗' }));
    await waitFor(() => expect(api.enqueueRun).toHaveBeenCalledWith('p1', expect.objectContaining({
      options: expect.objectContaining({ stages: expect.arrayContaining(['flooding']) }),
    })));
  });

  it('labels an invalid request instead of claiming it selected nothing', async () => {
    await open();
    fireEvent.click(screen.getByRole('button', { name: '性能与工况' }));
    // A resistance study without usable samples cannot be submitted.
    fireEvent.change(await screen.findByLabelText('阻力研究场景'), { target: { value: 'study' } });
    await waitFor(() => expect(within(document.querySelector('.workbench-alerts') as HTMLElement).getByRole('alert')).toBeVisible());
    expect(screen.getByLabelText('阻力研究场景')).toHaveValue('study');
    // A damaged scenario is selected too, which used to spread an undefined
    // stage list; the page stays up and names the explicit selections instead.
    fireEvent.click(screen.getByRole('button', { name: '破损研究' }));
    fireEvent.click(await screen.findByRole('button', { name: '添加破损场景' }));
    fireEvent.change(await screen.findByLabelText('请求破损场景'), { target: { value: 'flooding_1' } });
    await waitFor(() => expect(screen.getByRole('alert')).toBeVisible());
    fireEvent.click(screen.getByRole('button', { name: '概览' }));

    const panel = readiness();
    expect(within(panel).getByText('本次请求无效，不会提交')).toBeVisible();
    expect(within(panel).getByText(/采样|递增/)).toBeVisible();
    // The stages the request explicitly selects are still named.
    expect(within(panel).getByText('载荷与重心')).toBeVisible();
    expect(within(panel).getByText('阻力与功率')).toBeVisible();
    expect(within(panel).getByText('破损进水')).toBeVisible();
    expect(screen.getByRole('button', { name: '运行计算 ↗' })).toBeDisabled();
  });

  it('attributes a saved run to the diagnostics it produced, and links the missing mass', async () => {
    vi.mocked(api.listRuns).mockResolvedValue([savedRun()]);
    await open();
    const panel = readiness();
    const attribution = said(panel, '.readiness-attribution');
    expect(attribution).toContain('上一次检查');
    expect(attribution).toContain('运行 run-a');
    expect(attribution).toContain('修订 1');
    expect(attribution).toContain('工况 loaded');
    // The blocked stage keeps its own reason and is not called a missing input.
    expect(within(panel).getByText('暂不可计算')).toBeVisible();
    expect(within(panel).getByText(/型线资料不足/)).toBeVisible();
    expect(within(panel).getByText('计算失败')).toBeVisible();

    const action = within(panel).getByRole('button', { name: /steamer-structure/ });
    expect(action.textContent).toContain('质量');
    fireEvent.click(action);
    expect(await screen.findByRole('heading', { level: 1, name: 'Weights & Loading' })).toBeVisible();
    await waitFor(() => expect(focusedLabel()).toBe('lightship steamer-structure 质量'));
    // Following a finding is a view change and nothing else.
    expect(within(document.querySelector('.operation-bar') as HTMLElement).queryByText('未保存修改')).toBeNull();
    expect(api.saveProject).not.toHaveBeenCalled();
    expect(api.enqueueRun).not.toHaveBeenCalled();
  });

  it('offers the editable source when a serious finding also names a result-only path', async () => {
    const run = savedRun();
    const finding = { ...MASS_UNKNOWN, path: '$.stages.loading.data', source_path: '$.weight_groups[0].items[0].mass_t' };
    run.result!.diagnostics = [finding];
    run.result!.stages.loading.diagnostics = [finding];
    vi.mocked(api.listRuns).mockResolvedValue([run]);
    await open();
    const action = await within(readiness()).findByRole('button', { name: /steamer-structure/ });
    fireEvent.click(action);
    await waitFor(() => expect(focusedLabel()).toBe('lightship steamer-structure 质量'));
    expect(api.saveProject).not.toHaveBeenCalled();
    expect(api.enqueueRun).not.toHaveBeenCalled();
  });

  it('keeps a previous run readable as history while the draft is edited, without making it current', async () => {
    vi.mocked(api.listRuns).mockResolvedValue([savedRun()]);
    await open();
    fireEvent.click(screen.getByRole('button', { name: '船型与几何' }));
    fireEvent.change(await screen.findByLabelText('船长'), { target: { value: '96' } });
    fireEvent.click(screen.getByRole('button', { name: '概览' }));

    const panel = readiness();
    // The saved run is still the most useful thing on the page, and it is still
    // attributed to itself and described as the previous check.
    expect(said(panel, '.readiness-attribution')).toContain('运行 run-a');
    expect(said(panel, '.readiness-history')).toContain('上一次检查');
    expect(said(panel, '.readiness-history')).toContain('需要保存修订并重新运行');
    // The edited request is explicitly not certified by that older run.
    expect(within(panel).queryByText('已通过')).toBeNull();
    // And the guarded current result is still hidden, exactly as before.
    const result = screen.getByRole('heading', { name: /当前结果/ }).closest('.chapter-group') as HTMLElement;
    expect(within(result).getByText('尚无当前结果')).toBeVisible();
    expect(within(result).getByText(/草稿有未保存修改/)).toBeVisible();
  });

  it('refuses another condition’s findings and the five unavailable states separately', async () => {
    const stages = {
      loading: envelope('completed', true, { values: { total_mass_t: 27200 } }),
      equilibrium: envelope('unavailable', true, null, '型线资料不足'),
      gz: envelope('model_limit', true, null, '超出方法适用范围'),
      deck: envelope('canceled', true, null, '该阶段已取消'),
      resistance: envelope('not_requested', false, null, '未请求'),
      propulsion: envelope('failed', true, null, '数值内核未收敛'),
    } as AnalysisResult['stages'];
    vi.mocked(api.listRuns).mockResolvedValue([
      savedRun({ id: 'run-deep', condition_id: 'deep', result: {
        ...savedRun({}, stages).result!, condition_id: 'deep',
      } }, stages),
      savedRun({ id: 'run-loaded' }, stages),
    ]);
    await open();
    const panel = readiness();
    expect(said(panel, '.readiness-attribution')).toContain('运行 run-loaded');
    expect(said(panel, '.readiness-attribution')).not.toContain('run-deep');
    for (const label of ['计算完成', '暂不可计算', '模型越界', '已取消', '未请求', '计算失败']) {
      expect(within(panel).getAllByText(label).length, label).toBeGreaterThan(0);
    }
    // Each blocked stage keeps the reason the run itself recorded.
    expect(within(panel).getByText(/数值内核未收敛/)).toBeVisible();

    fireEvent.change(screen.getByLabelText('当前工况'), { target: { value: 'deep' } });
    await waitFor(() => expect(said(readiness(), '.readiness-attribution')).toContain('run-deep'));
  });
});

describe('arriving from a report diagnostic', () => {
  const href = diagnosticHref('p1', 'run-a', '$.weight_groups[0].items[0].mass_t');

  it('focuses the named field of an owned run without saving, running or remounting', async () => {
    vi.mocked(api.getRun).mockResolvedValue(savedRun());
    await open(href);
    expect(await screen.findByRole('heading', { level: 1, name: 'Weights & Loading' })).toBeVisible();
    await waitFor(() => expect(focusedLabel()).toBe('lightship steamer-structure 质量'));
    expect(api.getRun).toHaveBeenCalledWith('run-a');
    expect(api.saveProject).not.toHaveBeenCalled();
    expect(api.enqueueRun).not.toHaveBeenCalled();

    // The same draft survives a second arrival: no remount, no reload.
    fireEvent.change(document.activeElement as HTMLElement, { target: { value: '120' } });
    expect(screen.getByLabelText('lightship steamer-structure 质量')).toHaveValue(120);
    window.history.replaceState(null, '', diagnosticHref('p1', 'run-a', '$.hull.loa_m'));
    window.dispatchEvent(new HashChangeEvent('hashchange'));
    expect(await screen.findByRole('heading', { level: 1, name: 'Hull & Geometry' })).toBeVisible();
    await waitFor(() => expect(focusedLabel()).toBe('船长'));
    expect(api.getProject).toHaveBeenCalledTimes(1);
  });

  it('refuses a foreign run, a malformed address and a run with no saved result', async () => {
    vi.mocked(api.getRun).mockResolvedValue(savedRun({ project_id: 'p2' }));
    await open(href);
    expect(await screen.findByText(/其他项目/)).toBeVisible();
    expect(screen.getByRole('heading', { level: 1, name: '解析方箱' })).toBeVisible();
    expect(focusedLabel()).toBeNull();

    vi.mocked(api.getRun).mockResolvedValue(savedRun({ id: 'run-b', result: null }));
    window.history.replaceState(null, '', diagnosticHref('p1', 'run-b', '$.hull.loa_m'));
    window.dispatchEvent(new HashChangeEvent('hashchange'));
    expect(await screen.findByText(/尚无已保存结果/)).toBeVisible();

    cleanup();
    await open('#/projects/p1/diagnostics/run-a/%E0%A4%A');
    await waitFor(() => expect(api.getRun).toHaveBeenCalled());
    const alerts = document.querySelector('.workbench-alerts') as HTMLElement;
    expect(within(alerts).queryByText(/其他项目|尚无已保存结果/)).toBeNull();
    expect(focusedLabel()).toBeNull();
  });

  it('drops a late answer that belongs to a destination the reader has left', async () => {
    const pending = new Map<string, (run: RunView) => void>();
    vi.mocked(api.getRun).mockImplementation((id: string) => new Promise<RunView>(resolve => { pending.set(id, resolve); }));
    await open(href);

    // The reader leaves the diagnostic address for the project's plain one while
    // the answer is still out. The answer must not move the page afterwards.
    window.history.replaceState(null, '', '#/projects/p1');
    window.dispatchEvent(new HashChangeEvent('hashchange'));
    await act(async () => {
      pending.get('run-a')!(savedRun({ id: 'run-a' }));
      await Promise.resolve();
    });
    expect(focusedLabel()).toBeNull();
    expect(screen.getByRole('heading', { level: 1, name: '解析方箱' })).toBeVisible();
  });

  it('retires a pending focus when the reader returns to the plain project address', async () => {
    const frames: FrameRequestCallback[] = [];
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => { frames.push(callback); return frames.length; });
    vi.stubGlobal('cancelAnimationFrame', () => {});
    vi.mocked(api.getRun).mockResolvedValue(savedRun());
    await open(href);
    expect(await screen.findByRole('heading', { level: 1, name: 'Weights & Loading' })).toBeVisible();
    window.history.replaceState(null, '', '#/projects/p1');
    window.dispatchEvent(new HashChangeEvent('hashchange'));
    act(() => { for (const callback of frames.splice(0)) callback(0); });
    expect(focusedLabel()).toBeNull();
    expect(api.saveProject).not.toHaveBeenCalled();
  });

  it('shows the literal fallback path beside the focused Project Data editor', async () => {
    vi.mocked(api.getRun).mockResolvedValue(savedRun());
    await open(diagnosticHref('p1', 'run-a', '$.hull.sources.loa_m'));
    expect(await screen.findByRole('heading', { level: 1, name: 'Project Data' })).toBeVisible();
    await waitFor(() => expect(document.activeElement).toBe(screen.getByLabelText('项目 JSON')));
    const alerts = document.querySelector('.workbench-alerts') as HTMLElement;
    expect(within(alerts).getByText(/原路径 \$\.hull\.sources\.loa_m/)).toBeVisible();
    expect(api.saveProject).not.toHaveBeenCalled();
    expect(api.enqueueRun).not.toHaveBeenCalled();
  });

  it('follows the same link again after the reader goes back and forward', async () => {
    vi.mocked(api.getRun).mockResolvedValue(savedRun());
    await open(href);
    expect(await screen.findByRole('heading', { level: 1, name: 'Weights & Loading' })).toBeVisible();
    await waitFor(() => expect(focusedLabel()).toBe('lightship steamer-structure 质量'));

    // Back to the project's plain address: nothing is asked for again.
    window.history.replaceState(null, '', '#/projects/p1');
    window.dispatchEvent(new HashChangeEvent('hashchange'));
    await waitFor(() => expect(api.getRun).toHaveBeenCalledTimes(1));
    await new Promise(resolve => setTimeout(resolve, 0));
    expect(api.getRun).toHaveBeenCalledTimes(1);

    // Forward to the very same address: it is followed again, not remembered as
    // already consumed.
    window.history.replaceState(null, '', href);
    window.dispatchEvent(new HashChangeEvent('hashchange'));
    expect(await screen.findByRole('heading', { level: 1, name: 'Weights & Loading' })).toBeVisible();
    await waitFor(() => expect(focusedLabel()).toBe('lightship steamer-structure 质量'));
  });

  it('refuses a run that is not the one asked for, or disagrees with its own result', async () => {
    vi.mocked(api.getRun).mockResolvedValue(savedRun({ id: 'someone-else' }));
    await open(href);
    expect(await screen.findByText(/与地址要求的 run-a 不一致/)).toBeVisible();
    expect(focusedLabel()).toBeNull();

    cleanup();
    const inconsistent = savedRun();
    inconsistent.result!.condition_id = 'deep';
    vi.mocked(api.getRun).mockResolvedValue(inconsistent);
    await open(href);
    expect(await screen.findByText(/项目、工况或请求指纹与其保存结果不一致/)).toBeVisible();
    expect(focusedLabel()).toBeNull();

    cleanup();
    const moved = savedRun({ condition_id: 'removed-condition' });
    moved.result!.condition_id = 'removed-condition';
    vi.mocked(api.getRun).mockResolvedValue(moved);
    await open(href);
    expect(await screen.findByText(/工况 removed-condition 已不在当前项目/)).toBeVisible();
    expect(focusedLabel()).toBeNull();
    // A removed condition is never resurrected, so the selection is unchanged.
    expect(screen.getByLabelText('当前工况')).toHaveValue('loaded');
  });

  it('explains a malformed diagnostic address instead of arriving silently', async () => {
    await open('#/projects/p1/diagnostics/run-a/%E0%A4%A');
    expect(await screen.findByText(/地址里的诊断定位/)).toBeVisible();
    expect(api.getRun).not.toHaveBeenCalled();
    expect(focusedLabel()).toBeNull();

    cleanup();
    await open('#/projects/p1/diagnostics/run-a/hull.loa_m');
    expect(await screen.findByText(/诊断路径不是项目路径/)).toBeVisible();
    expect(api.getRun).not.toHaveBeenCalled();
  });

  it('keeps the newer-revision notice on screen after the jump succeeds', async () => {
    vi.mocked(api.getRun).mockResolvedValue(savedRun({ revision: 2 }));
    await open(href);
    expect(await screen.findByRole('heading', { level: 1, name: 'Weights & Loading' })).toBeVisible();
    await waitFor(() => expect(focusedLabel()).toBe('lightship steamer-structure 质量'));
    const alerts = document.querySelector('.workbench-alerts') as HTMLElement;
    expect(within(alerts).getByText(/该诊断来自修订 2/)).toBeVisible();
    expect(screen.getByLabelText('当前工况')).toHaveValue('loaded');
  });

  it('refuses a jump that would discard unapplied JSON, and lets the reader discard it', async () => {
    vi.mocked(api.getRun).mockResolvedValue(savedRun());
    const onDirtyChange = vi.fn();
    await open(undefined, onDirtyChange);
    fireEvent.click(screen.getByRole('button', { name: '项目数据' }));
    const editor = await screen.findByLabelText('项目 JSON') as HTMLTextAreaElement;
    const broken = '{"schema":"plimsoll-project-1"}';
    fireEvent.change(editor, { target: { value: broken } });

    // Hand-written text is the reader's unsaved work: the leave guard is told,
    // even though the applied draft is still clean.
    expect(onDirtyChange).toHaveBeenLastCalledWith(true);
    expect(within(document.querySelector('.operation-bar') as HTMLElement).queryByText('未保存修改')).toBeNull();

    // Following a diagnostic would drop that edit, so the jump is refused, the
    // chapter stays, and the text is untouched.
    window.history.replaceState(null, '', href);
    window.dispatchEvent(new HashChangeEvent('hashchange'));
    expect(await screen.findByText(/跳转会丢弃这段未应用的编辑/)).toBeVisible();
    expect(screen.getByRole('heading', { level: 1, name: 'Project Data' })).toBeVisible();
    expect((screen.getByLabelText('项目 JSON') as HTMLTextAreaElement).value).toBe(broken);
    expect(api.saveProject).not.toHaveBeenCalled();
    expect(api.enqueueRun).not.toHaveBeenCalled();

    // Chapter navigation refuses for the same reason and never discards it.
    fireEvent.click(screen.getByRole('button', { name: '概览' }));
    expect(screen.getByRole('heading', { level: 1, name: 'Project Data' })).toBeVisible();
    expect((screen.getByLabelText('项目 JSON') as HTMLTextAreaElement).value).toBe(broken);

    // The reader can throw invalid text away explicitly, and is then free to go.
    fireEvent.click(screen.getByRole('button', { name: '放弃未应用的文本' }));
    await waitFor(() => expect(onDirtyChange).toHaveBeenLastCalledWith(false));
    expect((screen.getByLabelText('项目 JSON') as HTMLTextAreaElement).value).not.toBe(broken);
    window.dispatchEvent(new HashChangeEvent('hashchange'));
    expect(await screen.findByRole('heading', { level: 1, name: 'Weights & Loading' })).toBeVisible();
    await waitFor(() => expect(focusedLabel()).toBe('lightship steamer-structure 质量'));
    expect(api.saveProject).not.toHaveBeenCalled();
  });

  it('never submits unapplied JSON, and keeps it across a save', async () => {
    vi.mocked(api.saveProject).mockImplementation(async (_id, input) => ({ project_id: 'p1', revision: 2, project: input.project }));
    await open();
    fireEvent.click(screen.getByRole('button', { name: '船型与几何' }));
    fireEvent.change(await screen.findByLabelText('船长'), { target: { value: '96' } });
    fireEvent.click(screen.getByRole('button', { name: '项目数据' }));
    const editor = await screen.findByLabelText('项目 JSON') as HTMLTextAreaElement;
    const typed = JSON.stringify({ ...project, name: '手改舰名' }, null, 2);
    fireEvent.change(editor, { target: { value: typed } });

    // Saving writes the applied draft — the dimension change, not the name the
    // reader typed but never applied — and leaves that text exactly as it was.
    fireEvent.click(screen.getByRole('button', { name: '保存修订' }));
    await waitFor(() => expect(api.saveProject).toHaveBeenCalled());
    const saved = vi.mocked(api.saveProject).mock.calls[0][1].project;
    expect((saved.hull.loa_m as number)).toBe(96);
    expect(saved.name).toBe('解析方箱');
    expect((screen.getByLabelText('项目 JSON') as HTMLTextAreaElement).value).toBe(typed);
    expect(api.enqueueRun).not.toHaveBeenCalled();

    // Applied on request, the very same text does reach the draft and the save.
    fireEvent.click(screen.getByRole('button', { name: '应用到草稿' }));
    await waitFor(() => expect(screen.getByRole('button', { name: '保存修订' })).not.toBeDisabled());
    fireEvent.click(screen.getByRole('button', { name: '保存修订' }));
    await waitFor(() => expect(api.saveProject).toHaveBeenCalledTimes(2));
    expect(vi.mocked(api.saveProject).mock.calls[1][1].project.name).toBe('手改舰名');
  });

  it('refuses a ledger item the live draft no longer holds, and says which one', async () => {
    vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 1, project: {
      ...project,
      weight_groups: [{ id: 'lightship', label: '空船', items: [{ id: 'deck-fittings', mass_t: 40, x_m: 20 }] }],
    } });
    vi.mocked(api.getRun).mockResolvedValue(savedRun());
    await open(href);
    // The saved run saw `steamer-structure`; the draft no longer has it, and the
    // reader is told so instead of being sent to the item now at that index.
    expect(await screen.findByText(/steamer-structure \/ .*已不在当前项目|steamer-structure.*已不在当前项目/)).toBeVisible();
    expect(screen.getByRole('heading', { level: 1, name: '解析方箱' })).toBeVisible();
    expect(focusedLabel()).toBeNull();
  });
});
