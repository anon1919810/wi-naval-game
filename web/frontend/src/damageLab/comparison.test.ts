import { describe, expect, it } from 'vitest';

import { compareTrials, delta } from './comparison';
import { labCopy } from '../i18n/lab';
import type { AnalysisResult, ProjectDocument } from '../types';
import type { CrewState, Experiment, LabResult, LabRun, ModuleState } from './types';

/**
 * Comparing two completed trials.
 *
 * These hold the module to the rules the plan fixes: a run that shares no basis
 * is refused with its reason, every changed input is listed, a changed draw is
 * never attributed to one setting, the accepted endpoints are printed as recorded
 * rather than interpolated, the availability factors stay multiplicative, and an
 * unknown operand produces an unknown difference instead of a zero.
 */

const l = (key: Parameters<typeof labCopy>[1], params?: Parameters<typeof labCopy>[2]) => labCopy('zh-CN', key, params);

const moduleState = (over: Partial<ModuleState> = {}): ModuleState => ({
  id: 'engine', label: '主机', compartment_id: 'room', mechanical_integrity: 1, flooding_availability: 1,
  staffing_availability: 1, effective_availability: 1, available_shaft_power_kw: 500, status: 'ok', causes: [], ...over,
});

const crewState = (over: Partial<CrewState> = {}): CrewState => ({
  id: 'watch', label: '值班组', compartment_id: 'room', module_id: 'engine', initial_personnel: 10,
  available: 6, incapacitated: 2, dead: 1, evacuated: 1, location: 'room', casualty_location: 'room',
  evacuated_location: null, evacuation_triggered: false, causes: [], ...over,
});

const experiment = (over: Partial<Experiment> = {}): Experiment => ({
  schema: 'plimsoll-damage-lab-experiment-1', source: 'fixture', estimate: true, duration_s: 12, time_step_s: 1,
  initial_water_m3: { room: 0 }, modules: [], crew_groups: [], breaches: [],
  impact: { position_m: [-4, 1.6, 2.4], severity: 0.6, radius_m: 2, source: 'fixture', estimate: true },
  remaining_gz_angles_deg: [0, 10],
  rules: { casualty_fraction: 0.4, fatal_fraction: 0.25, module_flood_threshold: 0.5, evacuate_fill_fraction: 0.3, source: 'fixture', estimate: true },
  ...over,
});

/** Each fixture is its own run: two records with one id are the same run. */
let runCount = 0;
const run = (over: {
  id?: string; experiment?: Experiment; modules?: ModuleState[]; crew?: CrewState[]; endpointTimeS?: number;
  revision?: number; condition?: string; methodVersions?: Record<string, string>; status?: string;
  volumeM3?: number; massT?: number; heelDeg?: number; trimDeg?: number; breaches?: LabResult['applied_breaches'];
} = {}): LabRun => {
  const declared = over.experiment ?? experiment();
  const request = { schema: 'plimsoll-damage-lab-request-1', condition_id: over.condition ?? 'normal', experiment: declared, method_versions: over.methodVersions ?? {} };
  const result = {
    schema: 'plimsoll-damage-lab-result-1', status: over.status ?? 'completed', condition_id: request.condition_id,
    request, request_fingerprint: 'f', input_snapshot: { id: 'p', revision: over.revision ?? 1 } as unknown as ProjectDocument,
    core_analysis: {} as AnalysisResult, method_versions: over.methodVersions ?? {}, validity: {}, diagnostics: [],
    events: [], snapshots: [], simulated_duration_s: declared.duration_s, elapsed_wall_seconds: 1, assumptions: [],
    applied_breaches: over.breaches ?? [],
    final_state: {
      time_s: over.endpointTimeS ?? 12, event_index: 4,
      ship: { time_s: over.endpointTimeS ?? 12, equilibrium: { p: 0, q: 0.2, waterline_d_m: 4, heel_deg: over.heelDeg ?? 0, trim_deg: over.trimDeg ?? 0.2 },
        total_onboard_water_mass_t: over.massT ?? 10, total_onboard_water_volume_m3: over.volumeM3 ?? 9.8, mass_conservation_error_t: 0, tanks: [] },
      compartments: [], modules: over.modules ?? [moduleState()], crew_groups: over.crew ?? [crewState()],
      capabilities: { shaft_power_kw: 500, known_shaft_power_subtotal_kw: 500 },
    },
  } as unknown as LabResult;
  return {
    id: over.id ?? `run-${++runCount}`, project_id: 'p', revision: over.revision ?? 1,
    condition_id: request.condition_id, status: result.status, request_fingerprint: 'f', request, result,
    cancel_requested: false, created_at: '', error: null, has_result: true,
  } as unknown as LabRun;
};

describe('comparing two completed trials', () => {
  it('detects layout, initial integrity, power and provenance changes omitted by the old census',()=>{
    const a=experiment({modules:[{id:'m',box:{center_m:[0,0,1],size_m:[1,1,1]},initial_integrity:1,nominal_shaft_power_kw:500,source:'source-a'} as never]});
    const b=structuredClone(a);b.modules[0].box.center_m[0]=1;b.modules[0].initial_integrity=0.5;b.modules[0].nominal_shaft_power_kw=600;b.modules[0].source='source-b';
    const c=compareTrials(run({experiment:a}),run({experiment:b}),l);
    expect(c.changes.map(row=>row.path)).toEqual(expect.arrayContaining(['modules[m].box.center_m','modules[m].initial_integrity','modules[m].nominal_shaft_power_kw','modules[m].source']));
    expect(c.uncontrolled.length).toBeGreaterThan(0);
  });
  it('refuses internally inconsistent identities even when both sides carry the same bad snapshot',()=>{
    const a=run(),b=run();a.result!.input_snapshot.id='wrong';b.result!.input_snapshot.id='wrong';
    expect(compareTrials(a,b,l).compatible).toBe(false);
  });
  it('lists modules present on only one side with unknown differences',()=>{
    const c=compareTrials(run(),run({modules:[]}),l);
    expect(c.modules[0]).toMatchObject({id:'engine',mechanical:null,effective:null});
  });
  it('calls two identical runs comparable, with zero differences and no changes', () => {
    const comparison = compareTrials(run(), run(), l);
    expect(comparison.compatible).toBe(true);
    expect(comparison.reasons).toEqual([]);
    expect(comparison.changes).toEqual([]);
    expect(comparison.uncontrolled).toEqual([]);
    expect(comparison.sameEndpoint).toBe(true);
    // A known value compared with itself is a real zero, not an unknown.
    expect(comparison.modules[0].mechanical).toBe(0);
    expect(comparison.ship.volumeM3).toBe(0);
    expect(comparison.crew[0].dead).toBe(0);
  });

  it('refuses a pair whose revision, condition, methods or status differ, and says which', () => {
    expect(compareTrials(run({ revision: 1 }), run({ revision: 2 }), l).reasons.join(' ')).toContain('项目修订不同');
    expect(compareTrials(run({ condition: 'normal' }), run({ condition: 'ballast' }), l).reasons.join(' ')).toContain('载荷工况不同');
    expect(compareTrials(run({ methodVersions: { coordinator: 'a' } }), run({ methodVersions: { coordinator: 'b' } }), l)
      .reasons.join(' ')).toContain('方法版本不同');
    expect(compareTrials(run({ status: 'canceled' }), run(), l).reasons.join(' ')).toContain('必须已完成');
    expect(compareTrials(run({ revision: 2, condition: 'ballast' }), run(), l).compatible).toBe(false);
  });

  it('lists every changed experiment input', () => {
    const changed = experiment({ impact: { position_m: [-3, 2.5, 2], severity: 0.75, radius_m: 2, source: 'fixture', estimate: true } });
    const comparison = compareTrials(run(), run({ experiment: changed }), l);
    const paths = comparison.changes.map(change => change.path);
    expect(paths).toContain('impact.position_m');
    expect(paths).toContain('impact.severity');
    expect(paths).not.toContain('impact.radius_m');
    expect(comparison.changes.find(change => change.path === 'impact.severity')).toMatchObject({ from: '0.6', to: '0.75' });
  });

  it('never attributes a difference to one setting when the draw or several inputs changed', () => {
    const drawn = experiment({ detonation: { position_m: [-4, 1.6, 2.4], fragment_count: 256, seed: 43, boundaries: [], source: 'fixture', estimate: true } });
    const seedOnly = compareTrials(run(), run({ experiment: drawn }), l);
    expect(seedOnly.uncontrolled.join(' ')).toContain('抽样本身变了');
    expect(seedOnly.uncontrolled).toHaveLength(2); // count and seed

    const many = experiment({ impact: { position_m: [-3, 2.5, 2], severity: 0.8, radius_m: 3, source: 'fixture', estimate: true } });
    const several = compareTrials(run(), run({ experiment: many }), l);
    expect(several.uncontrolled.join(' ')).toContain('不能归因于某一项设定');

    const longer = experiment({ duration_s: 24 });
    expect(compareTrials(run(), run({ experiment: longer }), l).uncontrolled.join(' ')).toContain('不在同一时间刻度上');
  });

  it('prints both accepted endpoints as recorded instead of interpolating', () => {
    const comparison = compareTrials(run({ endpointTimeS: 12 }), run({ endpointTimeS: 9.5, volumeM3: 4.2 }), l);
    expect(comparison.a.endpointTimeS).toBe(12);
    expect(comparison.b.endpointTimeS).toBe(9.5);
    expect(comparison.sameEndpoint).toBe(false);
    // The delta comes from the two recorded states, with nothing smoothed onto a
    // common time.
    expect(comparison.ship.volumeM3).toBeCloseTo(4.2 - 9.8, 10);
  });

  it('keeps an unknown operand unknown instead of calling it zero', () => {
    const comparison = compareTrials(run(),
      run({ modules: [moduleState({ staffing_availability: null, effective_availability: null })] }), l);
    const module = comparison.modules[0];
    // A factor both runs recorded is a real zero difference…
    expect(module.mechanical).toBe(0);
    expect(module.flooding).toBe(0);
    // …while a factor only one run recorded is unknown, never zero.
    expect(module.staffing).toBeNull();
    expect(module.effective).toBeNull();
    expect(module.multiplicative).toBeNull();
    // And a null ship value stays unknown rather than becoming a zero.
    expect(delta(9.8, null)).toBeNull();
  });

  it('reports the multiplicative relationship instead of repairing it', () => {
    const consistent = compareTrials(run(),
      run({ modules: [moduleState({ mechanical_integrity: 0.8, flooding_availability: 0.5, staffing_availability: 0.5, effective_availability: 0.2 })] }), l);
    expect(consistent.modules[0].multiplicative).toBe(true);
    expect(consistent.modules[0].effective).toBeCloseTo(0.2 - 1, 10);

    const disagreeing = compareTrials(run(),
      run({ modules: [moduleState({ mechanical_integrity: 0.8, flooding_availability: 0.5, staffing_availability: 0.5, effective_availability: 0.9 })] }), l);
    // 0.8 × 0.5 × 0.5 = 0.2, not 0.9: the page shows it disagreeing rather than
    // adding the losses up or overwriting the record.
    expect(disagreeing.modules[0].multiplicative).toBe(false);
  });

  it('compares crew counts per group without inventing an evacuation', () => {
    const comparison = compareTrials(run(),
      run({ crew: [crewState({ available: 4, incapacitated: 3, dead: 2, evacuated: null })] }), l);
    const crew = comparison.crew[0];
    expect(crew.available).toBe(-2);
    expect(crew.incapacitated).toBe(1);
    expect(crew.dead).toBe(1);
    // The other run never recorded an evacuation count, so there is no delta.
    expect(crew.evacuated).toBeNull();
  });

  it('compares breach areas per opening, and only where both runs recorded one', () => {
    const breach = { id: 'known-side-breach', from_id: 'sea', to_id: 'starboard-machinery', position_m: [0, 3, 2] as [number, number, number], area_m2: 0.4, discharge_coefficient: 0.6, source: 'fixture', estimate: true };
    const comparison = compareTrials(run({ breaches: [breach] }),
      run({ breaches: [{ ...breach, area_m2: 0.9 }] }), l);
    expect(comparison.breaches).toEqual([{ id: 'known-side-break'.replace('break', 'breach'), areaM2: 0.5 }]);
  });

  it('reads the method versions and snapshot identity from the frozen request', () => {
    // Two runs that look alike but were written against different snapshots are
    // still refused: identity comes from the record, not from appearance.
    const other = run();
    (other.result!.input_snapshot as unknown as { revision: number }).revision = 7;
    expect(compareTrials(run(), other, l).reasons.join(' ')).toContain('快照指向不同修订');
  });
});
