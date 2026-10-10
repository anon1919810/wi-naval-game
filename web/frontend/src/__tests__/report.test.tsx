import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { Report } from '../pages/Report';
import type { AnalysisResult, StageEnvelope } from '../types';
import { completedFixture, partialFixture } from './fixtures';

afterEach(cleanup);

describe('stored report semantics', () => {
  it('keeps a partial calculation readable and names its limited stage', () => {
    render(<Report result={partialFixture} runId="r1" />);
    expect(screen.getByText('部分完成')).toBeVisible();
    expect(screen.getByText('超出方法适用范围')).toBeVisible();
    expect(screen.queryByText('历史验证通过')).toBeNull();
    expect(screen.getByText(/request-123/)).toBeVisible();
  });

  it('does not turn unavailable deck coverage into a computed zero', () => {
    render(<Report result={partialFixture} runId="r1" />);
    expect(screen.getByText('甲板端点资料不足')).toBeVisible();
    expect(screen.queryByText('0 %')).toBeNull();
    expect(screen.getByRole('link', { name: /JSON/ })).toHaveAttribute('href', '/api/runs/r1/export?format=json');
    expect(screen.getByRole('link', { name: /CSV/ })).toHaveAttribute('href', '/api/runs/r1/export?format=csv');
  });

  it('marks incompatible method comparisons instead of showing a numeric delta', () => {
    const changed = structuredClone(completedFixture);
    changed.method_versions = { coordinator: 'different-version' };
    changed.request_fingerprint = 'request-456';
    render(<Report result={completedFixture} compareResult={changed} />);
    expect(screen.getByText(/不可直接比较/)).toBeVisible();
    expect(screen.getByText(/request-456/)).toBeVisible();
  });

  it('refuses deltas when a stage kernel version changed', () => {
    const changed = structuredClone(completedFixture);
    changed.stages.loading.method_versions = { kernel: 'new-kernel' };
    render(<Report result={completedFixture} compareResult={changed} />);
    expect(screen.getByText(/不可直接比较/)).toBeVisible();
  });

  it('shows resistance and shaft-power rows with applicability and estimate labels', () => {
    const actualShape = structuredClone(completedFixture);
    actualShape.stages.resistance = {
      ...actualShape.stages.resistance,
      requested: true, status: 'completed', reason: null, diagnostics: [], assumptions: [], method_versions: {},
      data: {
        method: 'holtrop_mennen_1982', estimate: true, primary_result: false,
        scenario: { source: 'Illustrative sourced study' }, validity: { model_applicable: false },
        rows: [{ speed_kn: 18, total_resistance_kn: 765.9, effective_power_kw: 7092.1,
          complete: true, estimate: true, primary_result: false, model_applicable: false }],
        power_rows: [{ speed_kn: 18, qpc: { value: 0.55, source: 'QPC study', estimate: true },
          effective_power_kw: 7092.1, shaft_power_kw: 12894.8, shaft_power_shp: 17292.2,
          complete: true, estimate: true, primary_result: false }],
      },
    };
    render(<Report result={actualShape} />);
    expect(screen.getByText('765.9 kN')).toBeVisible();
    expect(screen.getByText('12,894.8 kW')).toBeVisible();
    expect(screen.getByText('QPC study')).toBeVisible();
    expect(screen.getAllByText(/不在经验适用范围/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/工程估算/).length).toBeGreaterThan(0);
  });
});

/**
 * The saved shape the coordinator really writes, used to pin the report's own
 * projections: nested `values`, `power_rows`, and a stage list that includes a
 * name the interface has no label for yet.
 */
function stageEnvelope(status: StageEnvelope['status'], requested: boolean, data: StageEnvelope['data'] = null, reason: string | null = null,
  diagnostics: StageEnvelope['diagnostics'] = []): StageEnvelope {
  return {
    status, requested, reason,
    validity: { complete: status === 'completed', converged: status === 'completed' ? true : null, model_applicable: status === 'completed' ? true : null, historical_validated: null },
    method_versions: {}, assumptions: [], diagnostics, data,
  };
}

function canonicalReport(): AnalysisResult {
  const result = structuredClone(completedFixture);
  result.status = 'partial';
  result.validity = { complete: false, converged: true, model_applicable: false, historical_validated: null };
  result.input_snapshot = { ...result.input_snapshot, name: 'HMS Queen Mary', revision: 2,
    loading_conditions: [{ id: 'normal-engineering', label: '正常载荷' }] };
  result.stages = {
    loading: stageEnvelope('completed', true, { values: { total_mass_t: 27200, known_mass_t: 26900 } }),
    geometry: stageEnvelope('completed', true, { values: { volume_m3: 31000 } }),
    equilibrium: stageEnvelope('model_limit', true, { waterline_above_keel_m: 9.92, heel_deg: 0 }, '超出方法适用范围'),
    hydrostatics: stageEnvelope('unavailable', true, { values: { gm_t_m: 9.99 } }, '型线资料不足'),
    gz: stageEnvelope('completed', true, { rows: [{ angle_deg: 0, gz_m: 0 }, { angle_deg: 20, gz_m: 0.35 }, { angle_deg: 40, gz_m: 0.28 }] }),
    resistance: stageEnvelope('completed', true, { method: 'holtrop_mennen_1982', primary_result: true, validity: { model_applicable: true },
      power_rows: [{ speed_kn: 18, qpc: { value: 0.55, source: { id: 'qpc-study', page: '第 12 页' }, estimate: true },
        effective_power_kw: 7092.1, shaft_power_kw: 12894.8, complete: true, estimate: true, primary_result: true, model_applicable: true }] }),
    propulsion: stageEnvelope('completed', true, { values: { power_design_kw: 12000, power_trial_kw: 13500 } }),
    endurance: stageEnvelope('completed', true, { values: { method: 'steady_simultaneous_fuel_consumption', hours: 240,
      range_nm: 5760, speed_kn: 24, source: { id: 'fuel-study', page: '第 42 页' }, estimate: true } }),
    flooding: stageEnvelope('model_limit', true, { status: 'model_limit', stop_reason: 'partial_aperture',
      scenario: { id: 'f1', duration_s: 60, time_step_s: 0.5 },
      timeline: [{ time_s: 12.5, equilibrium: { heel_deg: 2.1, trim_deg: 0.4, waterline_above_keel_m: 4.3 } }],
      final_state: { time_s: 12.5 }, initial_total_water_volume_m3: 0, initial_total_water_mass_t: 0,
      cumulative_sea_exchange_m3: 4.5, cumulative_sea_exchange_t: 4.61, volume_conservation_error_m3: 0,
      mass_conservation_error_t: 1.2e-15, terminal_head_tolerance_m: 1e-8, terminal_max_head_difference_m: 0.02,
      remaining_gz: { rows: [{ angle_deg: 10, gz_m: 0.21 }] }, gz_snapshots: [{ time_s: 12.5 }],
      downflooding: { status: 'no_open_points', event: null } }, '仅部分开口'),
    'zz-new-kernel': stageEnvelope('completed', true, { values: { new_kernel_output: 1 } }),
    deck: stageEnvelope('not_requested', false, null, '未请求'),
  } as unknown as AnalysisResult['stages'];
  result.diagnostics = [
    // Attributed to a requested stage, but the stage never recorded it: this is
    // root evidence and has to survive.
    { code: 'resistance.fatal', severity: 'error', stage: 'resistance', path: '$.stages.resistance.data.power_rows', message: '阻力内核在该工作点不可用' },
    // A blocking warning with no stage is a finding, so it is not folded away.
    { code: 'coordinator.kernel_mismatch', severity: 'warning', blocking: true, path: '$.stages.resistance', message: '外推系数超出经验适用范围' },
    // The same ordinary note twice: one entry.
    { code: 'coordinator.note', severity: 'info', message: '已记录请求与快照指纹' },
    { code: 'coordinator.note', severity: 'info', message: '已记录请求与快照指纹' },
    // Exactly what the gz stage already shows, and that stage's own copy names no
    // stage of its own: stated once, not again above the stage.
    { code: 'gz.limit', severity: 'warning', stage: 'gz', path: '$.stages.gz', message: 'GZ 曲线仅计算到 60°' },
    // The same finding as the gz stage's, but stronger: it adds evidence.
    { code: 'gz.wide', severity: 'error', blocking: true, stage: 'gz', path: '$.stages.gz', message: 'GZ 曲线超出可计算范围' },
    // Also root-only for a stage that never recorded it.
    { code: 'equilibrium.limit', severity: 'warning', stage: 'equilibrium', path: '$.stages.equilibrium', message: '浮态阶段超出方法适用范围' },
  ];
  result.stages.gz.diagnostics = [
    { code: 'gz.limit', severity: 'warning', path: '$.stages.gz', message: 'GZ 曲线仅计算到 60°' },
    { code: 'gz.wide', severity: 'info', path: '$.stages.gz', message: 'GZ 曲线超出可计算范围' },
  ];
  return result;
}

describe('the report first screen', () => {
  it('reads the six saved values and keeps every unknown with its reason', () => {
    render(<Report result={canonicalReport()} runId="run-7" />);
    // The readings project the saved stages, so a value also appears in its
    // stage card; these assertions are about the reading itself.
    const readings = within(document.querySelector('.report-readings') as HTMLElement);
    expect(document.querySelectorAll('.report-reading')).toHaveLength(6);

    expect(readings.getByText('27,200 t')).toBeVisible();
    // The waterline is blocked with the equilibrium stage, so no number is shown.
    expect(readings.queryByText('9.92 m')).toBeNull();
    // Both equilibrium readings are blocked by that one stage, so both carry it.
    expect(readings.getAllByText(/模型越界：超出方法适用范围/)).toHaveLength(2);
    // The residual GM of an unavailable stage is not a result either.
    expect(readings.queryByText('9.99')).toBeNull();
    expect(readings.getByText(/暂不可计算：型线资料不足/)).toBeVisible();
    // Power comes from the single complete work point, with its speed.
    expect(readings.getByText('12,894.8 kW')).toBeVisible();
    expect(readings.getByText('阶段 阻力与功率 · 工作点 18 kn')).toBeVisible();
    // Endurance stays in nautical miles and keeps its declared source.
    expect(readings.getByText('5,760 nmi')).toBeVisible();
    expect(readings.getByText('阶段 续航 · 工作点 24 kn')).toBeVisible();
    expect(readings.getByText('来源 {"id":"fuel-study","page":"第 42 页"}')).toBeVisible();
    expect(readings.getAllByText('工程估算').length).toBeGreaterThan(0);
  });

  it('shows a true zero as a value, and a null field as unknown with its own reason', () => {
    const result = canonicalReport();
    result.stages.equilibrium = stageEnvelope('completed', true, { waterline_above_keel_m: null, heel_deg: 0 });
    render(<Report result={result} runId="run-7" />);
    const readings = within(document.querySelector('.report-readings') as HTMLElement);
    // A zero heel is a real reading, not a missing one.
    expect(readings.getByText('0 °')).toBeVisible();
    // The projection's field-level wording is stated for the reader, not printed.
    expect(readings.getByText('本次保存结果将此读数标为未知。')).toBeVisible();
    expect(readings.queryByText(/waterline_above_keel_m/)).toBeNull();
  });

  it('names the ship, the condition, the saved revision and the run, without an accreditation claim', () => {
    render(<Report result={canonicalReport()} runId="run-7" revision={4} />);
    expect(screen.getByRole('heading', { level: 1, name: 'HMS Queen Mary' })).toBeVisible();
    expect(screen.getByText(/工况 正常载荷/)).toBeVisible();
    expect(screen.getByText(/保存修订 4/)).toBeVisible();
    expect(screen.getByText(/运行 run-7/)).toBeVisible();
    // Identity, then state, then applicability in its three states.
    expect(screen.getByText('部分完成')).toBeVisible();
    expect(screen.getByText(/完整性：存在未完成阶段/)).toBeVisible();
    expect(screen.getByText('收敛：是 · 已声明')).toBeVisible();
    expect(screen.getByText('模型适用性：否')).toBeVisible();
    expect(screen.getByText('史实验证：未知 · 无结论')).toBeVisible();
    expect(within(document.querySelector('.report-cover') as HTMLElement).getByText(/不代表史实、设计或适航认证/)).toBeVisible();
  });

  it('drops the generic ship drawing and shows each stage exactly once, in requested order', () => {
    render(<Report result={canonicalReport()} runId="run-7" />);
    expect(document.querySelector('.ship-profile')).toBeNull();
    expect(document.querySelectorAll('.stability-plot')).toHaveLength(1);
    expect(document.querySelector('.stability-plot')!.closest('#stage-gz')).not.toBeNull();
    expect(screen.getAllByText(/partial_aperture/)).toHaveLength(1);

    const sections = Array.from(document.querySelectorAll('.report-stage-list > article')).map(node => node.id);
    // Known stages keep the canonical order; the unknown name follows them.
    expect(sections).toEqual(['stage-loading', 'stage-geometry', 'stage-equilibrium', 'stage-hydrostatics',
      'stage-gz', 'stage-resistance', 'stage-propulsion', 'stage-endurance', 'stage-flooding', 'stage-zz-new-kernel']);
    // The index locates the same sections.
    expect(screen.getAllByRole('link').map(link => link.getAttribute('href'))).toContain('#/reports/run-7/stages/flooding');
  });

  it('keeps declared design and trial powers in the stage detail only', () => {
    render(<Report result={canonicalReport()} runId="run-7" />);
    expect(screen.getByText('设计轴功率（设计声明）')).toBeVisible();
    expect(screen.getByText('试航轴功率（试航声明）')).toBeVisible();
    // They are never offered as the report's own power reading.
    const readings = within(document.querySelector('.report-readings') as HTMLElement);
    expect(document.querySelectorAll('.report-reading')).toHaveLength(6);
    expect(readings.getByText('12,894.8 kW')).toBeVisible();
    expect(readings.queryByText(/设计轴功率|试航轴功率/)).toBeNull();
  });

  it('shows a root finding directly, folds the ordinary one, and counts nothing twice', () => {
    render(<Report result={canonicalReport()} runId="run-7" />);
    const serious = document.querySelector<HTMLElement>('.stage-diagnostics-open')!;
    expect(document.querySelectorAll('.stage-diagnostics-open')).toHaveLength(1);
    // A blocking warning is a finding, so it is not behind a disclosure.
    expect(screen.getByText('外推系数超出经验适用范围')).toBeVisible();
    // A severe finding about a requested stage that never recorded it stays, and
    // the code and the path stay with it.
    expect(within(serious).getByText('阻力内核在该工作点不可用')).toBeVisible();
    expect(within(serious).getByText('resistance.fatal')).toBeVisible();
    expect(within(serious).getByText('$.stages.resistance.data.power_rows')).toBeVisible();
    expect(within(serious).getByText('阶段 阻力与功率')).toBeVisible();
    // A stronger restatement of a stage finding than the stage itself carries.
    expect(within(serious).getByText('GZ 曲线超出可计算范围')).toBeVisible();
    // The identical finding, where the stage's own copy names no stage: once.
    expect(screen.getAllByText('GZ 曲线仅计算到 60°')).toHaveLength(1);
    // The duplicated root note appears once.
    expect(screen.getAllByText('已记录请求与快照指纹')).toHaveLength(1);

    const fold = document.querySelector('.report-root-diagnostics-fold') as HTMLDetailsElement;
    expect(fold.hasAttribute('open')).toBe(false);
    expect(fold.textContent).toContain('已记录请求与快照指纹');
    // A stage's own finding stays in its stage card.
    expect(document.getElementById('stage-equilibrium')!.textContent).toContain('超出方法适用范围');
    // A root-only finding about a requested stage is not mistaken for one.
    expect(fold.textContent).toContain('浮态阶段超出方法适用范围');
    expect(screen.getAllByText('GZ 曲线仅计算到 60°')).toHaveLength(1);
  });

  it('keeps the firmest root finding when one finding is reported twice', () => {
    const result = canonicalReport();
    // The same finding twice, the weaker one first: the fatal reading of it must
    // not be folded away by the warning that arrived before it.
    result.diagnostics = [
      { code: 'coordinator.repeat', severity: 'warning', stage: 'resistance', path: '$.stages.resistance', message: '同一发现被记录两次' },
      { code: 'coordinator.repeat', severity: 'fatal', stage: 'resistance', path: '$.stages.resistance', message: '同一发现被记录两次' },
    ];
    render(<Report result={result} runId="run-7" />);
    const serious = document.querySelector('.stage-diagnostics-open') as HTMLElement;
    expect(serious).not.toBeNull();
    expect(within(serious).getByText('同一发现被记录两次')).toBeVisible();
    expect(within(serious).getByText('coordinator.repeat')).toBeVisible();
    // One finding, one line, and the message is not printed twice.
    expect(serious.querySelectorAll('p')).toHaveLength(1);
    expect(screen.getAllByText('同一发现被记录两次')).toHaveLength(1);

    // The reverse order names the same one line.
    cleanup();
    const reversed = canonicalReport();
    reversed.diagnostics = [
      { code: 'coordinator.repeat', severity: 'fatal', stage: 'resistance', path: '$.stages.resistance', message: '同一发现被记录两次' },
      { code: 'coordinator.repeat', severity: 'warning', stage: 'resistance', path: '$.stages.resistance', message: '同一发现被记录两次' },
    ];
    render(<Report result={reversed} runId="run-7" />);
    expect(document.querySelectorAll('.stage-diagnostics-open p')).toHaveLength(1);
  });

  it('compares only requested, finished, finite numbers', () => {
    const left = structuredClone(completedFixture);
    const right = structuredClone(left);
    const hydrostatics = (mass: unknown) => ({
      status: 'completed' as const, requested: true, reason: null,
      validity: { complete: true, converged: true, model_applicable: true, historical_validated: null },
      method_versions: {}, assumptions: [], diagnostics: [],
      // NaN and Infinity are not values, and never become a difference.
      data: { total_mass_t: mass, awp_m2: 1450 },
    });
    left.stages.hydrostatics = hydrostatics(NaN);
    right.stages.hydrostatics = hydrostatics(Infinity);
    // An unrequested stage may still hold numbers; they are not comparable.
    const deck = (freeboard: unknown) => ({
      status: 'completed' as const, requested: false, reason: '未请求',
      validity: { complete: false, converged: null, model_applicable: null, historical_validated: null },
      method_versions: {}, assumptions: [], diagnostics: [],
      data: { minimum_clearance_m: freeboard },
    });
    left.stages.deck = deck(4.2);
    right.stages.deck = deck(4.4);
    render(<Report result={left} compareResult={right} />);

    const cells = within(screen.getByRole('table')).getAllByRole('cell').map(cell => cell.textContent ?? '');
    // The finite area row is still compared.
    expect(cells.some(cell => cell.includes('m²'))).toBe(true);
    expect(cells.some(cell => /NaN|Infinity/.test(cell))).toBe(false);
    expect(cells.some(cell => cell.includes('4.2') || cell.includes('4.4'))).toBe(false);
  });

  it('keeps the audit trail inside the report, with the fingerprints still reachable', () => {
    render(<Report result={canonicalReport()} runId="run-7" />);
    const audit = document.querySelector('.report-audit')!;
    expect(audit.querySelector('.report-columns')).toBeNull();
    expect(audit.closest('.report-main')).not.toBeNull();
    // The reading column is not a third rail beside the body.
    expect(document.querySelectorAll('.report-columns')).toHaveLength(1);
    expect(document.querySelector('.report-columns > .stage-index')).not.toBeNull();
    expect(audit.textContent).toContain('project-123');
    expect(audit.textContent).toContain('input-123');
    expect(audit.textContent).toContain('request-123');
    // Long provenance is folded, not gone.
    const sources = Array.from(audit.querySelectorAll('details'));
    expect(sources.some(node => node.textContent?.includes('selected-loading-analysis-1'))).toBe(true);
  });
});
