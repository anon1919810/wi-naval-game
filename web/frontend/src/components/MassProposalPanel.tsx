import { useState } from 'react';

import { useConceptCopy, type ConceptKey } from '../i18n/concept';
import { useUnits } from './UnitProvider';
import { object, type Raw } from './formModel';
import {
  allocationProposal, conceptComponent, proposalKey, proposalsOf, type ApplyState,
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
 * A supported whole-battery allocation is one *cohort*: selecting any of its
 * pending members selects every pending member of the same declared group, and
 * deselecting it clears the group. Choosing a different model for a colliding
 * ledger item clears the complete previously chosen cohort, so a half-chosen
 * allocation can never be submitted; the server recomputes membership again and
 * never trusts the client's own cohort metadata.
 *
 * The selection is bound to one saved result's identity. A different revision,
 * condition, run, request or unsaved edit retires it *synchronously*, before the
 * new result is committed, so a checkbox can never be read as approving a
 * proposal it was not set for — including after switching A → B → A.
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
  armour: 'proposals.component.armour', fixed_armour: 'proposals.component.fixedArmour',
  // Both spellings of the auxiliary component are mapped: the generated model is
  // `concept_auxiliary.<id>`, and either the long or the short concept component
  // name then reads as the same translated component rather than as a raw key.
  auxiliary_weapons: 'proposals.component.auxiliary', auxiliary: 'proposals.component.auxiliary',
  machinery: 'proposals.component.machinery', fuel: 'proposals.component.fuel',
};

export function MassProposalPanel({ run, identity, dirty, requestChanged, apply, onApply, onRerun }: PanelProps) {
  const c = useConceptCopy();
  const units = useUnits();
  // The selection is owned by one saved-result identity *and* by the two facts
  // the identity alone does not carry: the draft's dirtiness and whether the
  // options on screen still match the run. Any change retires the whole choice.
  const ownerKey = `${identity}|${run?.id ?? ''}|${run?.request_fingerprint ?? ''}|${dirty}|${requestChanged === true}`;
  const [owned, setOwned] = useState<{ key: string; chosen: Record<string, true> }>(
    () => ({ key: ownerKey, chosen: {} }));
  const [announced, setAnnounced] = useState('');
  const selected = owned.key === ownerKey ? owned.chosen : {};
  // Retire the old approval permanently before this render commits. Masking it
  // alone would restore an old choice after switching A → B → A.
  if (owned.key !== ownerKey) {
    const had = Object.keys(owned.chosen).length > 0;
    setOwned({ key: ownerKey, chosen: {} });
    if (had) setAnnounced(c('proposals.selectionReset'));
  }

  const proposals = proposalsOf(run);
  const chosen = proposals.filter(row => selected[proposalKey(row)] === true);
  const hasCohorts = proposals.some(row => allocationProposal(row).supported);
  const busy = apply.phase === 'applying' || apply.phase === 'queueing';
  const saved = apply.phase === 'saved' || apply.phase === 'queueFailed';

  function toggle(proposal: Raw) {
    const key = proposalKey(proposal);
    const group = allocationProposal(proposal);
    setOwned(current => {
      const chosenNow = current.key === ownerKey ? current.chosen : {};
      if (chosenNow[key]) {
        const next = { ...chosenNow };
        if (group.supported) {
          // Deselecting one member clears the complete declared cohort, never a
          // partial one.
          for (const row of proposals) {
            if (allocationProposal(row).group_id === group.group_id) delete next[proposalKey(row)];
          }
          return { key: ownerKey, chosen: next };
        }
        delete next[key];
        return { key: ownerKey, chosen: next };
      }
      const next = { ...chosenNow };
      // At most one proposal per item: a physical and an empirical model may both
      // compare the same item, and choosing both is not a batch. A supported
      // cohort is one declared choice over *every* target its members recompute —
      // the declared target list, not only the rows still pending, because an
      // already-exact member of the cohort is absent from the batch while the
      // cohort still claims it. Selecting a cohort therefore claims all of those
      // targets, and any other chosen row over one of them is cleared first. A
      // chosen allocation cohort that touches a claimed target is retired in
      // full, so it is never left half-selected alongside the new choice.
      const claimed = group.supported
        ? new Set(proposals.filter(row => allocationProposal(row).group_id === group.group_id)
          .flatMap(row => [...allocationProposal(row).target_ids, String(row.item_id ?? '')]))
        : new Set<string>([String(proposal.item_id ?? '')]);
      const colliding = new Set<string>();
      for (const row of proposals) {
        const info = allocationProposal(row);
        if (info.supported && info.group_id !== group.group_id && chosenNow[proposalKey(row)]
          && (claimed.has(String(row.item_id ?? '')) || info.target_ids.some(id => claimed.has(id)))) {
          colliding.add(info.group_id);
        }
        if (claimed.has(String(row.item_id ?? ''))) delete next[proposalKey(row)];
      }
      for (const row of proposals) {
        if (colliding.has(allocationProposal(row).group_id)) delete next[proposalKey(row)];
      }
      if (group.supported) {
        // Selecting any member selects every pending member of its cohort: the
        // whole allocation is one declared choice.
        for (const row of proposals) {
          if (allocationProposal(row).group_id === group.group_id) next[proposalKey(row)] = true;
        }
        return { key: ownerKey, chosen: next };
      }
      next[key] = true;
      return { key: ownerKey, chosen: next };
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
                {allocationProposal(proposal).supported && <>
                  <div className="form-hint">{c('proposals.allocation.cohort', {
                    group: allocationProposal(proposal).group_id })}</div>
                  {allocationProposal(proposal).policy !== '' && <div className="form-hint">
                    {c('proposals.allocation.policy', { policy: allocationProposal(proposal).policy })}</div>}
                </>}
              </td>
            </tr>;
          })}</tbody>
        </table></div>
        <p className="form-hint">{c('proposals.note')} {c('proposals.onePerItem')}</p>
        {hasCohorts && <p className="form-hint">{c('proposals.allocation.hint')}</p>}
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
