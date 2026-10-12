import { useState } from 'react';

import type { RunView } from '../types';
import { EstimateInput, FactInput, IdPicker } from './FactInput';
import { QuantityField } from './QuantityField';
import { useUnits } from './UnitProvider';
import type { Dimension } from './units';
import { ResultSection, StudyResult } from './FormResults';
import { inputNumber, object, rows, sourceText, stringList, uniqueId, unassignedIds, type Raw } from './formModel';
import { isWeaponsPageLeaf, withBoundary, withRows } from './weaponsModel';
import { useWorkspaceCopy, type WorkspaceKey } from '../i18n/workspace';
import type { Copy } from './diagnosticGuidance';

// The guns page declares three boundary rows. The ammunition row owns the
// ship-wide outfit mass and the mounts row is the only parent of a rotating
// armour split, so both need real rows rather than an edited JSON blob.
export const GUN_PAGE_ROWS = ['guns', 'mounts', 'ammunition'] as const;
export type GunPageRow = typeof GUN_PAGE_ROWS[number];
export const GUN_ROW_LABELS: Record<GunPageRow, string> = {
  guns: '炮身', mounts: '炮座', ammunition: '弹药',
};
/**
 * The label each row is *saved* under in the project document. This is stored
 * row data rather than a translatable string on this page, so it stays one
 * fixed value in both languages; `GUN_ROW_LABEL_KEYS` below is the card's own
 * label, and the two are deliberately kept apart.
 */
export const GUN_ROW_LABEL_KEYS: Record<GunPageRow, WorkspaceKey> = {
  guns: 'guns.row.guns', mounts: 'guns.row.mounts', ammunition: 'guns.row.ammunition',
};

// Declared gun-battery inputs and the broadside shell-weight aggregate.
// `null` always means "unknown" — it must never be coerced to 0 when saved.
//
// A battery is any `systems.weapons` leaf that is not the weapons page's torpedo
// or miscellaneous-zone leaf, so a battery with declared counts and page rows is
// editable even when it declares no ammunition mass model. Without a
// `counted_ammunition_mass` model, an optional sourced projectile fact is used
// only for reporting; it never invents ammunition ledger mass.

export type GunBattery = Raw;
export type Weapons = Record<string, unknown>;

interface ShellMass {
  value: number | null; source: string | null; estimate: boolean | null;
  status?: string; origin?: string | null; mass_authority?: string | null;
}
interface GunsAggregate {
  installed_guns?: number | null; broadside_guns?: number | null; rounds_per_gun?: number | null;
  shell_mass_kg?: ShellMass;
  broadside_mass_kg?: number | null; broadside_mass_lb?: number | null; per_gun_shell_kg?: number | null;
  ship_wide_ammunition_t?: number | null; ledger_mass_t?: number | null;
  status?: string; formula?: string; shell_mass_boundary?: string;
  diagnostics?: Array<{ code?: string; message?: string; [key: string]: unknown }>;
}
interface BatteryView { guns?: GunsAggregate; rotating_armour_component?: Raw; rows?: Raw[] }

function numeric(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function pickBatteryView(runs: RunView[], batteryId: string): BatteryView | null {
  const key = `weapons.${batteryId}`;
  const withData = runs.filter(run => !!object(object(run.result?.stages?.systems?.data as Raw | undefined).page_rows)[key]);
  if (withData.length === 0) return null;
  const data = withData[0].result!.stages.systems!.data as Raw;
  return object(object(data.page_rows)[key]) as BatteryView;
}

function findAmmoModel(battery: GunBattery | null): { index: number; model: GunBattery } | null {
  if (!battery || !Array.isArray(battery.mass_models)) return null;
  const models = battery.mass_models as GunBattery[];
  const index = models.findIndex(m => !!m && typeof m === 'object' && m.method === 'counted_ammunition_mass');
  return index < 0 ? null : { index, model: models[index] };
}

function readProjectile(battery: GunBattery | null): { value: number | null; source: string | null; estimate: boolean | null } {
  const found = findAmmoModel(battery);
  if (!found) return { value: null, source: null, estimate: null };
  const inputs = object(found.model.inputs);
  const provenance = object(object(found.model.input_provenance).projectile_mass_kg);
  return {
    value: numeric(inputs.projectile_mass_kg),
    source: typeof provenance.source === 'string' ? provenance.source : null,
    estimate: provenance.estimate === true ? true : provenance.estimate === false ? false : null,
  };
}

// The core reads an installed count with `_count`, which rejects null outright;
// an unknown count is therefore expressed by omitting the key, never by null or 0.
function countProblem(raw: string): WorkspaceKey | null {
  if (raw.trim() === '') return null;
  const value = Number(raw);
  if (!Number.isFinite(value)) return 'units.finiteRequired';
  return Number.isInteger(value) && value >= 0 ? null : 'guns.count.problem';
}

export function GunsEditor({ weapons, runs, ledger, onPatchBattery }: {
  weapons: Weapons;
  runs: RunView[];
  ledger: Array<{ id: string; label?: string }>;
  onPatchBattery: (id: string, next: GunBattery) => void;
}) {
  const w = useWorkspaceCopy();
  const batteryIds = Object.keys(weapons).filter(id => !isWeaponsPageLeaf(id)
    && !!weapons[id] && typeof weapons[id] === 'object' && !Array.isArray(weapons[id]));
  const [choice, setChoice] = useState<string | null>(null);
  const batteryId = (choice && batteryIds.includes(choice) ? choice : batteryIds[0]) ?? '';
  const battery = batteryId ? object(weapons[batteryId]) : {};
  const view = pickBatteryView(runs, batteryId);
  const agg = view?.guns ?? null;
  const hasAmmo = findAmmoModel(battery) !== null;
  const projectile = readProjectile(battery);
  // Reporting-only declaration, used by page_rows.guns_view only when the
  // battery declares no ammunition mass model. See page_rows.guns_rows.
  const facts = object(battery.facts);
  const declaredFact = object(facts.projectile_mass_kg);
  const [problems, setProblems] = useState<Record<string, WorkspaceKey>>({});
  const [newId, setNewId] = useState('battery_1');
  const [rowTemplate, setRowTemplate] = useState<GunPageRow>('guns');
  const declaredRows = rows(battery.page_rows);
  // The core reads fixed row names, so only the categories still missing are
  // offered; a numbered duplicate like `guns_2` would be unsupported.
  const missingRows = GUN_PAGE_ROWS.filter(row => !declaredRows.some(entry => entry.row === row));
  const boundIds = [...new Set(declaredRows.flatMap(row => stringList(row.weight_item_ids)))];
  const unassigned = unassignedIds(stringList(battery.weight_item_ids), boundIds);
  const run = runs[0] ?? null;

  function emit(next: GunBattery) { onPatchBattery(batteryId, next); }
  function setCount(key: 'installed_guns' | 'broadside_guns' | 'rounds_per_gun', raw: string) {
    const problem = countProblem(raw);
    setProblems(previous => {
      const next = { ...previous };
      if (problem) next[key] = problem; else delete next[key];
      return next;
    });
    if (problem) return;
    const next = { ...battery };
    if (raw.trim() === '') delete next[key];
    else next[key] = Number(raw);
    emit(next);
  }
  function updateProjectile(value: number | null, patch: { source?: string | null; estimate?: boolean | null }) {
    const found = findAmmoModel(battery);
    if (!found) return;
    const models = (battery.mass_models as GunBattery[]).map(m => ({ ...m }));
    const model = { ...models[found.index] };
    model.inputs = { ...object(model.inputs), projectile_mass_kg: value };
    const provenance = { ...object(model.input_provenance) };
    const entry = { ...object(provenance.projectile_mass_kg) };
    if (patch.source !== undefined) entry.source = patch.source;
    if (patch.estimate !== undefined) entry.estimate = patch.estimate;
    provenance.projectile_mass_kg = entry;
    model.input_provenance = provenance;
    models[found.index] = model;
    emit({ ...battery, mass_models: models });
  }
  function patchFact(fact: Raw) {
    const next = { ...battery };
    // Remove only this declaration; any other declared fact on the battery stays.
    const rest = { ...facts };
    if (fact.value == null && fact.source == null && fact.estimate == null) delete rest.projectile_mass_kg;
    else rest.projectile_mass_kg = fact;
    if (Object.keys(rest).length === 0) delete next.facts; else next.facts = rest;
    emit(next);
  }
  function createBattery() {
    const id = uniqueId(newId.trim() || 'battery_1', batteryIds);
    setChoice(id);
    setProblems({});
    onPatchBattery(id, { weight_item_ids: [], source: null, estimate: null });
  }
  // Page rows are written and removed as a set: the leaf boundary stays the union
  // of its rows plus whatever remains unassigned, so an edit never silently
  // drops an unrelated binding.
  function commitRows(nextRows: Raw[], extra?: string[]) {
    const nextBound = [...new Set(nextRows.flatMap(row => stringList(row.weight_item_ids)))];
    const ids = extra ? [...new Set([...nextBound, ...extra])]
      : [...new Set([...nextBound, ...unassignedIds(stringList(battery.weight_item_ids), nextBound)])];
    emit(withRows(withBoundary(battery, ids), nextRows));
  }
  function patchRow(index: number, patch: Raw) { commitRows(declaredRows.map((row, i) => i === index ? { ...row, ...patch } : row)); }
  function addRow() {
    if (!missingRows.includes(rowTemplate)) return;
    const row: Raw = { row: rowTemplate, label: GUN_ROW_LABELS[rowTemplate],
      weight_item_ids: [], typed: { count: null, kind: null }, source: null, estimate: null };
    commitRows([...declaredRows, row]);
    setRowTemplate(missingRows.find(candidate => candidate !== rowTemplate) ?? rowTemplate);
  }
  function removeRow(index: number) { commitRows(declaredRows.filter((_, i) => i !== index)); }

  return <div className="guns-editor form-stack">
    <div className="form-card"><h3>{w('guns.title')}</h3>
      <p>{w('guns.intro')}</p>
      {batteryIds.length === 0 && <p className="form-hint">{w('guns.empty')}</p>}
      <div className="form-grid">
        <label className="field-label">{w('guns.current')}<select aria-label={w('guns.currentAria')} value={batteryId}
          onChange={e => setChoice(e.target.value)}>
          {batteryIds.length === 0 && <option value="">{w('guns.none')}</option>}
          {batteryIds.map(id => <option key={id} value={id}>{id}</option>)}
        </select></label>
        <label className="field-label">{w('guns.newId')}<input aria-label={w('guns.newIdAria')} value={newId}
          onChange={e => setNewId(e.target.value)} /></label>
        <button className="button button--secondary" type="button" onClick={createBattery}>{w('guns.add')}</button>
      </div>
    </div>

    {batteryId && <>
      <div className="form-card"><h3>{w('guns.declared.title', { id: batteryId })}</h3>
        <div className="form-grid">
          {([['installed_guns', 'guns.installed'], ['broadside_guns', 'guns.broadside'], ['rounds_per_gun', 'guns.roundsPerGun']] as const).map(([key, labelKey]) => {
            const label = w(labelKey);
            const problem = problems[key];
            return <label className="field-label" key={key}>{label}
              <input type="number" step="1" min="0" placeholder={w('units.unknown')} aria-label={w('guns.countAria', { id: batteryId, label })}
                aria-invalid={Boolean(problem)} value={numeric(battery[key]) ?? ''}
                onChange={e => setCount(key, e.target.value)} />
              {problem && <span className="field-error" role="alert">{w(problem)}</span>}</label>;
          })}
        </div>
        <p className="form-hint">{w('guns.countHint')}</p>
        {hasAmmo && <p className="form-hint">{w('guns.ammoHint')}</p>}
      </div>

      <div className="form-card"><h3>{w('guns.shell.title')}</h3>
        {hasAmmo ? <div className="form-grid">
          {/* The ammunition model is stored in kilograms; the reader sees the
              preferred mass unit and typing converts back to kilograms. */}
          <QuantityField label={w('guns.shell.mass')} aria-label={w('guns.shell.massAria', { id: batteryId })} value={projectile.value} dimension="mass" storedUnit="kg" kind="nonnegative"
            onChange={value => updateProjectile(value, {})} />
          <label className="field-label">{w('fact.source')}<input aria-label={w('guns.shell.sourceAria', { id: batteryId })} placeholder={w('fact.sourcePlaceholder')}
            value={projectile.source ?? ''}
            onChange={e => updateProjectile(projectile.value, { source: e.target.value.trim() === '' ? null : e.target.value })} /></label>
          <EstimateInput label={w('fact.estimateAria', { label: w('guns.shell.mass') })} value={projectile.estimate}
            onChange={estimate => updateProjectile(projectile.value, { estimate })} />
        </div> : <div className="form-card-body">
          <p className="section-intro">{w('guns.shell.fallback')}</p>
          <FactInput label={w('guns.shell.reportOnly', { id: batteryId })} value={declaredFact} dimension="mass" storedUnit="kg"
            onChange={f => patchFact({ value: f.value, source: f.source, estimate: f.estimate })} />
        </div>}
      </div>

      <div className="form-card"><h3>{w('guns.binding.title')}</h3>
        <p>{w('guns.binding.note')}</p>
        <IdPicker label={w('guns.binding.entry', { id: batteryId })} selected={battery.weight_item_ids} options={ledger}
          onChange={ids => emit({ ...battery, weight_item_ids: ids })} />
        <p className="form-hint">
          {stringList(battery.weight_item_ids).length === 0
            ? w('guns.binding.none')
            : w('guns.binding.count', { count: stringList(battery.weight_item_ids).length })}
        </p>
      </div>

      <div className="form-card"><h3>{w('guns.rows.title')}</h3>
        <p>{w('guns.rows.note')}</p>
        {declaredRows.length === 0 && <p className="form-hint">{w('guns.rows.empty')}</p>}
        {declaredRows.map((row, index) => <div className="form-grid" key={String(row.row ?? index)}>
          <label className="field-label">{w('guns.rows.id')}<input aria-label={w('guns.rows.idAria', { id: batteryId, row: String(row.row) })} value={String(row.row ?? '')} readOnly /></label>
          <label className="field-label">{w('guns.rows.count')}<input type="number" step="1" min="0" placeholder={w('units.unknown')}
            aria-label={w('guns.rows.countAria', { id: batteryId, row: String(row.row) })} value={numeric(object(row.typed).count) ?? ''}
            onChange={event => patchRow(index, { typed: { ...object(row.typed), count: inputNumber(event.target.value) } })} /></label>
          <label className="field-label">{w('guns.rows.kind')}<input aria-label={w('guns.rows.kindAria', { id: batteryId, row: String(row.row) })}
            placeholder={w('units.unknown')} value={String(object(row.typed).kind ?? '')}
            onChange={event => patchRow(index, { typed: { ...object(row.typed), kind: event.target.value.trim() === '' ? null : event.target.value } })} /></label>
          <label className="field-label">{w('guns.rows.source')}<input aria-label={w('guns.rows.sourceAria', { id: batteryId, row: String(row.row) })} placeholder={w('fact.sourcePlaceholder')}
            value={sourceText(row.source)}
            onChange={event => patchRow(index, { source: event.target.value.trim() === '' ? null : event.target.value })} /></label>
          <EstimateInput label={w('fact.estimateAria', { label: `${batteryId} ${String(row.row)}` })} value={row.estimate}
            onChange={estimate => patchRow(index, { estimate })} />
          <IdPicker label={w('fact.bindingAria', { label: `${batteryId} ${String(row.row)}` })} selected={row.weight_item_ids} options={ledger}
            onChange={ids => patchRow(index, { weight_item_ids: ids })} />
          <button className="text-button" type="button" onClick={() => removeRow(index)}>
            {w('guns.rows.remove', { row: String(row.row), note: row.row === 'ammunition' ? w('guns.rows.removeNote') : '' })}</button>
        </div>)}
        <div className="form-grid">
          <label className="field-label">{w('guns.rows.new')}<select aria-label={w('guns.rows.newAria', { id: batteryId })} value={rowTemplate}
            onChange={event => setRowTemplate(event.target.value as GunPageRow)}>
            {GUN_PAGE_ROWS.filter(row => missingRows.includes(row)).map(row => <option key={row} value={row}>{w('guns.rows.option', { row, label: w(GUN_ROW_LABEL_KEYS[row]) })}</option>)}
            {missingRows.length === 0 && <option value="">{w('guns.rows.allDeclared')}</option>}
          </select></label>
          <button className="button button--secondary" type="button" onClick={addRow} disabled={missingRows.length === 0}>{w('guns.rows.add')}</button>
        </div>
        <p className="form-hint">{w('guns.rows.footnote')}</p>
      </div>
    </>}

    <ResultSection available={true}>
      {agg
        ? <>
          <div className="metric-grid">
            <ResultFact label={w('guns.result.shellMass')} value={numeric(agg.shell_mass_kg?.value)} unit="kg" dimension="mass"
              note={numeric(agg.shell_mass_kg?.value) === null ? w('guns.note.shellUnknown')
                : agg.shell_mass_kg?.origin === 'declared_projectile_mass_kg_fact' ? w('guns.note.declaredFact') : w('guns.note.fromModel')}
              status={numeric(agg.shell_mass_kg?.value) === null ? 'unknown' : agg.shell_mass_kg?.estimate ? 'estimate' : 'known'} />
            {/* Derived weights inherit the shell's estimate state: an estimated
                projectile mass yields estimated broadside/per-gun weights. */}
            <ResultFact label={w('guns.result.broadside')} value={numeric(agg.broadside_mass_kg)} unit="kg" dimension="mass"
              note={numeric(agg.broadside_mass_kg) === null ? w('guns.note.broadsideUnknown') : w('guns.note.noCharge')}
              estimate={agg.shell_mass_kg?.estimate} />
            <ResultFact label={w('guns.result.perGun')} value={numeric(agg.per_gun_shell_kg)} unit="kg" dimension="mass"
              note={numeric(agg.per_gun_shell_kg) === null ? w('guns.note.perGunUnknown') : w('guns.note.noChargeShort')}
              estimate={agg.shell_mass_kg?.estimate} />
            <ResultFact label={w('guns.result.shipWide')} value={numeric(agg.ship_wide_ammunition_t)} unit="t" dimension="mass" note={w('guns.note.ledgerCarried')} />
            <ResultFact label={w('guns.result.ledgerMass')} value={numeric(agg.ledger_mass_t)} unit="t" dimension="mass" note={w('guns.note.ledger')} />
          </div>
          <p className="form-hint">{w('guns.result.formula', { boundary: String(agg.shell_mass_boundary ?? '') })}</p>
          <Diagnostics value={agg.diagnostics} />
        </>
        : <p className="section-intro">{w('guns.result.empty')}</p>}
      <StudyResult label={w('guns.result.rotating', { id: batteryId || w('guns.label.battery') })} data={view?.rotating_armour_component}
        metrics={[['rotating_armour_mass_t', w('armour.result.rotating'), 't', 'mass'], ['other_mount_mass_t', w('armour.result.otherMount'), 't', 'mass']]} />
    </ResultSection>
  </div>;
}

function ResultFact({ label, value, unit, note, status, estimate, dimension }: {
  label: string; value: number | null; unit: string; note: string;
  status?: 'known' | 'estimate' | 'unknown'; estimate?: boolean | null; dimension?: Dimension;
}) {
  const w = useWorkspaceCopy();
  const units = useUnits();
  const resolved = value === null ? 'unknown' : status ?? (estimate === true ? 'estimate' : 'known');
  return <div className={`fact-field fact-field--${resolved}`}>
    <span className="fact-label">{label}</span>
    <strong className="fact-value">{value === null ? w('factField.unknown') : dimension ? units.text(value, dimension, unit) : `${value} ${unit}`}</strong>
    <span className="fact-meta">{resolved === 'estimate' ? w('factField.estimatePrefix') : ''}{note}</span>
  </div>;
}

function Diagnostics({ value }: { value: unknown }) {
  const w = useWorkspaceCopy();
  const items = rows(value);
  if (items.length === 0) return null;
  return <ul className="diagnostics-list">
    {items.map((item, index) => <li key={index}><code>{String(item.code ?? w('report.diagnostics.fallback'))}</code>{item.message ? w('report.fact', { label: String(item.message) }) : ''}</li>)}
  </ul>;
}
