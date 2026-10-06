import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import * as api from '../api';
import { Run } from '../pages/Run';
import type { AnalysisResult, RunView, StageEnvelope } from '../types';

/**
 * The run page's behaviour: the six real states, a cancellation that was only
 * requested, a failing cancel that can be retried, polling that stops at a
 * terminal state, and late replies that must not overwrite the run in front of
 * the reader.
 *
 * Fixtures are inline and use the coordinator's saved shapes; the shared older
 * fixtures are left exactly as they are.
 */
vi.mock('../api', async original => ({ ...await original<typeof import('../api')>(),
  getRun: vi.fn(), cancelRun: vi.fn() }));

function stage(status: StageEnvelope['status'], requested: boolean, data: StageEnvelope['data'] = null, reason: string | null = null,
  diagnostics: StageEnvelope['diagnostics'] = []): StageEnvelope {
  return {
    status, requested, reason,
    validity: { complete: status === 'completed', converged: status === 'completed' ? true : null, model_applicable: status === 'completed' ? true : null, historical_validated: null },
    method_versions: {}, assumptions: [], diagnostics, data,
  };
}

function savedResult(stages: Record<string, StageEnvelope>, status: AnalysisResult['status'] = 'completed'): AnalysisResult {
  return {
    schema: 'plimsoll-analysis-1', status, project_id: 'p1', condition_id: 'normal',
    project_fingerprint: 'pf', input_fingerprint: 'if', request_fingerprint: 'rf',
    request: { stages: Object.keys(stages) },
    input_snapshot: { schema: 'plimsoll-project-1', id: 'p1', name: 'HMS Fixture', revision: 3, hull: {}, geometry: null,
      loading_conditions: [{ id: 'normal', label: '正常载荷' }], weight_groups: [] },
    units: { length: 'm', mass: 't' }, method_versions: {}, sources: {}, diagnostics: [],
    validity: { complete: status === 'completed', converged: true, model_applicable: true, historical_validated: null },
    stages,
  };
}

function runOf(patch: Partial<RunView> & { status: RunView['status'] }): RunView {
  return {
    id: 'run-1', project_id: 'p1', revision: 3, condition_id: 'normal', request_fingerprint: 'rf',
    created_at: '2026-10-06T00:00:00Z', started_at: null, finished_at: null,
    cancel_requested: false, result: null, error: null, ...patch,
  };
}

/** Six requested stages, more than any first screen could ever show. */
function manyStages(): Record<string, StageEnvelope> {
  return {
    loading: stage('completed', true, { values: { total_mass_t: 27200 } }),
    geometry: stage('completed', true, { values: { volume_m3: 31000 } }),
    equilibrium: stage('completed', true, { waterline_above_keel_m: 9.92, heel_deg: 0 }),
    hydrostatics: stage('completed', true, { values: { gm_t_m: 1.85 } }),
    resistance: stage('failed', true, null, '阻力表缺失'),
    flooding: stage('model_limit', true, { status: 'model_limit', stop_reason: 'partial_aperture' }, '仅部分开口'),
  };
}

let readCount = () => 0;

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (cause: unknown) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.mocked(api.getRun).mockReset();
  readCount = () => (api.getRun as unknown as { mock: { calls: unknown[][] } }).mock.calls.length;
  vi.mocked(api.cancelRun).mockReset();
});

afterEach(() => { cleanup(); vi.useRealTimers(); });

describe('run states', () => {
  it('names each of the six real states, without percentages or a guessed stage', async () => {
    const cases: Array<[RunView['status'], string]> = [
      ['queued', '排队中'], ['running', '计算中'], ['completed', '计算完成'],
      ['partial', '部分完成'], ['canceled', '已取消'], ['failed', '计算失败'],
    ];
    for (const [status, label] of cases) {
      const view = runOf({ status, result: savedResult(manyStages(), status === 'completed' ? 'completed' : 'partial') });
      vi.mocked(api.getRun).mockResolvedValue(view);
      const { unmount } = render(<Run runId="run-1" onBack={vi.fn()} onReport={vi.fn()} />);
      expect(await screen.findByRole('heading', { name: label })).toBeVisible();
      // A queued or running run has no stage progress to report at all: no
      // percentage, no fraction of stages, no claim about what is computing.
      const region = document.querySelector('.run-status')!;
      expect(region.textContent).not.toMatch(/%|已完成|正在计算/);
      unmount();
      cleanup();
    }
  });

  it('keeps every requested stage reachable, past four, with an index entry each', async () => {
    vi.mocked(api.getRun).mockResolvedValue(runOf({ status: 'partial', result: savedResult(manyStages(), 'partial') }));
    render(<Run runId="run-1" onBack={vi.fn()} onReport={vi.fn()} />);
    const cards = await screen.findAllByRole('article');
    expect(cards.map(card => card.id)).toEqual(['stage-loading', 'stage-geometry', 'stage-equilibrium',
      'stage-hydrostatics', 'stage-resistance', 'stage-flooding']);
    expect(screen.getAllByRole('link').map(link => link.getAttribute('href'))).toEqual([
      '#/runs/run-1/stages/loading', '#/runs/run-1/stages/geometry', '#/runs/run-1/stages/equilibrium',
      '#/runs/run-1/stages/hydrostatics', '#/runs/run-1/stages/resistance', '#/runs/run-1/stages/flooding',
    ]);
    // Every stage heading is a real focus target for the section it names.
    for (const card of cards) expect(card.querySelector('h3')!.getAttribute('tabindex')).toBe('-1');
  });

  it('reads the ship name, revision and condition from the saved snapshot, and folds the fingerprint away', async () => {
    vi.mocked(api.getRun).mockResolvedValue(runOf({ status: 'completed', result: savedResult({ loading: stage('completed', true, { values: { total_mass_t: 1 } }) }) }));
    render(<Run runId="run-1" onBack={vi.fn()} onReport={vi.fn()} />);
    expect(await screen.findByText('HMS Fixture')).toBeVisible();
    expect(screen.getByText('修订 3')).toBeVisible();
    expect(screen.getByText('正常载荷')).toBeVisible();
    expect(screen.getByText('run-1')).toBeVisible();
    // The fingerprint is folded, not printed across the header.
    const meta = document.querySelector('.run-meta') as HTMLDetailsElement;
    expect(meta).not.toBeNull();
    expect(meta.open).toBe(false);
    expect(within(meta).getByText('rf')).toBeInTheDocument();
    expect(document.querySelector('.run-identity')!.textContent).not.toContain('rf');
    expect(document.querySelector('.run-status')!.textContent).not.toContain('rf');
  });

  it('stops polling once the run is terminal', async () => {
    vi.mocked(api.getRun).mockResolvedValue(runOf({ status: 'completed', result: savedResult({ loading: stage('completed', true, null) }) }));
    render(<Run runId="run-1" onBack={vi.fn()} onReport={vi.fn()} />);
    await screen.findByRole('heading', { name: '计算完成' });
    await act(async () => { await vi.advanceTimersByTimeAsync(9000); });
    expect(api.getRun).toHaveBeenCalledTimes(1);
  });

  it('keeps polling a queued run and reports the saved result of a canceled one', async () => {
    const queued = runOf({ status: 'queued' });
    vi.mocked(api.getRun).mockResolvedValue(queued);
    const { unmount } = render(<Run runId="run-1" onBack={vi.fn()} onReport={vi.fn()} />);
    await screen.findByRole('heading', { name: '排队中' });
    await act(async () => { await vi.advanceTimersByTimeAsync(3100); });
    expect(readCount()).toBeGreaterThan(1);
    unmount();
    cleanup();

    // A canceled run that saved results before stopping is still reportable.
    const before = readCount();
    const canceled = runOf({ status: 'canceled', cancel_requested: true, result: savedResult(manyStages(), 'canceled') });
    vi.mocked(api.getRun).mockResolvedValue(canceled);
    const onReport = vi.fn();
    render(<Run runId="run-1" onBack={vi.fn()} onReport={onReport} />);
    await screen.findByRole('heading', { name: '已取消' });
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: '查看完整报告 ↗' })); });
    expect(onReport).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(readCount() - before).toBe(1);
  });
});

describe('cancellation', () => {
  it('calls a requested cancellation a request, never a cancellation', async () => {
    vi.mocked(api.getRun).mockResolvedValue(runOf({ status: 'running', cancel_requested: true }));
    const { unmount } = render(<Run runId="run-1" onBack={vi.fn()} onReport={vi.fn()} />);
    expect(await screen.findByRole('heading', { name: '已请求取消' })).toBeVisible();
    expect(screen.queryByRole('heading', { name: '已取消' })).toBeNull();
    expect(screen.getByRole('button', { name: '已请求取消' })).toBeDisabled();
    unmount();

    // Only the server's own terminal state ends it.
    cleanup();
    vi.mocked(api.getRun).mockResolvedValue(runOf({ status: 'canceled', cancel_requested: true }));
    render(<Run runId="run-1" onBack={vi.fn()} onReport={vi.fn()} />);
    expect(await screen.findByRole('heading', { name: '已取消' })).toBeVisible();
  });

  it('separates a failing cancel from reading, keeps the run, and allows a retry', async () => {
    vi.mocked(api.getRun).mockResolvedValue(runOf({ status: 'running' }));
    vi.mocked(api.cancelRun).mockRejectedValueOnce(new Error('取消请求未被接受'))
      .mockResolvedValueOnce(runOf({ status: 'canceled', cancel_requested: true }));
    render(<Run runId="run-1" onBack={vi.fn()} onReport={vi.fn()} />);
    const button = await screen.findByRole('button', { name: '取消计算' });
    await act(async () => { fireEvent.click(button); });

    expect(await screen.findByText(/取消请求未被接受/)).toBeVisible();
    // The read loop keeps running and must not erase the cancel failure.
    await act(async () => { await vi.advanceTimersByTimeAsync(1600); });
    expect(readCount()).toBeGreaterThan(1);
    expect(screen.getByText(/取消请求未被接受/)).toBeVisible();
    expect(screen.getByRole('heading', { name: '计算中' })).toBeVisible();

    const retry = screen.getByRole('button', { name: '重试取消' });
    await act(async () => { fireEvent.click(retry); });
    await waitFor(() => expect(screen.getByRole('heading', { name: '已取消' })).toBeVisible());
    expect(screen.queryByText(/取消请求未被接受/)).toBeNull();
    expect(api.cancelRun).toHaveBeenCalledTimes(2);
  });

  it('stops the outstanding poll once a terminal cancel answer arrives', async () => {
    vi.mocked(api.getRun).mockResolvedValue(runOf({ status: 'running' }));
    vi.mocked(api.cancelRun).mockResolvedValue(runOf({ status: 'canceled', cancel_requested: true }));
    render(<Run runId="run-1" onBack={vi.fn()} onReport={vi.fn()} />);
    const button = await screen.findByRole('button', { name: '取消计算' });
    await act(async () => { fireEvent.click(button); });
    await screen.findByRole('heading', { name: '已取消' });
    const calls = readCount();
    await act(async () => { await vi.advanceTimersByTimeAsync(6000); });
    expect(api.getRun).toHaveBeenCalledTimes(calls);
  });
});

describe('late replies', () => {
  it('drops a read that arrives after the page moved to another run', async () => {
    const first = deferred<RunView>();
    const second = deferred<RunView>();
    vi.mocked(api.getRun).mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
    const { rerender } = render(<Run runId="run-a" onBack={vi.fn()} onReport={vi.fn()} />);
    rerender(<Run runId="run-b" onBack={vi.fn()} onReport={vi.fn()} />);

    await act(async () => {
      second.resolve(runOf({ id: 'run-b', status: 'completed', result: savedResult({ loading: stage('completed', true, { values: { total_mass_t: 2 } }) }) }));
      await second.promise;
    });
    expect(await screen.findByRole('heading', { name: '计算完成' })).toBeVisible();

    await act(async () => {
      first.resolve(runOf({ id: 'run-a', status: 'failed' }));
      await first.promise;
    });
    // The superseded run never appears, and neither does its state.
    expect(screen.queryByRole('heading', { name: '计算失败' })).toBeNull();
    expect(screen.getByText('run-b')).toBeVisible();
  });

  it('ignores a cancel reply that arrives after the page moved on, and after unmount', async () => {
    vi.mocked(api.getRun).mockResolvedValue(runOf({ status: 'running' }));
    const late = deferred<RunView>();
    vi.mocked(api.cancelRun).mockReturnValue(late.promise);
    const { rerender, unmount } = render(<Run runId="run-a" onBack={vi.fn()} onReport={vi.fn()} />);
    const button = await screen.findByRole('button', { name: '取消计算' });
    await act(async () => { fireEvent.click(button); });
    rerender(<Run runId="run-b" onBack={vi.fn()} onReport={vi.fn()} />);
    await act(async () => {
      late.resolve(runOf({ status: 'canceled', cancel_requested: true }));
      await late.promise;
    });
    expect(screen.queryByRole('heading', { name: '已取消' })).toBeNull();

    unmount();
    await act(async () => {
      late.resolve(runOf({ status: 'canceled', cancel_requested: true }));
      await late.promise;
    });
    expect(document.body.textContent).toBe('');
  });

  it('reports a first read that failed, instead of a skeleton that never resolves', async () => {
    vi.mocked(api.getRun).mockRejectedValueOnce(new Error('工作空间暂时不可达'))
      .mockResolvedValue(runOf({ status: 'completed', result: savedResult({ loading: stage('completed', true, { values: { total_mass_t: 27200 } }) }) }));
    render(<Run runId="run-1" onBack={vi.fn()} onReport={vi.fn()} />);
    expect(await screen.findByText('工作空间暂时不可达')).toBeVisible();
    expect(screen.queryByLabelText('正在读取运行')).toBeNull();
    // A failed first read waits for the reader, and only for the reader.
    expect(api.getRun).toHaveBeenCalledTimes(1);

    const retry = screen.getByRole('button', { name: '重新读取' });
    await act(async () => { fireEvent.click(retry); });
    expect(await screen.findByRole('heading', { name: '计算完成' })).toBeVisible();
    expect(screen.queryByText('工作空间暂时不可达')).toBeNull();
  });

  it('keeps watching a run after a cancel that was only accepted', async () => {
    const running = runOf({ status: 'running' });
    const canceling = { ...running, cancel_requested: true };
    const canceled = runOf({ status: 'canceled', cancel_requested: true });
    let serverDone = false;
    let readsAfterCancel = 0;
    vi.mocked(api.getRun).mockImplementation(async () => {
      if (!serverDone) return running;
      readsAfterCancel += 1;
      // The server acknowledges the request first and only later reports the
      // run as actually ended.
      return readsAfterCancel >= 2 ? canceled : canceling;
    });
    vi.mocked(api.cancelRun).mockImplementation(async () => { serverDone = true; return canceling; });
    render(<Run runId="run-1" onBack={vi.fn()} onReport={vi.fn()} />);

    const before = readCount();
    const button = await screen.findByRole('button', { name: '取消计算' });
    await act(async () => { fireEvent.click(button); });

    // Accepted, but not finished: still running, still only requested.
    expect(await screen.findByRole('heading', { name: '已请求取消' })).toBeVisible();
    expect(screen.queryByRole('heading', { name: '已取消' })).toBeNull();
    // The read loop was restarted by the nonterminal answer and keeps running.
    expect(readCount()).toBeGreaterThan(before);
    await act(async () => { await vi.advanceTimersByTimeAsync(1600); });
    expect(readCount()).toBeGreaterThan(before + 1);
    expect(await screen.findByRole('heading', { name: '已取消' })).toBeVisible();
    // And it stops there.
    const settled = readCount();
    await act(async () => { await vi.advanceTimersByTimeAsync(6000); });
    expect(readCount()).toBe(settled);
  });

  it('does not replace a loaded run with an error when a later read fails', async () => {
    vi.mocked(api.getRun).mockResolvedValueOnce(runOf({ status: 'running' }))
      .mockRejectedValueOnce(new Error('工作空间暂时不可达'))
      .mockResolvedValueOnce(runOf({ status: 'completed' }));
    render(<Run runId="run-1" onBack={vi.fn()} onReport={vi.fn()} />);
    await screen.findByRole('heading', { name: '计算中' });
    await act(async () => { await vi.advanceTimersByTimeAsync(1600); });
    expect(screen.getByText('工作空间暂时不可达')).toBeVisible();
    expect(screen.getByRole('heading', { name: '计算中' })).toBeVisible();
    expect(screen.getByRole('button', { name: '取消计算' })).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: '重新读取' }));
    expect(await screen.findByRole('heading', { name: '计算完成' })).toBeVisible();
    expect(screen.queryByText('工作空间暂时不可达')).toBeNull();
  });

  it('can recover a failed poll while cancellation is already requested', async () => {
    vi.mocked(api.getRun).mockResolvedValueOnce(runOf({ status: 'running', cancel_requested: true }))
      .mockRejectedValueOnce(new Error('轮询连接中断'))
      .mockResolvedValueOnce(runOf({ status: 'canceled', cancel_requested: true }));
    render(<Run runId="run-1" onBack={vi.fn()} onReport={vi.fn()} />);
    await screen.findByRole('heading', { name: '已请求取消' });
    await act(async () => { await vi.advanceTimersByTimeAsync(1600); });
    expect(screen.getByText('轮询连接中断')).toBeVisible();
    expect(screen.getByRole('button', { name: '已请求取消' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '重新读取' }));
    expect(await screen.findByRole('heading', { name: '已取消' })).toBeVisible();
    expect(api.getRun).toHaveBeenCalledTimes(3);
  });
});

describe('stage evidence on the run page', () => {
  it('shows severe diagnostics directly and keeps the damage evidence in one place', async () => {
    const stages = manyStages();
    stages.resistance = stage('failed', true, null, '阻力表缺失',
      [{ code: 'resistance.no_bracket', severity: 'error', path: '$.stages.resistance', message: '速度网格内没有完整单调功率区间' },
        { code: 'resistance.note', severity: 'info', path: '$.stages.resistance', message: '使用工程估算方法' }]);
    stages.flooding = stage('model_limit', true, {
      status: 'model_limit', stop_reason: 'partial_aperture',
      validity: { complete: false, model_applicable: false, numerical_convergence: true, safe: null },
      scenario: { id: 'f1', duration_s: 60, time_step_s: 0.5 },
      timeline: [{ time_s: 12.5, equilibrium: { heel_deg: 2.1, trim_deg: 0.4, waterline_above_keel_m: 4.3 } }],
      final_state: { time_s: 12.5 }, initial_total_water_volume_m3: 0, initial_total_water_mass_t: 0,
      cumulative_sea_exchange_m3: 4.5, cumulative_sea_exchange_t: 4.61,
      volume_conservation_error_m3: 0, mass_conservation_error_t: 1.2e-15,
      terminal_head_tolerance_m: 1e-8, terminal_max_head_difference_m: 0.02,
      remaining_gz: { rows: [{ angle_deg: 10, gz_m: 0.21 }] }, gz_snapshots: [{ time_s: 12.5 }],
      downflooding: { status: 'no_open_points', event: null },
      diagnostics: [{ code: 'flooding.aperture_height', message: '液面越过有限开口高度' }],
    }, '仅部分开口');
    vi.mocked(api.getRun).mockResolvedValue(runOf({ status: 'partial', result: savedResult(stages, 'partial') }));
    render(<Run runId="run-1" onBack={vi.fn()} onReport={vi.fn()} />);

    // A severe finding is in place, not behind a disclosure.
    expect(await screen.findByText('速度网格内没有完整单调功率区间')).toBeVisible();
    // An ordinary note stays reachable without crowding the page.
    expect(screen.getByText('使用工程估算方法')).toBeInTheDocument();
    expect(document.querySelectorAll('.stage-diagnostics-open')).toHaveLength(1);
    // The damage evidence appears once, inside the flooding stage.
    expect(screen.getAllByText(/partial_aperture/)).toHaveLength(1);
    expect(screen.getAllByText('4.5 m³')).toHaveLength(1);
  });

  it('does not present residual numbers of a failed stage as results', async () => {
    const stages = { hydrostatics: stage('unavailable', true, { values: { gm_t_m: 9.99 } }, '型线资料不足') };
    vi.mocked(api.getRun).mockResolvedValue(runOf({ status: 'partial', result: savedResult(stages, 'partial') }));
    render(<Run runId="run-1" onBack={vi.fn()} onReport={vi.fn()} />);
    expect(await screen.findByText('型线资料不足')).toBeVisible();
    expect(screen.queryByText('9.99')).toBeNull();
    expect(screen.queryByText('初稳性高 GM')).toBeNull();
  });
});
