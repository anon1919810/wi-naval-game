import { compareTrials, type Delta } from './comparison';
import { useLabCopy } from '../i18n/lab';
import { useLabFormat } from '../i18n/labFormat';
import type { LabRun } from './types';

/**
 * Two completed trials, side by side and read-only.
 *
 * Selecting a pair here only reads: it fetches each record through the page's own
 * read path, and it never moves the camera, replaces the active replay or
 * restores a draft. Leaving the comparison to look at a trial is a separate,
 * explicit action, and one whose revision belongs to another revision of the
 * project says so before the reader presses it.
 *
 * Everything shown comes from `compareTrials`, so the page and its tests agree on
 * one set of rules: a pair that shares no basis is refused with its reason, a
 * changed draw is never attributed to one setting, the accepted endpoints are
 * printed as recorded, and an unknown operand stays unknown.
 */

interface Props {
  /** Completed records of this project, newest first. */
  records: LabRun[];
  a: LabRun | null;
  b: LabRun | null;
  /** The revision the page is currently editing, for the view-trial warning. */
  currentRevision: number;
  /** Which side, if any, is still being read. */
  loading?: 'a' | 'b' | 'both' | null;
  viewDisabled?: boolean;
  onSelect: (side: 'a' | 'b', id: string) => void;
  /** Restores a trial through the page's existing saved-trial flow. */
  onView: (run: LabRun) => void;
}

export default function ComparisonPanel({ records, a, b, currentRevision, loading, viewDisabled, onSelect, onView }: Props) {
  const l = useLabCopy(), f = useLabFormat();
  const comparison = a?.result && b?.result ? compareTrials(a, b, l) : null;
  const delta = (value: Delta) => value === null ? l('value.unknown')
    : `${value > 0 ? '+' : ''}${Math.abs(value) > 0 && Math.abs(value) < 0.0000005 ? value.toExponential(2) : f.numeric(value, 6)}`;
  const choice = (side: 'a' | 'b', selected: LabRun | null) => (
    <label>{l(side === 'a' ? 'compare.sideA' : 'compare.sideB')}
      <select aria-label={l(side === 'a' ? 'compare.sideA' : 'compare.sideB')} value={selected?.id ?? ''}
        onChange={event => onSelect(side, event.target.value)}>
        <option value="">{l('compare.choose')}</option>
        {records.map(run => <option key={run.id} value={run.id}>
          {f.status(run.status)} · R{run.revision} · {run.id.slice(0, 8)}
        </option>)}
      </select></label>
  );
  const view = (run: LabRun) => <>
    <button type="button" data-audio="manual" onClick={() => onView(run)} disabled={viewDisabled || run.revision !== currentRevision || (!run.has_result && !run.result)}>
      {l('compare.view', { id: run.id.slice(0, 8) })}
    </button>
    {run.revision !== currentRevision && <span className="lab-note">
      {l('compare.revisionMismatch', { revision: run.revision, current: currentRevision })}
    </span>}
  </>;

  return <section className="lab-comparison">
    <span className="lab-kicker">{l('compare.uiKicker')}</span><h2>{l('compare.uiTitle')}</h2>
    <p className="lab-note">{l('compare.uiNote')}</p>
    <div className="lab-pair">{choice('a', a)}{choice('b', b)}</div>
    {loading && <p role="status" className="lab-note">{l(loading === 'both' ? 'compare.readingBoth' : loading === 'a' ? 'compare.readingA' : 'compare.readingB')}</p>}
    {a && !a.result && <p className="lab-note">{l('compare.noResult', { id: a.id.slice(0, 8) })}</p>}
    {b && !b.result && <p className="lab-note">{l('compare.noResult', { id: b.id.slice(0, 8) })}</p>}
    {comparison && <>
      <div className="lab-pair">
        <div><strong>{l('compare.sideA')}</strong><span className="lab-note">{l('compare.provenance', {
          revision: comparison.a.revision, condition: comparison.a.condition,
          endpoint: f.numeric(comparison.a.endpointTimeS, 2), simulated: f.numeric(comparison.a.simulatedDurationS, 2) })}</span>{view(a!)}</div>
        <div><strong>{l('compare.sideB')}</strong><span className="lab-note">{l('compare.provenance', {
          revision: comparison.b.revision, condition: comparison.b.condition,
          endpoint: f.numeric(comparison.b.endpointTimeS, 2), simulated: f.numeric(comparison.b.simulatedDurationS, 2) })}</span>{view(b!)}</div>
      </div>
      {comparison.reasons.map(reason => <p className="lab-error" role="alert" key={reason}>{reason}</p>)}
      {comparison.compatible && !comparison.sameEndpoint && <p role="alert" className="lab-note">{l('compare.endpointDiffers', {
        a: f.numeric(comparison.a.endpointTimeS, 2), b: f.numeric(comparison.b.endpointTimeS, 2) })}</p>}
      {comparison.uncontrolled.map(flag => <p role="status" className="lab-note" key={flag}>{flag}</p>)}

      <h3>{l('compare.changesTitle')}</h3>
      {comparison.changes.length === 0 ? <p className="lab-note">{l('compare.noChanges')}</p>
        : <table tabIndex={0} aria-label={l('compare.uiTitle')}><thead><tr><th>{l('compare.path')}</th><th>{l('compare.sideA')}</th><th>{l('compare.sideB')}</th></tr></thead>
          <tbody>{comparison.changes.map(change => <tr key={change.path}>
            <th>{change.path}</th><td>{change.from}</td><td>{change.to}</td></tr>)}</tbody></table>}

      {comparison.compatible ? <>
      <h3>{l('compare.modulesTitle')}</h3>
      {comparison.modules.length === 0 ? <p className="lab-note">{l('compare.noModules')}</p>
        : <table tabIndex={0} aria-label={l('compare.uiTitle')}><thead><tr><th>{l('compare.module')}</th><th>{l('compare.mechanical')}</th><th>{l('compare.flooding')}</th>
          <th>{l('compare.staffing')}</th><th>{l('compare.effective')}</th><th>{l('compare.power')}</th></tr></thead>
          <tbody>{comparison.modules.map(module => <tr key={module.id}>
            <th>{module.label}</th><td>{delta(module.mechanical)}</td><td>{delta(module.flooding)}</td>
            <td>{delta(module.staffing)}</td><td>{delta(module.effective)}</td><td>{delta(module.shaftPowerKw)}</td>
          </tr>)}</tbody></table>}

      <h3>{l('compare.crewTitle')}</h3>
      {comparison.crew.length === 0 ? <p className="lab-note">{l('compare.noCrew')}</p>
        : <table tabIndex={0} aria-label={l('compare.uiTitle')}><thead><tr><th>{l('compare.group')}</th><th>{l('compare.available')}</th><th>{l('compare.incapacitated')}</th>
          <th>{l('compare.dead')}</th><th>{l('compare.evacuated')}</th></tr></thead>
          <tbody>{comparison.crew.map(group => <tr key={group.id}>
            <th>{group.label}</th><td>{delta(group.available)}</td><td>{delta(group.incapacitated)}</td>
            <td>{delta(group.dead)}</td><td>{delta(group.evacuated)}</td></tr>)}</tbody></table>}

      <h3>{l('compare.shipTitle')}</h3>
      <table tabIndex={0} aria-label={l('compare.uiTitle')}><thead><tr><th>{l('compare.quantity')}</th><th>{l('compare.difference')}</th></tr></thead><tbody>
        <tr><th>{l('compare.volume')}</th><td>{delta(comparison.ship.volumeM3)}</td></tr>
        <tr><th>{l('compare.mass')}</th><td>{delta(comparison.ship.massT)}</td></tr>
        <tr><th>{l('compare.heel')}</th><td>{delta(comparison.ship.heelDeg)}</td></tr>
        <tr><th>{l('compare.trim')}</th><td>{delta(comparison.ship.trimDeg)}</td></tr>
        {comparison.breaches.map(breach => <tr key={breach.id}>
          <th>{l('compare.breach', { id: breach.id })}</th><td>{delta(breach.areaM2)}</td></tr>)}
      </tbody></table>
      </> : <p className="lab-note">{l('compare.withheld')}</p>}
    </>}
  </section>;
}
