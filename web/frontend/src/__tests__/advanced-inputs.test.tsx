import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import * as api from '../api';
import { Run } from '../pages/Run';
import { Report } from '../pages/Report';
import { Workbench } from '../pages/Workbench';
import type { AnalysisResult, ProjectDocument, RunView } from '../types';
import { completedFixture } from './fixtures';
import { tankFromCompartment, scenarioProblems, EMPTY_FLOODING_REQUEST } from '../components/floodingModel';
import { MassModelEditor } from '../components/MassModelEditor';
import { DamageEditor } from '../components/DamageEditor';

vi.mock('../api', async original => ({ ...await original<typeof import('../api')>(),
  getProject: vi.fn(), saveProject: vi.fn(), listRuns: vi.fn(), enqueueRun: vi.fn(),
  getRun: vi.fn(), cancelRun: vi.fn() }));

const project: ProjectDocument = {
  schema: 'plimsoll-project-1', id: 'p1', name: 'Fixture', revision: 1,
  hull: { loa_m: 90, lwl_m: 88, beam_m: 12, draught_normal_m: 4 },
  geometry: null,
  weight_groups: [{ id: 'armour', label: '固定装甲', items: [
    { id: 'belt', mass_t: 120, x_m: 0, y_m: 0, kg_m: 1, source: 'survey', estimate: false }] }],
  loading_conditions: [{ id: 'normal', label: '正常', overrides: {} }],
  compartments: [{ id: 'room', label: '舱室', length_m: 10, beam_m: 6, height_m: 3, x_m: 1, y_m: 0,
    keel_to_bottom_m: 0.5, permeability: 0.9, free_surface: true, source: 'declared layout', estimate: false }],
  systems: { armour: { fixed: { weight_item_ids: ['belt'] } } },
};

let saved: ProjectDocument = project;

describe('advanced boundary review', () => {
  it('blocks a locked-centroid tank connected to an open flooding edge', () => {
    const problems = scenarioProblems({ tanks: [{ id: 'tank', free_surface: false }],
      connections: [{ from: 'sea', to: 'tank', open: true }] }, []);
    expect(problems.some(problem => problem.includes('无自由液面是锁定重心代理'))).toBe(true);
  });
  it('copies declared compartment geometry without adopting legacy water', () => {
    const room = (project.compartments as Record<string, unknown>[])[0];
    expect(tankFromCompartment({ ...room, initial_volume_m3: 99 }, 1.025)).toMatchObject({
      id: 'room', length_m: 10, initial_volume_m3: null, source: 'declared layout', estimate: false,
    });
  });

  it('offers provenance for self-declared counts and rejects fractions', () => {
    const doc = structuredClone(project);
    doc.systems = { armour: { fixed: { weight_item_ids: ['belt'], mass_models: [{
      id: 'count', method: 'counted_unit_mass', linked_weight_item_id: 'belt',
      inputs: { unit_mass_t: 4, count_value: 2, count_basis: 'inventory' }, input_provenance: {},
      source: 'fixture', estimate: true, comparison_tolerance: { relative: 0, absolute_t: 0 },
    }] } } };
    const onChange = vi.fn();
    render(<MassModelEditor project={doc} run={null} onChange={onChange} />);
    expect(screen.getByLabelText('count 计数 · 件 来源')).toBeVisible();
    expect(screen.getByLabelText('count 计数 · 件 估算状态')).toBeVisible();
    change('count 计数 · 件', '2.5');
    expect(screen.getByRole('alert')).toHaveTextContent('非负整数');
    expect(onChange).not.toHaveBeenCalled();
  });

  it('keeps referenced compartment identities immutable and blocks deletion', () => {
    const doc = structuredClone(project);
    doc.systems = { armour: { fixed: { weight_item_ids: ['belt'], minimum_main_belt: {
      protected_compartment_ids: ['room'],
    } } } };
    render(<DamageEditor project={doc} run={null} request={EMPTY_FLOODING_REQUEST}
      onChange={vi.fn()} onRequestChange={vi.fn()} requestError="" />);
    expect(screen.getByLabelText('项目舱室 room id')).toHaveAttribute('readonly');
    expect(screen.getByRole('button', { name: '移除项目舱室 room' })).toBeDisabled();
    expect(screen.getByText(/被引用：主装甲带研究/)).toBeVisible();
  });
});

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
  saved = structuredClone(project);
  vi.mocked(api.getProject).mockImplementation(async () => ({ project_id: 'p1', revision: saved === project ? 1 : 2, project: structuredClone(saved) }));
  vi.mocked(api.listRuns).mockResolvedValue([]);
  vi.mocked(api.getRun).mockRejectedValue(new Error('no stored result'));
  vi.mocked(api.saveProject).mockImplementation(async (_id, input) => {
    saved = structuredClone(input.project) as ProjectDocument;
    return { project_id: 'p1', revision: 2, project: structuredClone(saved) };
  });
  vi.mocked(api.enqueueRun).mockResolvedValue({ id: 'run-1' } as RunView);
});

async function open(chapter: string) {
  render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
  fireEvent.click(await screen.findByRole('button', { name: chapter }));
  return screen.findByRole('heading', { name: /破损研究|性能与工况|重量与载荷|火炮武备/ });
}

async function persist(): Promise<ProjectDocument> {
  fireEvent.click(screen.getByRole('button', { name: '保存修订' }));
  await waitFor(() => expect(api.saveProject).toHaveBeenCalled());
  return saved;
}

function change(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

function scenarioOf(doc: ProjectDocument, index = 0): Record<string, any> {
  return (doc.flooding_scenarios as Record<string, any>[])[index];
}
function resistanceOf(doc: ProjectDocument, index = 0): Record<string, any> {
  return (doc.resistance_scenarios as Record<string, any>[])[index];
}
function inputsOf(scenario: Record<string, any>): Record<string, any> {
  return scenario.inputs as Record<string, any>;
}

/** Declare a complete, runnable single-hole scenario for flooding_1. */
function declareCompleteScenario() {
  change('flooding_1 进水时长 · s', '60');
  change('flooding_1 时间步长 · s', '0.5');
  change('flooding_1 场景 来源', 'declared damage case');
  change('flooding_1 场景 估算状态', 'confirmed');
  change('flooding_1 海水密度', '1.025');
  change('flooding_1 海水 来源', 'sea water density');
  change('flooding_1 海水 估算状态', 'confirmed');
  fireEvent.click(screen.getByRole('button', { name: '添加舱室' }));
  change('flooding_1 舱室 tank_1 长度', '10');
  change('flooding_1 舱室 tank_1 型宽', '6');
  change('flooding_1 舱室 tank_1 高度', '3');
  change('flooding_1 舱室 tank_1 纵向位置', '1');
  change('flooding_1 舱室 tank_1 横向位置', '0');
  change('flooding_1 舱室 tank_1 舱底距基线', '0.5');
  change('flooding_1 舱室 tank_1 渗透率 [0,1]', '0.9');
  change('flooding_1 舱室 tank_1 自由液面', 'yes');
  change('flooding_1 舱室 tank_1 液体密度 · t/m³', '1.025');
  change('flooding_1 舱室 tank_1 初始水量', '0');
  change('flooding_1 舱室 tank_1 来源', 'declared compartment');
  change('flooding_1 舱室 tank_1 估算状态', 'estimate');
  fireEvent.click(screen.getByRole('button', { name: '添加连接' }));
  change('flooding_1 连接 opening_1 纵向位置', '0');
  change('flooding_1 连接 opening_1 横向位置', '0');
  change('flooding_1 连接 opening_1 高度（基线以上）', '0.2');
  change('flooding_1 连接 opening_1 面积', '0.05');
  change('flooding_1 连接 opening_1 流量系数 Cd [0,1]', '0.6');
  change('flooding_1 连接 opening_1 液体密度 · t/m³', '1.025');
  change('flooding_1 连接 opening_1 开启状态', 'yes');
  change('flooding_1 连接 opening_1 来源', 'declared aperture');
  change('flooding_1 连接 opening_1 估算状态', 'estimate');
}

describe('advanced inputs · resistance scenarios', () => {
  it('declares both canonical methods with per-input provenance and no orphan keys', async () => {
    await open('性能与工况');
    change('新阻力场景 id', 'taylor');
    fireEvent.click(screen.getByRole('button', { name: '添加阻力场景' }));
    change('taylor 阻力方法', 'taylor_gertler_source_axis_strict');
    change('taylor 姿态策略', 'selected_plane_longitudinal_trim_proxy_v1');
    change('taylor 研究来源', 'Gertler table reproduction');
    change('taylor 研究估算状态', 'estimate');
    change('taylor 表 ID', 'gertler-806');
    change('taylor 摩擦方法', 'schoenherr_implicit_ittc_0.242');
    change('taylor 艉部系数 c_stern', '-1');
    change('taylor 艉部系数 c_stern 来源', 'source axis');
    change('taylor 艉部系数 c_stern 估算状态', 'confirmed');
    change('新阻力场景 id', 'holtrop');
    fireEvent.click(screen.getByRole('button', { name: '添加阻力场景' }));
    change('holtrop 研究来源', 'Holtrop 1982 inputs');
    change('holtrop 研究估算状态', 'confirmed');
    const doc = await persist();
    const scenarios = doc.resistance_scenarios as Record<string, any>[];
    expect(scenarios.map(entry => entry.method)).toEqual(['taylor_gertler_source_axis_strict', 'holtrop_mennen_1982']);
    expect(scenarios[0].inputs.c_stern).toBe(-1);
    expect(scenarios[0].input_provenance.c_stern).toEqual({ source: 'source axis', estimate: false });
    expect(scenarios[0].friction_method).toBe('schoenherr_implicit_ittc_0.242');
    expect(scenarios[0].attitude_policy).toBe('selected_plane_longitudinal_trim_proxy_v1');
    // Provenance exists only where an input exists, and no shape data is invented.
    expect(Object.keys(scenarios[0].input_provenance)).toEqual(['c_stern']);
    expect(Object.keys(scenarios[1].inputs)).toEqual([]);
    expect(scenarios[1].appendages).toBeUndefined();
  });

  it('separates unknown, declared absence and supplied data for appendages and bow thruster', async () => {
    await open('性能与工况');
    fireEvent.click(screen.getByRole('button', { name: '添加阻力场景' }));
    change('scenario_1 附体声明', 'absent');
    change('scenario_1 首侧推声明', 'absent');
    let doc = await persist();
    expect(inputsOf(resistanceOf(doc)).appendages).toEqual([]);
    expect(inputsOf(resistanceOf(doc)).bow_thruster).toEqual({ present: false });
    // An absent thruster may not keep increment geometry, so the transition back
    // to presence clears any stale diameter or coefficient.
    change('scenario_1 附体声明', 'present');
    change('scenario_1 首侧推声明', 'present');
    change('scenario_1 首侧推隧道直径', '2.5');
    change('scenario_1 首侧推增量系数', '0.35');
    change('scenario_1 附体 1 面积', '12');
    change('scenario_1 附体 1 系数', '1.4');
    change('scenario_1 首侧推声明', 'absent');
    doc = await persist();
    expect(inputsOf(resistanceOf(doc)).bow_thruster).toEqual({ present: false });
    expect(inputsOf(resistanceOf(doc)).appendages).toEqual([{ area_m2: 12, factor: 1.4 }]);
    change('scenario_1 附体声明', 'unknown');
    change('scenario_1 首侧推声明', 'unknown');
    doc = await persist();
    expect(inputsOf(resistanceOf(doc))).toEqual({});
    expect(resistanceOf(doc).input_provenance).toEqual({});
  });

  it('keeps appendage and thruster provenance independent and usable while unknown', async () => {
    await open('性能与工况');
    fireEvent.click(screen.getByRole('button', { name: '添加阻力场景' }));
    change('scenario_1 附体来源', 'appendage plan');
    change('scenario_1 首侧推来源', 'tunnel survey');
    const doc = await persist();
    const inputs = inputsOf(resistanceOf(doc));
    // A source without a value is an explicit unknown input, never an orphan
    // provenance key, and neither statement overwrites the other.
    expect(inputs.appendages).toBeNull();
    expect(inputs.bow_thruster).toBeNull();
    expect(resistanceOf(doc).input_provenance.appendages.source).toBe('appendage plan');
    expect(resistanceOf(doc).input_provenance.bow_thruster.source).toBe('tunnel survey');
  });

  it('refuses an out-of-domain input instead of writing it into the project', async () => {
    await open('性能与工况');
    fireEvent.click(screen.getByRole('button', { name: '添加阻力场景' }));
    change('scenario_1 球鼻艏面积', '-4');
    expect(screen.getByRole('alert')).toHaveTextContent('不能为负数');
    const doc = await persist();
    expect(inputsOf(resistanceOf(doc)).bulb_area_m2).toBeUndefined();
  });
});

describe('advanced inputs · system mass models', () => {
  it('edits a counted ammunition model without touching the ledger', async () => {
    // A gun battery that declares installed guns and rounds per gun: the counted
    // ammunition model reads both plus the two shell masses.
    const armed: ProjectDocument = structuredClone(project);
    armed.systems = { ...(armed.systems as any), weapons: { main: {
      weight_item_ids: ['belt'], installed_guns: 8, rounds_per_gun: 80 } } };
    saved = armed;
    await open('重量与载荷');
    fireEvent.change(screen.getByLabelText('选择系统叶'), { target: { value: 'weapons.main' } });
    fireEvent.click(await screen.findByRole('button', { name: '添加质量模型' }));
    change('model_1 模型方法', 'counted_ammunition_mass');
    change('model_1 弹丸质量', '0.0159');
    change('model_1 弹丸质量 来源', 'munition label');
    change('model_1 弹丸质量 估算状态', 'confirmed');
    change('model_1 装药质量', '0.0064');
    change('model_1 装药质量 来源', 'munition label');
    change('model_1 装药质量 估算状态', 'confirmed');
    change('model_1 装舰数量字段', 'installed_guns');
    change('model_1 模型来源', 'declared ammunition outfit');
    change('model_1 模型估算状态', 'estimate');
    change('model_1 相对容差', '0.01');
    change('model_1 绝对容差', '0.01');
    // An estimated model needs provenance on the named count inputs too.
    expect(screen.getByRole('status')).toHaveTextContent('装舰数量字段');
    change('model_1 装舰数量字段 来源', 'armoury list');
    change('model_1 装舰数量字段 估算状态', 'confirmed');
    change('model_1 携弹数字段 来源', 'armoury list');
    change('model_1 携弹数字段 估算状态', 'confirmed');
    expect(screen.queryByRole('status')).toBeNull();
    const doc = await persist();
    const model = (doc.systems as any).weapons.main.mass_models[0];
    expect(model.method).toBe('counted_ammunition_mass');
    // rounds_field names the installed-count field; it is not a copy of the key.
    expect(model.inputs.rounds_field).toBe('rounds_per_gun');
    expect(model.inputs).not.toHaveProperty('rounds_per_gun');
    expect(model.inputs).toMatchObject({ projectile_mass_kg: 15.9, charge_mass_kg: 6.4, count_field: 'installed_guns' });
    expect(model.input_provenance.count_field).toEqual({ source: 'armoury list', estimate: false });
    expect(model.input_provenance.rounds_field).toEqual({ source: 'armoury list', estimate: false });
    expect(model.estimate).toBe(true);
    // The ledger stays the single mass authority.
    expect(doc.weight_groups[0].items).toEqual(project.weight_groups[0].items);
  });

  it('keeps a self-declared count unknown instead of inventing a known zero', async () => {
    await open('重量与载荷');
    fireEvent.click(await screen.findByRole('button', { name: '添加质量模型' }));
    change('model_1 模型方法', 'counted_unit_mass');
    change('model_1 单具质量', '12');
    change('model_1 单具质量 来源', 'crane list');
    change('model_1 单具质量 估算状态', 'confirmed');
    change('model_1 计数方式', 'value');
    const doc = await persist();
    const model = (doc.systems as any).armour.fixed.mass_models[0];
    expect(model.inputs.count_value).toBeNull();
    expect(model.inputs.count_basis).toBe('');
    expect(screen.getByRole('status')).toBeDefined();
  });

  it('adds and removes a model, and refuses an estimated model without input provenance', async () => {
    await open('重量与载荷');
    fireEvent.click(await screen.findByRole('button', { name: '添加质量模型' }));
    change('model_1 模型估算状态', 'estimate');
    expect(screen.getByRole('status')).toHaveTextContent('估算模型必须为输入');
    fireEvent.click(screen.getByRole('button', { name: '移除模型 model_1' }));
    const doc = await persist();
    expect((doc.systems as any).armour.fixed.mass_models).toEqual([]);
    expect(doc.weight_groups[0].items).toHaveLength(1);
  });
});

describe('advanced inputs · guns page rows', () => {
  it('creates, binds and removes guns / mounts / ammunition rows', async () => {
    await open('火炮武备');
    fireEvent.click(await screen.findByRole('button', { name: '添加炮组' }));
    change('battery_1 新增行', 'ammunition');
    fireEvent.click(screen.getByRole('button', { name: '添加炮页行' }));
    fireEvent.click(screen.getByLabelText('battery_1 行 ammunition 账本绑定 belt'));
    let doc = await persist();
    const battery = (doc.systems as any).weapons.battery_1;
    expect(battery.page_rows.map((row: any) => row.row)).toEqual(['ammunition']);
    expect(battery.page_rows[0].weight_item_ids).toEqual(['belt']);
    expect(battery.weight_item_ids).toEqual(['belt']);
    // The three canonical categories are the only ones offered, so no
    // unsupported `guns_2` row can be generated.
    const options = screen.getByLabelText('battery_1 新增行').textContent ?? '';
    expect(options).not.toContain('guns_2');
    fireEvent.click(screen.getByRole('button', { name: /移除行 ammunition/ }));
    doc = await persist();
    const trimmed = (doc.systems as any).weapons.battery_1;
    expect(trimmed.page_rows).toBeUndefined();
    // The binding survives the row removal: removing a declaration is not a
    // silent way to drop ledger mass ownership.
    expect(trimmed.weight_item_ids).toEqual(['belt']);
  });

  it('adds all three canonical rows and then offers no further category', async () => {
    await open('火炮武备');
    fireEvent.click(await screen.findByRole('button', { name: '添加炮组' }));
    fireEvent.click(screen.getByRole('button', { name: '添加炮页行' }));
    change('battery_1 新增行', 'mounts');
    fireEvent.click(screen.getByRole('button', { name: '添加炮页行' }));
    change('battery_1 新增行', 'ammunition');
    fireEvent.click(screen.getByRole('button', { name: '添加炮页行' }));
    expect(screen.getByRole('button', { name: '添加炮页行' })).toBeDisabled();
    const doc = await persist();
    expect((doc.systems as any).weapons.battery_1.page_rows.map((row: any) => row.row))
      .toEqual(['guns', 'mounts', 'ammunition']);
  });
});

describe('advanced inputs · flooding scenarios', () => {
  it('edits, saves and reopens a blank-project scenario draft', async () => {
    await open('破损研究');
    fireEvent.click(await screen.findByRole('button', { name: '添加破损场景' }));
    change('flooding_1 进水时长 · s', '30');
    change('flooding_1 场景 来源', 'declared case');
    const doc = await persist();
    expect(scenarioOf(doc)).toMatchObject({ schema: 'plimsoll-flooding-scenario-1', id: 'flooding_1',
      duration_s: 30, time_step_s: null, source: 'declared case' });
    expect(scenarioOf(doc).sea).toEqual({ id: 'sea', fluid_density_t_m3: null, source: null, estimate: null });
    cleanup();
    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '破损研究' }));
    expect(await screen.findByLabelText('flooding_1 进水时长 · s')).toHaveValue(30);
    expect(screen.getByLabelText('flooding_1 场景 来源')).toHaveValue('declared case');
    // Unknown stays unknown after reopening; it is never turned into a default.
    expect(screen.getByLabelText('flooding_1 时间步长 · s')).toHaveValue(null);
    expect(screen.getByLabelText('flooding_1 海水密度')).toHaveValue(null);
  });

  it('copies project compartments into the scenario without copying water or ledger mass', async () => {
    await open('破损研究');
    fireEvent.click(await screen.findByRole('button', { name: '添加破损场景' }));
    change('flooding_1 海水密度', '1.025');
    fireEvent.click(screen.getByRole('button', { name: '从项目舱室复制' }));
    const doc = await persist();
    const tanks = scenarioOf(doc).tanks;
    expect(tanks).toHaveLength(1);
    expect(tanks[0]).toMatchObject({ id: 'room', length_m: 10, beam_m: 6, height_m: 3, x_m: 1,
      keel_to_bottom_m: 0.5, permeability: 0.9, free_surface: true, fluid_density_t_m3: 1.025,
      source: 'declared layout', estimate: false });
    // Initial water is not declared by the project, so the copy leaves it unknown.
    expect(tanks[0].initial_volume_m3).toBeNull();
    expect(doc.weight_groups[0].items).toEqual(project.weight_groups[0].items);
  });

  it('refuses to run while the scenario is incomplete and explains why', async () => {
    await open('破损研究');
    fireEvent.click(await screen.findByRole('button', { name: '添加破损场景' }));
    change('flooding_1 进水时长 · s', '30');
    fireEvent.change(screen.getByLabelText('请求破损场景'), { target: { value: 'flooding_1' } });
    expect(await screen.findByRole('alert')).toHaveTextContent('破损场景不可运行');
    expect(screen.getByRole('button', { name: '运行计算 ↗' })).toBeDisabled();
    expect(api.enqueueRun).not.toHaveBeenCalled();
  });

  it('omits the optional aperture height until it is requested', async () => {
    await open('破损研究');
    fireEvent.click(await screen.findByRole('button', { name: '添加破损场景' }));
    fireEvent.click(screen.getByRole('button', { name: '添加连接' }));
    expect(screen.queryByLabelText('flooding_1 连接 opening_1 有限开口高度')).toBeNull();
    fireEvent.click(screen.getByLabelText('flooding_1 连接 opening_1 请求有限开口高度检查'));
    expect(screen.getByLabelText('flooding_1 连接 opening_1 有限开口高度')).toBeVisible();
    let doc = await persist();
    // Requested but not yet quantified: the key exists and stays unknown.
    expect(scenarioOf(doc).connections[0].aperture_height_m).toBeNull();
    change('flooding_1 连接 opening_1 有限开口高度', '0.9');
    doc = await persist();
    expect(scenarioOf(doc).connections[0].aperture_height_m).toBe(0.9);
    fireEvent.click(screen.getByLabelText('flooding_1 连接 opening_1 请求有限开口高度检查'));
    doc = await persist();
    // Un-requesting the check removes the key instead of storing a null value.
    expect(scenarioOf(doc).connections[0]).not.toHaveProperty('aperture_height_m');
  });

  it('adds, edits and removes multiple scenario openings', async () => {
    await open('破损研究');
    fireEvent.click(await screen.findByRole('button', { name: '添加破损场景' }));
    change('flooding_1 场景开口知识', 'no');
    change('新增开口 id', 'vent_1');
    fireEvent.click(screen.getByRole('button', { name: '添加开口' }));
    change('新增开口 id', 'vent_2');
    fireEvent.click(screen.getByRole('button', { name: '添加开口' }));
    change('flooding_1 开口 vent_1 z_m', '5.4');
    change('flooding_1 开口 vent_1 来源', 'ventilation plan');
    change('flooding_1 开口 vent_2 z_m', '6.1');
    change('flooding_1 开口 vent_2 开启', 'no');
    const doc = await persist();
    expect(scenarioOf(doc).openings.map((row: any) => row.id)).toEqual(['opening_1', 'vent_1', 'vent_2']);
    expect(scenarioOf(doc).openings[1]).toMatchObject({ z_m: 5.4, source: 'ventilation plan' });
    expect(scenarioOf(doc).openings[2]).toMatchObject({ z_m: 6.1, open: false });
    fireEvent.click(screen.getByRole('button', { name: '移除开口 vent_2' }));
    const trimmed = await persist();
    expect(scenarioOf(trimmed).openings.map((row: any) => row.id)).toEqual(['opening_1', 'vent_1']);
  });

  it('pairs an explicit environment density with the scenario sea density', async () => {
    await open('破损研究');
    fireEvent.click(await screen.findByRole('button', { name: '添加破损场景' }));
    declareCompleteScenario();
    fireEvent.change(screen.getByLabelText('请求破损场景'), { target: { value: 'flooding_1' } });
    // A seawater scenario cannot run against a fresh-water environment request.
    change('破损环境密度', '1.0');
    expect(screen.getByRole('alert')).toHaveTextContent('海水密度必须等于本次请求的环境密度 1 t/m³');
    change('flooding_1 海水密度', '1.0');
    change('flooding_1 舱室 tank_1 液体密度 · t/m³', '1.0');
    change('flooding_1 连接 opening_1 液体密度 · t/m³', '1.0');
    await persist();
    fireEvent.click(screen.getByRole('button', { name: '运行计算 ↗' }));
    await waitFor(() => expect(api.enqueueRun).toHaveBeenCalled());
    const body = vi.mocked(api.enqueueRun).mock.calls[0][1] as any;
    // The density is a request-wide, explicit choice, not a hidden default.
    expect(body.options.equilibrium).toEqual({ rho_t_m3: 1 });
    expect(body.options.flooding.scenario.sea.fluid_density_t_m3).toBe(1);
  });

  it('enqueues a valid nonzero flooding run with the saved scenario and limits', async () => {
    await open('破损研究');
    fireEvent.click(await screen.findByRole('button', { name: '添加破损场景' }));
    declareCompleteScenario();
    fireEvent.change(screen.getByLabelText('请求破损场景'), { target: { value: 'flooding_1' } });
    change('破损最大接受步数', '20000');
    change('剩余稳性采样', '10, 20, 30, 40');
    expect(screen.queryByRole('alert')).toBeNull();
    await persist();
    fireEvent.click(screen.getByRole('button', { name: '运行计算 ↗' }));
    await waitFor(() => expect(api.enqueueRun).toHaveBeenCalled());
    const body = vi.mocked(api.enqueueRun).mock.calls[0][1] as any;
    expect(body.options.stages).toContain('flooding');
    expect(body.options.stages).toContain('loading');
    expect(body.options.flooding.scenario.id).toBe('flooding_1');
    expect(body.options.flooding.scenario.duration_s).toBe(60);
    expect(body.options.flooding.options.max_steps).toBe(20000);
    expect(body.options.flooding.options.remaining_gz_angles_deg).toEqual([10, 20, 30, 40]);
    expect(body.options.flooding.options.remaining_gz_snapshot).toBe('final');
    expect(body.revision).toBe(2);
    expect(body.condition_id).toBe('normal');
  });

  it('refuses a run whose connection points at an undeclared node', async () => {
    await open('破损研究');
    fireEvent.click(await screen.findByRole('button', { name: '添加破损场景' }));
    declareCompleteScenario();
    fireEvent.change(screen.getByLabelText('请求破损场景'), { target: { value: 'flooding_1' } });
    // Removing a referenced tank is an explicit safe removal: the dependent
    // connection goes with it instead of leaving a dangling reference.
    fireEvent.click(screen.getByRole('button', { name: /移除舱室 tank_1/ }));
    expect(await screen.findByRole('status')).toHaveTextContent('已移除舱室 tank_1 及引用它的连接');
    expect(screen.getByRole('alert')).toHaveTextContent('破损场景不可运行');
    expect(api.enqueueRun).not.toHaveBeenCalled();
  });

  it('does not request flooding when no scenario is chosen', async () => {
    await open('破损研究');
    fireEvent.click(await screen.findByRole('button', { name: '添加破损场景' }));
    declareCompleteScenario();
    await persist();
    fireEvent.click(screen.getByRole('button', { name: '运行计算 ↗' }));
    await waitFor(() => expect(api.enqueueRun).toHaveBeenCalled());
    const body = vi.mocked(api.enqueueRun).mock.calls[0][1] as any;
    expect(body.options.flooding).toBeUndefined();
    expect(body.options.stages).not.toContain('flooding');
  });
});

describe('advanced inputs · flooding results', () => {
  const floodingData = {
    status: 'model_limit', stop_reason: 'partial_aperture', method_version: 'connected-quasi-static-flooding-1',
    validity: { complete: false, model_applicable: false, numerical_convergence: true, safe: null },
    scenario: { id: 'flooding_1', duration_s: 60, time_step_s: 0.5 },
    timeline: [
      { time_s: 0, volumes_m3: { tank_1: 0 }, total_onboard_water_volume_m3: 0,
        equilibrium: { heel_deg: 0, trim_deg: 0.2, waterline_above_keel_m: 4.1 } },
      { time_s: 12.5, volumes_m3: { tank_1: 4.5 }, total_onboard_water_volume_m3: 4.5,
        equilibrium: { heel_deg: 2.1, trim_deg: 0.4, waterline_above_keel_m: 4.3 } },
    ],
    final_state: { time_s: 12.5, volumes_m3: { tank_1: 4.5 } },
    initial_total_water_volume_m3: 0, initial_total_water_mass_t: 0,
    cumulative_sea_exchange_m3: 4.5, cumulative_sea_exchange_t: 4.61,
    volume_conservation_error_m3: 0, mass_conservation_error_t: 1.2e-15,
    terminal_head_tolerance_m: 1e-8, terminal_max_head_difference_m: 0.02,
    remaining_gz: { rows: [{ angle_deg: 10, gz_m: 0.21 }, { angle_deg: 20, gz_m: 0.33 }] },
    gz_snapshots: [{ time_s: 12.5 }],
    downflooding: { status: 'no_open_points', event: null },
    diagnostics: [{ code: 'flooding.aperture_height', message: '液面越过有限开口高度' }],
  };

  function resultWithFlooding(): AnalysisResult {
    const result = structuredClone(completedFixture);
    result.status = 'partial';
    result.validity.complete = false;
    result.stages.flooding = { status: 'model_limit', requested: true, reason: 'partial aperture',
      validity: { complete: false, converged: true, model_applicable: false, historical_validated: null },
      method_versions: { flooding: 'connected-quasi-static-flooding-1' }, assumptions: [],
      diagnostics: [{ code: 'flooding.aperture_height', message: '液面越过有限开口高度' }],
      data: floodingData };
    return result;
  }

  it('reports stop reason, requested versus simulated time, conservation and remaining GZ', () => {
    render(<Report result={resultWithFlooding()} />);
    expect(screen.getByText(/partial_aperture/)).toBeVisible();
    expect(screen.getByText('请求时长')).toBeVisible();
    expect(screen.getByText('60 s')).toBeVisible();
    // 12.5 s of 60 s requested is a model limit, never a completion.
    expect(screen.getByText('12.5 s')).toBeVisible();
    expect(screen.getByText('未达请求时长即停止')).toBeVisible();
    expect(screen.getByText('水量守恒误差')).toBeVisible();
    expect(screen.getByText('质量守恒误差')).toBeVisible();
    expect(screen.getAllByText('4.5 m³').length).toBeGreaterThan(0);
    expect(screen.getByText('剩余静性力臂 GZ · m')).toBeVisible();
    expect(screen.getByText('0.21')).toBeVisible();
    // The accepted trajectory is listed with its attitude, never summarised away.
    expect(screen.getByText('横倾 · °')).toBeVisible();
    expect(screen.getByText('2.1')).toBeVisible();
  });

  it('keeps a partial flooding run labelled partial on the run page and reuses the cancel route', async () => {
    const run: RunView = { id: 'run-9', project_id: 'p1', revision: 1, condition_id: 'normal',
      status: 'completed', request_fingerprint: 'fp', created_at: '2026-10-04T00:00:00Z',
      started_at: null, finished_at: null, cancel_requested: false, result: resultWithFlooding(), error: null };
    vi.mocked(api.getRun).mockResolvedValue(run);
    vi.mocked(api.cancelRun).mockResolvedValue({ ...run, status: 'canceled', cancel_requested: true });
    render(<Run runId="run-9" onBack={vi.fn()} onReport={vi.fn()} />);
    // The damage facts appear both in the stage card and in the run-page summary.
    expect((await screen.findAllByText(/partial_aperture/)).length).toBeGreaterThan(0);
    await waitFor(() => expect(api.getRun).toHaveBeenCalled());
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: '查看完整报告 ↗' })); });
    expect(api.cancelRun).not.toHaveBeenCalled();
  });

  it('cancels a queued run through the existing endpoint', async () => {
    const queued: RunView = { id: 'run-10', project_id: 'p1', revision: 1, condition_id: 'normal',
      status: 'running', request_fingerprint: 'fp', created_at: '2026-10-04T00:00:00Z',
      started_at: null, finished_at: null, cancel_requested: false, result: null, error: null };
    vi.mocked(api.getRun).mockResolvedValue(queued);
    vi.mocked(api.cancelRun).mockResolvedValue({ ...queued, cancel_requested: true });
    render(<Run runId="run-10" onBack={vi.fn()} onReport={vi.fn()} />);
    const button = await screen.findByRole('button', { name: '取消计算' });
    await act(async () => { fireEvent.click(button); });
    await waitFor(() => expect(api.cancelRun).toHaveBeenCalledWith('run-10'));
  });
});
