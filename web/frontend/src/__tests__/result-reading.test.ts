import { describe, expect, it } from 'vitest';

import { reportReadings, requestedStages, readStageTarget, stageHref } from '../components/resultReading';
import type { AnalysisResult, StageEnvelope } from '../types';

/**
 * Inline fixtures carry the shapes the coordinator actually writes
 * (`loading.data.values`, `resistance.data.power_rows`, `endurance.data.values`),
 * so this file pins the saved paths on its own and leaves the shared older
 * fixtures alone.
 */
function stage(status: StageEnvelope['status'], requested: boolean, data: StageEnvelope['data'] = null, reason: string | null = null): StageEnvelope {
  return {
    status, requested, reason,
    validity: { complete: status === 'completed', converged: status === 'completed' ? true : null, model_applicable: status === 'completed' ? true : null, historical_validated: null },
    method_versions: {}, assumptions: [], diagnostics: [], data,
  };
}

function result(stages: Record<string, StageEnvelope>, status: AnalysisResult['status'] = 'completed'): AnalysisResult {
  return { schema: 'plimsoll-analysis-1', status, stages } as unknown as AnalysisResult;
}

function byKey(stages: Record<string, StageEnvelope>, key: string) {
  const reading = reportReadings(result(stages)).find(item => item.key === key);
  if (!reading) throw new Error(`reading ${key} was not projected`);
  return reading;
}

function completeStages(): Record<string, StageEnvelope> {
  return {
    loading: stage('completed', true, { values: { total_mass_t: 27200, known_mass_t: 26900, lcg_m: 198.4 } }),
    equilibrium: stage('completed', true, { waterline_above_keel_m: 9.92, heel_deg: 0, trim_deg: 0.2 }),
    hydrostatics: stage('completed', true, { values: { gm_t_m: 1.85, awp_projected_xy_m2: 2640 } }),
    resistance: stage('completed', true, {
      method: 'holtrop_mennen_1982', primary_result: true, estimate: true,
      validity: { model_applicable: true },
      power_rows: [{ speed_kn: 18, qpc: { value: 0.55, source: 'QPC study', estimate: true },
        effective_power_kw: 7092.1, shaft_power_kw: 12894.8, shaft_power_shp: 17292.2,
        complete: true, estimate: true, primary_result: true, model_applicable: true }],
    }),
    endurance: stage('completed', true, { values: { method: 'steady_simultaneous_fuel_consumption', hours: 240,
      range_nm: 5760, speed_kn: 24, power_kw: 8500, limiting_fuel: 'oil',
      source: { id: 'fuel-study', page: '第四十二页' }, estimate: true } }),
  };
}

describe('saved-result readings', () => {
  it('reads only the saved paths, each with its own unit identity', () => {
    const readings = reportReadings(result(completeStages()));
    expect(readings.map(item => item.key)).toEqual([
      'loading.total_mass_t', 'equilibrium.waterline_above_keel_m', 'equilibrium.heel_deg',
      'hydrostatics.gm_t_m', 'resistance.shaft_power_kw', 'endurance.range_nm',
    ]);

    const mass = readings[0];
    expect(mass).toMatchObject({ state: 'known', value: 27200, dimension: 'mass', storedUnit: 't', canonicalUnit: 't' });

    const waterline = readings[1];
    expect(waterline).toMatchObject({ state: 'known', value: 9.92, dimension: 'length', storedUnit: 'm' });

    const heel = readings[2];
    expect(heel).toMatchObject({ state: 'known', value: 0, dimension: 'angle', storedUnit: 'deg' });

    const gm = readings[3];
    expect(gm).toMatchObject({ state: 'known', value: 1.85, dimension: 'length', storedUnit: 'm' });

    const power = readings[4];
    expect(power).toMatchObject({ state: 'known', value: 12894.8, dimension: 'power', storedUnit: 'kW' });
    expect(power.context).toBe('阶段 阻力与功率 · 工作点 18 kn');
    expect(power.source).toBe('QPC study');
    expect(power.estimate).toBe(true);

    const range = readings[5];
    // nmi is canonical: a range has no dimension to convert.
    expect(range).toMatchObject({ state: 'known', value: 5760, canonicalUnit: 'nmi' });
    expect(range.dimension).toBeUndefined();
    expect(range.context).toBe('阶段 续航 · 工作点 24 kn');
  });

  it('never substitutes another path, key or input for a missing saved field', () => {
    const stages = completeStages();
    // Legacy shapes: a top-level mass, a draught and a GM at the envelope root
    // are not the coordinator's paths, and the snapshot's own draught is not a
    // reading of this result either.
    stages.loading = stage('completed', true, { total_mass_t: 27200 });
    stages.equilibrium = stage('completed', true, { draught_m: 9.9, heel_deg: 0 });
    stages.hydrostatics = stage('completed', true, { gm_t_m: 1.85, values: {} });

    const mass = byKey(stages, 'loading.total_mass_t');
    const waterline = byKey(stages, 'equilibrium.waterline_above_keel_m');
    const gm = byKey(stages, 'hydrostatics.gm_t_m');

    expect([mass.state, waterline.state, gm.state]).toEqual(['unknown', 'unknown', 'unknown']);
    expect([mass.value, waterline.value, gm.value]).toEqual([null, null, null]);
    expect(mass.reason).toBe('本次结果未给出此字段');
  });

  it('suppresses residual numbers of stages that did not deliver a result', () => {
    const stages = completeStages();
    stages.hydrostatics = stage('unavailable', true, { values: { gm_t_m: 9.99 } }, '型线资料不足');
    stages.equilibrium = stage('model_limit', true, { waterline_above_keel_m: 9.92, heel_deg: 0 }, '超出方法适用范围');
    stages.loading = stage('failed', true, { values: { total_mass_t: 27200 } }, '权重账本自检未通过');
    stages.resistance = stage('canceled', true, { power_rows: [{ speed_kn: 18, shaft_power_kw: 12894.8, complete: true, primary_result: true }] });

    const blocked = ['loading.total_mass_t', 'equilibrium.waterline_above_keel_m', 'hydrostatics.gm_t_m', 'resistance.shaft_power_kw']
      .map(key => byKey(stages, key));
    expect(blocked.map(item => item.state)).toEqual(['failed', 'model_limit', 'unavailable', 'canceled']);
    expect(blocked.every(item => item.value === null)).toBe(true);
    expect(blocked[0].reason).toBe('计算失败：权重账本自检未通过');
    expect(blocked[1].reason).toBe('模型越界：超出方法适用范围');
    expect(blocked[2].reason).toBe('资料不足：型线资料不足');
    expect(blocked[3].reason).toBe('该阶段已取消');
    expect(blocked[3].context).toBe('阶段 阻力与功率');
  });

  it('separates a genuine zero from null and from a missing field', () => {
    const stages = completeStages();
    stages.equilibrium = stage('completed', true, { waterline_above_keel_m: 0, heel_deg: 0 });
    stages.hydrostatics = stage('completed', true, { values: { gm_t_m: null } });
    stages.loading = stage('completed', true, { values: {} });

    const waterline = byKey(stages, 'equilibrium.waterline_above_keel_m');
    const heel = byKey(stages, 'equilibrium.heel_deg');
    const gm = byKey(stages, 'hydrostatics.gm_t_m');
    const mass = byKey(stages, 'loading.total_mass_t');

    expect([waterline.state, waterline.value, waterline.reason]).toEqual(['known', 0, null]);
    expect([heel.state, heel.value, heel.reason]).toEqual(['known', 0, null]);
    expect([gm.state, gm.value]).toEqual(['unknown', null]);
    expect(gm.reason).toBe('保存结果中 values.gm_t_m 为 null');
    expect([mass.state, mass.value]).toEqual(['unknown', null]);
    expect(mass.reason).toBe('本次结果未给出此字段');
    expect(mass.reason).not.toBe(gm.reason);
  });

  it('refuses a stored number that is not finite', () => {
    const stages = completeStages();
    stages.equilibrium = stage('completed', true, { waterline_above_keel_m: '9.92', heel_deg: 0 });
    const reading = byKey(stages, 'equilibrium.waterline_above_keel_m');
    expect([reading.state, reading.value]).toEqual(['unknown', null]);
    expect(reading.reason).toBe('保存结果中 waterline_above_keel_m 不是有限数字');
  });

  it('still shows a completed stage of a partial or canceled overall result', () => {
    const stages = completeStages();
    stages.deck = stage('unavailable', true, null, '甲板端点资料不足');
    stages.endurance = stage('canceled', true, { values: { range_nm: 5760, speed_kn: 24 } }, '运行被取消');

    for (const status of ['partial', 'canceled'] as const) {
      const readings = reportReadings(result(stages, status));
      const mass = readings.find(item => item.key === 'loading.total_mass_t')!;
      const gm = readings.find(item => item.key === 'hydrostatics.gm_t_m')!;
      const range = readings.find(item => item.key === 'endurance.range_nm')!;
      expect([mass.state, mass.value]).toEqual(['known', 27200]);
      expect([gm.state, gm.value]).toEqual(['known', 1.85]);
      expect([range.state, range.value]).toEqual(['canceled', null]);
    }
  });

  it('names an unrequested or absent stage instead of reading it', () => {
    const stages = completeStages();
    stages.hydrostatics = stage('not_requested', false, null, '未请求');
    const gm = byKey(stages, 'hydrostatics.gm_t_m');
    expect([gm.state, gm.value, gm.reason]).toEqual(['not_requested', null, '本次请求未运行该阶段']);

    const missing = byKey({ loading: stage('completed', true, { values: { total_mass_t: 1 } }) }, 'equilibrium.heel_deg');
    expect([missing.state, missing.value, missing.reason]).toEqual(['not_requested', null, '该运行没有保存此阶段']);
  });

  it('keeps several power work points as several, never picking the first row', () => {
    const stages = completeStages();
    stages.resistance = stage('completed', true, { primary_result: true, validity: { model_applicable: true },
      power_rows: [
        { speed_kn: 16, shaft_power_kw: 10200, complete: true, primary_result: true },
        { speed_kn: 18, shaft_power_kw: 12894.8, complete: true, primary_result: true },
      ] });
    const power = byKey(stages, 'resistance.shaft_power_kw');
    expect([power.state, power.value]).toEqual(['multiple', null]);
    expect(power.reason).toBe('多个工作点，见阻力与功率');
    expect(power.context).toBe('阶段 阻力与功率 · 2 个工作点');
  });

  it('accepts only a complete, primary, in-scope single work point', () => {
    const single = (row: Record<string, unknown>, data: Record<string, unknown> = {}) => {
      const stages = completeStages();
      stages.resistance = stage('completed', true, { ...data, power_rows: [row] });
      return byKey(stages, 'resistance.shaft_power_kw');
    };

    expect(single({ speed_kn: 18, shaft_power_kw: 12894.8, complete: false, primary_result: true }))
      .toMatchObject({ state: 'unknown', value: null, reason: '该工作点未完整求得，见阻力与功率' });
    expect(single({ speed_kn: 18, shaft_power_kw: 12894.8, complete: true, primary_result: false }))
      .toMatchObject({ state: 'unknown', value: null, reason: '该工作点为非主试算，见阻力与功率' });
    expect(single({ speed_kn: 18, shaft_power_kw: 12894.8, complete: true, primary_result: true, model_applicable: false }))
      .toMatchObject({ state: 'unknown', value: null, reason: '该工作点不在经验适用范围，见阻力与功率' });
    // An out-of-scope envelope speaks for the row it carries, however in-scope
    // that one row claims to be.
    const outOfScopeStage = completeStages();
    outOfScopeStage.resistance = stage('completed', true, { validity: { complete: true, model_applicable: false, historical_validated: null },
      power_rows: [{ speed_kn: 18, shaft_power_kw: 12894.8, complete: true, primary_result: true }] });
    expect(byKey(outOfScopeStage, 'resistance.shaft_power_kw'))
      .toMatchObject({ state: 'unknown', value: null, reason: '该工作点不在经验适用范围，见阻力与功率' });
    const outOfScopeData = completeStages();
    outOfScopeData.resistance = stage('completed', true, { validity: { model_applicable: false },
      power_rows: [{ speed_kn: 18, shaft_power_kw: 12894.8, complete: true, primary_result: true, model_applicable: true }] });
    expect(byKey(outOfScopeData, 'resistance.shaft_power_kw'))
      .toMatchObject({ state: 'unknown', value: null, reason: '该工作点不在经验适用范围，见阻力与功率' });
    expect(single({ speed_kn: 18, shaft_power_kw: null, complete: true, primary_result: true }))
      .toMatchObject({ state: 'unknown', value: null, reason: '该工作点未给出有限航速或轴功率，见阻力与功率' });
    expect(single({ speed_kn: 18, shaft_power_kw: 12894.8, complete: true, primary_result: true }, { primary_result: false }))
      .toMatchObject({ state: 'unknown', value: null, reason: '该工作点为非主试算，见阻力与功率' });
    expect(single({ speed_kn: 0, shaft_power_kw: 0, complete: true, primary_result: true }))
      .toMatchObject({ state: 'known', value: 0, context: '阶段 阻力与功率 · 工作点 0 kn' });

    const empty = completeStages();
    empty.resistance = stage('completed', true, { power_rows: [] });
    expect(byKey(empty, 'resistance.shaft_power_kw')).toMatchObject({ state: 'unknown', value: null, reason: '本次结果未给出此字段' });
  });

  it('keeps a structured declared source and the estimate flag without claiming historical verification', () => {
    const stages = completeStages();
    stages.loading = stage('completed', true, { values: { total_mass_t: 27200 },
      source: { id: 'weight-ledger', sheet: 'B' }, estimate: true });
    stages.endurance = stage('completed', true, { values: { range_nm: 5760, source: '   ', estimate: null } });

    const mass = byKey(stages, 'loading.total_mass_t');
    expect(mass.source).toBe('{"id":"weight-ledger","sheet":"B"}');
    expect(mass.estimate).toBe(true);
    expect(mass.source).not.toMatch(/验证|confirmed|historically/i);

    const range = byKey(stages, 'endurance.range_nm');
    expect(range.source).toBeNull();
    expect(range.estimate).toBeNull();
    // No speed declared: the reading still stands, without an invented work point.
    expect(range.context).toBe('阶段 续航');

    const withoutFlag = completeStages();
    withoutFlag.endurance = stage('completed', true, { values: { range_nm: 5760, speed_kn: 24 } });
    expect(byKey(withoutFlag, 'endurance.range_nm').estimate).toBeNull();
  });

  it('requires affirmative saved primary and applicability evidence for a power reading', () => {
    const stages = completeStages();
    stages.resistance = stage('completed', true, { power_rows: [{ speed_kn: 18, shaft_power_kw: 100, complete: true }] });
    stages.resistance.validity.model_applicable = null;
    expect(byKey(stages, 'resistance.shaft_power_kw')).toMatchObject({ state: 'unknown', value: null });
    stages.resistance.data = { primary_result: null, validity: { model_applicable: null },
      power_rows: [{ speed_kn: 18, shaft_power_kw: 100, complete: true, primary_result: null }] };
    expect(byKey(stages, 'resistance.shaft_power_kw')).toMatchObject({ state: 'unknown', value: null });
    stages.resistance.data = { primary_result: true, validity: { model_applicable: true },
      power_rows: [{ speed_kn: 18, shaft_power_kw: 100, complete: true, primary_result: true }] };
    expect(byKey(stages, 'resistance.shaft_power_kw')).toMatchObject({ state: 'known', value: 100 });
  });
});

describe('requested stages', () => {
  it('keeps the canonical order and pushes unknown stages behind it in saved order', () => {
    const stages: Record<string, StageEnvelope> = {
      historical: stage('completed', true),
      loading: stage('completed', true),
      'zz-experimental': stage('completed', true),
      resistance: stage('failed', true, null, '阻力表缺失'),
      equilibrium: stage('completed', true),
      gz: stage('completed', true),
      'aa-new-kernel': stage('completed', true),
      deck: stage('not_requested', false),
    };
    expect(requestedStages(result(stages)).map(item => item.name))
      .toEqual(['loading', 'equilibrium', 'gz', 'resistance', 'historical', 'zz-experimental', 'aa-new-kernel']);
  });

  it('returns nothing for a result that requested no stage', () => {
    expect(requestedStages(result({}))).toEqual([]);
    expect(requestedStages(null)).toEqual([]);
  });
});

describe('stage addresses', () => {
  it('keeps the tool route and the run id while adding the stage tail', () => {
    expect(stageHref('reports', 'r1', 'equilibrium')).toBe('#/reports/r1/stages/equilibrium');
    expect(stageHref('runs', 'run-7', 'flooding')).toBe('#/runs/run-7/stages/flooding');
    // A name with a slash or non-ASCII survives the round trip as one segment.
    expect(stageHref('reports', 'run/7', '稳性 曲线')).toBe('#/reports/run%2F7/stages/%E7%A8%B3%E6%80%A7%20%E6%9B%B2%E7%BA%BF');
  });

  it('reads back its own address and ignores every other target', () => {
    expect(readStageTarget('#/reports/r1/stages/gz', 'reports', 'r1')).toBe('gz');
    expect(readStageTarget(stageHref('runs', 'run/7', '稳性 曲线'), 'runs', 'run/7')).toBe('稳性 曲线');
    expect(readStageTarget('/reports/r1/stages/deck', 'reports', 'r1')).toBe('deck');

    // Old links, other pages, other ids, missing or broken tails: no target.
    expect(readStageTarget('#/reports/r1', 'reports', 'r1')).toBeNull();
    expect(readStageTarget('#/reports/r1/stages/gz', 'runs', 'r1')).toBeNull();
    expect(readStageTarget('#/runs/r2/stages/gz', 'reports', 'r1')).toBeNull();
    expect(readStageTarget('#/reports/r1/gz', 'reports', 'r1')).toBeNull();
    expect(readStageTarget('#/reports/r1/stages/', 'reports', 'r1')).toBeNull();
    expect(readStageTarget('#/reports//stages/gz', 'reports', 'r1')).toBeNull();
    expect(readStageTarget('#/reports/r1/stages/gz/extra', 'reports', 'r1')).toBeNull();
    expect(readStageTarget('#/reports/r1/stages/%E0%A4%A', 'reports', 'r1')).toBeNull();
    expect(readStageTarget('#stage-loading', 'reports', 'r1')).toBeNull();
    expect(readStageTarget('', 'reports', 'r1')).toBeNull();
  });

  it('does not answer for a stage the saved result never requested', () => {
    // The address is still readable; whether it points at a real section is the
    // page's decision, never a value invented here.
    const stages = { loading: stage('completed', true, { values: { total_mass_t: 27200 } }) };
    const names = requestedStages(result(stages)).map(item => item.name);
    expect(names).toEqual(['loading']);
    expect(readStageTarget(stageHref('reports', 'r1', 'flooding'), 'reports', 'r1')).toBe('flooding');
    expect(readStageTarget(stageHref('reports', 'r1', names[0]), 'reports', 'r1')).toBe('loading');
  });
});
