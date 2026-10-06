import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import * as api from '../api';
import { StageIndex } from '../components/StageIndex';
import { ReportPage } from '../pages/Report';
import type { AnalysisResult, RunView, StageEnvelope } from '../types';

/**
 * Stage positioning: the address, the scroll, the focus and the wait for a
 * section that is still mounting, plus how that behaves inside the real report
 * page. Reading the saved values is covered by result-reading.test.ts and
 * report.test.tsx, and no route library is involved anywhere.
 */
vi.mock('../api', async original => ({ ...await original<typeof import('../api')>(),
  getRun: vi.fn(), listRuns: vi.fn() }));
function stage(status: StageEnvelope['status'] = 'completed'): StageEnvelope {
  return {
    status, requested: true, reason: null,
    validity: { complete: status === 'completed', converged: null, model_applicable: null, historical_validated: null },
    method_versions: {}, assumptions: [], diagnostics: [], data: {},
  };
}

const listed = ['loading', 'equilibrium', 'resistance'].map(name => ({ name, stage: stage() }));

/** Stands in for the page body the index positions inside. */
function Report({ runId, names = listed.map(item => item.name), headingTabIndex = -1 }:
{ runId?: string; names?: string[]; headingTabIndex?: number }) {
  return <>
    <StageIndex page="reports" runId={runId} stages={names.map(name => ({ name, stage: stage() }))} />
    {names.map(name => <section key={name} id={`stage-${name}`}>
      <h3 tabIndex={headingTabIndex}>{name}</h3>
    </section>)}
  </>;
}

let scrolled: string[] = [];

// JSDOM schedules anchor navigation on a timer. Model the browser's immediate
// hash commit explicitly so an event from a previous test cannot cancel a click.
function clickStage(name: string) {
  const link = screen.getByRole('link', { name });
  link.addEventListener('click', event => event.preventDefault(), { once: true });
  fireEvent.click(link);
  window.history.replaceState(null, '', link.getAttribute('href')!);
  window.dispatchEvent(new HashChangeEvent('hashchange'));
}

beforeEach(() => {
  scrolled = [];
  Element.prototype.scrollIntoView = function scrollIntoView(this: Element) { scrolled.push(this.id); };
  window.history.replaceState(null, '', '/');
});

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('stage index navigation', () => {
  it('keeps the tool route in every address and lists exactly the requested stages', () => {
    render(<Report runId="r1" />);
    const links = screen.getAllByRole('link');
    expect(links.map(link => link.getAttribute('href'))).toEqual([
      '#/reports/r1/stages/loading', '#/reports/r1/stages/equilibrium', '#/reports/r1/stages/resistance',
    ]);
    expect(links.map(link => link.textContent)).toEqual(['载荷与重心', '浮态平衡', '阻力与功率']);
    // No percentage, no fabricated progress: the index only locates.
    expect(document.body.textContent).not.toMatch(/%/);
  });

  it('scrolls to the section and moves focus onto its heading when clicked', () => {
    render(<Report runId="r1" />);
    clickStage('浮态平衡');
    expect(scrolled).toEqual(['stage-equilibrium', 'stage-equilibrium']);
    expect(document.activeElement).toBe(document.getElementById('stage-equilibrium')!.querySelector('h3'));
  });

  it('focuses a heading that does not declare tabIndex yet, without inventing an address', () => {
    render(<Report runId="r1" headingTabIndex={undefined as unknown as number} />);
    clickStage('阻力与功率');
    const heading = document.getElementById('stage-resistance')!.querySelector('h3')!;
    expect(heading.getAttribute('tabindex')).toBe('-1');
    expect(document.activeElement).toBe(heading);
  });

  it('uses buttons, and still positions, when there is no run address to offer', () => {
    render(<Report />);
    expect(screen.queryByRole('link')).toBeNull();
    const button = screen.getByRole('button', { name: '载荷与重心' });
    expect(button).toHaveAttribute('type', 'button');
    fireEvent.click(button);
    expect(scrolled).toEqual(['stage-loading']);
    expect(document.activeElement).toBe(document.getElementById('stage-loading')!.querySelector('h3'));
  });

  it('positions a deep link without stealing focus, and ignores a target it never requested', async () => {
    window.history.replaceState(null, '', '#/reports/r1/stages/resistance');
    render(<Report runId="r1" />);
    await waitFor(() => expect(scrolled).toContain('stage-resistance'));
    expect(document.activeElement).toBe(document.body);

    // Another page, another run, an old address and an unrequested stage are
    // all no-ops: the reader stays on the current page.
    scrolled = [];
    for (const hash of ['#/runs/r1/stages/resistance', '#/reports/r2/stages/resistance',
      '#/reports/r1', '#/reports/r1/stages/flooding', '#stage-loading']) {
      window.history.replaceState(null, '', hash);
      window.dispatchEvent(new HashChangeEvent('hashchange'));
    }
    await Promise.resolve();
    expect(scrolled).toEqual([]);
    expect(document.activeElement).toBe(document.body);
  });

  it('follows a later hashchange while mounted and stops listening once unmounted', async () => {
    render(<Report runId="r1" />);
    window.history.replaceState(null, '', '#/reports/r1/stages/equilibrium');
    window.dispatchEvent(new HashChangeEvent('hashchange'));
    await waitFor(() => expect(scrolled).toEqual(['stage-equilibrium']));
    expect(document.activeElement).toBe(document.body);

    cleanup();
    scrolled = [];
    window.history.replaceState(null, '', '#/reports/r1/stages/loading');
    window.dispatchEvent(new HashChangeEvent('hashchange'));
    await Promise.resolve();
    expect(scrolled).toEqual([]);
  });

  it('waits for a section that is still mounting, without retrying forever', async () => {
    render(<StageIndex page="reports" runId="r1" stages={listed} />);
    // Nothing to position yet: no section carries the target id.
    clickStage('浮态平衡');
    expect(scrolled).toEqual([]);

    const section = document.createElement('section');
    section.id = 'stage-equilibrium';
    section.innerHTML = '<h3 tabindex="-1">浮态平衡</h3>';
    document.body.appendChild(section);
    await waitFor(() => expect(scrolled).toContain('stage-equilibrium'));
    expect(document.activeElement).toBe(section.querySelector('h3'));

    section.remove();
    cleanup();
  });

  it('renders nothing at all when no stage was requested', () => {
    const { container } = render(<StageIndex page="runs" stages={[]} />);
    expect(container.querySelector('nav')).toBeNull();
  });

  it.each(['existing', 'invalid', 'same'] as const)('keeps the latest target and click focus through %s hash navigation', mode => {
    const frames = new Map<number, FrameRequestCallback>();
    let sequence = 0;
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation(callback => {
      frames.set(++sequence, callback); return sequence;
    });
    vi.spyOn(window, 'cancelAnimationFrame').mockImplementation(id => { frames.delete(id); });
    const { container } = render(<>
      <StageIndex page="reports" runId="r1" stages={listed} />
      <section id="stage-resistance"><h3 tabIndex={-1}>阻力与功率</h3></section>
    </>);
    clickStage('浮态平衡');
    if (mode === 'existing') clickStage('阻力与功率');
    const target = mode === 'same' ? 'equilibrium' : mode === 'existing' ? 'resistance' : 'not-requested';
    window.history.replaceState(null, '', `#/reports/r1/stages/${target}`);
    window.dispatchEvent(new HashChangeEvent('hashchange'));
    const late = document.createElement('section');
    late.id = 'stage-equilibrium';
    late.innerHTML = '<h3 tabindex="-1">浮态平衡</h3>';
    container.appendChild(late);
    const queued = [...frames.values()]; frames.clear();
    queued.forEach(callback => callback(0));
    expect(scrolled).toEqual(mode === 'same' ? ['stage-equilibrium'] : mode === 'existing' ? ['stage-resistance', 'stage-resistance', 'stage-resistance'] : []);
    expect(document.activeElement).toBe(mode === 'same' ? late.querySelector('h3') : mode === 'existing' ? document.querySelector('#stage-resistance h3') : document.body);
  });
});

function savedResult(stages: Record<string, StageEnvelope>, status: AnalysisResult['status'] = 'completed'): AnalysisResult {
  return {
    schema: 'plimsoll-analysis-1', status, project_id: 'p1', condition_id: 'normal',
    project_fingerprint: 'pf', input_fingerprint: 'if', request_fingerprint: 'rf',
    request: { stages: Object.keys(stages) },
    input_snapshot: { schema: 'plimsoll-project-1', id: 'p1', name: 'HMS Fixture', revision: 2, hull: {}, geometry: null,
      loading_conditions: [{ id: 'normal', label: '正常载荷' }], weight_groups: [] },
    units: { length: 'm', mass: 't' }, method_versions: { coordinator: 'selected-loading-analysis-1' },
    sources: {}, diagnostics: [],
    validity: { complete: status === 'completed', converged: true, model_applicable: true, historical_validated: null },
    stages,
  };
}

function runOf(id: string, result: AnalysisResult | null): RunView {
  return {
    id, project_id: 'p1', revision: 2, condition_id: 'normal', status: result ? 'completed' : 'running',
    request_fingerprint: 'rf', created_at: '2026-10-06T00:00:00Z', started_at: null, finished_at: null,
    cancel_requested: false, result, error: null,
  };
}

const reportStages = (): Record<string, StageEnvelope> => ({
  loading: stage(), equilibrium: stage(), resistance: stage(),
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (cause: unknown) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

describe('the report page', () => {
  beforeEach(() => {
    vi.mocked(api.getRun).mockReset();
    vi.mocked(api.listRuns).mockReset();
    vi.mocked(api.listRuns).mockResolvedValue([]);
  });

  afterEach(() => { cleanup(); });

  it('reads a copied stage address without reloading, and keeps the page unit choice', async () => {
    const result = savedResult(reportStages());
    result.stages.loading.data = { values: { total_mass_t: 27200 } };
    vi.mocked(api.getRun).mockResolvedValue(runOf('run-1', result));
    window.location.hash = '#/reports/run-1/stages/equilibrium';
    render(<ReportPage runId="run-1" onBack={vi.fn()} />);

    expect(await screen.findByRole('heading', { level: 1, name: 'HMS Fixture' })).toBeVisible();
    const reads = vi.mocked(api.getRun).mock.calls.length;
    await waitFor(() => expect(scrolled).toContain('stage-equilibrium'));
    // A deep link positions only: it neither takes focus nor asks for the run again.
    expect(document.activeElement).toBe(document.body);
    expect(api.getRun).toHaveBeenCalledTimes(reads);

    fireEvent.change(screen.getByLabelText('报告mass显示单位'), { target: { value: 'kg' } });
    const readings = within(document.querySelector('.report-readings') as HTMLElement);
    expect(readings.getByText('27,200,000 kg')).toBeVisible();

    // The address a reader copies is the link's own href.
    expect(screen.getByRole('link', { name: '阻力与功率' }).getAttribute('href')).toBe('#/reports/run-1/stages/resistance');
    // The browser moves the address; the page reacts to it without another
    // request, and the reading grid keeps the reader's unit choice.
    window.location.hash = '#/reports/run-1/stages/resistance';
    window.dispatchEvent(new HashChangeEvent('hashchange'));
    await waitFor(() => expect(scrolled).toContain('stage-resistance'));
    expect(document.activeElement).toBe(document.body);
    expect(api.getRun).toHaveBeenCalledTimes(reads);
    expect(within(document.querySelector('.report-readings') as HTMLElement).getByText('27,200,000 kg')).toBeVisible();
    expect(document.querySelector('.report-stage-list')).not.toBeNull();

    // An address this run never requested leaves the reader where they are.
    scrolled = [];
    window.location.hash = '#/reports/run-1/stages/flooding';
    window.dispatchEvent(new HashChangeEvent('hashchange'));
    await Promise.resolve();
    expect(scrolled).toEqual([]);
  });

  it('keeps the main report readable when a comparison fails', async () => {
    vi.mocked(api.getRun).mockImplementation(async (id: string) => {
      if (id === 'run-1') return runOf('run-1', savedResult(reportStages()));
      throw new Error('对照运行读取失败');
    });
    vi.mocked(api.listRuns).mockResolvedValue([
      runOf('run-2', savedResult(reportStages())),
      runOf('run-3', savedResult(reportStages())),
    ]);
    render(<ReportPage runId="run-1" onBack={vi.fn()} />);
    await screen.findByRole('heading', { level: 1, name: 'HMS Fixture' });

    fireEvent.change(screen.getByLabelText('对照另一运行'), { target: { value: 'run-3' } });
    expect(await screen.findByText('对照运行读取失败')).toBeVisible();
    // The report itself is untouched by a comparison failure.
    expect(screen.getByRole('heading', { level: 1, name: 'HMS Fixture' })).toBeVisible();
    expect(document.querySelectorAll('.report-stage-list > article')).toHaveLength(3);

    // Clearing the selection clears the failure with it.
    fireEvent.change(screen.getByLabelText('对照另一运行'), { target: { value: 'run-2' } });
    await waitFor(() => expect(screen.queryByText('对照运行读取失败')).toBeNull());
    fireEvent.change(screen.getByLabelText('对照另一运行'), { target: { value: '' } });
    expect(screen.queryByText('对照运行读取失败')).toBeNull();
    expect(screen.queryByRole('heading', { name: '两次运行对照' })).toBeNull();
  });

  it('ignores a comparison that resolves after the reader chose another', async () => {
    const slow = deferred<RunView>();
    vi.mocked(api.getRun).mockImplementation(async (id: string) => {
      if (id === 'run-1') return runOf('run-1', savedResult(reportStages()));
      if (id === 'run-2') return slow.promise;
      const other = savedResult(reportStages());
      other.request_fingerprint = 'latest-choice';
      return runOf('run-3', other);
    });
    vi.mocked(api.listRuns).mockResolvedValue([
      runOf('run-2', savedResult(reportStages())),
      runOf('run-3', savedResult(reportStages())),
    ]);
    render(<ReportPage runId="run-1" onBack={vi.fn()} />);
    await screen.findByRole('heading', { level: 1, name: 'HMS Fixture' });

    fireEvent.change(screen.getByLabelText('对照另一运行'), { target: { value: 'run-2' } });
    fireEvent.change(screen.getByLabelText('对照另一运行'), { target: { value: 'run-3' } });
    await screen.findByRole('heading', { name: '两次运行对照' });
    expect(screen.getByText('latest-choice')).toBeVisible();

    // The superseded comparison arrives late, with its own request fingerprint.
    await act(async () => {
      const stale = savedResult(reportStages());
      stale.request_fingerprint = 'superseded-choice';
      slow.resolve(runOf('run-2', stale));
      await slow.promise;
    });
    expect(screen.queryByText('superseded-choice')).toBeNull();
    expect(screen.getByText('latest-choice')).toBeVisible();
    expect(screen.getAllByRole('heading', { name: '两次运行对照' })).toHaveLength(1);
  });

  it('separates the primary load failure from a comparison failure', async () => {
    vi.mocked(api.getRun).mockRejectedValueOnce(new Error('报告读取失败'));
    render(<ReportPage runId="run-1" onBack={vi.fn()} />);
    expect(await screen.findByText('报告读取失败')).toBeVisible();
    // No report and no comparison control, because there is no report to compare.
    expect(screen.queryByLabelText('对照另一运行')).toBeNull();
    expect(document.querySelector('.report-readings')).toBeNull();
  });

  it('starts a different run from nothing, and drops answers that belong to the old one', async () => {
    const old = deferred<RunView>();
    vi.mocked(api.getRun).mockImplementation(async (id: string) => {
      if (id === 'run-1') return old.promise;
      if (id === 'run-3') return runOf('run-3', savedResult(reportStages()));
      throw new Error('对照运行读取失败');
    });
    const { rerender } = render(<ReportPage runId="run-1" onBack={vi.fn()} />);
    rerender(<ReportPage runId="run-2" onBack={vi.fn()} />);

    await act(async () => {
      old.resolve(runOf('run-1', savedResult(reportStages())));
      await old.promise;
    });
    expect(screen.queryByRole('heading', { level: 1, name: 'HMS Fixture' })).toBeNull();

    vi.mocked(api.getRun).mockImplementation(async (id: string) => {
      if (id === 'run-3') return runOf('run-3', savedResult(reportStages()));
      throw new Error('对照运行读取失败');
    });
    rerender(<ReportPage runId="run-3" onBack={vi.fn()} />);
    expect(await screen.findByRole('heading', { level: 1, name: 'HMS Fixture' })).toBeVisible();
    // The new run starts with no history, no comparison and no stale failure.
    expect(screen.getByLabelText('对照另一运行')).toHaveValue('');
    expect(screen.queryByText(/读取失败/)).toBeNull();
    expect(screen.queryByRole('heading', { name: '两次运行对照' })).toBeNull();
  });
  it('scopes the page unit choice to one saved run and resets it for another', async () => {
    const first = savedResult(reportStages());
    first.input_snapshot = { ...first.input_snapshot, name: 'HMS First' };
    first.stages.loading.data = { values: { total_mass_t: 27200 } };
    const second = savedResult(reportStages());
    second.input_snapshot = { ...second.input_snapshot, name: 'HMS Second', display_preferences: {} };
    second.stages.loading.data = { values: { total_mass_t: 27200 } };
    vi.mocked(api.getRun).mockImplementation(async (id: string) => (id === 'run-1' ? runOf('run-1', first) : runOf('run-2', second)));
    const readings = () => within(document.querySelector('.report-readings') as HTMLElement);

    const { rerender } = render(<ReportPage runId="run-1" onBack={vi.fn()} />);
    expect(await screen.findByRole('heading', { level: 1, name: 'HMS First' })).toBeVisible();
    fireEvent.change(screen.getByLabelText('报告mass显示单位'), { target: { value: 'kg' } });
    expect(readings().getByText('27,200,000 kg')).toBeVisible();

    // The same run, a different stage address: the reader's choice is theirs.
    window.location.hash = '#/reports/run-1/stages/equilibrium';
    window.dispatchEvent(new HashChangeEvent('hashchange'));
    await waitFor(() => expect(scrolled).toContain('stage-equilibrium'));
    expect(readings().getByText('27,200,000 kg')).toBeVisible();

    // Another run, one that resolves immediately: no unmount can be relied on to
    // clear the choice, so the saved identity has to.
    rerender(<ReportPage runId="run-2" onBack={vi.fn()} />);
    expect(await screen.findByRole('heading', { level: 1, name: 'HMS Second' })).toBeVisible();
    expect(readings().getByText('27,200 t')).toBeVisible();
    expect(readings().queryByText('27,200,000 kg')).toBeNull();
    expect(screen.getByLabelText('报告mass显示单位')).toHaveValue('t');
  });
});