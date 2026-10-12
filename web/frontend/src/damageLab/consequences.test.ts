import { describe, expect, it } from 'vitest';

import { explainTarget } from './consequences';
import { labCopy } from '../i18n/lab';
import type { AnalysisResult, ProjectDocument } from '../types';
import type { Boundary, FragmentTrace, LabEvent, LabResult, LabState, ModuleState } from './types';

/**
 * Explaining a selected target from the recorded evidence.
 *
 * These pin the refusals as much as the findings: a pre-detonation frame shows
 * nothing that happened later, the paths are ranked with the remainder counted,
 * a boundary's state is read off its own recorded load and threshold, an unknown
 * factor stays unknown, the native flow is labeled as the core's and as an
 * aggregate, and no explanation is ever built from an event's prose.
 */

const t = (key: Parameters<typeof labCopy>[1], params?: Parameters<typeof labCopy>[2]) => labCopy('zh-CN', key, params);

const moduleState = (over: Partial<ModuleState> = {}): ModuleState => ({
  id: 'engine', label: '主机', compartment_id: 'starboard-machinery', mechanical_integrity: 1,
  flooding_availability: 1, staffing_availability: 1, effective_availability: 1, available_shaft_power_kw: 500,
  status: 'ok', causes: [], ...over,
});

const state = (over: Partial<LabState> = {}): LabState => ({
  time_s: 0, event_index: 0, ship: null, compartments: [], modules: [moduleState()], crew_groups: [],
  capabilities: { shaft_power_kw: 500, known_shaft_power_subtotal_kw: 500 }, ...over,
});

const trace = (index: number, exposure: number, over: Partial<FragmentTrace> = {}): FragmentTrace => ({
  index, direction: [1, 0, 0], termination: 'target', blocked_by: null,
  segments: [{ from_m: [0, 0, 0], to_m: [1, 0, 0], compartment_id: 'starboard-machinery', transmission: 1,
    boundary_id: 'wall:starboard-machinery:port-machinery', boundary_transmission: 0.35 }],
  hits: [{ kind: 'module', id: 'engine', position_m: [1, 0, 0], exposure }], ...over,
});

const wall = (over: Partial<Boundary & { absorbed_exposure: number; generated_area_m2: number }> = {}) => ({
  id: 'wall:starboard-machinery:port-machinery', from_id: 'starboard-machinery', to_id: 'port-machinery',
  position_m: [0, 0, 2] as [number, number, number], transmission: 0, breach_threshold: 0.1, max_breach_area_m2: 0.5,
  discharge_coefficient: 0.6, source: 'fixture', estimate: true, absorbed_exposure: 0.5, generated_area_m2: 0.02, ...over,
});

const detonation = (over: Partial<LabEvent> = {}): LabEvent => ({
  index: 1, time_s: 0, kind: 'detonation', target_id: 'starboard-machinery',
  message: 'untrusted prose: module destroyed, 47 dead, 3 m hole', data: { position_m: [0, 0, 2], fragment_count: 128, seed: 42 }, ...over,
});

const result = (over: {
  snapshots?: LabState[]; events?: LabEvent[]; boundaries?: ReturnType<typeof wall>[]; traces?: FragmentTrace[];
  core?: unknown; fragmentation?: LabResult['fragmentation'];
} = {}): LabResult => ({
  schema: 'plimsoll-damage-lab-result-1', status: 'completed', condition_id: 'normal',
  request: { schema: 'plimsoll-damage-lab-request-1', condition_id: 'normal', experiment: {} as never, method_versions: {} },
  request_fingerprint: 'f', input_snapshot: {} as ProjectDocument,
  core_analysis: (over.core ?? { stages: {} }) as AnalysisResult, method_versions: {}, validity: {}, diagnostics: [],
  events: over.events ?? [detonation()],
  snapshots: over.snapshots ?? [state({ detonation_occurred: true })],
  final_state: state({ detonation_occurred: true }), simulated_duration_s: 12, elapsed_wall_seconds: 1, assumptions: [],
  fragmentation: over.fragmentation === undefined ? {
    method_version: 'compartment-fragment-rays-1', position_m: [0, 0, 2], compartment_id: 'starboard-machinery',
    fragment_count: 128, seed: 42, canceled: false, traces: over.traces ?? [trace(0, 0.8), trace(1, 0.2)],
    module_exposure: { engine: 1 }, crew_exposure: {},
    boundaries: over.boundaries ?? [wall()], generated_breaches: [], source: 'fixture', estimate: true,
  } : over.fragmentation,
} as unknown as LabResult);

const core = (over: { flows?: unknown; equilibrium?: unknown; transfers?: unknown } = {}) => ({
  stages: { flooding: { status: 'completed', data: {
    final_state: { flows: over.flows ?? [], equilibrium: over.equilibrium ?? {} },
    timeline: [{ edge_transfers: over.transfers ?? [] }],
  } } },
});

describe('explaining a selected target', () => {
  it('reveals nothing at a frame accepted before the detonation', () => {
    const explanation = explainTarget(result({
      snapshots: [state({ detonation_occurred: false, event_index: 0 }), state({ detonation_occurred: true, event_index: 1 })],
    }), 0, { kind: 'module', id: 'engine' }, t);
    expect(explanation.beforeDetonation).toBe(true);
    // The saved run still holds paths, walls and water — this frame shows none of it.
    expect(explanation.paths).toEqual([]);
    expect(explanation.boundaries).toEqual([]);
    expect(explanation.flows).toEqual([]);
    expect(explanation.exposure).toBeNull();
    expect(explanation.notes.join(' ')).toContain('起爆之前');
  });

  it('ranks the contributing paths and counts the remainder', () => {
    const explanation = explainTarget(result({ traces: [trace(0, 0.2), trace(1, 0.8), trace(2, 0.5)] }), 0, { kind: 'module', id: 'engine' }, t);
    expect(explanation.paths.map(path => path.exposure)).toEqual([0.8, 0.5, 0.2]);
    // The path keeps its own index and its transmission sequence.
    expect(explanation.paths[0].index).toBe(1);
    expect(explanation.paths[0].sequence).toContain('starboard-machinery');
    expect(explanation.paths[0].source).toBe('game');
    expect(explanation.remainder).toBe(0);
    expect(explanation.exposure).toBeCloseTo(1, 10);
  });

  it('lists the most significant paths and reports how many were left out', () => {
    const traces = Array.from({ length: 7 }, (_, index) => trace(index, (index + 1) / 10));
    const explanation = explainTarget(result({ traces }), 0, { kind: 'module', id: 'engine' }, t);
    expect(explanation.paths).toHaveLength(5);
    expect(explanation.remainder).toBe(2);
    expect(explanation.notes.join(' ')).toContain('另有 2 条路径');
  });

  it('reads each boundary response off its own recorded load and threshold', () => {
    const generated = explainTarget(result({ snapshots:[state({detonation_occurred:true,generated_breaches:[{id:'fragment:wall:starboard-machinery:port-machinery',area_m2:0.02} as never]})], boundaries: [wall({ absorbed_exposure: 0.5, breach_threshold: 0.1, generated_area_m2: 0.02 })] }), 0, { kind: 'module', id: 'engine' }, t);
    expect(generated.boundaries[0]).toMatchObject({ state: 'generated', absorbedExposure: 0.5, threshold: 0.1, generatedAreaM2: 0.02 });

    const sealed = explainTarget(result({ boundaries: [wall({ absorbed_exposure: 0.05, breach_threshold: 0.1, generated_area_m2: 0 })] }), 0, { kind: 'module', id: 'engine' }, t);
    expect(sealed.boundaries[0].state).toBe('sealed');

    // The load met the threshold but the recorded area is still zero: not a hole.
    const deferred = explainTarget(result({ boundaries: [wall({ absorbed_exposure: 0.5, breach_threshold: 0.1, generated_area_m2: 0 })] }), 0, { kind: 'module', id: 'engine' }, t);
    expect(deferred.boundaries[0].state).toBe('deferred');
  });

  it('separates the three factors and links each to the first accepted event', () => {
    const snapshots = [
      state({ event_index: 0, modules: [moduleState({ mechanical_integrity: 1, staffing_availability: null })] }),
      state({ event_index: 3, time_s: 4, modules: [moduleState({ mechanical_integrity: 0.6, staffing_availability: null })] }),
    ];
    const explanation = explainTarget(result({ snapshots }), 1, { kind: 'module', id: 'engine' }, t);
    const [mechanical, flooding, staffing] = explanation.factors;
    expect(mechanical).toMatchObject({ kind: 'mechanical', value: 0.6, firstFrame: 1, firstEventIndex: 3, firstEventTimeS: 4, source: 'game' });
    expect(flooding).toMatchObject({ kind: 'flooding', source: 'mixed' });
    // A factor the record does not hold stays unknown, with no first event invented.
    expect(staffing).toMatchObject({ kind: 'staffing', value: null, firstFrame: null, firstEventIndex: null });
  });

  it('reads only the selected accepted frame, filters by compartment and preserves reverse flow',()=>{
    const first=state({detonation_occurred:true});
    const second=state({time_s:4,event_index:5,ship:{time_s:4,equilibrium:{heel_deg:2,trim_deg:0},
      flows:[{id:'hole',from:'sea',to:'lab-water:starboard-machinery',flow_m3_s:-0.2,mass_flow_t_s:-0.205},{id:'other',from:'sea',to:'lab-water:forward-control',mass_flow_t_s:9}],
      edge_transfers:[{connection_id:'hole',from:'sea',to:'lab-water:starboard-machinery',transfer_m3:-0.1}]} as never});
    const r=result({snapshots:[first,second],core:core({flows:[{from:'sea',to:'starboard-machinery',mass_flow_t_s:99}]})});
    expect(explainTarget(r,0,{kind:'module',id:'engine'},t).flows).toEqual([]);
    const explanation=explainTarget(r,1,{kind:'module',id:'engine'},t);
    expect(explanation.flows).toHaveLength(2);
    expect(explanation.flows[0]).toMatchObject({from:'starboard-machinery',to:'sea',massFlowTS:0.205,flowM3S:0.2});
    expect(explanation.flows[1].transferM3).toBe(0.1);expect(explanation.aggregate).toBe(false);
    expect(explanation.hydraulic).toEqual({heelDeg:2,trimDeg:0});
  });
  it('does not reveal a generated hole before its accepted event, even at the same time',()=>{
    const r=result({snapshots:[state({detonation_occurred:true,event_index:1}),state({detonation_occurred:true,event_index:2,generated_breaches:[{id:'fragment:wall:starboard-machinery:port-machinery',area_m2:0.02} as never]})]});
    expect(explainTarget(r,0,{kind:'module',id:'engine'},t).boundaries[0]).toMatchObject({state:'deferred',generatedAreaM2:0});
    expect(explainTarget(r,1,{kind:'module',id:'engine'},t).boundaries[0]).toMatchObject({state:'generated',generatedAreaM2:0.02});
  });

  it('never builds an explanation out of an event’s prose', () => {
    const explanation = explainTarget(result(), 0, { kind: 'module', id: 'engine' }, t);
    const rendered = JSON.stringify(explanation);
    expect(rendered).not.toContain('module destroyed');
    expect(rendered).not.toContain('47 dead');
  });

  it('says there is no evidence rather than inventing some', () => {
    const explanation = explainTarget(result({ traces: [], fragmentation: null }), 0, { kind: 'crew', id: 'watch' }, t);
    expect(explanation.paths).toEqual([]);
    expect(explanation.exposure).toBeNull();
    expect(explanation.notes.join(' ')).toContain('没有记录破片报告');
  });
});
