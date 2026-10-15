import { useEffect, useRef, useState } from 'react';

import { useWorkspaceCopy } from '../i18n/workspace';
import { useConceptCopy, type ConceptKey } from '../i18n/concept';
import { QuantityField } from './QuantityField';
import { number, numericProblem, object, sourceText, stringList, type NumericDomain, type Raw } from './formModel';
import { systemLeaves } from './massModels';
import {
  addArmour, armourEnabled, armourOf, BALANCE_ASSUMPTION_KEYS, batteries, batteryTargets,
  conceptEnabled, conceptOf, ENGINE_KINDS, GUN_TYPES, mismatchedRoles, MOUNT_TYPES, newBattery,
  newConcept, patchArmour, patchBattery, patchRole, removeArmour, removeBattery, ROLES, roles,
  STERN_TYPES, withConcept, withoutConcept,
  type Role,
} from './conceptDesign';
import type { ProjectDocument } from '../types';

/**
 * The declared concept design, edited as ordinary project inputs.
 *
 * Every control here writes a canonical key of the draft and nothing else. No
 * weight, centre of gravity or estimate is produced in this file: an estimate is
 * a server result, and a number typed into this editor is a *declaration*. That
 * is why an empty numeric input is written as `null` and left editable instead
 * of being filled with a plausible default, and why the one set of numbers the
 * contract lets the GUI offer — the starting balance assumptions — is written
 * explicitly and labelled as editable estimates everywhere it is shown.
 *
 * Bindings are choices among what the project already declares. The items a
 * binding may name are the ledger items owned by the chosen system, because a
 * generated estimate has to appear on a system row that owns its target; a
 * weight or a centre of gravity is never invented to fill one in.
 */

interface EditorProps {
  project: ProjectDocument;
  onChange: (project: ProjectDocument) => void;
}

const CONCEPT_STERN: Readonly<Record<string, ConceptKey>> = {
  cruiser: 'concept.stern.cruiser', small_transom: 'concept.stern.small_transom',
  large_transom: 'concept.stern.large_transom', round: 'concept.stern.round',
};
const CONCEPT_GUN: Readonly<Record<string, ConceptKey>> = {
  muzzle_loading: 'concept.gunType.muzzle_loading', breech_loading: 'concept.gunType.breech_loading',
  quick_firing: 'concept.gunType.quick_firing', anti_air: 'concept.gunType.anti_air',
  dual_purpose: 'concept.gunType.dual_purpose', automatic: 'concept.gunType.automatic',
  machine_gun: 'concept.gunType.machine_gun',
};
const CONCEPT_MOUNT: Readonly<Record<string, ConceptKey>> = {
  broadside: 'concept.mountType.broadside', coles_turret: 'concept.mountType.coles_turret',
  open_barbette: 'concept.mountType.open_barbette', turret_barbette: 'concept.mountType.turret_barbette',
  deck_hoist: 'concept.mountType.deck_hoist', deck: 'concept.mountType.deck',
  casemate: 'concept.mountType.casemate',
};
const CONCEPT_KIND: Readonly<Record<string, ConceptKey>> = {
  simple: 'concept.kind.simple', compound: 'concept.kind.compound', turbine: 'concept.kind.turbine',
};

/**
 * The starting assumptions, each with the name a reader reads.
 *
 * The stored keys are the core's; the labels are not derived from them, because
 * `space_hull_fraction` is not something to put in front of a reader.
 */
const ASSUMPTION_LABELS: Readonly<Record<string, ConceptKey>> = {
  steadiness: 'concept.balance.steadiness',
  space_hull_fraction: 'concept.balance.spaceHull',
  space_deck_fraction: 'concept.balance.spaceDeck',
  super_factor: 'concept.balance.superFactor',
  super_factor_long: 'concept.balance.superFactorLong',
  concentration: 'concept.balance.concentration',
  strength_target: 'concept.balance.strengthTarget',
};

/**
 * A declared number, stored exactly as typed.
 *
 * Nothing is rounded, truncated or clamped on the way in. A fractional count or
 * a wrong-signed year is *kept* and marked, so the reader can see and correct
 * what they typed and so the server sees the same value the reader did; a silent
 * `Math.trunc` here would store a number nobody entered.
 */
function DeclaredNumber({ label, value, onChange, hint, kind = 'signed', min, max, unit, ariaLabel }: {
  label: string; value: unknown; onChange: (next: number | null) => void; hint?: string;
  kind?: NumericDomain; min?: number; max?: number; unit?: string; ariaLabel?: string;
}) {
  const w = useWorkspaceCopy();
  const stored = number(value);
  const [text, setText] = useState(() => (stored === null ? '' : String(stored)));
  // Re-derive only when the stored value changed underneath this control (a
  // save, a reload, another row), never while the reader is mid-type.
  const [editing, setEditing] = useState(false);
  useEffect(() => {
    if (!editing) setText(stored === null ? '' : String(stored));
  }, [stored, editing]);
  const problem = numericProblem(kind, text, w);
  return <label className="field-label">{label}
    <input type="number" step="any" min={min} max={max} placeholder={w('units.unknown')}
      aria-label={ariaLabel ?? label} aria-invalid={Boolean(problem)}
      value={text}
      onFocus={() => setEditing(true)}
      onBlur={() => setEditing(false)}
      onChange={event => {
        const raw = event.target.value;
        setText(raw);
        if (raw.trim() === '') { onChange(null); return; }
        const typed = Number(raw);
        // Kept verbatim: a wrong value is refused with a message, not rewritten.
        onChange(Number.isFinite(typed) ? typed : null);
      }} />
    {unit && <span className="field-unit">{unit}</span>}
    {hint && <small>{hint}</small>}
    {problem && <span className="field-error" role="alert">{problem}</span>}
  </label>;
}

/** A declared number in a unit of its own, printed and stored as that unit. */
function CanonicalNumber({ label, value, onChange, unit, hint, ariaLabel, min, max, step = 'any' }: {
  label: string; value: unknown; onChange: (next: number | null) => void; unit: string;
  hint?: string; ariaLabel?: string; min?: number; max?: number; step?: number | 'any';
}) {
  const w = useWorkspaceCopy();
  return <label className="field-label">{label}
    <input type="number" step={step} min={min} max={max} placeholder={w('units.unknown')}
      aria-label={ariaLabel ?? label} value={number(value) ?? ''}
      onChange={event => {
        const raw = event.target.value.trim();
        if (raw === '') { onChange(null); return; }
        const typed = Number(raw);
        if (!Number.isFinite(typed)) return;
        onChange(typed);
      }} />
    <span className="field-unit">{unit}</span>
    {hint && <small>{hint}</small>}
  </label>;
}

function EnumSelect({ label, value, options, labels, onChange, placeholder, hint, ariaLabel }: {
  label: string; value: unknown; options: ReadonlyArray<string>;
  labels: Readonly<Record<string, ConceptKey>>;
  onChange: (next: string | null) => void; placeholder: string; hint?: string; ariaLabel?: string;
}) {
  const c = useConceptCopy();
  return <label className="field-label">{label}
    <select aria-label={ariaLabel ?? label} value={typeof value === 'string' ? value : ''}
      onChange={event => onChange(event.target.value === '' ? null : event.target.value)}>
      <option value="">{placeholder}</option>
      {options.map(option => <option key={option} value={option}>
        {labels[option] ? c(labels[option]) : option}
      </option>)}
    </select>
    {hint && <small>{hint}</small>}
  </label>;
}

/** One existing, owned ledger item, chosen by the reader. Never invented. */
function ItemSelect({ label, value, options, onChange, hint, emptyLabel, ariaLabel }: {
  label: string; value: unknown; options: Array<{ id: string; label: string }>;
  onChange: (next: string | null) => void; hint?: string; emptyLabel?: string; ariaLabel?: string;
}) {
  const c = useConceptCopy();
  const current = typeof value === 'string' ? value : '';
  const listed = options.some(option => option.id === current);
  return <label className="field-label">{label}
    <select aria-label={ariaLabel ?? label} value={current}
      onChange={event => onChange(event.target.value === '' ? null : event.target.value)}>
      <option value="">{emptyLabel ?? c('concept.roles.unallocated')}</option>
      {/* A binding that no longer resolves is still shown, as unresolved, so the
          reader sees what is there rather than watching it vanish. */}
      {current !== '' && !listed && <option value={current}>{current}</option>}
      {options.map(option => <option key={option.id} value={option.id}>{option.label}</option>)}
    </select>
    {hint && <small>{hint}</small>}
  </label>;
}

/**
 * The optional gun-house and barbette armour estimate for one battery row.
 *
 * Every control writes an ordinary declared key of that row's `armour` object
 * and nothing else. No mass is produced here: the number is a server result, and
 * the reader's inputs stay exactly as typed. Switching the block on writes an
 * empty block so an undeclared thickness is visibly unknown; switching it off
 * removes only the block, leaving any ledger mass and any accepted record alone.
 */
function BatteryArmourBlock({ project, config, index, commit }: {
  project: ProjectDocument; config: Raw; index: number; commit: (next: Raw) => void;
}) {
  const c = useConceptCopy();
  const battery = batteries(config)[index];
  if (!battery) return null;
  const targets = batteryTargets(battery);
  const armour = armourOf(config, index);
  const enabled = armourEnabled(config, index);
  const leaves = systemLeaves(project.systems);
  const ledger = project.weight_groups.flatMap(group => group.items
    .filter(item => item && typeof item.id === 'string' && item.id !== '')
    .map(item => ({ id: String(item.id), label: `${group.label || group.id} / ${item.id}`,
      mass: number(item.mass_t) })));
  const itemById = new Map(ledger.map(item => [item.id, item]));
  const leaf = leaves.find(entry => entry.id === object(armour).system_id);
  // The armour target must be a fourth, distinct item of its own owning system.
  const owned = stringList(leaf?.leaf.weight_item_ids)
    .map(id => itemById.get(id))
    .filter((item): item is { id: string; label: string; mass: number | null } => item !== undefined)
    .filter(item => item.id !== targets.guns && item.id !== targets.mounts
      && item.id !== targets.ammunition)
    .map(item => ({ id: item.id, label: item.label }));

  function patch(patchValue: Raw) { commit(patchArmour(config, index, patchValue)); }

  return <div className="form-card">
    <h4>{c('concept.armour.use')}</h4>
    <label className="field-label">
      <input type="checkbox" aria-label={c('concept.armour.use')} checked={enabled}
        onChange={event => commit(event.target.checked
          ? addArmour(config, index) : removeArmour(config, index))} />
      {enabled ? c('concept.on') : c('concept.off')}
    </label>
    <p className="form-hint">{c('concept.armour.scope')}</p>
    {!enabled ? null : <>
      <div className="form-grid">
        <ItemSelect label={c('concept.armour.system')} value={object(armour).system_id}
          options={leaves.map(entry => ({ id: entry.id, label: entry.id }))}
          hint={c('concept.armour.systemHint')}
          onChange={next => patch({ system_id: next,
            // The new owner may not link the old binding, so it is cleared
            // rather than carried into a system that does not hold it. The row's
            // own three bindings are a separate concern and are left alone.
            item_id: null })} />
        <ItemSelect label={c('concept.armour.item')} value={object(armour).item_id} options={owned}
          hint={c('concept.armour.bindingHint')} onChange={next => patch({ item_id: next })} />
        <QuantityField label={c('concept.armour.face')} dimension="length" storedUnit="mm" kind="nonnegative"
          value={number(object(armour).face_mm)} hint={c('concept.armour.thicknessHint')}
          onChange={next => patch({ face_mm: next })} />
        <QuantityField label={c('concept.armour.side')} dimension="length" storedUnit="mm" kind="nonnegative"
          value={number(object(armour).rear_roof_mm)} hint={c('concept.armour.thicknessHint')}
          onChange={next => patch({ rear_roof_mm: next })} />
        <QuantityField label={c('concept.armour.barbette')} dimension="length" storedUnit="mm" kind="nonnegative"
          value={number(object(armour).barbette_mm)} hint={c('concept.armour.thicknessHint')}
          onChange={next => patch({ barbette_mm: next })} />
        <QuantityField label={c('concept.armour.freeboard')} ariaLabel={c('concept.armour.freeboard')}
          value={number(object(armour).freeboard_m)} dimension="length" storedUnit="m"
          kind="nonnegative" hint={c('concept.armour.freeboardHint')}
          onChange={next => patch({ freeboard_m: next })} />
        <DeclaredNumber label={c('concept.armour.super')} kind="nonnegative" min={0} max={10}
          value={object(armour).super_factor} hint={c('concept.armour.superHint')}
          onChange={next => patch({ super_factor: next })} />
      </div>
      <p className="form-hint">{c('concept.armour.conditionalHint')}</p>
      <p className="form-hint">{c('concept.armour.separate')}</p>
    </>}
  </div>;
}

export function ConceptDesignEditor({ project, onChange }: EditorProps) {
  const c = useConceptCopy();
  const config = conceptOf(project);
  const enabled = conceptEnabled(project);
  const balance = object(config.balance);
  const machinery = object(config.machinery);
  const fuel = object(config.fuel);
  const ledger = project.weight_groups.flatMap(group => group.items
    .filter(item => item && typeof item.id === 'string' && item.id !== '')
    .map(item => ({ id: String(item.id), label: `${group.label || group.id} / ${item.id}`, mass: number(item.mass_t) })));
  const itemById = new Map(ledger.map(item => [item.id, item]));
  const leaves = systemLeaves(project.systems);
  const leafIds = leaves.map(leaf => leaf.id);
  const current = roles(config);
  const mismatched = mismatchedRoles(config);
  // Row keys are local UI identities; an editable battery name cannot own focus.
  const rowKeys = useRef<number[]>([]);
  const nextRowKey = useRef(0);
  const batteryRows = batteries(config);
  while (rowKeys.current.length < batteryRows.length) rowKeys.current.push(nextRowKey.current++);
  rowKeys.current.length = batteryRows.length;

  function commit(next: Raw) { onChange(withConcept(project, next)); }
  function patch(patchValue: Raw) { commit({ ...config, ...patchValue }); }
  function patchBalance(patchValue: Raw) { commit({ ...config, balance: { ...balance, ...patchValue } }); }
  function updateBattery(index: number, patchValue: Raw) { commit(patchBattery(config, index, patchValue)); }

  /**
   * The items a system owns, with their ledger labels.
   *
   * A generated model is attached to a declared system row and proposes a value
   * for an item that row already links, so these are the only items that system
   * can legitimately be asked to estimate. Changing the owning system therefore
   * has to re-derive the bindings, not keep ones the new owner does not hold.
   */
  function ownedItems(systemId: unknown): Array<{ id: string; label: string }> {
    const leaf = leaves.find(entry => entry.id === systemId);
    if (!leaf) return [];
    return stringList(leaf.leaf.weight_item_ids)
      .map(id => itemById.get(id))
      .filter((item): item is { id: string; label: string; mass: number | null } => item !== undefined)
      .map(item => ({ id: item.id, label: item.label }));
  }

  function systemOptions(): Array<{ id: string; label: string }> {
    return leaves.map(leaf => ({ id: leaf.id, label: leaf.id }));
  }

  return <div className="concept-editor form-stack">
    <div className="form-card">
      <h3>{c('concept.enable')}</h3>
      <p>{c('concept.enableHint')}</p>
      <label className="field-label">
        <input type="checkbox" aria-label={c('concept.enable')} checked={enabled}
          onChange={event => onChange(event.target.checked
            ? withConcept(project, newConcept()) : withoutConcept(project))} />
        {enabled ? c('concept.on') : c('concept.off')}
      </label>
    </div>

    {!enabled ? null : <>
      <div className="form-card">
        <h3>{c('concept.group.declaration')}</h3>
        <p>{c('concept.intro')}</p>
        <label className="field-label">{c('concept.source.label')}
          <input aria-label={c('concept.source.label')} value={sourceText(config.source)}
            placeholder={c('concept.source.placeholder')}
            onChange={event => patch({ source: event.target.value.trim() === '' ? '' : event.target.value })} />
          <small>{c('concept.source.hint')}</small>
        </label>
        {sourceText(config.source).trim() === '' &&
          <p className="form-error" role="alert">{c('concept.missingSource')}</p>}
        <p className="form-hint">{c('concept.methodNote', {
          method: String(config.method ?? ''), schema: String(config.schema ?? '') })}</p>
      </div>

      <div className="form-card">
        <h3>{c('concept.group.hull')}</h3>
        <div className="form-grid">
          <QuantityField label={c('concept.target.label')} ariaLabel={c('concept.target.label')}
            value={number(config.target_displacement_t)} dimension="mass" storedUnit="t" kind="positive"
            hint={c('concept.target.hint')} onChange={next => patch({ target_displacement_t: next })} />
          <DeclaredNumber label={c('concept.hullYear.label')} kind="integer" min={1850} max={1950}
            value={config.hull_year} hint={c('concept.hullYear.hint')}
            onChange={next => patch({ hull_year: next })} />
          <QuantityField label={c('concept.freeboard.label')} ariaLabel={c('concept.freeboard.label')}
            value={number(config.freeboard_m)} dimension="length" storedUnit="m" kind="positive"
            hint={c('concept.freeboard.hint')} onChange={next => patch({ freeboard_m: next })} />
          <EnumSelect label={c('concept.stern.label')} value={config.stern} options={STERN_TYPES}
            labels={CONCEPT_STERN} placeholder={c('concept.roles.unallocated')}
            onChange={next => patch({ stern: next })} />
          <DeclaredNumber label={c('concept.screws.label')} kind="integer" min={1} max={8}
            value={config.screws} hint={c('concept.screws.hint')} onChange={next => patch({ screws: next })} />
        </div>
      </div>

      <div className="form-card">
        <h3>{c('concept.group.batteries')}</h3>
        <p>{c('concept.group.batteries.note')}</p>
        {batteryRows.map((battery, index) => {
          const targets = batteryTargets(battery);
          const owned = ownedItems(battery.system_id);
          // Three distinct items, so each picker excludes the other two.
          const forGuns = owned.filter(item => item.id !== targets.mounts && item.id !== targets.ammunition);
          const forMounts = owned.filter(item => item.id !== targets.guns && item.id !== targets.ammunition);
          const forAmmo = owned.filter(item => item.id !== targets.guns && item.id !== targets.mounts);
          return <details className="form-card" key={rowKeys.current[index]} open>
            <summary>{String(battery.id ?? index)}</summary>
            <div className="form-card-body">
              <div className="form-grid">
                <label className="field-label">{c('concept.battery.id')}
                  <input aria-label={c('concept.battery.id')} value={String(battery.id ?? '')}
                    onChange={event => updateBattery(index, { id: event.target.value })} /></label>
                <ItemSelect label={c('concept.battery.system')} value={battery.system_id}
                  options={systemOptions()} hint={c('concept.battery.systemHint')}
                  onChange={next => updateBattery(index, {
                    system_id: next,
                    // The new owner may not link any of the old bindings, so they
                    // are cleared rather than carried into a system that does not
                    // hold them. No mass is invented to fill the gap.
                    guns_item_id: null, mounts_item_id: null, ammunition_item_id: null,
                  })} />
              </div>
              <p className="form-hint">{c('concept.battery.bindingHint')}</p>
              <div className="form-grid">
                <ItemSelect label={c('concept.battery.guns')} value={battery.guns_item_id} options={forGuns}
                  onChange={next => updateBattery(index, { guns_item_id: next })} />
                <ItemSelect label={c('concept.battery.mounts')} value={battery.mounts_item_id} options={forMounts}
                  onChange={next => updateBattery(index, { mounts_item_id: next })} />
                <ItemSelect label={c('concept.battery.ammunition')} value={battery.ammunition_item_id}
                  options={forAmmo} onChange={next => updateBattery(index, { ammunition_item_id: next })} />
              </div>
              {!targets.distinct && <p className="form-error" role="alert">{c('concept.battery.distinct')}</p>}
              <div className="form-grid">
                {/* A calibre is stored in millimetres and is typed in
                    millimetres. It is not a length the reader may prefer in feet,
                    and converting a typed 152.4 into 152,400 mm would be the
                    wrong number written confidently. */}
                <CanonicalNumber label={c('concept.battery.calibre')} unit="mm" min={0}
                  value={battery.calibre_mm} onChange={next => updateBattery(index, { calibre_mm: next })} />
                <DeclaredNumber label={c('concept.battery.barrelCalibres')} kind="positive" min={1} max={100}
                  value={battery.barrel_calibres} hint={c('concept.battery.barrelCalibresHint')}
                  onChange={next => updateBattery(index, { barrel_calibres: next })} />
                <DeclaredNumber label={c('concept.battery.year')} kind="integer" min={1850} max={1950}
                  value={battery.year}
                  onChange={next => updateBattery(index, { year: next })} />
                <EnumSelect label={c('concept.battery.gunType')} value={battery.gun_type} options={GUN_TYPES}
                  labels={CONCEPT_GUN} placeholder={c('concept.roles.unallocated')}
                  onChange={next => updateBattery(index, { gun_type: next })} />
                <EnumSelect label={c('concept.battery.mountType')} value={battery.mount_type}
                  options={MOUNT_TYPES} labels={CONCEPT_MOUNT} placeholder={c('concept.roles.unallocated')}
                  onChange={next => updateBattery(index, { mount_type: next })} />
                <DeclaredNumber label={c('concept.battery.mountCount')} kind="integer" min={0} max={1000}
                  value={battery.mount_count}
                  onChange={next => updateBattery(index, { mount_count: next })} />
                <DeclaredNumber label={c('concept.battery.barrelsPerMount')} kind="integer" min={1} max={10}
                  value={battery.barrels_per_mount}
                  onChange={next => updateBattery(index, { barrels_per_mount: next })} />
                <DeclaredNumber label={c('concept.battery.rounds')} kind="integer" min={0} max={10000}
                  value={battery.rounds_per_gun}
                  onChange={next => updateBattery(index, { rounds_per_gun: next })} />
                <CanonicalNumber label={c('concept.battery.shell')} unit="kg" min={0}
                  value={battery.shell_mass_kg} ariaLabel={c('concept.battery.shell')}
                  hint={c('concept.battery.shellHint')}
                  onChange={next => updateBattery(index, { shell_mass_kg: next })} />
                <DeclaredNumber label={c('concept.battery.broadside')} kind="integer" min={0} max={1000}
                  value={battery.broadside_guns} hint={c('concept.battery.broadsideHint')}
                  onChange={next => updateBattery(index, { broadside_guns: next })} />
                <label className="field-label">
                  <input type="checkbox" aria-label={c('concept.battery.sharedCradle')}
                    checked={battery.shared_cradle === true}
                    onChange={event => updateBattery(index, { shared_cradle: event.target.checked })} />
                  {c('concept.battery.sharedCradle')}
                  <small>{c('concept.battery.sharedCradleHint')}</small>
                </label>
              </div>
              <button className="text-button" type="button"
                onClick={() => { rowKeys.current.splice(index, 1); commit(removeBattery(config, index)); }}>{c('concept.battery.remove')}</button>
              <BatteryArmourBlock project={project} config={config} index={index}
                commit={commit} />
            </div>
          </details>;
        })}
        <button className="button button--secondary" type="button"
          onClick={() => patch({ batteries: [...batteries(config), newBattery(batteries(config))] })}>
          {c('concept.battery.add')}
        </button>
      </div>

      <div className="form-card">
        <h3>{c('concept.group.machinery')}</h3>
        <label className="field-label">
          <input type="checkbox" aria-label={c('concept.machinery.use')}
            checked={config.machinery !== null && config.machinery !== undefined}
            onChange={event => patch({
              machinery: event.target.checked
                ? { system_id: null, item_id: null, year: null, kind: null, coal_pct: null, speed_kn: null, shaft_power_kw: null }
                : null,
              // Fuel is a consequence of a declared engine, so it goes with it.
              fuel: event.target.checked ? config.fuel : null,
            })} />
          {c('concept.machinery.use')}
        </label>
        <p className="form-hint">{c('concept.machinery.scope')}</p>
        {config.machinery === null || config.machinery === undefined ? null : <div className="form-grid">
          <ItemSelect label={c('concept.machinery.system')} value={machinery.system_id} options={systemOptions()}
            onChange={next => patch({ machinery: { ...machinery, system_id: next, item_id: null },
              fuel: object(config.fuel).item_id === undefined ? config.fuel : { ...object(config.fuel), system_id: next, item_id: null } })} />
          <ItemSelect label={c('concept.machinery.item')} value={machinery.item_id}
            options={ownedItems(machinery.system_id)} hint={c('concept.battery.bindingHint')}
            onChange={next => patch({ machinery: { ...machinery, item_id: next } })} />
          <DeclaredNumber label={c('concept.machinery.year')} kind="integer" min={1850} max={1950}
            value={machinery.year} onChange={next => patch({ machinery: { ...machinery, year: next } })} />
          <EnumSelect label={c('concept.machinery.kind')} value={machinery.kind} options={ENGINE_KINDS}
            labels={CONCEPT_KIND} placeholder={c('concept.roles.unallocated')}
            onChange={next => patch({ machinery: { ...machinery, kind: next } })} />
          <DeclaredNumber label={c('concept.machinery.coal')} kind="nonnegative" min={0} max={100} unit="%"
            value={machinery.coal_pct} hint={c('concept.machinery.coalHint')}
            onChange={next => patch({ machinery: { ...machinery, coal_pct: next } })} />
          <QuantityField label={c('concept.machinery.speed')} ariaLabel={c('concept.machinery.speed')}
            value={number(machinery.speed_kn)} dimension="speed" storedUnit="kn" kind="positive"
            onChange={next => patch({ machinery: { ...machinery, speed_kn: next } })} />
          <QuantityField label={c('concept.machinery.power')} ariaLabel={c('concept.machinery.power')}
            value={number(machinery.shaft_power_kw)} dimension="power" storedUnit="kW" kind="positive"
            hint={c('concept.machinery.powerHint')}
            onChange={next => patch({ machinery: { ...machinery, shaft_power_kw: next } })} />
        </div>}
      </div>

      <div className="form-card">
        <h3>{c('concept.group.fuel')}</h3>
        {config.machinery === null || config.machinery === undefined
          ? <p className="form-hint">{c('concept.fuel.requires')}</p>
          : <label className="field-label">
            <input type="checkbox" aria-label={c('concept.fuel.use')}
              checked={config.fuel !== null && config.fuel !== undefined}
              onChange={event => patch({ fuel: event.target.checked
                ? { system_id: machinery.system_id ?? null, item_id: null, range_nm: null, cruise_speed_kn: null } : null })} />
            {c('concept.fuel.use')}
          </label>}
        {config.fuel === null || config.fuel === undefined ? null : <div className="form-grid">
          <ItemSelect label={c('concept.fuel.system')} value={fuel.system_id} options={systemOptions()}
            onChange={next => patch({ fuel: { ...fuel, system_id: next, item_id: null } })} />
          <ItemSelect label={c('concept.fuel.item')} value={fuel.item_id}
            options={ownedItems(fuel.system_id)} hint={c('concept.battery.bindingHint')}
            onChange={next => patch({ fuel: { ...fuel, item_id: next } })} />
          {/* A range is a distance in nautical miles. It is typed and stored in
              nautical miles and never passes through a speed or length
              conversion, which would be a different quantity entirely. */}
          <CanonicalNumber label={c('concept.fuel.range')} unit="nm" min={0}
            value={fuel.range_nm} onChange={next => patch({ fuel: { ...fuel, range_nm: next } })} />
          <QuantityField label={c('concept.fuel.cruise')} ariaLabel={c('concept.fuel.cruise')}
            value={number(fuel.cruise_speed_kn)} dimension="speed" storedUnit="kn" kind="positive"
            hint={c('concept.fuel.cruiseHint')}
            onChange={next => patch({ fuel: { ...fuel, cruise_speed_kn: next } })} />
        </div>}
      </div>

      <div className="form-card">
        <h3>{c('concept.group.balance')}</h3>
        <p>{c('concept.balance.note')}</p>
        <label className="field-label">{c('concept.balance.assumptionSource')}
          <input aria-label={c('concept.balance.assumptionSource')} value={sourceText(balance.assumption_source)}
            placeholder={c('concept.balance.assumptionSourcePlaceholder')}
            onChange={event => patchBalance({ assumption_source: event.target.value })} />
          <small>{c('concept.balance.assumptionSourceHint')}</small>
        </label>
        <p className="form-hint">{c('concept.balance.presetsNote')}</p>
        <div className="form-grid">
          <ItemSelect label={c('concept.balance.structureSystem')} value={balance.structure_system_id}
            options={systemOptions()}
            onChange={next => patchBalance({ structure_system_id: next, structure_item_id: null })} />
          <ItemSelect label={c('concept.balance.structureItem')} value={balance.structure_item_id}
            options={ownedItems(balance.structure_system_id)} hint={c('concept.balance.structureItemHint')}
            onChange={next => patchBalance({ structure_item_id: next })} />
          {BALANCE_ASSUMPTION_KEYS.map(key => <DeclaredNumber key={key}
            label={c(ASSUMPTION_LABELS[key] ?? 'concept.balance.steadiness')} value={balance[key]}
            onChange={next => patchBalance({ [key]: next })} />)}
          <QuantityField label={c('concept.balance.bulkheadBeam')} ariaLabel={c('concept.balance.bulkheadBeam')}
            value={number(balance.bulkhead_beam_m)} dimension="length" storedUnit="m" kind="positive"
            hint={c('concept.balance.bulkheadBeamHint')}
            onChange={next => patchBalance({ bulkhead_beam_m: next })} />
        </div>
      </div>

      <div className="form-card">
        <h3>{c('concept.group.roles')}</h3>
        {ledger.length === 0 ? <p className="form-hint">{c('concept.battery.bindingHint')}</p> : <>
          <div className="stage-table-scroll" role="region" aria-label={c('concept.group.roles')} tabIndex={0}>
          <table className="stage-table"><thead><tr>
            <th>{c('proposals.col.item')}</th><th>{c('concept.group.roles')}</th>
          </tr></thead><tbody>{ledger.map(item => <tr key={item.id}>
            <td>{item.label}</td>
            <td><select aria-label={`${item.id} ${c('concept.group.roles')}`}
              value={typeof current[item.id] === 'string' ? String(current[item.id]) : ''}
              onChange={event => commit(patchRole(config, item.id,
                event.target.value === '' ? null : event.target.value as Role))}>
              <option value="">{c('concept.roles.unallocated')}</option>
              {ROLES.map(role => <option key={role} value={role}>{c(`concept.role.${role}` as ConceptKey)}</option>)}
            </select></td>
          </tr>)}</tbody></table>
          </div>
          {mismatched.length > 0 && <p className="form-error" role="alert">
            {c('concept.roles.suggestion')}: {mismatched.join(', ')}
          </p>}
          <p className="form-hint">{c('concept.roles.empty')}</p>
        </>}
      </div>
    </>}
  </div>;
}
