import { cleanup, fireEvent, screen } from '@testing-library/react';
import { renderZh as render } from '../__tests__/locale';
import { afterEach, describe, expect, it, vi } from 'vitest';

import ComparisonPanel from './ComparisonPanel';
import type { AnalysisResult, ProjectDocument } from '../types';
import type { CrewState, Experiment, LabResult, LabRun, ModuleState } from './types';

/**
 * The read-only comparison of two completed trials.
 *
 * The rules themselves live in `comparison.ts` and are tested there; these hold
 * the component to what it must *show*: both records' provenance, a refusal with
 * its reason and no tables, the accepted endpoints as recorded, an unknown delta
 * as unknown, and a view-trial action that states a revision mismatch instead of
 * quietly leaving the current revision.
 */

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

let count = 0;
const run = (over: {
  id?: string; experiment?: Experiment; modules?: ModuleState[]; crew?: CrewState[]; endpointTimeS?: number;
  revision?: number; condition?: string; methodVersions?: Record<string, string>; status?: string; volumeM3?: number;
} = {}): LabRun => {
  const declared = over.experiment ?? experiment();
  const request = { schema: 'plimsoll-damage-lab-request-1', condition_id: over.condition ?? 'normal', experiment: declared, method_versions: over.methodVersions ?? {} };
  const result = {
    schema: 'plimsoll-damage-lab-result-1', status: over.status ?? 'completed', condition_id: request.condition_id, request,
    request_fingerprint: 'f', input_snapshot: { id: 'p', revision: over.revision ?? 1 } as unknown as ProjectDocument,
    core_analysis: {} as AnalysisResult, method_versions: over.methodVersions ?? {}, validity: {}, diagnostics: [],
    events: [], snapshots: [], simulated_duration_s: declared.duration_s, elapsed_wall_seconds: 1, assumptions: [], applied_breaches: [],
    final_state: {
      time_s: over.endpointTimeS ?? 12, event_index: 4,
      ship: { time_s: over.endpointTimeS ?? 12, equilibrium: { p: 0, q: 0.2, waterline_d_m: 4, heel_deg: 0, trim_deg: 0.2 },
        total_onboard_water_mass_t: 10, total_onboard_water_volume_m3: over.volumeM3 ?? 9.8, mass_conservation_error_t: 0, tanks: [] },
      compartments: [], modules: over.modules ?? [moduleState()], crew_groups: over.crew ?? [crewState()],
      capabilities: { shaft_power_kw: 500, known_shaft_power_subtotal_kw: 500 },
    },
  } as unknown as LabResult;
  return {
    id: over.id ?? `run-${++count}`, project_id: 'p', revision: over.revision ?? 1, condition_id: request.condition_id,
    status: result.status, request_fingerprint: 'f', request, result, cancel_requested: false, created_at: '', error: null, has_result: true,
  } as unknown as LabRun;
};

afterEach(cleanup);

const show = (a: LabRun | null, b: LabRun | null, currentRevision = 1) => render(
  <ComparisonPanel records={[a, b].filter((entry): entry is LabRun => Boolean(entry))} a={a} b={b}
    currentRevision={currentRevision} onSelect={vi.fn()} onView={vi.fn()} />);

describe('the trial comparison panel', () => {
  it('shows both records with their provenance and a difference direction', () => {
    show(run({ id: 'aaa', endpointTimeS: 12 }), run({ id: 'bbb', endpointTimeS: 12, volumeM3: 4.2 }));
    // Both sides are named, with revision, condition, endpoint and simulated time.
    expect(screen.getAllByText(/修订 1 · normal/)).toHaveLength(2);
    expect(screen.getAllByText(/接受终点 12\.00 s/)).toHaveLength(2);
    // The difference column states its direction rather than leaving it implied.
    expect(screen.getByText('差值（B − A）')).toBeVisible();
    expect(screen.getByText('-5.600000')).toBeVisible();
  });

  it('refuses a pair that shares no basis, with the reason and without tables', () => {
    show(run({ id: 'aaa' }), run({ id: 'bbb', revision: 2 }));
    // The revision differs and so do the frozen snapshots, so more than one
    // reason is listed; both of them are reasons, and no table is shown.
    expect(screen.getAllByRole('alert').map(node => node.textContent).join(' ')).toContain('项目修订不同');
    expect(screen.queryByRole('table')).toBeNull();
  });

  it('lists every changed input', () => {
    const changed = experiment({ impact: { position_m: [-3, 2.5, 2], severity: 0.75, radius_m: 2, source: 'fixture', estimate: true } });
    show(run({ id: 'aaa' }), run({ id: 'bbb', experiment: changed }));
    const table = screen.getAllByRole('table')[0];
    expect(table.textContent).toContain('impact.severity');
    expect(table.textContent).toContain('0.6');
    expect(table.textContent).toContain('0.75');
    expect(table.textContent).not.toContain('impact.radius_m');
  });

  it('flags two runs that stopped at different accepted times', () => {
    show(run({ id: 'aaa', endpointTimeS: 12 }), run({ id: 'bbb', endpointTimeS: 9.5 }));
    expect(screen.getAllByRole('alert').map(node => node.textContent).join(' ')).toContain('停在不同接受时刻');
    expect(screen.getByText(/接受终点 9\.50 s/)).toBeVisible();
  });

  it('shows a difference it cannot compute as unknown instead of as zero', () => {
    show(run({ id: 'aaa' }), run({ id: 'bbb', crew: [crewState({ available: 4, evacuated: null })] }));
    const crewTable = screen.getAllByRole('table')[1];
    // Available/incapacitated/dead have real differences; the unrecorded
    // evacuation count does not become a zero.
    expect(crewTable.textContent).toContain('-2.000000');
    expect(crewTable.textContent).toContain('未知');
  });

  it('states a revision mismatch on the view action instead of hiding it', () => {
    const onView = vi.fn();
    const older = (id: string) => run({ id, revision: 2 });
    render(<ComparisonPanel records={[older('aaa'), older('bbb')]} a={older('aaa')} b={older('bbb')}
      currentRevision={3} onSelect={vi.fn()} onView={onView} />);
    // Each side belongs to an older revision than the page, and each says so.
    expect(screen.getAllByText(/属于修订 2，而本页处于修订 3/)).toHaveLength(2);
    fireEvent.click(screen.getAllByRole('button', { name: /查看试验/ })[0]);
    // The action itself still goes through the page's own saved-trial flow.
    expect(screen.getAllByRole('button', { name: /查看试验/ })[0]).toBeDisabled();
    expect(onView).not.toHaveBeenCalled();
  });

  it('reads a chosen record without restoring anything', () => {
    const onSelect = vi.fn(), onView = vi.fn();
    const records = [run({ id: 'aaa' }), run({ id: 'bbb' })];
    render(<ComparisonPanel records={records} a={records[0]} b={null} currentRevision={1} onSelect={onSelect} onView={onView} />);
    fireEvent.change(screen.getByLabelText('试验 B'), { target: { value: 'bbb' } });
    expect(onSelect).toHaveBeenCalledWith('b', 'bbb');
    // Selecting is not viewing: nothing was restored.
    expect(onView).not.toHaveBeenCalled();
  });
  it('shows missing endpoint times as unknown rather than zero seconds',()=>{
    const a=run({id:'a'}),b=run({id:'b'});a.result!.final_state.time_s=null as never;a.result!.simulated_duration_s=null as never;
    show(a,b);
    expect(screen.getByText(/接受终点 未知 s · 模拟时长 未知 s/)).toBeVisible();
  });
});
