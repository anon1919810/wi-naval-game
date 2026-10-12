import { useState } from 'react';

import type { RunView } from '../types';
import { EstimateInput, IdPicker } from './FactInput';
import { QuantityField } from './QuantityField';
import { useUnits } from './UnitProvider';
import type { Dimension } from './units';
import { ResultSection } from './FormResults';
import { number, object, rows, sourceText, stringList, unassignedIds, uniqueId, type Raw } from './formModel';
import {
  declaredMass, declaredRows, MISC_LEAF, rowBoundIds, TYPED_FIELDS,
  templatesFor, TORPEDO_LEAF, typedProblem, typedValue,
  WEAPONS_PAGE_LEAVES, withBoundary, withRows, type WeaponsLeafId,
} from './weaponsModel';
import { useWorkspaceCopy, type WorkspaceKey } from '../i18n/workspace';

// Declared torpedo / mines / depth-charge / miscellaneous-zone inputs and the
// aggregated weapon-page rows. `null` always means "unknown" — it must never be
// coerced to 0 when saved, and unknown aggregates are never recomputed here.
//
// Ledger mass is read only from the selected loading ledger through the rows'
// `weight_item_ids`. A declared zone mass (`typed.mass_t`) is an informational
// design input shown separately; it is never added into displacement and a row
// without a binding is reported as unknown, not as 0 t.

export type Weapons = Record<string, unknown>;

interface WeaponsView {
  rows?: Array<Record<string, unknown>>;
  values?: Record<string, unknown>;
  weapons?: Record<string, unknown>;
  diagnostics?: Array<{ code?: string; message?: string; [key: string]: unknown }>;
}

function numeric(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

// Most recent run carrying a weapons page_rows view for the selected leaf.
// The aggregate values come from the backend computation — never recomputed here.
function pickWeaponsView(runs: RunView[], leafId: string): WeaponsView | null {
  const key = `weapons.${leafId}`;
  const withData = runs.filter(run => {
    const pageRows = (run.result?.stages?.systems?.data as Raw | undefined)?.page_rows;
    return !!object(pageRows)[key];
  });
  if (withData.length === 0) return null;
  const data = withData[0].result!.stages.systems!.data as Raw;
  return object(object(data.page_rows)[key]) as WeaponsView;
}

const LEAF_TITLES: Record<WeaponsLeafId, WorkspaceKey> = { torpedo: 'weapons.leaf.torpedo', misc_weight: 'weapons.leaf.misc' };

export function WeaponsEditor({ weapons, runs, ledger, onPatchLeaf }: {
  weapons: Weapons;
  runs: RunView[];
  ledger: Array<{ id: string; label?: string }>;
  onPatchLeaf: (leafId: string, next: Raw) => void;
}) {
  const w = useWorkspaceCopy();
  const available = WEAPONS_PAGE_LEAVES.filter(id => weapons[id] && typeof weapons[id] === 'object');
  const [choice, setChoice] = useState<WeaponsLeafId | null>(null);
  const leafId = (choice && available.includes(choice) ? choice : available[0]) ?? TORPEDO_LEAF;
  const leaf = object(weapons[leafId]);
  const declared = declaredRows(leaf);
  const units = useUnits();
  const [problems, setProblems] = useState<Record<string, WorkspaceKey>>({});
  const bound = rowBoundIds(declared);
  const unassigned = unassignedIds(stringList(leaf.weight_item_ids), bound);
  const leafAbsent = leaf.status === 'absent';
  const view = pickWeaponsView(runs, leafId);
  const run = runs[0] ?? null;

  function emit(next: Raw) { onPatchLeaf(leafId, next); }
  function commitRows(nextRows: Raw[], extra?: string[]) {
    const nextBound = rowBoundIds(nextRows);
    const ids = extra
      ? [...new Set([...nextBound, ...extra])]
      : [...new Set([...nextBound, ...unassignedIds(stringList(leaf.weight_item_ids), nextBound)])];
    emit(withBoundary(withRows(leaf, nextRows), ids));
  }
  function patchRow(index: number, patch: Raw) {
    commitRows(declared.map((row, i) => i === index ? { ...row, ...patch } : row));
  }
  function addRow(templateId: string) {
    const template = templatesFor(leafId).find(item => item.id === templateId) ?? templatesFor(leafId)[0];
    // `template.label` is the label stored in the project document; this page's
    // own label for the same template is `w(template.labelKey)`.
    const row: Raw = {
      row: uniqueId(template.id, declared.map(item => item.row)),
      label: template.label,
      weight_item_ids: [],
      typed: { ...template.typed },
      source: null,
      estimate: null,
    };
    commitRows([...declared, row]);
  }
  function removeRow(index: number) {
    commitRows(declared.filter((_, i) => i !== index));
  }
  function setTyped(index: number, field: string, raw: string) {
    const key = `${leafId}/${declared[index]?.row ?? index}/${field}`;
    const problem = typedProblem(field, raw, key => key) as WorkspaceKey | null;
    setProblems(previous => {
      const next = { ...previous };
      if (problem) next[key] = problem; else delete next[key];
      return next;
    });
    if (problem) return;
    patchRow(index, { typed: { ...object(declared[index].typed), [field]: typedValue(field, raw) } });
  }
  function createLeaf(id: WeaponsLeafId) {
    setChoice(id);
    setProblems({});
    onPatchLeaf(id, { weight_item_ids: [] });
  }
  function patchLeaf(patch: Raw) { emit({ ...leaf, ...patch }); }

  const templates = templatesFor(leafId);
  const [template, setTemplate] = useState(templates[0].id);

  return <div className="weapons-editor form-stack">
    <div className="form-card"><h3>{w('weapons.groups.title')}</h3>
      <p>{w('weapons.groups.intro')}</p>
      {available.length === 0 && <p className="form-hint">{w('weapons.groups.empty')}</p>}
      <div className="form-grid">
        <label className="field-label">{w('weapons.groups.current')}<select aria-label={w('weapons.groups.currentAria')} value={leafId}
          onChange={e => setChoice(e.target.value as WeaponsLeafId)}>
          {WEAPONS_PAGE_LEAVES.map(id => <option key={id} value={id} disabled={!available.includes(id)}>
            {w(LEAF_TITLES[id])}{available.includes(id) ? '' : w('weapons.groups.undeclared')}</option>)}
        </select></label>
        {!available.includes(TORPEDO_LEAF) && <button className="button button--secondary" type="button"
          onClick={() => createLeaf(TORPEDO_LEAF)}>{w('weapons.groups.addTorpedo')}</button>}
        {!available.includes(MISC_LEAF) && <button className="button button--secondary" type="button"
          onClick={() => createLeaf(MISC_LEAF)}>{w('weapons.groups.addMisc')}</button>}
      </div>
    </div>

    <div className="form-card"><h3>{w(LEAF_TITLES[leafId])}</h3>
      <p>{w('weapons.rows.note')}</p>
      {declared.length === 0 && <p className="form-hint">{w('weapons.rows.empty')}</p>}
      {declared.map((row, index) => {
        const typed = object(row.typed);
        const fields = Object.keys(typed).filter(field => field in TYPED_FIELDS);
        return <details className="form-card" open key={String(row.row ?? index)}>
          <summary>{String(row.label ?? row.row)}</summary><div className="form-card-body">
            <div className="form-grid">
              {fields.map(field => {
                const spec = TYPED_FIELDS[field];
                const label = w(spec.label);
                const key = w('weapons.row.aria', { leaf: leafId, row: String(row.row), label });
                const value = typed[field];
                const problem = problems[`${leafId}/${String(row.row)}/${field}`];
                if (!spec.dimension) return <label className="field-label" key={field}>{label}
                  <input type={spec.kind === 'text' ? 'text' : 'number'} step={spec.kind === 'integer' ? 1 : 'any'}
                    min={spec.kind === 'signed' ? undefined : 0} placeholder={w('units.unknown')} aria-label={key}
                    aria-invalid={Boolean(problem)} value={value == null ? '' : String(value)}
                    onChange={e => setTyped(index, field, e.target.value)} />
                  {problem && <span className="field-error" role="alert">{w(problem)}</span>}</label>;
                // A convertible quantity is typed in the reader's unit and stored
                // canonically; the domain is still checked on the stored value.
                return <QuantityField key={field} label={label} ariaLabel={key} value={number(value)}
                  dimension={spec.dimension} storedUnit={spec.storedUnit} kind={spec.kind === 'integer' ? 'integer' : spec.kind === 'positive' ? 'positive' : spec.kind === 'nonnegative' ? 'nonnegative' : 'signed'}
                  invalid={Boolean(problem)}
                  onChange={next => setTyped(index, field, next === null ? '' : String(next))} />;
              })}
              <label className="field-label">{w('weapons.rows.source')}<input aria-label={w('weapons.rows.sourceAria', { leaf: leafId, row: String(row.row) })}
                value={sourceText(row.source)} placeholder={w('fact.sourcePlaceholder')}
                onChange={e => patchRow(index, { source: e.target.value.trim() === '' ? null : e.target.value })} /></label>
              <EstimateInput label={w('fact.estimateAria', { label: `${leafId} ${String(row.row)}` })} value={row.estimate}
                onChange={estimate => patchRow(index, { estimate })} />
            </div>
            <IdPicker label={w('fact.bindingAria', { label: `${leafId} ${String(row.row)}` })} selected={row.weight_item_ids} options={ledger}
              onChange={ids => patchRow(index, { weight_item_ids: ids })} />
            <button className="text-button" type="button" onClick={() => removeRow(index)}>{w('weapons.rows.remove')}</button>
          </div></details>;
      })}
      <div className="form-grid">
        <label className="field-label">{w('weapons.rows.template')}<select aria-label={w('weapons.rows.templateAria')} value={template}
          onChange={e => setTemplate(e.target.value)}>
          {templates.map(item => <option key={item.id} value={item.id}>{w('weapons.rows.option', { label: w(item.labelKey), id: item.id })}</option>)}
        </select></label>
        <button className="button button--secondary" type="button" onClick={() => addRow(template)}>{w('weapons.rows.add')}</button>
      </div>
    </div>

    <div className="form-card"><h3>{w('weapons.binding.title')}</h3>
      <p>{w('weapons.binding.note')}</p>
      <IdPicker label={w('weapons.binding.unassigned')} selected={unassigned} options={ledger}
        onChange={ids => commitRows(declared, ids)} />
      <p className="form-hint">
        {leafAbsent
          ? w('weapons.binding.absentNote')
          : bound.length + unassigned.length === 0
            ? w('weapons.binding.noneNote')
            : w('weapons.binding.countNote', { count: bound.length + unassigned.length, unassigned: unassigned.length })}
      </p>
      <label className="field-label">{w('weapons.status.label')}<select aria-label={w('weapons.status.aria', { leaf: leafId })} value={leafAbsent ? 'absent' : 'present'}
        onChange={e => {
          const absent = e.target.value === 'absent';
          const next: Raw = { ...leaf, status: absent ? 'absent' : 'present' };
          if (absent) next.reason = typeof leaf.reason === 'string' && leaf.reason ? leaf.reason : w('weapons.status.reason');
          else delete next.reason;
          emit(next);
        }}>
        <option value="present">{w('weapons.status.present')}</option><option value="absent">{w('weapons.status.absent')}</option>
      </select></label>
      {leafAbsent && <label className="field-label">{w('weapons.status.reasonLabel')}<input aria-label={w('weapons.status.reasonAria', { leaf: leafId })}
        value={sourceText(leaf.reason)} placeholder={w('weapons.status.reasonPlaceholder')}
        onChange={e => patchLeaf({ reason: e.target.value.trim() === '' ? null : e.target.value })} /></label>}
    </div>

    <ResultSection available={true}>
      {view
        ? <>
          <div className="metric-grid">
            {(view.rows ?? []).map((row, index) => {
              const name = String(row.label ?? row.row ?? index);
              const mass = numeric(row.weight_t);
              const declaredValue = declaredMass(row);
              return <div key={String(row.row ?? index)} className="metric-grid">
                <ResultFact label={w('weapons.result.ledgerMass', { name })} value={mass} unit="t" dimension="mass"
                  note={row.mass_status === 'ledger_bound' ? null : w('weapons.result.unboundNote')} />
                {declaredValue !== null && <ResultFact label={w('weapons.result.declaredMass', { name })} value={declaredValue} unit="t" dimension="mass"
                  note={w('weapons.result.declaredNote')} />}
              </div>;
            })}
          </div>
          <p className="form-hint">{w('weapons.result.note')}</p>
          <Diagnostics value={view.diagnostics} />
        </>
        : <p className="section-intro">{w(leafId === MISC_LEAF ? 'weapons.result.miscEmpty' : 'weapons.result.torpedoEmpty')}</p>}
    </ResultSection>
  </div>;
}

function ResultFact({ label, value, unit, note, dimension }: {
  label: string; value: number | null; unit: string; note: string | null; dimension?: Dimension;
}) {
  const w = useWorkspaceCopy();
  const units = useUnits();
  return <div className={`fact-field fact-field--${value === null ? 'unknown' : 'known'}`}>
    <span className="fact-label">{label}</span>
    <strong className="fact-value">{value === null ? w('factField.unknown') : dimension ? units.text(value, dimension) : `${value} ${unit}`}</strong>
    <span className="fact-meta">{note ?? w('formResults.sourceRun')}</span>
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