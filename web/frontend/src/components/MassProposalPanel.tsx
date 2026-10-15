import { useEffect, useState } from 'react';

import { useConceptCopy, type ConceptKey } from '../i18n/concept';
import { useUnits } from './UnitProvider';
import { object, type Raw } from './formModel';
import {
  conceptComponent, proposalKey, proposalsOf, type ApplyState,
} from './conceptDesign';
import type { RunView } from '../types';

/**
 * The reviewed batch, presented as one explicit choice.
 *
 * Nothing here applies anything by itself and nothing is selected for the
 * reader. The panel shows, per estimate, the current ledger mass, the estimate,
 * the difference, and where the number came from — its method, its declared
 * source and the boundary of the method that produced it — because an estimate
 * a reader cannot place is an estimate they should not accept.
 *
 * The selection is bound to one saved result's identity. A different revision,
 * condition or run retires it, because a checkbox that survives into a new
 * result is a checkbox approving something it was never set for.
 */

interface PanelProps {
  run: RunView | null;
  /** Identity of the result the selection belongs to; '' when there is none. */
  identity: string;
  /** The draft has edits the saved result does not describe. */
  dirty: boolean;
  requestChanged?: boolean;
  apply: ApplyState;
  onApply: (proposals: Raw[]) => void;
  onRerun: () => void;
}

const COMPONENT_KEYS: Readonly<Record<string, ConceptKey>> = {
  structure: 'proposals.component.structure', guns: 'proposals.component.guns',
  mounts: 'proposals.component.mounts', ammunition: 'proposals.component.ammunition',
  armour: 'proposals.component.armour',
  machinery: 'proposals.component.machinery', fuel: 'proposals.component.fuel',
};

export function MassProposalPanel({ run, identity, dirty, requestChanged, apply, onApply, onRerun }: PanelProps) {
  const c = useConceptCopy();
  const units = useUnits();
  const [selected, setSelected] = useState<Record<string, true>>({});
  const [announced, setAnnounced] = useState('');

  // A different result is a different set of proposals. The selection goes with
  // the result, and the reader is told it went rather than left wondering why a
  // button is disabled.
  useEffect(() => {
    setSelected(previous => Object.keys(previous).length === 0 ? previous : (setAnnounced(c('proposals.selectionReset')), {}));
  }, [identity, c]);

  const proposals = proposalsOf(run);
  const chosen = proposals.filter(row => selected[proposalKey(row)] === true);
  const busy = apply.phase === 'applying' || apply.phase === 'queueing';
  const saved = apply.phase === 'saved' || apply.phase === 'queueFailed';

  function toggle(proposal: Raw) {
    const key = proposalKey(proposal);
    setSelected(previous => {
      if (previous[key]) {
        const next = { ...previous };
        delete next[key];
        return next;
      }
      // At most one proposal per item: a physical and an empirical model may
      // both compare the same item, and choosing both is not a batch.
      const next = { ...previous };
      for (const row of proposals) if (row.item_id === proposal.item_id) delete next[proposalKey(row)];
      return { ...next, [key]: true };
    });
  }

  return <section className="form-card concept-proposals">
    <h3>{c('proposals.title')}</h3>
    <p>{c('proposals.intro')}</p>
    <p className="form-hint">{c('proposals.order')}</p>
    {announced && <p className="form-hint" role="status">{announced}</p>}

    {saved && <div className="notice" role="status">
      {apply.phase === 'saved'
        ? c('proposals.saved', { revision: String(apply.revision ?? '') })
        : c('proposals.queueFailed', { revision: String(apply.revision ?? ''), reason: apply.reason ?? '' })}
      {apply.phase === 'queueFailed' && <div className="notice-actions">
        <button className="button button--secondary" type="button" onClick={onRerun}>{c('proposals.rerun')}</button>
      </div>}
    </div>}
    {apply.phase === 'failed' && <div className="notice notice--error" role="alert">
      {c('proposals.failed', { reason: apply.reason ?? '' })}</div>}
    {apply.phase === 'conflict' && <div className="notice notice--conflict" role="alert">
      {c('proposals.conflict', { revision: String(apply.revision ?? '') })}</div>}

    {dirty ? <p className="form-hint">{c('proposals.emptyDirty')}</p>
      : requestChanged ? <p className="form-hint">{c('proposals.requestChanged')}</p>
      : proposals.length === 0 ? <p className="section-intro">{c('proposals.empty')}</p> : <>
        <div className="stage-table-scroll"><table className="stage-table">
          <caption>{c('proposals.title')}</caption>
          <thead><tr>
            <th>{c('proposals.select')}</th>
            <th>{c('proposals.col.item')}</th>
            <th>{c('proposals.col.component')}</th>
            <th>{c('proposals.col.current')}</th>
            <th>{c('proposals.col.estimate')}</th>
            <th>{c('proposals.col.delta')}</th>
            <th>{c('proposals.col.method')}</th>
          </tr></thead>
          <tbody>{proposals.map(proposal => {
            const key = proposalKey(proposal);
            const component = conceptComponent(proposal);
            const model = object(proposal.model);
            const source = object(model.source);
            const declaration = typeof source.source === 'string' ? source.source
              : typeof source.declaration === 'string' ? source.declaration
              : typeof source.model_source === 'string' ? source.model_source : '';
            const currentMass = proposal.current_mass_t;
            return <tr key={key}>
              <td><input type="checkbox" aria-label={`${String(proposal.item_id)} ${c('proposals.select')}`}
                checked={selected[key] === true} disabled={busy}
                onChange={() => toggle(proposal)} /></td>
              <td>{String(proposal.item_id ?? '')}</td>
              <td>{COMPONENT_KEYS[component] ? c(COMPONENT_KEYS[component]) : (component || '—')}</td>
              <td>{currentMass === null || currentMass === undefined
                ? c('proposals.unknownMass') : units.text(currentMass, 'mass')}</td>
              <td>{units.text(proposal.proposed_mass_t, 'mass')}</td>
              <td>{proposal.difference_t === null || proposal.difference_t === undefined
                ? c('proposals.unknownMass') : units.text(proposal.difference_t, 'mass')}</td>
              <td>
                <div>{String(proposal.source_model_id ?? '')}</div>
                <div>{String(model.method ?? '')}{typeof source.method_version === 'string' ? ` · ${source.method_version}` : ''}</div>
                <div className="form-hint">{c('proposals.underlying', {
                  system: String(proposal.source_system_id ?? ''), model: String(proposal.source_model_id ?? '') })}</div>
                {declaration !== '' && <div className="form-hint">{declaration}</div>}
                {typeof model.boundary === 'string' && model.boundary !== '' &&
                  <div className="form-hint">{c('proposals.boundary')}: {model.boundary}</div>}
                {typeof model.capacity_estimate_t === 'number' &&
                  <div className="form-hint">{units.text(model.capacity_estimate_t, 'mass')} · {c('proposals.capacityNote')}</div>}
                {typeof model.note === 'string' && model.note !== '' &&
                  <div className="form-hint">{model.note}</div>}
              </td>
            </tr>;
          })}</tbody>
        </table></div>
        <p className="form-hint">{c('proposals.note')} {c('proposals.onePerItem')}</p>
        <p className="form-hint" role="status">{c('proposals.selected', { count: chosen.length })}</p>
        <button className="button button--primary" type="button" disabled={busy || chosen.length === 0}
          onClick={() => onApply(chosen)}
          title={chosen.length === 0 ? c('proposals.applyNeedsSelection') : undefined}>
          {busy ? c('proposals.applyBusy') : c('proposals.apply')}
        </button>
        {dirty && <p className="form-hint">{c('proposals.applyBlocked')}</p>}
      </>}
  </section>;
}
