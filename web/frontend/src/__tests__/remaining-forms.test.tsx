import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import * as api from '../api';
import { Workbench } from '../pages/Workbench';
import type { ProjectDocument, RunView } from '../types';
import { completedFixture } from './fixtures';

vi.mock('../api', async original => ({ ...await original<typeof import('../api')>(),
  getProject: vi.fn(), saveProject: vi.fn(), listRuns: vi.fn(), enqueueRun: vi.fn(), getRun: vi.fn() }));

const fact = (value: unknown) => ({ value, source: 'fixture source', estimate: true });
const project: ProjectDocument = {
  schema: 'plimsoll-project-1', id: 'p1', name: 'Fixture', revision: 1,
  hull: { loa_m: 20, lwl_m: 20, beam_m: 10, draught_normal_m: 4, block_coeff: 1, waterplane_coeff: 1 },
  geometry: null, metadata: { country: fact('UK') },
  weight_groups: [{ id: 'machinery', label: 'Machinery', items: [{ id: 'engine', mass_t: 50 }] },
    { id: 'fuel', label: 'Fuel', items: [{ id: 'coal', mass_t: 10 }] }],
  loading_conditions: [{ id: 'normal', label: 'Normal', overrides: {} }, { id: 'deep', label: 'Deep', overrides: {} }],
  compartments: [{ id: 'room', label: 'Room', x_m: 0, length_m: 10 }],
  systems: {
    armour: { fixed: { weight_item_ids: ['engine'], page_rows: [{ row: 'main', group: 'belts', thickness_mm: 229, weight_item_ids: ['engine'] }] } },
    propulsion: { weight_item_ids: ['engine'], facts: { shafts: fact(4), boilers: fact(42) },
      fuel_bindings: { coal: { weight_item_ids: ['coal'], source: 'fixture source', estimate: true } } },
  },
  resistance_scenarios: [{ id: 'study', method: 'holtrop', qpc: fact(.55) }],
};

beforeEach(() => { cleanup(); vi.clearAllMocks();
  vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 1, project });
  vi.mocked(api.listRuns).mockResolvedValue([]);
  vi.mocked(api.saveProject).mockImplementation(async (_id, input) => ({ project_id: 'p1', revision: 2, project: input.project }));
  vi.mocked(api.getRun).mockRejectedValue(new Error('no stored result'));
});
async function open(chapter: string) {
  render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
  fireEvent.click(await screen.findByRole('button', { name: chapter }));
}
async function saved() {
  fireEvent.click(screen.getByRole('button', { name: '保存修订' }));
  await waitFor(() => expect(api.saveProject).toHaveBeenCalled());
  return vi.mocked(api.saveProject).mock.calls[0][1].project;
}

it('saves armour thickness, declared extents and coverage provenance without changing ledger mass', async () => {
  await open('装甲与武备');
  fireEvent.change(screen.getByLabelText('main 厚度 · mm'), { target: { value: '200' } });
  fireEvent.change(screen.getByLabelText('main 艉端 · m'), { target: { value: '-5' } });
  fireEvent.change(screen.getByLabelText('main 艏端 · m'), { target: { value: '5' } });
  fireEvent.change(screen.getByLabelText('受保护平面面积 · m² 值'), { target: { value: '100' } });
  fireEvent.change(screen.getByLabelText('受保护平面面积 · m² 来源'), { target: { value: 'deck plan' } });
  const p = await saved(); const fixed = (p.systems as any).armour.fixed;
  expect(fixed.page_rows[0].thickness_mm).toBe(200);
  expect(fixed.page_rows[0].extents_m).toEqual({ aft_m: -5, fore_m: 5 });
  expect(fixed.deck_coverage.covered_plan_area_m2.value).toBe(100);
  expect(fixed.deck_coverage.covered_plan_area_m2.source).toBe('deck plan');
  expect(p.weight_groups[0].items[0].mass_t).toBe(50);
});

it('clears a machinery fact to null and saves source and three-state estimate', async () => {
  await open('动力与性能');
  fireEvent.change(screen.getByLabelText('轴数 值'), { target: { value: '' } });
  fireEvent.change(screen.getByLabelText('轴数 来源'), { target: { value: 'survey' } });
  fireEvent.change(screen.getByLabelText('轴数 估算状态'), { target: { value: 'unknown' } });
  const p = await saved();
  expect((p.systems as any).propulsion.facts.shafts).toEqual({ value: null, source: 'survey', estimate: null });
  expect((p.systems as any).armour).toEqual((project.systems as any).armour);
});

it('creates Standard with an explicit base and excluded item and keeps Normal intact', async () => {
  await open('性能与工况');
  fireEvent.click(screen.getByRole('button', { name: '添加 Standard 工况' }));
  fireEvent.click(screen.getByLabelText('standard 扣除 coal'));
  fireEvent.change(screen.getByLabelText('standard 规则来源'), { target: { value: 'declared fuel removal' } });
  fireEvent.change(screen.getByLabelText('standard 规则估算状态'), { target: { value: 'estimate' } });
  const p = await saved();
  expect(p.loading_conditions.find(c => c.id === 'standard')?.definition).toEqual({
    kind: 'standard', base_condition_id: 'normal', excluded_item_ids: ['coal'], source: 'declared fuel removal', estimate: true });
  expect(p.loading_conditions[0]).toEqual(project.loading_conditions[0]);
});

it('submits an explicit fixed-power request with bracket, QPC and target trim', async () => {
  vi.mocked(api.enqueueRun).mockResolvedValue({ id: 'run1' } as RunView);
  await open('性能与工况');
  fireEvent.change(screen.getByLabelText('阻力研究场景'), { target: { value: 'study' } });
  fireEvent.change(screen.getByLabelText('功率请求模式'), { target: { value: 'fixed_power' } });
  fireEvent.change(screen.getByLabelText('速度采样 · kn'), { target: { value: '10, 20' } });
  fireEvent.change(screen.getByLabelText('给定轴功率 · kW'), { target: { value: '1000' } });
  fireEvent.change(screen.getByLabelText('QPC 值'), { target: { value: '.55' } });
  fireEvent.change(screen.getByLabelText('QPC 来源'), { target: { value: 'declared QPC' } });
  fireEvent.change(screen.getByLabelText('QPC 估算状态'), { target: { value: 'estimate' } });
  fireEvent.change(screen.getByLabelText('目标纵倾 · °'), { target: { value: '1' } });
  fireEvent.click(screen.getByRole('button', { name: '运行计算 ↗' }));
  await waitFor(() => expect(api.enqueueRun).toHaveBeenCalled());
  const opts = vi.mocked(api.enqueueRun).mock.calls[0][1].options as any;
  expect(opts.resistance).toEqual({ scenario_id: 'study', mode: 'fixed_power', speeds_kn: [10, 20], fixed_shaft_power_kw: 1000,
    qpc_override: { value: .55, source: 'declared QPC', estimate: true } });
  expect(opts.equilibrium.target_trim_deg).toBe(1);
});

it('saves optional Hull facts and metadata while preserving the six existing inputs', async () => {
  await open('船型与几何');
  fireEvent.change(screen.getByLabelText('国家 值'), { target: { value: 'Japan' } });
  fireEvent.change(screen.getByLabelText('满载设计方形系数 值'), { target: { value: '.6' } });
  const p = await saved();
  expect((p.metadata as any).country.value).toBe('Japan');
  expect((p.hull.design_facts as any).block_coeff_deep.value).toBe(.6);
  expect(p.hull.lwl_m).toBe(20); expect(p.hull.block_coeff).toBe(1);
});

it('does not display another condition or revision as current armour results', async () => {
  vi.mocked(api.listRuns).mockResolvedValue([{ id: 'old', revision: 1, condition_id: 'deep', created_at: '2026-10-01',
    result: { stages: { systems: { data: { page_rows: { 'armour.fixed': { values: { declared_rows_total_t: 9876 }, rows: [] } } } } } } } as unknown as RunView]);
  await open('装甲与武备');
  expect(screen.queryByText(/9876/)).not.toBeInTheDocument();
  expect(screen.getByText('保存并运行当前工况后显示结果')).toBeVisible();
});

function summaryRun(id: string, overrides: Partial<RunView> = {}): RunView {
  return { id, project_id: 'p1', revision: 1, condition_id: 'normal', status: 'completed',
    request_fingerprint: 'fp', created_at: '2026-10-02T00:00:00Z', started_at: null, finished_at: null,
    cancel_requested: false, error: null, result: null, ...overrides } as RunView;
}
function armourResult(total: number): RunView['result'] {
  const result = structuredClone(completedFixture);
  result.stages.systems.data = { page_rows: { 'armour.fixed': { values: { declared_rows_total_t: total }, rows: [] } } };
  return result;
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(r => { resolve = r; });
  return { promise, resolve };
}

it('retrieves the eligible run result that the run list never carries', async () => {
  vi.mocked(api.listRuns).mockResolvedValue([summaryRun('r9')]);
  vi.mocked(api.getRun).mockResolvedValue(summaryRun('r9', { result: armourResult(4321) }));
  await open('装甲与武备');
  // The list payload carries no result, so the aggregate appears only after one bounded fetch.
  expect(await screen.findByText('4321 t')).toBeVisible();
  expect(vi.mocked(api.getRun)).toHaveBeenCalledTimes(1);
  expect(vi.mocked(api.getRun)).toHaveBeenCalledWith('r9');
});

it('uses a run list payload directly without requesting it again', async () => {
  vi.mocked(api.listRuns).mockResolvedValue([summaryRun('inline', { result: armourResult(2468) })]);
  await open('装甲与武备');
  expect(await screen.findByText('2468 t')).toBeVisible();
  expect(vi.mocked(api.getRun)).not.toHaveBeenCalled();
});

it('never fetches or shows a result for another revision, condition or project', async () => {
  vi.mocked(api.listRuns).mockResolvedValue([
    summaryRun('other-condition', { condition_id: 'deep', result: armourResult(7777) }),
    summaryRun('other-revision', { revision: 9, result: armourResult(7777) }),
    summaryRun('other-project', { project_id: 'p2', result: armourResult(7777) }),
    summaryRun('not-finished', { status: 'running', result: armourResult(7777) }),
  ]);
  await open('装甲与武备');
  await waitFor(() => expect(screen.getByText('保存并运行当前工况后显示结果')).toBeVisible());
  expect(vi.mocked(api.getRun)).not.toHaveBeenCalled();
  expect(screen.queryByText(/7777/)).not.toBeInTheDocument();
});

it('hides a displayed result the moment the condition changes, before getRun resolves', async () => {
  vi.mocked(api.listRuns).mockResolvedValue([
    summaryRun('normal-run', { result: armourResult(1111) }),
    summaryRun('deep-run', { condition_id: 'deep', created_at: '2026-10-03T00:00:00Z' }),
  ]);
  const pending = deferred<RunView>();
  vi.mocked(api.getRun).mockReturnValue(pending.promise);
  await open('装甲与武备');
  expect(await screen.findByText('1111 t')).toBeVisible();
  fireEvent.change(screen.getByLabelText('当前工况'), { target: { value: 'deep' } });
  // Hidden synchronously: 1111 belonged to normal and the deep result is in flight.
  expect(screen.queryByText(/1111/)).not.toBeInTheDocument();
  expect(screen.getByText('保存并运行当前工况后显示结果')).toBeVisible();
  pending.resolve(summaryRun('deep-run', { condition_id: 'deep', result: armourResult(2222) }));
  expect(await screen.findByText('2222 t')).toBeVisible();
});

it('discards a getRun response that does not match the requested identity', async () => {
  vi.mocked(api.listRuns).mockResolvedValue([summaryRun('deep-run', { condition_id: 'deep' })]);
  vi.mocked(api.getRun).mockResolvedValue(summaryRun('deep-run', { condition_id: 'normal', result: armourResult(3131) }));
  await open('装甲与武备');
  fireEvent.change(screen.getByLabelText('当前工况'), { target: { value: 'deep' } });
  await waitFor(() => expect(api.getRun).toHaveBeenCalled());
  await waitFor(() => expect(screen.getByText('保存并运行当前工况后显示结果')).toBeVisible());
  expect(screen.queryByText(/3131/)).not.toBeInTheDocument();
});

it('hides stored results while the draft is dirty', async () => {
  vi.mocked(api.listRuns).mockResolvedValue([summaryRun('r1', { result: armourResult(555) })]);
  await open('装甲与武备');
  expect(await screen.findByText('555 t')).toBeVisible();
  fireEvent.change(screen.getByLabelText('main 厚度 · mm'), { target: { value: '300' } });
  expect(screen.queryByText(/555/)).not.toBeInTheDocument();
  expect(screen.getByText('保存并运行当前工况后显示结果')).toBeVisible();
});

it('saves a declared belt study with its compartment list and provenance', async () => {
  await open('装甲与武备');
  fireEvent.click(screen.getByLabelText('主带保护舱室 room'));
  fireEvent.change(screen.getByLabelText('主带研究来源'), { target: { value: 'declared study' } });
  const p = await saved();
  const belt = (p.systems as any).armour.fixed.minimum_main_belt;
  expect(belt.protected_compartment_ids).toEqual(['room']);
  expect(belt.source).toBe('declared study');
  // This projection is always an independent engineering estimate.
  expect(belt.estimate).toBe(true);
});

it('omits page_rows when the last armour row is removed and saves validly', async () => {
  await open('装甲与武备');
  fireEvent.click(screen.getByRole('button', { name: '移除声明行' }));
  const p = await saved();
  expect((p.systems as any).armour.fixed).not.toHaveProperty('page_rows');
  expect((p.systems as any).armour.fixed.weight_item_ids).toEqual([]);
});

it('records display preferences without converting any declared design input', async () => {
  await open('船型与几何');
  fireEvent.change(screen.getByLabelText('长度显示单位'), { target: { value: 'ft' } });
  fireEvent.change(screen.getByLabelText('质量显示单位'), { target: { value: 'long_ton' } });
  const p = await saved();
  expect(p.display_preferences).toEqual({ length: 'ft', mass: 'long_ton' });
  // Design inputs remain canonical SI; the preference is display-only.
  expect(p.hull.lwl_m).toBe(20);
  expect(p.hull.draught_normal_m).toBe(4);
  expect(screen.getByText(/所有设计输入与计算结果仍为规范 SI/)).toBeVisible();
});

it('surfaces hull measures from the real hydrostatics result keys', async () => {
  const result = structuredClone(completedFixture);
  result.stages.l0.data = { hull_ratios: { design_lwl_over_beam: 2 } };
  result.stages.hydrostatics.data = { values: { awp_m2: 480.5, volume_m3: 1234.5, displacement_t: 1265.3 },
    wetted_surface: { area_m2: 2100.25 }, selected_length_beam_ratio: { value: 6.25 } };
  vi.mocked(api.listRuns).mockResolvedValue([summaryRun('r1', {
    result })]);
  await open('船型与几何');
  expect(await screen.findByText('480.5 m²')).toBeVisible();
  expect(screen.getByText('2100.25 m²')).toBeVisible();
  expect(screen.getByText('1265.3 t')).toBeVisible();
  expect(screen.getByText('6.25')).toBeVisible();
  expect(vi.mocked(api.getRun)).not.toHaveBeenCalled();
});

it('retains the endurance result estimate and source instead of displaying it as confirmed', async () => {
  const result = structuredClone(completedFixture);
  result.stages.endurance.data = { values: { range_nm: 3210, estimate: true, source: 'declared fuel study' } };
  vi.mocked(api.listRuns).mockResolvedValue([summaryRun('endurance', { result })]);
  await open('动力与性能');
  const value = await screen.findByText('3210 nm');
  const field = value.closest('.fact-field')!;
  expect(field.classList.contains('fact-field--estimate')).toBe(true);
  expect(field.textContent).toContain('declared fuel study');
});
