import { useRef, useState } from 'react';

import { useConceptCopy, type ConceptKey } from '../i18n/concept';
import { QuantityField } from './QuantityField';
import { ledgerItems, number, object, stringList, type Raw } from './formModel';
import { systemLeaves } from './massModels';
import { DeclaredNumber, ItemSelect } from './declaredInputs';
import {
  armourGeometryReferences,
  claimedTargetIds, changeFixedArmourKind, costEnabled, costOf, duplicateFixedArmourIds,
  duplicateTargets, fixedArmour, fixedArmourIdValid, fixedArmourRole, fixedArmourTargetConflicts,
  FIXED_ARMOUR_ALL_FIELDS, FIXED_ARMOUR_COVERAGE_KEYS,
  FIXED_ARMOUR_KINDS, FIXED_ARMOUR_KIND_LABELS, FIXED_ARMOUR_PLATE_KINDS, fixedArmourKind,
  MAX_FIXED_ARMOUR_RECORDS, newCost, newFixedArmour, patchCost, patchFixedArmour,
  removeCost, removeFixedArmour, replaceFixedArmour,
} from './conceptDesign';
import type { ProjectDocument } from '../types';

/**
 * The optional fixed (non-rotating) armour regions, declared as ordinary inputs.
 *
 * The recovered original held seven fixed regions and this editor refuses to
 * merge them: each record names one of the seven, carries its own identifier,
 * its own editable source and its own owned ledger target, and declares only the
 * fields that region actually has. A belt's declared extents are not a conning
 * tower's height, so switching kind drops what the new region does not have
 * instead of carrying a number across.
 *
 * It computes nothing. The recovered `weightBeltMainCalc` … `weightConningCalc`
 * expressions, the recovered seven-way deck switch and the original's own
 * `INCH = 0.0185` long-ton constant all live in the core; the readings arrive in
 * the saved result and are printed by `ConceptComponentReadings`. Every number
 * here is therefore a *declaration*, an empty input stays an explicit unknown
 * rather than a plausible zero, and nothing is adopted into a weight.
 */

interface FixedArmourEditorProps {
  project: ProjectDocument;
  config: Raw;
  commit: (next: Raw) => void;
}

const PLATE_FIELDS = new Set<string>(FIXED_ARMOUR_PLATE_KINDS);

/**
 * One declared region, with its identity, its binding and its own geometry.
 *
 * Every binding offered here is an item the chosen system already links, minus
 * everything another component already claims — a battery row's guns, a
 * layout's complete two-group armour, the balance's own adjustable structure
 * item and the other fixed regions alike. One ledger item carries one component's
 * mass, so a refused choice is shown as refused rather than offered as a default.
 */
function FixedArmourRecord({ project, config, index, commit }: {
  project: ProjectDocument; config: Raw; index: number; commit: (next: Raw) => void;
}) {
  const c = useConceptCopy();
  const [blocked, setBlocked] = useState(false);
  const record = fixedArmour(config)[index];
  if (!record) return null;
  const kind = fixedArmourKind(record.kind);
  const leaves = systemLeaves(project.systems);
  const itemById = new Map(ledgerItems(project).map(item => [item.id, item]));
  const leaf = leaves.find(entry => entry.id === record.system_id);
  // Every component's claim, including this region's own binding, so the picker
  // offers only what nothing else holds. The record's own current binding is put
  // back below, because editing another input must never silently drop a binding
  // the reader already made — even before a kind, and therefore a role, exists.
  const claimed = new Set(claimedTargetIds(config));
  const mine = record.item_id;
  const owned = stringList(leaf?.leaf.weight_item_ids)
    .map(id => itemById.get(id))
    .filter((item): item is { id: string; label: string } => item !== undefined)
    .filter(item => item.id === mine || !claimed.has(item.id));
  const duplicated = new Set(duplicateFixedArmourIds(config));
  const conflicts = new Set(fixedArmourTargetConflicts(config));
  const id = typeof record.id === 'string' ? record.id : '';
  const role = fixedArmourRole(record);
  // A region the geometric panels select cannot be deleted, renamed or given a
  // different kind: any of those would leave the geometry pointing at nothing or
  // at a kind it does not accept. The refusal is precise and the reader is told
  // where to clear the reference — nothing is unlinked or moved for them.
  const linked = new Set(armourGeometryReferences(config));
  const referenced = id !== '' && linked.has(id);

  function patch(patchValue: Raw) { commit(patchFixedArmour(config, index, patchValue)); }

  const thickness = <QuantityField key="thickness"
    label={kind === 'conning' ? c('concept.fixedArmour.foreThickness') : c('concept.fixedArmour.thickness')}
    ariaLabel={kind === 'conning' ? c('concept.fixedArmour.foreThickness') : c('concept.fixedArmour.thickness')}
    dimension="length" storedUnit="mm" kind="nonnegative" value={number(record.thickness_mm)}
    hint={c('concept.fixedArmour.thicknessHint')} onChange={next => patch({ thickness_mm: next })} />;

  return <div className="form-card">
    <div className="form-grid">
      <label className="field-label">{c('concept.fixedArmour.id')}
        <input aria-label={c('concept.fixedArmour.id')} value={id}
          onChange={event => {
            const next = event.target.value;
            // A linked region keeps its identifier: renaming it would leave the
            // geometry pointing at nothing. Clear the reference there first.
            if (referenced && next !== id) { setBlocked(true); return; }
            setBlocked(false);
            patch({ id: next });
          }} />
        <small>{c('concept.fixedArmour.idHint')}</small>
      </label>
      <label className="field-label">{c('concept.fixedArmour.source')}
        <input aria-label={c('concept.fixedArmour.source')}
          value={typeof record.source === 'string' ? record.source : ''}
          placeholder={c('concept.source.placeholder')}
          onChange={event => patch({ source: event.target.value.trim() === '' ? '' : event.target.value })} />
        <small>{c('concept.fixedArmour.sourceHint')}</small>
      </label>
      <label className="field-label">{c('concept.fixedArmour.kind')}
        <select aria-label={c('concept.fixedArmour.kind')} value={kind ?? ''}
          onChange={event => {
            // A linked region keeps its kind: the geometry accepts only some
            // kinds, so switching away would make its own reference invalid.
            if (referenced) { setBlocked(true); return; }
            setBlocked(false);
            const next = fixedArmourKind(event.target.value);
            // An undeclared kind is not a region: it keeps the declaration's
            // identity and drops every field no kind claims. This *replaces* the
            // record rather than merging into it, because a merge would bring the
            // previous kind's geometry back.
            commit(next === null
              ? replaceFixedArmour(config, index, { id, kind: null, system_id: record.system_id ?? null,
                item_id: record.item_id ?? null, source: record.source ?? '', ...withoutFields() })
              : replaceFixedArmour(config, index, changeFixedArmourKind(record, next)));
          }}>
          <option value="">{c('concept.fixedArmour.kindUnknown')}</option>
          {FIXED_ARMOUR_KINDS.map(name => <option key={name} value={name}>
            {c(FIXED_ARMOUR_KIND_LABELS[name])}
          </option>)}
        </select>
        <small>{c('concept.fixedArmour.kindHint')}</small>
      </label>
      <ItemSelect label={c('concept.fixedArmour.system')} ariaLabel={c('concept.fixedArmour.system')}
        value={record.system_id} options={leaves.map(entry => ({ id: entry.id, label: entry.id }))}
        hint={c('concept.fixedArmour.systemHint')}
        onChange={next => patch({
          system_id: next,
          // The new owner may not link the old binding, so it is cleared rather
          // than carried into a system that does not hold it. No mass is invented.
          item_id: null,
        })} />
      <ItemSelect label={c('concept.fixedArmour.item')} ariaLabel={c('concept.fixedArmour.item')}
        value={record.item_id} options={owned} hint={c('concept.fixedArmour.bindingHint')}
        onChange={next => patch({ item_id: next })} />
    </div>

    {leaf === undefined && record.system_id !== null && record.system_id !== undefined
      ? <p className="form-hint">{c('concept.fixedArmour.unownedHint')}</p> : null}
    {role === null ? null : <p className="form-hint">{c('concept.fixedArmour.roleHint')}
      {' '}{c(`concept.role.${role}` as ConceptKey)}</p>}
    {duplicated.has(id) && id !== '' ? <p className="form-error" role="alert">
      {c('concept.fixedArmour.duplicateId', { id })}</p> : null}
    {!fixedArmourIdValid(record.id) ? <p className="form-error" role="alert">
      {c('concept.fixedArmour.invalidId')}</p> : null}
    {typeof record.item_id === 'string' && conflicts.has(record.item_id)
      ? <p className="form-error" role="alert">
        {c('concept.fixedArmour.targetConflict', { item: record.item_id })}</p> : null}

    {kind === null ? null : <div className="form-grid">
      {PLATE_FIELDS.has(kind) ? <>
        {thickness}
        <QuantityField label={c('concept.fixedArmour.length')} ariaLabel={c('concept.fixedArmour.length')}
          dimension="length" storedUnit="m" kind="nonnegative" value={number(record.length_m)}
          hint={c('concept.fixedArmour.lengthHint')}
          onChange={next => patch({ length_m: next })} />
        <QuantityField label={c('concept.fixedArmour.height')} ariaLabel={c('concept.fixedArmour.height')}
          dimension="length" storedUnit="m" kind="nonnegative" value={number(record.height_m)}
          hint={c('concept.fixedArmour.heightHint')}
          onChange={next => patch({ height_m: next })} />
      </> : kind === 'deck' ? <>
        {thickness}
        <label className="field-label">{c('concept.fixedArmour.coverage')}
          <select aria-label={c('concept.fixedArmour.coverage')}
            value={typeof record.coverage_index === 'number' ? String(record.coverage_index) : ''}
            onChange={event => patch({ coverage_index: event.target.value === ''
              ? null : Number(event.target.value) })}>
            <option value="">{c('concept.fixedArmour.kindUnknown')}</option>
            {FIXED_ARMOUR_COVERAGE_KEYS.map((name, selector) =>
              <option key={selector} value={selector}>{c(name)}</option>)}
          </select>
          <small>{c('concept.fixedArmour.coverageHint')}</small>
        </label>
        <DeclaredNumber label={c('concept.fixedArmour.forecastleFraction')} kind="nonnegative" min={0} max={1}
          value={record.forecastle_fraction} hint={c('concept.fixedArmour.fractionHint')}
          onChange={next => patch({ forecastle_fraction: next })} />
        <DeclaredNumber label={c('concept.fixedArmour.quarterdeckFraction')} kind="nonnegative" min={0} max={1}
          value={record.quarterdeck_fraction} hint={c('concept.fixedArmour.fractionHint')}
          onChange={next => patch({ quarterdeck_fraction: next })} />
        <QuantityField label={c('concept.fixedArmour.forecastleThickness')}
          ariaLabel={c('concept.fixedArmour.forecastleThickness')}
          dimension="length" storedUnit="mm" kind="nonnegative" value={number(record.forecastle_mm)}
          hint={c('concept.fixedArmour.thicknessHint')}
          onChange={next => patch({ forecastle_mm: next })} />
        <QuantityField label={c('concept.fixedArmour.quarterdeckThickness')}
          ariaLabel={c('concept.fixedArmour.quarterdeckThickness')}
          dimension="length" storedUnit="mm" kind="nonnegative" value={number(record.quarterdeck_mm)}
          hint={c('concept.fixedArmour.thicknessHint')}
          onChange={next => patch({ quarterdeck_mm: next })} />
      </> : <>
        {thickness}
        <QuantityField label={c('concept.fixedArmour.aftThickness')}
          ariaLabel={c('concept.fixedArmour.aftThickness')}
          dimension="length" storedUnit="mm" kind="nonnegative" value={number(record.aft_mm)}
          hint={c('concept.fixedArmour.thicknessHint')}
          onChange={next => patch({ aft_mm: next })} />
      </>}
    </div>}
    {kind === 'belt_ends' || kind === 'bulkhead' || kind === 'bulge'
      ? <p className="form-hint">{c('concept.fixedArmour.bulkheadHint')}</p> : null}
    {kind === 'conning' ? <p className="form-hint">{c('concept.fixedArmour.conningHint')}</p> : null}
    <p className="form-hint">{c('concept.fixedArmour.separate')}</p>
    {referenced ? <p className="form-hint">{c('concept.armourGeometry.linkProtect')}</p> : null}
    {blocked ? <p className="form-error" role="alert">
      {c('concept.armourGeometry.linkProtect')}</p> : null}
    <button className="text-button" type="button"
      onClick={() => {
        if (referenced) { setBlocked(true); return; }
        setBlocked(false);
        commit(removeFixedArmour(config, index));
      }}>
      {c('concept.fixedArmour.remove')}
    </button>
  </div>;
}

/** Every declared engineering field of one record, set to unknown. */
function withoutFields(): Raw {
  const next: Raw = {};
  for (const field of FIXED_ARMOUR_ALL_FIELDS) next[field] = null;
  return next;
}

/**
 * The optional empirical cost reading: an explicit on/off and a source.
 *
 * Nothing else. There is no ledger target, no mass, no proposal and no adoption
 * control here, because money in the recovered source is a reading and never a
 * weight — and a cost section that offered a target would be offering to put
 * money into the ledger, which the core refuses anyway.
 */
function CostSection({ config, commit }: { config: Raw; commit: (next: Raw) => void }) {
  const c = useConceptCopy();
  const cost = costOf(config);
  const enabled = costEnabled(config);
  return <div className="form-card">
    <h4>{c('concept.group.cost')}</h4>
    <label className="field-label">
      <input type="checkbox" aria-label={c('concept.cost.use')} checked={enabled}
        onChange={event => commit(event.target.checked
          ? { ...config, cost: newCost() } : removeCost(config))} />
      {enabled ? c('concept.on') : c('concept.off')}
    </label>
    <p className="form-hint">{c('concept.cost.note')}</p>
    {!enabled ? null : <>
      <div className="form-grid">
        <label className="field-label">{c('concept.cost.source')}
          <input aria-label={c('concept.cost.source')}
            value={typeof object(cost).source === 'string' ? String(object(cost).source) : ''}
            placeholder={c('concept.source.placeholder')}
            onChange={event => commit(patchCost(config,
              { source: event.target.value.trim() === '' ? null : event.target.value }))} />
          <small>{c('concept.cost.sourceHint')}</small>
        </label>
      </div>
      <p className="form-hint">{c('concept.cost.selectedOnly')}</p>
    </>}
  </div>;
}

/**
 * The fixed armour section and the cost section, as two ordinary blocks of the
 * concept draft.
 *
 * Row keys are local UI identities: an editable identifier cannot own focus, so a
 * renamed region keeps the row it was edited in. Adding is refused at the
 * contract's own limit rather than writing a fifty-first record the server would
 * reject, and deleting a region removes only its declaration — never a ledger
 * item, never an adopted mass and never another region's binding.
 */
export function FixedArmourEditor({ project, config, commit }: FixedArmourEditorProps) {
  const c = useConceptCopy();
  const records = fixedArmour(config);
  const atLimit = records.length >= MAX_FIXED_ARMOUR_RECORDS;
  // A hand-edited document can bind one item to two components; the contract
  // refuses that, so it is named here rather than resolved by dropping either.
  const collisions = duplicateTargets(config);
  const rowKeys = useRef<number[]>([]);
  const nextRowKey = useRef(0);
  while (rowKeys.current.length < records.length) rowKeys.current.push(nextRowKey.current++);
  rowKeys.current.length = records.length;

  return <div className="form-card">
    <h3>{c('concept.group.fixedArmour')}</h3>
    <p>{c('concept.fixedArmour.note')}</p>
    {collisions.length === 0 ? null : <p className="form-error" role="alert">
      {c('concept.fixedArmour.targetConflict', { item: collisions.join(', ') })}</p>}
    {records.map((record, index) => <details className="form-card"
      key={rowKeys.current[index]} open>
      <summary>{typeof record.id === 'string' && record.id !== ''
        ? record.id
        : `${c('concept.fixedArmour.id')} ${index + 1}`}</summary>
      <div className="form-card-body">
        <FixedArmourRecord project={project} config={config} index={index} commit={commit} />
      </div>
    </details>)}
    <button className="button button--secondary" type="button" disabled={atLimit}
      onClick={() => commit({ ...config, fixed_armour: [...records, newFixedArmour(records)] })}>
      {c('concept.fixedArmour.add')}
    </button>
    {atLimit && <p className="form-hint">
      {c('concept.fixedArmour.max', { count: MAX_FIXED_ARMOUR_RECORDS })}</p>}
    <ArmourReviewEditor config={config} commit={commit} />
    <CostSection config={config} commit={commit} />
  </div>;
}

export function ArmourReviewEditor({ config, commit }: { config: Raw; commit: (next: Raw) => void }) {
  const c = useConceptCopy();
  const enabled = config.armour_review !== undefined && config.armour_review !== null;
  const review = object(config.armour_review);
  const patch = (next: Raw) => commit({ ...config, armour_review: { ...review, ...next } });
  return <section className="form-card" aria-label={c('armourReview.title')}>
    <h4>{c('armourReview.title')}</h4>
    <label className="checkbox-label"><input type="checkbox" checked={enabled}
      aria-label={c('armourReview.enable')} onChange={event => {
        if (event.target.checked) commit({ ...config, armour_review: { source: null, belt_inclination_deg: null } });
        else { const { armour_review: _removed, ...rest } = config; commit(rest); }
      }} />{c('armourReview.enable')}</label>
    <p className="form-hint">{c('armourReview.note')}</p>
    {enabled && <div className="form-grid">
      <label className="field-label">{c('armourReview.source')}<input
        aria-label={c('armourReview.source')} value={typeof review.source === 'string' ? review.source : ''}
        onChange={event => patch({ source: event.target.value || null })} /></label>
      <DeclaredNumber label={c('armourReview.angle')} value={review.belt_inclination_deg}
        kind="signed" min={-89} max={89} unit="°" onChange={value => patch({ belt_inclination_deg: value })} />
    </div>}
  </section>;
}
