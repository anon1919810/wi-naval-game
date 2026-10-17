import { useRef, useState } from 'react';

import { useConceptCopy, type ConceptKey } from '../i18n/concept';
import { QuantityField } from './QuantityField';
import { ledgerItems, number, object, sourceText, stringList, type Raw } from './formModel';
import { systemLeaves } from './massModels';
import { DeclaredNumber, ItemSelect } from './declaredInputs';
import {
  addLayoutArmour, allocationLayoutReferences, batteries, batteryLayouts, componentBindings, deckProfileOf,
  duplicateLayoutReferences, GUN_TYPE_LABELS, LAYOUT_INDEX_COUNT, layoutArmourConflicts,
  layoutArmourEnabled, layoutArmourOf, layoutGroupOf, MAX_BATTERY_LAYOUTS,
  MOUNT_SELECTOR_COUNT, MOUNT_TYPE_LABELS, newBatteryLayout, newLayoutGroup,
  patchBatteryLayout, patchDeckProfile, patchLayoutArmour, patchLayoutGroup,
  removeBatteryLayout, removeLayoutArmour,
} from './conceptDesign';
import type { ProjectDocument } from '../types';

/**
 * The optional two-group mount layouts, edited as ordinary project inputs.
 *
 * A layout saves the identity of two mount groups the way the original held
 * them, and it saves nothing it read from somewhere else: a group names an
 * existing battery row and the calibre, year, gun class, mount class, mount
 * count, barrels per mount and shared cradle stay on that row. What this file
 * writes is exactly `battery_layouts`: an identifier, an editable source, two
 * groups, two group-2 doubled flags, six deck parameters and an optional
 * armour target of its own.
 *
 * It computes nothing. The recovered guns-in-mount and arrangement tables are
 * labels here, so a reader picks the source's own entry rather than a number
 * this file derived; the freeboard, the height factor and the complete
 * two-group armour are the server's readings, and the result panel prints the
 * values and the reasons the server returned.
 */

interface LayoutEditorProps {
  project: ProjectDocument;
  config: Raw;
  commit: (next: Raw) => void;
}

/** The battery row ids one group names, so an unresolved pick can still be shown. */
function groupBatteryId(layout: Raw, group: 'group1' | 'group2'): string | null {
  const value = layout[group];
  const id = value === null || value === undefined ? null : object(value).battery_id;
  return typeof id === 'string' && id !== '' ? id : null;
}

const NO_LABELS: Readonly<Record<string, ConceptKey>> = {};

/** One declared fact of a referenced row, printed as that row holds it. */
function factText(value: unknown, labels: Readonly<Record<string, ConceptKey>>,
  copy: (key: ConceptKey, params?: Record<string, string | number>) => string): string {
  if (typeof value === 'string' && labels[value]) return copy(labels[value]);
  const known = number(value);
  return known === null ? copy('concept.layout.flag.unknown') : String(known);
}

/**
 * One group: the row it references, its two recovered identity readings and its
 * three layer counts.
 */
function LayoutGroupBlock({ config, index, group, groupLabel, commit }: {
  config: Raw; index: number; group: 'group1' | 'group2'; groupLabel: ConceptKey;
  commit: (next: Raw) => void;
}) {
  const c = useConceptCopy();
  const current = layoutGroupOf(config, index, group);
  const label = (name: ConceptKey) => `${c(groupLabel)} · ${c(name)}`;
  const batteryId = current === null ? null : object(current).battery_id;
  const referenced = typeof batteryId === 'string' ? batteryId : null;
  // A row already claimed by another layout, or by this layout's other group,
  // is not offered: one row belongs to one group, and one row to one layout.
  const claimed = new Set<string>();
  batteryLayouts(config).forEach((layout, other) => {
    for (const field of ['group1', 'group2'] as const) {
      if (other === index && field === group) continue;
      const id = groupBatteryId(layout, field);
      if (id !== null) claimed.add(id);
    }
  });
  const rows = batteries(config)
    .filter(row => typeof row.id === 'string' && row.id !== '')
    .map(row => ({ id: String(row.id), label: String(row.id) }))
    .filter(row => !claimed.has(row.id));
  const referencedRow = batteries(config).find(row => String(row.id ?? '') === referenced);
  const facts = referencedRow === undefined ? '' : [
    `${factText(referencedRow.calibre_mm, NO_LABELS, c)} mm`,
    factText(referencedRow.year, NO_LABELS, c),
    factText(referencedRow.gun_type, GUN_TYPE_LABELS, c),
    factText(referencedRow.mount_type, MOUNT_TYPE_LABELS, c),
    factText(referencedRow.mount_count, NO_LABELS, c),
    factText(referencedRow.barrels_per_mount, NO_LABELS, c),
    referencedRow.shared_cradle === true ? c('concept.battery.sharedCradle') : '',
  ].filter(part => part !== '').join(' · ');

  return <div className="form-card">
    <h4>{c(groupLabel)}</h4>
    <div className="form-grid">
      <ItemSelect label={label('concept.layout.group.battery')} ariaLabel={label('concept.layout.group.battery')}
        value={batteryId} options={rows} emptyLabel={c('concept.layout.group.batteryEmpty')}
        hint={c('concept.layout.group.batteryHint')}
        onChange={next => commit(patchLayoutGroup(config, index, group,
          // Naming no row returns the group to absent, which is not an empty group.
          next === null ? null : { ...(current ?? newLayoutGroup()), battery_id: next }))} />
    </div>
    {referencedRow === undefined ? null : <>
      <p className="form-hint">{c('concept.layout.group.rowFacts', { facts })}</p>
      <div className="form-grid">
        <label className="field-label">{label('concept.layout.group.selector')}
          <select aria-label={label('concept.layout.group.selector')}
            value={typeof object(current).mount_selector === 'number'
              ? String(object(current).mount_selector) : ''}
            onChange={event => commit(patchLayoutGroup(config, index, group, {
              mount_selector: event.target.value === '' ? null : Number(event.target.value),
            }))}>
            <option value="">{c('concept.layout.group.batteryEmpty')}</option>
            {Array.from({ length: MOUNT_SELECTOR_COUNT }, (_, selector) =>
              <option key={selector} value={selector}>
                {selector} · {c(`concept.layout.selectorName.${selector}` as ConceptKey)}
              </option>)}
          </select>
          <small>{c('concept.layout.group.selectorHint')}</small>
        </label>
        <label className="field-label">{label('concept.layout.group.layoutIndex')}
          <select aria-label={label('concept.layout.group.layoutIndex')}
            value={typeof object(current).layout_index === 'number'
              ? String(object(current).layout_index) : ''}
            onChange={event => commit(patchLayoutGroup(config, index, group, {
              layout_index: event.target.value === '' ? null : Number(event.target.value),
            }))}>
            <option value="">{c('concept.layout.group.batteryEmpty')}</option>
            {Array.from({ length: LAYOUT_INDEX_COUNT }, (_, layout) =>
              <option key={layout} value={layout}>
                {layout} · {c(`concept.layout.layoutName.${layout}` as ConceptKey)}
              </option>)}
          </select>
          <small>{c('concept.layout.group.layoutHint')}</small>
        </label>
        <DeclaredNumber label={label('concept.layout.group.elevated')}
          ariaLabel={label('concept.layout.group.elevated')} kind="integer" min={0} max={1000}
          value={object(current).elevated_mounts}
          onChange={next => commit(patchLayoutGroup(config, index, group, { elevated_mounts: next }))} />
        <DeclaredNumber label={label('concept.layout.group.deck')}
          ariaLabel={label('concept.layout.group.deck')} kind="integer" min={0} max={1000}
          value={object(current).deck_mounts}
          onChange={next => commit(patchLayoutGroup(config, index, group, { deck_mounts: next }))} />
        <DeclaredNumber label={label('concept.layout.group.depressed')}
          ariaLabel={label('concept.layout.group.depressed')} kind="integer" min={0} max={1000}
          value={object(current).depressed_mounts}
          onChange={next => commit(patchLayoutGroup(config, index, group, { depressed_mounts: next }))} />
      </div>
      <p className="form-hint">{c('concept.layout.group.countHint')}</p>
      <button className="text-button" type="button"
        onClick={() => commit(patchLayoutGroup(config, index, group, null))}>
        {c('concept.layout.group.clear')}
      </button>
    </>}
  </div>;
}

/**
 * The layout's own complete two-group armour target.
 *
 * The target is an existing item of an existing system, distinct from every
 * other component's target, and it carries the same complete-armour role as a
 * single-row estimate. A referenced row that keeps its own estimate is named
 * here rather than being edited away: two models of one battery's armour would
 * weigh the same guns twice, and which of them goes is the reader's decision.
 */
function LayoutArmourBlock({ project, config, index, commit }: {
  project: ProjectDocument; config: Raw; index: number; commit: (next: Raw) => void;
}) {
  const c = useConceptCopy();
  const armour = layoutArmourOf(config, index);
  const enabled = layoutArmourEnabled(config, index);
  const leaves = systemLeaves(project.systems);
  const itemById = new Map(ledgerItems(project).map(item => [item.id, item]));
  const leaf = leaves.find(entry => entry.id === object(armour).system_id);
  const mine = object(armour).item_id;
  // An item another component already binds is not offered: the screen refuses
  // one target under two components, so this is a refused choice, not a default.
  const claimed = new Set(Object.keys(componentBindings(config)));
  const owned = stringList(leaf?.leaf.weight_item_ids)
    .map(id => itemById.get(id))
    .filter((item): item is { id: string; label: string } => item !== undefined)
    .filter(item => item.id === mine || !claimed.has(item.id));
  const conflicts = layoutArmourConflicts(config, index);

  function patch(patchValue: Raw) { commit(patchLayoutArmour(config, index, patchValue)); }

  return <div className="form-card">
    <h4>{c('concept.layout.armour.use')}</h4>
    <label className="field-label">
      <input type="checkbox" aria-label={c('concept.layout.armour.use')} checked={enabled}
        onChange={event => commit(event.target.checked
          ? addLayoutArmour(config, index) : removeLayoutArmour(config, index))} />
      {enabled ? c('concept.on') : c('concept.off')}
    </label>
    <p className="form-hint">{c('concept.layout.armour.scope')}</p>
    {/* Only an enabled complete estimate conflicts. A row's own single-group
        estimate beside layout-only readings is a legal declaration, so nothing
        is warned about until the reader actually asks for the second model of
        the same guns — and even then the row's declaration is left alone and
        the screen refuses the pair. */}
    {enabled && conflicts.length > 0 ? <p className="form-error" role="alert">
      {c('concept.layout.armour.conflict', { batteries: conflicts.join(', ') })}
    </p> : null}
    {!enabled ? null : <div className="form-grid">
      <ItemSelect label={c('concept.layout.armour.system')} ariaLabel={c('concept.layout.armour.system')}
        value={object(armour).system_id} options={leaves.map(entry => ({ id: entry.id, label: entry.id }))}
        hint={c('concept.armour.systemHint')}
        onChange={next => patch({
          system_id: next,
          // The new owner may not link the old binding, so it is cleared rather
          // than carried into a system that does not hold it.
          item_id: null,
        })} />
      <ItemSelect label={c('concept.layout.armour.item')} ariaLabel={c('concept.layout.armour.item')}
        value={object(armour).item_id} options={owned}
        hint={c('concept.layout.armour.bindingHint')}
        onChange={next => patch({ item_id: next })} />
      <QuantityField label={c('concept.layout.armour.face')} dimension="length" storedUnit="mm"
        kind="nonnegative" value={number(object(armour).face_mm)}
        hint={c('concept.layout.armour.thicknessHint')}
        onChange={next => patch({ face_mm: next })} />
      <QuantityField label={c('concept.layout.armour.side')} dimension="length" storedUnit="mm"
        kind="nonnegative" value={number(object(armour).rear_roof_mm)}
        hint={c('concept.layout.armour.thicknessHint')}
        onChange={next => patch({ rear_roof_mm: next })} />
      <QuantityField label={c('concept.layout.armour.barbette')} dimension="length" storedUnit="mm"
        kind="nonnegative" value={number(object(armour).barbette_mm)}
        hint={c('concept.layout.armour.thicknessHint')}
        onChange={next => patch({ barbette_mm: next })} />
    </div>}
  </div>;
}

export function BatteryLayoutEditor({ project, config, commit }: LayoutEditorProps) {
  const c = useConceptCopy();
  const layouts = batteryLayouts(config);
  const atLimit = layouts.length >= MAX_BATTERY_LAYOUTS;
  const duplicates = duplicateLayoutReferences(config);
  // A layout the whole-battery allocation still selects cannot be deleted and its
  // identifier cannot be repointed: either would leave a dangling reference. The
  // refusal is precise and the reader is told where to clear the reference — no
  // reference is silently cleared or moved for them.
  const allocated = new Set(allocationLayoutReferences(config));
  const [blocked, setBlocked] = useState<string | null>(null);
  // Row keys are local UI identities; an editable layout id cannot own focus.
  const rowKeys = useRef<number[]>([]);
  const nextRowKey = useRef(0);
  while (rowKeys.current.length < layouts.length) rowKeys.current.push(nextRowKey.current++);
  rowKeys.current.length = layouts.length;

  return <div className="form-card">
    <h3>{c('concept.layout.title')}</h3>
    <p>{c('concept.layout.note')}</p>
    {duplicates.length === 0 ? null : <p className="form-error" role="alert">
      {c('concept.layout.reference.duplicate', { batteries: duplicates.join(', ') })}
    </p>}
    {layouts.map((layout, index) => {
      const id = String(layout.id ?? '');
      const referenced = allocated.has(id);
      return <details className="form-card" key={rowKeys.current[index]} open>
      <summary>{String(layout.id ?? index)}</summary>
      <div className="form-card-body">
        <div className="form-grid">
          <label className="field-label">{c('concept.layout.id')}
            <input aria-label={c('concept.layout.id')} value={id}
              onChange={event => {
                const next = event.target.value;
                // A selected layout keeps its identifier: changing it would leave
                // the allocation pointing at nothing. Clear the selection there
                // first; nothing is repointed for the reader.
                if (referenced && next !== id) { setBlocked(id); return; }
                setBlocked(null);
                commit(patchBatteryLayout(config, index, { id: next }));
              }} />
            <small>{c('concept.layout.idHint')}</small>
          </label>
          <label className="field-label">{c('concept.layout.source')}
            <input aria-label={c('concept.layout.source')} value={sourceText(layout.source)}
              placeholder={c('concept.source.placeholder')}
              onChange={event => commit(patchBatteryLayout(config, index,
                { source: event.target.value.trim() === '' ? '' : event.target.value }))} />
            <small>{c('concept.layout.sourceHint')}</small>
          </label>
        </div>
        {referenced ? <p className="form-hint">{c('concept.layout.reference.allocated')}</p> : null}
        {blocked === id ? <p className="form-error" role="alert">
          {c('concept.layout.reference.allocated')}</p> : null}
        <p className="form-hint">{c('concept.layout.group.note')}</p>
        <LayoutGroupBlock config={config} index={index} group="group1"
          groupLabel="concept.layout.group1" commit={commit} />
        <LayoutGroupBlock config={config} index={index} group="group2"
          groupLabel="concept.layout.group2" commit={commit} />
        <div className="form-card">
          <h4>{c('concept.layout.flags.title')}</h4>
          <div className="form-grid">
            <TriState label={c('concept.layout.flag.elevation')} value={layout.group2_double_elevation}
              onChange={next => commit(patchBatteryLayout(config, index,
                { group2_double_elevation: next }))} />
            <TriState label={c('concept.layout.flag.depression')} value={layout.group2_double_depression}
              onChange={next => commit(patchBatteryLayout(config, index,
                { group2_double_depression: next }))} />
          </div>
          <p className="form-hint">{c('concept.layout.flag.hint')}</p>
        </div>
        <div className="form-card">
          <h4>{c('concept.layout.deck.title')}</h4>
          <p className="form-hint">{c('concept.layout.deck.note')}</p>
          <div className="form-grid">
            <DeclaredNumber label={c('concept.layout.deck.forecastle')} kind="nonnegative" min={0} max={1}
              value={deckProfileOf(config, index).forecastle_fraction}
              hint={c('concept.layout.deck.fractionHint')}
              onChange={next => commit(patchDeckProfile(config, index, { forecastle_fraction: next }))} />
            <DeclaredNumber label={c('concept.layout.deck.forwardDeck')} kind="nonnegative" min={0} max={1}
              value={deckProfileOf(config, index).forward_deck_fraction}
              hint={c('concept.layout.deck.fractionHint')}
              onChange={next => commit(patchDeckProfile(config, index, { forward_deck_fraction: next }))} />
            <QuantityField label={c('concept.layout.deck.forwardFore')} dimension="length" storedUnit="m"
              kind="nonnegative" value={number(deckProfileOf(config, index).forward_fore_m)}
              hint={c('concept.layout.deck.freeboardHint')}
              onChange={next => commit(patchDeckProfile(config, index, { forward_fore_m: next }))} />
            <QuantityField label={c('concept.layout.deck.forwardAft')} dimension="length" storedUnit="m"
              kind="nonnegative" value={number(deckProfileOf(config, index).forward_aft_m)}
              hint={c('concept.layout.deck.freeboardHint')}
              onChange={next => commit(patchDeckProfile(config, index, { forward_aft_m: next }))} />
            <QuantityField label={c('concept.layout.deck.aftFore')} dimension="length" storedUnit="m"
              kind="nonnegative" value={number(deckProfileOf(config, index).aft_fore_m)}
              hint={c('concept.layout.deck.freeboardHint')}
              onChange={next => commit(patchDeckProfile(config, index, { aft_fore_m: next }))} />
            <QuantityField label={c('concept.layout.deck.aftAft')} dimension="length" storedUnit="m"
              kind="nonnegative" value={number(deckProfileOf(config, index).aft_aft_m)}
              hint={c('concept.layout.deck.freeboardHint')}
              onChange={next => commit(patchDeckProfile(config, index, { aft_aft_m: next }))} />
          </div>
        </div>
        <LayoutArmourBlock project={project} config={config} index={index} commit={commit} />
        <button className="text-button" type="button"
          onClick={() => {
            if (referenced) { setBlocked(id); return; }
            setBlocked(null);
            rowKeys.current.splice(index, 1);
            commit(removeBatteryLayout(config, index));
          }}>
          {c('concept.layout.remove')}
        </button>
      </div>
    </details>;
    })}
    <button className="button button--secondary" type="button" disabled={atLimit}
      onClick={() => commit({ ...config, battery_layouts: [...layouts, newBatteryLayout(layouts)] })}>
      {c('concept.layout.add')}
    </button>
    {atLimit && <p className="form-hint">{c('concept.layout.max', { count: MAX_BATTERY_LAYOUTS })}</p>}
  </div>;
}

/**
 * A boolean that may also be unknown.
 *
 * Three real choices, not a checkbox: an undeclared flag is `null`, and a
 * checkbox cannot say "unknown" — it would have to guess `false`, which is the
 * one thing the recovered expression is not allowed to do.
 */
function TriState({ label, value, onChange }: {
  label: string; value: unknown; onChange: (next: boolean | null) => void;
}) {
  const c = useConceptCopy();
  return <label className="field-label">{label}
    <select aria-label={label} value={value === true ? 'true' : value === false ? 'false' : ''}
      onChange={event => onChange(event.target.value === '' ? null : event.target.value === 'true')}>
      <option value="">{c('concept.layout.flag.unknown')}</option>
      <option value="true">{c('concept.layout.flag.yes')}</option>
      <option value="false">{c('concept.layout.flag.no')}</option>
    </select>
  </label>;
}
