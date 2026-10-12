import { useState } from 'react';
import type { Experiment, LabResult, LabState, Room, ShipState } from './types';
import type { InspectionTarget } from './narrative';
import { explainTarget } from './consequences';
import { useLabCopy } from '../i18n/lab';
import { useLabFormat } from '../i18n/labFormat';

function Comparison({ before, after, format }: {
  before: number | null | undefined; after: number | null | undefined;
  format: (n: number | null | undefined) => string;
}) {
  return <><span className="lab-before">{format(before)} <span aria-hidden="true">→</span></span><strong>{format(after)}</strong></>;
}

export default function Inspector({ experiment, state, baseline = null, rooms = [], selected, inspection, result = null, frame = 0, onSelect, onInspect }: {
  experiment: Experiment; state: LabState | null; baseline?: LabState | null; rooms?: Room[];
  selected: string; inspection?: InspectionTarget | null; onSelect: (id: string) => void; onInspect?: (target: InspectionTarget) => void;
  result?: LabResult | null; frame?: number;
}) {
  const l = useLabCopy();
  const f = useLabFormat();
  const [allCrew, setAllCrew] = useState(false);
  // With a declared detonation the mechanical figures are normalised whole
  // numbers rather than fractions; the formatter decides which, and it never
  // turns an absent value into a zero.
  const format = experiment.detonation ? (value: number | null | undefined) => value == null ? l('value.unknown') : `${f.numeric(value * 100, 2)}%` : f.percent;
  const crewDefinition = inspection?.kind === 'crew' ? experiment.crew_groups.find(c => c.id === inspection.id) : null;
  const roomId = inspection?.kind === 'compartment' ? inspection.id : crewDefinition?.compartment_id;
  // The explanation is derived per render from the saved record: changing the frame
  // or the selected target re-derives it, and the run itself is never modified.
  const explanation = result && inspection ? explainTarget(result, frame, inspection, l) : null;
  const definition = crewDefinition ? experiment.modules.find(m => m.id === crewDefinition.module_id)
    : roomId ? experiment.modules.find(m => m.id === selected && m.compartment_id === roomId)
    ?? experiment.modules.find(m => m.compartment_id === roomId) : experiment.modules.find(m => m.id === selected) ?? experiment.modules[0];
  const selectedRoom = roomId ?? definition?.compartment_id;
  const room = rooms.find(r => r.id === selectedRoom), roomState = state?.compartments.find(r => r.id === selectedRoom);
  const module = state?.modules.find(m => m.id === definition?.id);
  const initial = baseline?.modules.find(m => m.id === definition?.id);
  const groups = experiment.crew_groups.filter(g => allCrew || !selectedRoom || g.compartment_id === selectedRoom);
  return <aside className="lab-inspector" aria-label={l('panel.label')}>
    <span className="lab-kicker">{l('panel.kicker')}</span><h2>{l('panel.title')}</h2>
    <div className="lab-module-list">{experiment.modules.map(m => {
      const result = state?.modules.find(row => row.id === m.id);
      return <button key={m.id} aria-pressed={selected === m.id} onClick={() => onSelect(m.id)}>
        <span>{m.label}</span><strong>{result ? format(result.effective_availability) : l('panel.modulePending')}</strong></button>;
    })}</div>
    {selectedRoom && <section className="lab-room-summary"><span className="lab-kicker">{l('panel.roomKicker')}</span>
      <h3>{room?.label ?? selectedRoom}</h3><p className="lab-note">{l('panel.roomNote', { volume: f.numeric(roomState?.volume_m3, 2), fill: f.percent(roomState?.fill_fraction) })}</p>
    </section>}
    {definition && <section><span className="lab-kicker">{definition.role.toUpperCase()} / GAME ESTIMATE</span><h3>{definition.label}</h3>
      <p className="lab-note">{l('panel.moduleNote')}</p>
      <dl><div><dt>{l('panel.mechanical')}</dt><dd><Comparison before={initial?.mechanical_integrity} after={module?.mechanical_integrity} format={format} /></dd></div>
        <div><dt>{l('panel.flooding')}</dt><dd><Comparison before={initial?.flooding_availability} after={module?.flooding_availability} format={format} /></dd></div>
        <div><dt>{l('panel.staffing')}</dt><dd><Comparison before={initial?.staffing_availability} after={module?.staffing_availability} format={format} /></dd></div>
        <div className="lab-total"><dt>{l('panel.effective')}</dt><dd><Comparison before={initial?.effective_availability} after={module?.effective_availability} format={format} /></dd></div></dl>
      {module && <p className="lab-factor-equation">{format(module.mechanical_integrity)} × {format(module.flooding_availability)} × {format(module.staffing_availability)} = {format(module.effective_availability)}</p>}
      {/* An unrecognised cause code is left exactly as the core wrote it; only
          the three this interface knows are given a localized name. */}
      <p className="lab-note">{module?.causes.length
        ? module.causes.map(c => l(`panel.cause.${c}` as 'panel.cause.localized_game_impact')).join(' / ')
        : state ? l('panel.cause.none') : l('panel.cause.pending')}{module?.staffing_availability === 0 ? l('panel.cause.noDuty') : ''}</p>
    </section>}
    <section><span className="lab-kicker">{l('panel.crewKicker')}</span><h3>{l('panel.crewTitle')}</h3>
      <label className="lab-check"><input type="checkbox" checked={allCrew} onChange={e => setAllCrew(e.target.checked)} />{l('panel.allCrew')}</label>
      {!groups.length && <p className="lab-note">{l('panel.crewEmpty')}</p>}
      {groups.map(group => {
        const crew = state?.crew_groups.find(c => c.id === group.id);
        const before = baseline?.crew_groups.find(c => c.id === group.id);
        const count = (n: number | null | undefined) => f.numeric(n, 0);
        return <div className="lab-crew" key={group.id} data-selected={inspection?.kind === 'crew' && inspection.id === group.id ? 'true' : undefined}>
          <button className="lab-crew-select" aria-pressed={inspection?.kind === 'crew' && inspection.id === group.id} onClick={() => onInspect?.({ kind: 'crew', id: group.id })}>{group.label} <span aria-hidden="true">→</span></button>
          <dl>{([['available', 'panel.crew.available'], ['incapacitated', 'panel.crew.incapacitated'], ['dead', 'panel.crew.dead'], ['evacuated', 'panel.crew.evacuated']] as const).map(([key, label]) =>
            <div key={key}><dt>{l(label)}</dt><dd><Comparison before={before?.[key]} after={crew?.[key]} format={count} /></dd></div>)}</dl>
          <p className="lab-note">{crew?.evacuation_triggered ? l('panel.crew.evacuatedNote') : l('panel.crew.input', { compartment: group.compartment_id, count: f.numeric(group.personnel, 0) })}</p></div>;
      })}
    </section>
    <section><span className="lab-kicker">{l('panel.powerKicker')}</span><h3>{l('panel.powerTitle')}</h3>
      <p className="lab-power">{f.numeric(state?.capabilities.shaft_power_kw, 0)} <small>kW</small></p>
      {baseline && <p className="lab-note">{l('panel.powerChange', { before: f.numeric(baseline.capabilities.shaft_power_kw, 0), after: f.numeric(state?.capabilities.shaft_power_kw, 0) })}</p>}
      {state?.capabilities.shaft_power_kw == null && <p className="lab-note">{l('panel.powerUnknown', { subtotal: f.numeric(state?.capabilities.known_shaft_power_subtotal_kw, 0) })}</p>}
    </section>
    {explanation && <section><span className="lab-kicker">{l('explain.kicker')}</span><h3>{l('explain.title')}</h3>
      <p className="lab-note">{l('explain.note')}</p>
      {/* Every note is a refusal or a limit of the record, so it sits with the
          findings rather than being folded away. */}
      {explanation.notes.map(note => <p className="lab-note" key={note}>{note}</p>)}
      {explanation.paths.length > 0 && <>
        <h4>{l('explain.pathsTitle')}</h4>
        <ol>{explanation.paths.map(path => <li key={path.index}>
          <strong>{l('explain.pathLabel', { index: path.index })}</strong>
          <span className="lab-note"> {l('explain.exposure', { value: f.numeric(path.exposure, 3) })}</span>
          <p className="lab-note">{path.sequence}{path.blockedBy ? ` · ${l('explain.blockedBy', { boundary: path.blockedBy })}` : ''}</p>
        </li>)}</ol></>}
      {explanation.boundaries.length > 0 && <>
        <h4>{l('explain.boundariesTitle')}</h4>
        <ul>{explanation.boundaries.map(boundary => <li key={boundary.id}>
          <strong>{boundary.id}</strong>
          <span className="lab-note"> {l(boundary.state === 'generated' ? 'explain.state.generated'
            : boundary.state === 'deferred' ? 'explain.state.deferred'
              : boundary.state === 'sealed' ? 'explain.state.sealed' : 'explain.state.unknown')}</span>
          <p className="lab-note">{l('explain.load', { absorbed: f.numeric(boundary.absorbedExposure, 3),
            threshold: f.numeric(boundary.threshold, 3), area: f.numeric(boundary.generatedAreaM2, 4) })}</p>
        </li>)}</ul></>}
      {explanation.factors.length > 0 && <>
        <h4>{l('explain.factorsTitle')}</h4>
        <dl>{explanation.factors.map(factor => <div key={factor.kind}>
          <dt>{l(factor.kind === 'mechanical' ? 'compare.mechanical' : factor.kind === 'flooding' ? 'compare.flooding' : 'compare.staffing')}</dt>
          <dd>{f.numeric(factor.value, 3)}
            {factor.firstEventIndex !== null && <span className="lab-note"> {l('explain.firstEvent', {
              event: factor.firstEventIndex, time: f.numeric(factor.firstEventTimeS, 2) })}</span>}
          </dd></div>)}</dl></>}
      {explanation.flows.length > 0 && <>
        <h4>{l('explain.flowsTitle')}</h4>
        <ul>{explanation.flows.map((flow, index) => <li className="lab-note" key={`${flow.id ?? flow.from}-${flow.to}-${index}`}>{l('explain.flowRow', {
          from: flow.from, to: flow.to, transfer: f.numeric(flow.transferM3, 4), mass: f.numeric(flow.massFlowTS, 4), volume: f.numeric(flow.flowM3S, 4) })}</li>)}</ul></>}
      {explanation.hydraulic.heelDeg !== null && <>
        <h4>{l('explain.endpointTitle')}</h4>
        <p className="lab-note">{l('compare.heel')} {f.numeric(explanation.hydraulic.heelDeg, 2)} · {l('compare.trim')} {f.numeric(explanation.hydraulic.trimDeg, 2)}</p></>}
    </section>}
  </aside>;
}

export function ShipMetrics({ state, baseline }: { state: LabState | null; baseline: ShipState | null }) {
  const l = useLabCopy();
  const f = useLabFormat();
  const ship = state?.ship;
  const reference = ship ? baseline : null;
  return <div className="lab-ship-metrics" aria-label={l('ship.label')}>
    <div><span>{l('ship.water')}</span><strong>{f.numeric(ship?.total_onboard_water_mass_t)} <small>t</small></strong>
      <p className="lab-note">{l('ship.firstSolution')} {f.numeric(reference?.total_onboard_water_mass_t)} t</p></div>
    <div><span>{l('ship.heel')}</span><strong>{f.numeric(ship?.equilibrium.heel_deg, 2)} <small>°</small></strong>
      <p className="lab-note">{l('ship.firstSolution')} {f.numeric(reference?.equilibrium.heel_deg, 2)}°</p></div>
    <div><span>{l('ship.trim')}</span><strong>{f.numeric(ship?.equilibrium.trim_deg, 2)} <small>°</small></strong>
      <p className="lab-note">{l('ship.firstSolution')} {f.numeric(reference?.equilibrium.trim_deg, 2)}°</p></div>
    <div><span>{l('ship.residual')}</span><strong>{ship ? ship.mass_conservation_error_t.toExponential(1) : l('value.unknown')} <small>t</small></strong>
      <p className="lab-note">{l('ship.coreState')}</p></div>
  </div>;
}

export function CoreEvidence({ result }: { result: LabResult }) {
  const l = useLabCopy();
  const f = useLabFormat();
  const stage = result.core_analysis.stages.flooding;
  const native = stage.data;
  const remaining = native?.remaining_gz as { rows?: Array<{ angle_deg: number; gz_m: number | null }>; converged?: boolean } | null;
  const rows = remaining?.rows ?? [], segments: Array<Array<{ angle_deg: number; gz_m: number }>> = [];
  let segment: Array<{ angle_deg: number; gz_m: number }> = [];
  for (const row of rows) {
    if (Number.isFinite(row.angle_deg) && row.gz_m != null && Number.isFinite(row.gz_m)) {
      if (!segment.length) segments.push(segment); segment.push({ angle_deg: row.angle_deg, gz_m: row.gz_m });
    } else segment = [];
  }
  const points = segments.flat(), angles = rows.map(p => p.angle_deg).filter(Number.isFinite);
  const xMin = angles.length ? Math.min(...angles) : 0, xMax = angles.length ? Math.max(...angles) : 0;
  const yMin = Math.min(0, ...points.map(p => p.gz_m)), yMax = Math.max(.1, ...points.map(p => p.gz_m));
  const x = (angle: number) => xMax === xMin ? 180 : 20 + (angle - xMin) / (xMax - xMin) * 320;
  const y = (gz: number) => 100 - (gz - yMin) / (yMax - yMin) * 80;
  const xy = (p: { angle_deg: number; gz_m: number }) => `${x(p.angle_deg)},${y(p.gz_m)}`;
  return <section className="lab-evidence" aria-label={l('evidence.label')}>
    <div><span className="lab-kicker">{l('evidence.kicker')}</span><h2>{l('evidence.title')}</h2>
      {/* The stop reason is the core's own saved token, printed verbatim; the
          sentence around it is what this interface owns. */}
      <p>{l('evidence.stop', { reason: String(native?.stop_reason ?? stage.reason ?? stage.status), duration: f.numeric(result.simulated_duration_s, 2) })}</p>
      <p className="lab-note">{l('evidence.note')}</p>
      <details><summary>{l('evidence.details')}</summary>
        <p>{result.assumptions.join(' · ')}</p>
        <pre>{JSON.stringify({ method_versions: result.method_versions, validity: result.validity, diagnostics: result.diagnostics }, null, 2)}</pre>
      </details></div>
    <div><span className="lab-kicker">{l('evidence.remainingKicker')}</span>
      {points.length ? <><svg viewBox="0 0 360 125" role="img" aria-label={l('evidence.remainingLabel')}>
        <path d={`M20 15V100H340 M20 ${y(0)}H340`} fill="none" stroke="currentColor" opacity=".3" />
        {xMin <= 0 && xMax >= 0 && <path d={`M${x(0)} 15V100`} fill="none" stroke="currentColor" opacity=".3" />}
        {segments.map((part, i) => <polyline key={i} points={part.map(xy).join(' ')} fill="none" stroke="var(--accent)" strokeWidth="2" />)}
        {points.map(p => <circle key={p.angle_deg} cx={x(p.angle_deg)} cy={y(p.gz_m)} r="3" fill="var(--accent)" />)}
        <text x="20" y="120">{xMin}°</text><text x="340" y="120" textAnchor="end">{xMax}°</text><text x="25" y="15">GZ / m</text></svg>
        <p className="lab-note">{l('evidence.remainingNote')}</p></> : <p>{l('evidence.remainingUnavailable')}</p>}
    </div>
  </section>;
}