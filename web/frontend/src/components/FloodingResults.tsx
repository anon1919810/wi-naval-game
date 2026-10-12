import { number, object, rows, type Raw } from './formModel';
import { useUnits } from './UnitProvider';
import type { Dimension } from './units';
import { formatNumber } from './units';
import { useWorkspaceCopy, type WorkspaceKey } from '../i18n/workspace';

export type { Dimension };

// Flooding result facts, read straight from the stored run payload.
//
// Nothing is recomputed here, and a partial trajectory is never presented as a
// completed one: the reported status, stop reason and the requested-versus-
// simulated time stay exactly as the kernel recorded them. Volumes, masses,
// angles and lengths follow the reader's unit; durations, densities, forces and
// conservation thresholds keep their canonical units.
//
// The status and stop-reason codes are the kernel's own; only their display
// names are looked up, and a code with no entry falls through to the code
// itself so an unrecognised result is never shown as a blank.

const STATUS_LABELS: Record<string, WorkspaceKey> = {
  completed: 'flooding.status.completed', model_limit: 'flooding.status.model_limit',
  downflooding_event: 'flooding.status.downflooding_event', equilibrium_failure: 'flooding.status.equilibrium_failure',
  canceled: 'flooding.status.canceled', invalid_input: 'flooding.status.invalid_input', running: 'flooding.status.running',
};
const STOP_LABELS: Record<string, WorkspaceKey> = {
  scheduled_completion: 'flooding.stop.scheduled_completion', equal_heads_or_no_open_flow: 'flooding.stop.equal_heads_or_no_open_flow',
  hydraulic_equilibrium_tolerance: 'flooding.stop.hydraulic_equilibrium_tolerance',
  partial_aperture: 'flooding.stop.partial_aperture', receiver_capacity: 'flooding.stop.receiver_capacity', dry_out: 'flooding.stop.dry_out',
  step_limit: 'flooding.stop.step_limit', timestep_limit: 'flooding.stop.timestep_limit',
  downflooding_event: 'flooding.stop.downflooding_event', equilibrium_failure: 'flooding.stop.equilibrium_failure',
  canceled: 'flooding.stop.canceled', invalid_input: 'flooding.stop.invalid_input',
};

function stateRow(entry: Raw) { return object(entry.equilibrium); }

export function FloodingResults({ data }: { data: Raw }) {
  const units = useUnits();
  const w = useWorkspaceCopy();
  const status = typeof data.status === 'string' ? data.status : 'unknown';
  const stop = typeof data.stop_reason === 'string' ? data.stop_reason : '';
  const scenario = object(data.scenario);
  const timeline = rows(data.timeline);
  const finalState = data.final_state === null || data.final_state === undefined ? null : object(data.final_state);
  const requested = number(scenario.duration_s);
  // Durations and step limits are canonical seconds and never rescaled.
  const simulated = finalState ? number(finalState.time_s) : null;
  const validity = object(data.validity);
  const tankIds = Object.keys(object(finalState?.volumes_m3 ?? {})).length > 0
    ? Object.keys(object(finalState?.volumes_m3)) : Object.keys(object(object(timeline[0]).volumes_m3));
  // Long trajectories stay readable: sample at most twelve accepted states and
  // say so, keeping the complete record available in the raw stage payload.
  const sample = timeline.length <= 12 ? timeline
    : Array.from({ length: 12 }, (_, index) => timeline[Math.round(index * (timeline.length - 1) / 11)]);
  const downflooding = object(data.downflooding);

  const statusKey = STATUS_LABELS[status];
  const stopKey = STOP_LABELS[stop];
  const simulatedNote = simulated === null || requested === null ? w('floodingResults.simulated.none')
    : simulated < requested ? w('floodingResults.simulated.short') : w('floodingResults.simulated.full');

  return <div className="flooding-results">
    <p className="result-context">{w('floodingResults.statusLabel')}<strong>{statusKey ? w(statusKey) : status}</strong>
      {stop && w('floodingResults.stopLabel', { label: stopKey ? w(stopKey) : stop, code: stop })}
      {/* numerical_convergence is three-state: only a real false means "did not
          converge", and null stays unknown. */}
      {validity.numerical_convergence === false && w('floodingResults.converged.no')}
      {validity.numerical_convergence === null && w('floodingResults.converged.unknown')}
      {validity.model_applicable === false && w('floodingResults.notApplicable')}
      {validity.complete === false && w('floodingResults.incomplete')}</p>
    <div className="metric-grid">
      <Datum label={w('floodingResults.requested')} text={requested === null ? w('units.unknown') : `${requested} s`} note={w('floodingResults.requested.note')} />
      <Datum label={w('floodingResults.simulated')} text={simulated === null ? w('units.unknown') : `${simulated} s`} note={simulatedNote} />
      <Datum label={w('floodingResults.volumeError')} text={units.text(data.volume_conservation_error_m3, 'volume')} note={w('floodingResults.conservation.note')} />
      <Datum label={w('floodingResults.massError')} text={units.text(data.mass_conservation_error_t, 'mass')} note={w('floodingResults.conservation.note')} />
      <Datum label={w('floodingResults.initialWater')} text={units.text(data.initial_total_water_volume_m3, 'volume')}
        note={w('floodingResults.initialWater.note', { mass: units.text(data.initial_total_water_mass_t, 'mass') })} />
      <Datum label={w('floodingResults.exchange')} text={units.text(data.cumulative_sea_exchange_m3, 'volume')}
        note={w('floodingResults.exchange.note', { mass: units.text(data.cumulative_sea_exchange_t, 'mass') })} />
      <Datum label={w('floodingResults.accepted')} text={String(timeline.length)} note={w('floodingResults.accepted.note')} />
    </div>
    {number(data.terminal_max_head_difference_m) !== null && <p className="form-hint">
      {w('floodingResults.head', { difference: units.text(data.terminal_max_head_difference_m, 'length'), tolerance: units.text(data.terminal_head_tolerance_m, 'length') })}
    </p>}
    {Object.keys(downflooding).length > 0 && <p className="form-hint">
      {w('floodingResults.downflooding', {
        status: String(downflooding.status ?? w('units.unknown')),
        event: downflooding.event
          ? w('floodingResults.downflooding.event', { value: String(object(downflooding.event).kind ?? object(downflooding.event).time_s ?? w('floodingResults.downflooding.acceptedState')) })
          : '',
      })}
      {w('floodingResults.openingsOrigin', { source: String(data.coordinator_openings_origin ?? data.openings_origin ?? w('units.unknown')) })}
    </p>}

    {sample.length > 0 && <div className="stage-table-scroll"><table className="stage-table">
      <caption>{w('floodingResults.timeline.caption', { count: timeline.length, sampled: timeline.length > 12 ? w('floodingResults.timeline.sampled') : '' })}</caption>
      <thead><tr><th>{w('floodingResults.th.time')}</th>{tankIds.map(key => <th key={key}>{key} · {units.unit('volume')}</th>)}<th>{w('floodingResults.th.totalWater', { unit: units.unit('volume') })}</th><th>{w('floodingResults.th.heel', { unit: units.unit('angle') })}</th><th>{w('floodingResults.th.trim', { unit: units.unit('angle') })}</th><th>{w('floodingResults.th.draught', { unit: units.unit('length') })}</th></tr></thead>
      <tbody>{sample.map((entry, index) => {
        const row = object(entry);
        const solved = stateRow(row);
        return <tr key={index}>
            <td>{number(row.time_s) === null ? w('units.unknown') : formatNumber(row.time_s as number)}</td>
          {tankIds.map(key => <td key={key}>{units.number(object(row.volumes_m3)[key], 'volume')}</td>)}
          <td>{units.number(row.total_onboard_water_volume_m3, 'volume')}</td>
          <td>{units.number(solved.heel_deg, 'angle')}</td>
          <td>{units.number(solved.trim_deg, 'angle')}</td>
          <td>{units.number(solved.waterline_above_keel_m, 'length')}</td>
        </tr>;
      })}</tbody></table></div>}

    {rows(object(data.remaining_gz).rows).length > 0 && <div className="stage-table-scroll"><table className="stage-table">
      <caption>{w('floodingResults.gz.caption')}</caption>
      <thead><tr><th>{w('floodingResults.gz.th.angle', { unit: units.unit('angle') })}</th><th>{w('floodingResults.gz.th.gz', { unit: units.unit('length') })}</th></tr></thead>
      <tbody>{rows(object(data.remaining_gz).rows).map((row, index) => {
        const point = object(row);
        return <tr key={index}>
          <td>{units.number(point.angle_deg, 'angle')}</td><td>{units.number(point.gz_m, 'length')}</td>
        </tr>;
      })}</tbody></table></div>}
    {rows(data.gz_snapshots).length > 1 && <p className="form-hint">{w('floodingResults.snapshots', { count: rows(data.gz_snapshots).length })}</p>}

    <p className="form-hint">{w('floodingResults.closing')}</p>
  </div>;
}

function Datum({ label, text, note }: { label: string; text: string; note: string }) {
  const w = useWorkspaceCopy();
  const known = text !== w('units.unknown');
  return <div className={`fact-field fact-field--${known ? 'known' : 'unknown'}`}>
    <span className="fact-label">{label}</span>
    <strong className="fact-value">{text}</strong>
    <span className="fact-meta">{note}</span>
  </div>;
}
