import { useRef } from 'react';

import { useConceptCopy, type ConceptKey } from '../i18n/concept';
import { QuantityField } from './QuantityField';
import { ledgerItems, number, object, stringList, type Raw } from './formModel';
import { systemLeaves } from './massModels';
import { DeclaredNumber, ItemSelect } from './declaredInputs';
import {
  auxiliaryWeaponIdValid, auxiliaryWeaponKind, auxiliaryWeaponLocationCount,
  auxiliaryWeaponRole, auxiliaryWeaponTarget, auxiliaryWeaponTargetConflicts, auxiliaryWeapons,
  AUXILIARY_WEAPON_KINDS, AUXILIARY_WEAPON_KIND_LABELS, AUXILIARY_WEAPON_LOCATION_KEYS,
  AUXILIARY_WEAPON_ROLE, changeAuxiliaryWeaponKind, claimedTargetIds, duplicateAuxiliaryWeaponIds,
  duplicateTargets, MAX_AUXILIARY_WEAPONS, newAuxiliaryWeapon, patchAuxiliaryWeapon,
  removeAuxiliaryWeapon, replaceAuxiliaryWeapon, withoutAuxiliaryFields,
} from './conceptDesign';
import type { ProjectDocument } from '../types';

/**
 * The optional auxiliary weapons, declared as ordinary inputs.
 *
 * The recovered original held five separate auxiliary descriptions — two torpedo
 * sets, one mine rack and two depth-charge/AS-mortar batteries — and this editor
 * keeps them five separate things: each record names one family, carries its own
 * identifier, its own editable source and its own owned ledger target, and
 * declares only the fields that family has. A torpedo is a diameter, a length and
 * a count; a mine and a depth charge are a whole-unit mass and a count. They are
 * independent of the gun batteries and of the fixed armour regions, and none of
 * them is ever merged into one.
 *
 * It computes nothing. The recovered `sizeNweight` expressions, the
 * `dateHull < 1907` year branch and the nine/four/four per-location mount factors
 * live in the core. What this file does instead is keep the two facts the recovered
 * form could not express: an empty input stays an *unknown* rather than a zero or a
 * default, and `loads` keeps its own meaning per family — number of sets for a
 * torpedo, reloads for a mine and a depth charge — because the recovered
 * expressions read the same field as two different quantities.
 */

interface AuxiliaryWeaponsEditorProps {
  project: ProjectDocument;
  config: Raw;
  commit: (next: Raw) => void;
}

/**
 * One declared record, with its identity, its binding and its own engineering
 * fields.
 *
 * Every binding offered is an item the chosen system already links, minus
 * everything another component already claims — a battery row's guns, a layout's
 * complete armour, a fixed armour region, another auxiliary weapon, the
 * machinery and fuel items and the balance's own adjustable structure item.
 * One ledger item carries one component's mass, so a refused choice is shown as
 * refused rather than offered as a default, and no existing binding or adopted
 * mass is ever removed to resolve a collision.
 */
function AuxiliaryWeaponRecord({ project, config, index, commit }: {
  project: ProjectDocument; config: Raw; index: number; commit: (next: Raw) => void;
}) {
  const c = useConceptCopy();
  const record = auxiliaryWeapons(config)[index];
  if (!record) return null;
  const kind = auxiliaryWeaponKind(record.kind);
  const leaves = systemLeaves(project.systems);
  const itemById = new Map(ledgerItems(project).map(item => [item.id, item]));
  const leaf = leaves.find(entry => entry.id === record.system_id);
  // Every component's claim, including this record's own binding, so the picker
  // offers only what nothing else holds. The record's own current binding is put
  // back below, because editing another input must never silently drop a binding
  // the reader already made — even before a kind, and therefore a role, exists.
  const claimed = new Set(claimedTargetIds(config));
  const mine = record.item_id;
  const owned = stringList(leaf?.leaf.weight_item_ids)
    .map(id => itemById.get(id))
    .filter((item): item is { id: string; label: string } => item !== undefined)
    .filter(item => item.id === mine || !claimed.has(item.id));
  const duplicated = new Set(duplicateAuxiliaryWeaponIds(config));
  const conflicts = new Set(auxiliaryWeaponTargetConflicts(config));
  const id = typeof record.id === 'string' ? record.id : '';
  const spaceReferenced = stringList(object(config.auxiliary_space).torpedo_ids).includes(id);
  const locations = kind === null ? [] : AUXILIARY_WEAPON_LOCATION_KEYS[kind];

  function patch(patchValue: Raw) { commit(patchAuxiliaryWeapon(config, index, patchValue)); }

  return <div className="form-card">
    <div className="form-grid">
      <label className="field-label">{c('concept.auxiliary.id')}
        <input aria-label={c('concept.auxiliary.id')} value={id} disabled={spaceReferenced}
          onChange={event => { if (!spaceReferenced) patch({ id: event.target.value }); }} />
        <small>{c('concept.auxiliary.idHint')}</small>
      </label>
      <label className="field-label">{c('concept.auxiliary.source')}
        <input aria-label={c('concept.auxiliary.source')}
          value={typeof record.source === 'string' ? record.source : ''}
          placeholder={c('concept.source.placeholder')}
          onChange={event => patch({ source: event.target.value.trim() === '' ? '' : event.target.value })} />
        <small>{c('concept.auxiliary.sourceHint')}</small>
      </label>
      <label className="field-label">{c('concept.auxiliary.kind')}
        <select aria-label={c('concept.auxiliary.kind')} value={kind ?? ''} disabled={spaceReferenced}
          onChange={event => {
            if (spaceReferenced) return;
            const next = auxiliaryWeaponKind(event.target.value);
            // An undeclared family is not a weapon: it keeps the declaration's
            // identity and drops every field no family claims. This *replaces* the
            // record rather than merging into it, because a merge would bring the
            // previous family's own field back as an adopted value.
            commit(next === null
              ? replaceAuxiliaryWeapon(config, index, { id, kind: null,
                system_id: record.system_id ?? null, item_id: record.item_id ?? null,
                source: record.source ?? '', ...withoutAuxiliaryFields() })
              : replaceAuxiliaryWeapon(config, index, changeAuxiliaryWeaponKind(record, next)));
          }}>
          <option value="">{c('concept.auxiliary.kindUnknown')}</option>
          {AUXILIARY_WEAPON_KINDS.map(name => <option key={name} value={name}>
            {c(AUXILIARY_WEAPON_KIND_LABELS[name])}
          </option>)}
        </select>
        <small>{c('concept.auxiliary.kindHint')}</small>
      </label>
      <ItemSelect label={c('concept.auxiliary.system')} ariaLabel={c('concept.auxiliary.system')}
        value={record.system_id} options={leaves.map(entry => ({ id: entry.id, label: entry.id }))}
        hint={c('concept.auxiliary.systemHint')}
        onChange={next => patch({
          system_id: next,
          // The new owner may not link the old binding, so it is cleared rather
          // than carried into a system that does not hold it. No mass is invented.
          item_id: null,
        })} />
      <ItemSelect label={c('concept.auxiliary.item')} ariaLabel={c('concept.auxiliary.item')}
        value={record.item_id} options={owned} hint={c('concept.auxiliary.bindingHint')}
        onChange={next => patch({ item_id: next })} />
    </div>

    {leaf === undefined && record.system_id !== null && record.system_id !== undefined
      ? <p className="form-hint">{c('concept.fixedArmour.unownedHint')}</p> : null}
    {auxiliaryWeaponRole(record) === null ? null : <p className="form-hint">
      {c('concept.auxiliary.roleHint')} {c(`concept.role.${AUXILIARY_WEAPON_ROLE}` as ConceptKey)}</p>}
    {duplicated.has(id) && id !== '' ? <p className="form-error" role="alert">
      {c('concept.auxiliary.duplicateId', { id })}</p> : null}
    {!auxiliaryWeaponIdValid(record.id) ? <p className="form-error" role="alert">
      {c('concept.auxiliary.invalidId')}</p> : null}
    {typeof record.item_id === 'string' && conflicts.has(record.item_id)
      ? <p className="form-error" role="alert">
        {c('concept.auxiliary.targetConflict', { item: record.item_id })}</p> : null}

    {kind === null ? null : <div className="form-grid">
      {/* The two integers the contract bounds. A declared zero is a determined
          zero to the recovered expressions — never a missing number — so it is
          stored as typed and never rounded, truncated or filled in. */}
      <DeclaredNumber label={c('concept.auxiliary.count')} kind="integer" min={0} max={1000000}
        value={record.count} hint={c('concept.auxiliary.countHint')}
        onChange={next => patch({ count: next })} />
      <DeclaredNumber label={c(kind === 'torpedo' ? 'concept.auxiliary.loads.torpedo'
        : 'concept.auxiliary.loads.reload')} kind="integer" min={0} max={1000000}
        value={record.loads}
        hint={c(kind === 'torpedo' ? 'concept.auxiliary.loads.torpedoHint'
          : 'concept.auxiliary.loads.reloadHint')}
        onChange={next => patch({ loads: next })} />
      <label className="field-label">{c('concept.auxiliary.location')}
        <select aria-label={c('concept.auxiliary.location')}
          value={typeof record.location_index === 'number' ? String(record.location_index) : ''}
          onChange={event => patch({ location_index: event.target.value === ''
            ? null : Number(event.target.value) })}>
          <option value="">{c('concept.auxiliary.locationUnknown')}</option>
          {locations.map((name, location) =>
            <option key={location} value={location}>{c(name)}</option>)}
        </select>
        <small>{c('concept.auxiliary.locationHint', {
          count: auxiliaryWeaponLocationCount(kind) })}</small>
      </label>
      {kind === 'torpedo' ? <>
        <QuantityField label={c('concept.auxiliary.diameter')} ariaLabel={c('concept.auxiliary.diameter')}
          dimension="length" storedUnit="mm" kind="nonnegative" value={number(record.diameter_mm)}
          hint={c('concept.auxiliary.diameterHint')}
          onChange={next => patch({ diameter_mm: next })} />
        <QuantityField label={c('concept.auxiliary.length')} ariaLabel={c('concept.auxiliary.length')}
          dimension="length" storedUnit="m" kind="nonnegative" value={number(record.length_m)}
          hint={c('concept.auxiliary.lengthHint')}
          onChange={next => patch({ length_m: next })} />
      </> : <QuantityField label={c('concept.auxiliary.unitMass')}
        ariaLabel={c('concept.auxiliary.unitMass')} dimension="mass" storedUnit="kg"
        kind="nonnegative" value={number(record.unit_mass_kg)}
        hint={c('concept.auxiliary.unitMassHint')}
        onChange={next => patch({ unit_mass_kg: next })} />}
    </div>}
    <p className="form-hint">{c('concept.auxiliary.separate')}</p>
    {spaceReferenced ? <p className="form-hint">{c('space.unlinkFirst')}</p> : null}
    <button className="text-button" type="button" disabled={spaceReferenced}
      onClick={() => { if (!spaceReferenced) commit(removeAuxiliaryWeapon(config, index)); }}>
      {c('concept.auxiliary.remove')}
    </button>
  </div>;
}

/**
 * The auxiliary weapons section, as one ordinary block of the concept draft.
 *
 * Row keys are local UI identities, so a renamed record keeps the row it was
 * edited in. Adding is refused at the contract's own limit rather than writing a
 * fifty-first record the server would reject, and deleting a record removes only
 * its declaration — never a ledger item, never an adopted mass and never another
 * component's binding.
 */
export function AuxiliaryWeaponsEditor({ project, config, commit }: AuxiliaryWeaponsEditorProps) {
  const c = useConceptCopy();
  const records = auxiliaryWeapons(config);
  const atLimit = records.length >= MAX_AUXILIARY_WEAPONS;
  // A hand-edited document can bind one item to two components; the contract
  // refuses that, so it is named here rather than resolved by dropping either.
  const collisions = duplicateTargets(config);
  const rowKeys = useRef<number[]>([]);
  const nextRowKey = useRef(0);
  while (rowKeys.current.length < records.length) rowKeys.current.push(nextRowKey.current++);
  rowKeys.current.length = records.length;

  return <div className="form-card">
    <h3>{c('concept.group.auxiliary')}</h3>
    <p>{c('concept.auxiliary.note')}</p>
    {collisions.length === 0 ? null : <p className="form-error" role="alert">
      {c('concept.auxiliary.targetConflict', { item: collisions.join(', ') })}</p>}
    {records.map((record, index) => <details className="form-card"
      key={rowKeys.current[index]} open>
      <summary>{typeof record.id === 'string' && record.id !== ''
        ? record.id
        : `${c('concept.auxiliary.id')} ${index + 1}`}</summary>
      <div className="form-card-body">
        <AuxiliaryWeaponRecord project={project} config={config} index={index} commit={commit} />
      </div>
    </details>)}
    <button className="button button--secondary" type="button" disabled={atLimit}
      onClick={() => commit({ ...config, auxiliary_weapons: [...records, newAuxiliaryWeapon(records)] })}>
      {c('concept.auxiliary.add')}
    </button>
    {atLimit && <p className="form-hint">
      {c('concept.auxiliary.max', { count: MAX_AUXILIARY_WEAPONS })}</p>}
  </div>;
}
