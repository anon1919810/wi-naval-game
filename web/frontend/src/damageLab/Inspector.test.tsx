import { cleanup, screen } from '@testing-library/react';
import { renderZh as render } from '../__tests__/locale';
import { afterEach, expect, it } from 'vitest';
import Inspector, { CoreEvidence } from './Inspector';
import type { Experiment, LabResult, LabState } from './types';

afterEach(cleanup);
it('plots negative GZ samples inside the chart and keeps unavailable gaps open', () => {
  const result = { simulated_duration_s: 0, assumptions: [], method_versions: {}, validity: {}, diagnostics: [],
    core_analysis: { stages: { flooding: { status: 'completed', data: { remaining_gz: { rows: [
      { angle_deg: -20, gz_m: -.2 }, { angle_deg: -10, gz_m: null },
      { angle_deg: 0, gz_m: 0 }, { angle_deg: 10, gz_m: .1 }, { angle_deg: 20, gz_m: .2 },
    ] } } } } } } as unknown as LabResult;
  render(<CoreEvidence result={result} />);
  const chart = screen.getByRole('img', { name: '最终接受状态的剩余稳性曲线' });
  expect(screen.getByText('-20°')).toBeInTheDocument();
  expect(screen.getByText('20°')).toBeInTheDocument();
  for (const point of chart.querySelectorAll('circle')) {
    expect(Number(point.getAttribute('cx'))).toBeGreaterThanOrEqual(20);
    expect(Number(point.getAttribute('cx'))).toBeLessThanOrEqual(340);
  }
  const segments = chart.querySelectorAll('polyline');
  expect(segments).toHaveLength(2);
  expect(segments[0].getAttribute('points')!.trim().split(' ')).toHaveLength(1);
  expect(segments[1].getAttribute('points')!.trim().split(' ')).toHaveLength(3);
});

const frameState = (over: Record<string, unknown> = {}) => ({
  time_s: 0, event_index: 1, ship: null, compartments: [], modules: [], crew_groups: [],
  capabilities: { shaft_power_kw: 500, known_shaft_power_subtotal_kw: 500 }, detonation_occurred: true, ...over,
});

it('explains the selected target from the record, and withholds it before the burst', () => {
  const experiment = { schema: 'plimsoll-damage-lab-experiment-1', source: 'fixture', estimate: true,
    modules: [{ id: 'engine', label: '主机', compartment_id: 'room', role: 'propulsion' }], crew_groups: [] } as unknown as Experiment;
  const result = {
    events: [{ index: 1, time_s: 0, kind: 'detonation', target_id: 'room', message: 'untrusted prose' }],
    snapshots: [frameState({generated_breaches:[{id:'fragment:wall:room:hold',area_m2:0.02}]}), frameState()],
    core_analysis: { stages: {} },
    fragmentation: {
      traces: [{ index: 3, direction: [1, 0, 0], termination: 'target', blocked_by: null,
        segments: [{ from_m: [0, 0, 0], to_m: [1, 0, 0], compartment_id: 'room', transmission: 1,
          boundary_id: 'wall:room:hold', boundary_transmission: 0.35 }],
        hits: [{ kind: 'module', id: 'engine', position_m: [1, 0, 0], exposure: 0.8 }] }],
      boundaries: [{ id: 'wall:room:hold', from_id: 'room', to_id: 'hold', position_m: [0, 0, 1], transmission: 0,
        breach_threshold: 0.1, max_breach_area_m2: 0.5, discharge_coefficient: 0.6, source: 'fixture', estimate: true,
        absorbed_exposure: 0.5, generated_area_m2: 0.02 }],
      module_exposure: { engine: 0.8 }, crew_exposure: {}, generated_breaches: [],
    },
  } as unknown as LabResult;
  const common = { experiment, state: frameState() as unknown as LabState, rooms: [], selected: 'engine',
    inspection: { kind: 'module', id: 'engine' } as const, result, onSelect: () => {} };

  const view = render(<Inspector {...common} frame={0} />);
  expect(screen.getByText('该目标为何受影响')).toBeInTheDocument();
  // The path keeps its own index, its transmission sequence and its exposure…
  expect(screen.getByText('路径 3')).toBeInTheDocument();
  expect(screen.getByText(/暴露 0\.800/)).toBeInTheDocument();
  expect(screen.getByText(/room \(0\.35\)/)).toBeInTheDocument();
  // …its boundary response is read off the record, and no event prose is used.
  expect(screen.getByText(/已记录开口/)).toBeInTheDocument();
  expect(screen.queryByText(/untrusted prose/)).toBeNull();
  view.unmount();

  // The same record at a frame the run marked pre-detonation shows none of it.
  render(<Inspector {...common} frame={0}
    result={{ ...result, snapshots: [{ ...frameState(), detonation_occurred: false }, frameState()] } as unknown as LabResult} />);
  expect(screen.getByText(/起爆之前/)).toBeInTheDocument();
  expect(screen.queryByText('路径 3')).toBeNull();
  expect(screen.queryByText(/已记录开口/)).toBeNull();
});
