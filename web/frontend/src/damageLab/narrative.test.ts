import { expect, it } from 'vitest';
import { replayEntries, comparisonBaseline } from './narrative';
import type { LabResult, LabState } from './types';

/**
 * The narrative is derived in one explicit language rather than from a hidden
 * one, so these assertions name the language they are checking. The frame
 * order, the targets and the significant flags are language-independent and are
 * checked in both.
 */
const ZH = 'zh-CN' as const;

const state = (index: number, time: number, integrity = 1, staff: number | null = 1, flood = 1): LabState => ({
  event_index: index, time_s: time, ship: null, compartments: [],
  modules: [{ id: 'engine', label: 'Engine', compartment_id: 'room', mechanical_integrity: integrity,
    staffing_availability: staff, flooding_availability: flood, effective_availability: staff == null ? null : integrity * staff * flood,
    available_shaft_power_kw: null, status: 'available', causes: [] }],
  crew_groups: [], capabilities: { shaft_power_kw: null, known_shaft_power_subtotal_kw: 0 },
});
const result = (snapshots: LabState[]) => ({ snapshots, events: snapshots.slice(1).map(s => ({
  index: s.event_index, time_s: s.time_s, kind: 'accepted_ship_state', target_id: null, message: 'do not parse me',
})), status: 'completed' }) as unknown as LabResult;

it('preserves distinct simultaneous frames and folds unchanged records', () => {
  const entries = replayEntries(result([state(-1, 0), state(0, 0, .4), state(1, 0, .4), state(2, 1, .4)]), ZH);
  expect(entries.map(e => e.frame)).toEqual([0, 1, 2, 3]);
  expect(entries[1].changes[0].title).toBe('机械损伤');
  expect(entries[1].targets).toContainEqual({ kind: 'module', id: 'engine' });
  expect(entries[2].significant).toBe(false);
});

it('explains staffing loss before later flooding loss without leaking future causes', () => {
  const entries = replayEntries(result([state(-1, 0), state(0, 0, .4), state(1, 7, .4, 0), state(2, 10, .4, 0, 0)]), ZH);
  expect(entries[2].changes.map(c => c.title)).toEqual(['值勤可用度变化']);
  expect(entries[2].changes[0].detail).not.toContain('进水停机');
  expect(entries[3].changes[0].title).toBe('进水停机');
});

it('uses the first accepted equilibrium and retains unknown staffing', () => {
  const initial = state(-1, 0), accepted = state(0, 0, 1, null);
  accepted.ship = { equilibrium: { heel_deg: 2, trim_deg: 3 } } as LabState['ship'];
  const report = result([initial, accepted]);
  expect(comparisonBaseline(report).initial).toBe(initial);
  expect(comparisonBaseline(report).ship).toBe(accepted.ship);
  expect(replayEntries(report, ZH)[1].changes.find(c => c.title === '值勤可用度变化')?.detail).toContain('未知');
});

it('keeps detonation and generated holes as distinct simultaneous events',()=>{
  const report=result([state(-1,0),state(0,0),state(1,0)]);
  report.events[0]={index:0,time_s:0,kind:'detonation',target_id:'room',message:'untrusted display text',data:{position_m:[0,0,1],fragment_count:128,seed:42}};
  report.events[1]={index:1,time_s:0,kind:'generated_breaches',target_id:'room',message:'untrusted display text',data:{breaches:[{id:'hole',from_id:'room',to_id:'sea',area_m2:.2,discharge_coefficient:.6,position_m:[0,1,1],source:'game',estimate:true}]}};
  const entries=replayEntries(report, ZH);
  expect(entries[0].changes).toHaveLength(0);
  expect(entries[1].title).toBe('起爆与破片路径');
  expect(entries[2].title).toBe('生成水力破口');
  expect(entries[1].changes[0].detail).not.toContain('untrusted');
});
