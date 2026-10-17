import { useConceptCopy } from '../i18n/concept';
import { object, type Raw } from './formModel';
import {
  allocationLayoutIds, batteryLayouts, batteryMassAllocationEnabled, batteryMassAllocationOf,
  invalidAllocationLayoutIds, newBatteryMassAllocation, patchBatteryMassAllocation,
  removeBatteryMassAllocation,
} from './conceptDesign';

/**
 * The optional whole-battery mount allocation, declared as ordinary inputs.
 *
 * This is a *declaration of scope* and nothing else: one source text and an
 * explicit selection of two-group layouts. It computes no mass, offers no ledger
 * target and has no adoption path — the source total and the per-row allocations
 * are the server's own readings, printed elsewhere beside their own method.
 *
 * The selection is deliberately three-valued. `null` is an unknown selection and
 * is not the same fact as an explicit empty array, which declares a known zero
 * scope; no layout is ever chosen for the reader. A selected id that no longer
 * names exactly one declared layout is a dangling reference and is named
 * precisely rather than silently cleared, because which reference goes is the
 * reader's decision and not this screen's.
 */

interface BatteryMassAllocationPanelProps {
  config: Raw;
  commit: (next: Raw) => void;
}

export function BatteryMassAllocationPanel({ config, commit }: BatteryMassAllocationPanelProps) {
  const c = useConceptCopy();
  const section = batteryMassAllocationOf(config);
  const enabled = batteryMassAllocationEnabled(config);
  const ids = allocationLayoutIds(config);
  const layouts = batteryLayouts(config)
    .map((layout, index) => ({ id: typeof layout.id === 'string' ? layout.id : '', index }))
    .filter(layout => layout.id !== '');
  const invalid = invalidAllocationLayoutIds(config);
  // A null selection is unknown: an empty array is the only explicit "nothing".
  const known = ids !== null;

  function patch(next: Raw) { commit(patchBatteryMassAllocation(config, next)); }

  function toggle(id: string) {
    if (ids === null) return;
    patch({ layout_ids: ids.includes(id) ? ids.filter(item => item !== id) : [...ids, id] });
  }

  return <div className="form-card">
    <h3>{c('concept.group.batteryAllocation')}</h3>
    <label className="field-label">
      <input type="checkbox" aria-label={c('concept.batteryAllocation.use')} checked={enabled}
        onChange={event => commit(event.target.checked
          ? { ...config, battery_mass_allocation: newBatteryMassAllocation() }
          : removeBatteryMassAllocation(config))} />
      {enabled ? c('concept.on') : c('concept.off')}
    </label>
    <p className="form-hint">{c('concept.batteryAllocation.note')}</p>
    {!enabled ? null : <>
      <div className="form-grid">
        <label className="field-label">{c('concept.batteryAllocation.source')}
          <input aria-label={c('concept.batteryAllocation.source')}
            value={typeof object(section).source === 'string' ? String(object(section).source) : ''}
            placeholder={c('concept.source.placeholder')}
            onChange={event => patch({
              source: event.target.value.trim() === '' ? null : event.target.value })} />
          <small>{c('concept.batteryAllocation.sourceHint')}</small>
        </label>
      </div>
      <p className="form-hint">{c('concept.batteryAllocation.policy')}</p>
      <label className="field-label">
        <input type="checkbox" aria-label={c('concept.batteryAllocation.scopeKnown')} checked={known}
          onChange={event => patch({ layout_ids: event.target.checked ? [] : null })} />
        {c('concept.batteryAllocation.scopeKnown')}
      </label>
      <p className="form-hint">{c(known
        ? 'concept.batteryAllocation.scopeEmptyHint' : 'concept.batteryAllocation.scopeUnknown')}</p>
      {known ? <>
        <h4>{c('concept.batteryAllocation.layouts')}</h4>
        {layouts.length === 0
          ? <p className="form-hint">{c('concept.batteryAllocation.noLayouts')}</p>
          : <div className="metric-grid">{layouts.map(layout => <label
            className="field-label field-label--inline" key={`${layout.id}-${layout.index}`}>
            <input type="checkbox"
              aria-label={`${layout.id} ${c('concept.batteryAllocation.layouts')}`}
              checked={ids.includes(layout.id)} onChange={() => toggle(layout.id)} />
            {layout.id}
          </label>)}</div>}
        {invalid.length > 0 ? <p className="form-error" role="alert">
          {c('concept.batteryAllocation.invalid')} {invalid.join(', ')}</p> : null}
        <p className="form-hint">{c('concept.batteryAllocation.separate')}</p>
        <p className="form-hint">{c('concept.batteryAllocation.reference')}</p>
      </> : null}
    </>}
  </div>;
}
