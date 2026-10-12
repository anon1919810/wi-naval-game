import { useState } from 'react';

import type { ProjectDocument, RunView } from '../types';
import { EstimateInput } from './FactInput';
import { QuantityField } from './QuantityField';
import { useUnits } from './UnitProvider';
import { Diagnostics, ResultSection } from './FormResults';
import { number, object, rows, sourceText, stageData, stringList, uniqueId, type Raw } from './formModel';
import {
  COUNT_FIELDS, MASS_METHODS, methodSpec, modelHints, modelInputs, modelList, modelProvenance,
  newModel, patchInputProvenance, patchModelInput, patchTextInput, ROUNDS_FIELD, systemLeaves,
  textInputsFor, toleranceValue, type ModelField, type SystemLeaf,
} from './massModels';
import { useWorkspaceCopy, type WorkspaceKey } from '../i18n/workspace';

// Physical mass models compare a declared formula against the selected loading
// ledger. This editor never computes a mass and never writes one: the ledger
// stays the only mass authority, and a difference is only a review-required
// proposal in the saved result.

export function MassModelEditor({ project, run, onChange }: {
  project: ProjectDocument; run: RunView | null; onChange: (project: ProjectDocument) => void;
}) {
  const w = useWorkspaceCopy();
  const units = useUnits();
  const systems = object(project.systems);
  const leaves = systemLeaves(systems);
  const [choice, setChoice] = useState<string | null>(null);
  const [method, setMethod] = useState<string>(MASS_METHODS[0].id);
  const [newId, setNewId] = useState('model_1');
  const [problems, setProblems] = useState<Record<string, WorkspaceKey>>({});
  const leaf: SystemLeaf | null = leaves.find(item => item.id === choice) ?? leaves[0] ?? null;
  const summary = object(object(stageData(run, 'systems')).systems);
  const result = leaf ? object(summary[leaf.id]) : {};

  // The leaf is addressed by its declared path, so armour.fixed, propulsion and
  // weapons.<battery> are all edited in place without touching siblings.
  function patchLeaf(next: Raw) {
    if (!leaf) return;
    const clone = structuredClone(systems) as Raw;
    let cursor = clone;
    for (const key of leaf.labels.slice(0, -1)) cursor = object(cursor[key]);
    const last = leaf.labels[leaf.labels.length - 1];
    cursor[last] = { ...object(cursor[last]), ...next };
    onChange({ ...project, systems: clone });
  }
  function patchModels(models: Raw[]) { patchLeaf({ ...leaf?.leaf, mass_models: models }); }

  function create() {
    if (!leaf) return;
    const id = uniqueId(newId.trim() || 'model_1', modelList(leaf.leaf).map(model => model.id));
    patchModels([...modelList(leaf.leaf), newModel(id, method, stringList(leaf.leaf.weight_item_ids)[0] ?? null)]);
  }

  if (!leaf) {
    return <div className="form-card"><h3>{w('massModel.empty.title')}</h3>
      <p>{w('massModel.empty.note')}</p>
      <p className="form-hint">{w('massModel.empty.hint')}</p>
    </div>;
  }

  const models = modelList(leaf.leaf);
  return <div className="mass-model-editor form-stack">
    <div className="form-card"><h3>{w('massModel.select.title')}</h3>
      <p>{w('massModel.select.note')}</p>
      <div className="form-grid">
        <label className="field-label">{w('massModel.select.current')}<select aria-label={w('massModel.select.currentAria')} value={leaf.id} onChange={event => setChoice(event.target.value)}>
          {leaves.map(item => <option key={item.id} value={item.id}>{item.id}</option>)}
        </select></label>
        <label className="field-label">{w('massModel.select.ledger')}<input aria-label={w('massModel.select.ledgerAria', { id: leaf.id })} readOnly
          value={stringList(leaf.leaf.weight_item_ids).join(', ') || w('massModel.select.unbound')} /></label>
      </div>
      {stringList(leaf.leaf.weight_item_ids).length === 0
        && <p className="form-hint">{w('massModel.select.hint')}</p>}
    </div>

    {models.map((model, index) => {
      const spec = methodSpec(model.method);
      const hints = modelHints(model, leaf.leaf, w);
      const inputs = modelInputs(model);
      const provenance = modelProvenance(model);
      const tolerance = object(model.comparison_tolerance);
      function patchModel(value: Raw) { patchModels(models.map((row, i) => i === index ? { ...row, ...value } : row)); }
      function field(input: ModelField) {
        const problem = problems[`${model.id}/${input.key}`];
        const inputLabel = w(input.label);
        // A density or other canonical quantity keeps a plain input; a geometry or
        // mass input is typed in the reader's unit and stored canonically.
        const valueControl = input.dimension
          ? <QuantityField label={inputLabel} ariaLabel={w('fact.valueAria', { label: `${model.id} ${inputLabel}` })} value={number(inputs[input.key])}
            dimension={input.dimension} storedUnit={input.storedUnit} kind={input.kind} invalid={Boolean(problem)}
            onChange={next => patchModel({ inputs: { ...inputs, [input.key]: next } })} />
          : <label className="field-label">{inputLabel}
            <input type="number" step="any" placeholder={w('units.unknown')} aria-label={`${model.id} ${inputLabel}`}
              aria-invalid={Boolean(problem)} value={number(inputs[input.key]) ?? ''}
              onChange={event => {
                const outcome = patchModelInput(model, input, event.target.value, key => key);
                setProblems(previous => {
                  const next = { ...previous };
                  const key = `${model.id}/${input.key}`;
                  if (outcome.problem) next[key] = outcome.problem as WorkspaceKey; else delete next[key];
                  return next;
                });
                if (!outcome.problem) patchModel(outcome.model);
              }} />
            {problem && <span className="field-error" role="alert">{w(problem)}</span>}
          </label>;
        return <div className="form-grid" key={input.key}>
          {valueControl}
          <label className="field-label">{w('fact.source')}<input aria-label={w('fact.sourceAria', { label: `${model.id} ${inputLabel}` })} placeholder={w('fact.sourcePlaceholder')}
            value={sourceText(object(provenance[input.key]).source)}
            onChange={event => patchModel(patchInputProvenance(model, input.key, { source: event.target.value.trim() === '' ? null : event.target.value }))} /></label>
          <EstimateInput label={w('fact.estimateAria', { label: `${model.id} ${inputLabel}` })} value={object(provenance[input.key]).estimate}
            onChange={estimate => patchModel(patchInputProvenance(model, input.key, { estimate }))} />
        </div>;
      }
      return <details className="form-card" open key={String(model.id)}>
        <summary>{String(model.id)} · {String(model.method)}</summary><div className="form-card-body">
          <div className="form-grid">
            <label className="field-label">{w('massModel.method.label')}<select aria-label={w('massModel.method.aria', { id: String(model.id) })} value={String(model.method)}
              onChange={event => { const linked = model.linked_weight_item_id;
              const next = newModel(String(model.id), event.target.value, typeof linked === 'string' ? linked : null);
                next.comparison_tolerance = tolerance;
                next.source = model.source ?? null;
                next.estimate = model.estimate ?? null;
                next.input_provenance = provenance;
                patchModel(next); }}>
              {MASS_METHODS.map(entry => <option key={entry.id} value={entry.id}>{w('massModel.method.option', { label: w(entry.label), id: entry.id })}</option>)}
            </select></label>
            <label className="field-label">{w('massModel.binding.label')}<select aria-label={w('massModel.binding.aria', { id: String(model.id) })} value={String(model.linked_weight_item_id ?? '')}
              onChange={event => patchModel({ linked_weight_item_id: event.target.value === '' ? null : event.target.value })}>
              <option value="">{w('massModel.binding.pick')}</option>
              {stringList(leaf.leaf.weight_item_ids).map(item => <option key={item} value={item}>{item}</option>)}
            </select></label>
            <label className="field-label">{w('massModel.source.label')}<input aria-label={w('massModel.source.aria', { id: String(model.id) })} value={sourceText(model.source)} placeholder={w('fact.sourcePlaceholder')}
              onChange={event => patchModel({ source: event.target.value.trim() === '' ? null : event.target.value })} /></label>
            <EstimateInput label={w('fact.estimateAria', { label: String(model.id) })} value={model.estimate} onChange={estimate => patchModel({ estimate })} />
            <label className="field-label">{w('massModel.boundary.label')}<input aria-label={w('massModel.boundary.aria', { id: String(model.id) })} value={typeof model.boundary === 'string' ? model.boundary : ''}
              placeholder={w('massModel.boundary.placeholder')} onChange={event => patchModel({ boundary: event.target.value.trim() === '' ? undefined : event.target.value })} /></label>
          </div>
          <h4>{w('massModel.inputs.title')}</h4>
          {(spec?.fields ?? []).map(field)}
          {/* Count and rounds inputs are declared inputs too, so an estimated
              model needs their own source and estimate flag. */}
          {textInputsFor(String(model.method)).map(input => {
            const entry = object(provenance[input.key]);
            const inputLabel = w(input.label);
            return <div className="form-grid" key={input.key}>
              <label className="field-label">{inputLabel}
                <input aria-label={`${model.id} ${inputLabel}`} placeholder={w('massModel.inputs.undeclared')} readOnly={input.key === 'rounds_field'}
                  value={String(inputs[input.key] ?? '')}
                  onChange={event => patchModel(patchTextInput(model, input.key, event.target.value.trim()))} />
              </label>
              <label className="field-label">{w('fact.source')}<input aria-label={w('fact.sourceAria', { label: `${model.id} ${inputLabel}` })} placeholder={w('fact.sourcePlaceholder')}
                value={sourceText(entry.source)}
                onChange={event => patchModel(patchInputProvenance(model, input.key, { source: event.target.value.trim() === '' ? null : event.target.value }))} /></label>
              <EstimateInput label={w('fact.estimateAria', { label: `${model.id} ${inputLabel}` })} value={entry.estimate}
                onChange={estimate => patchModel(patchInputProvenance(model, input.key, { estimate }))} />
            </div>;
          })}
          {spec?.counted && <div className="form-grid">
            <label className="field-label">{w('massModel.count.label')}<select aria-label={w('massModel.count.aria', { id: String(model.id) })}
              value={'count_field' in inputs ? 'field' : 'count_value' in inputs ? 'value' : ''}
              onChange={event => {
                const next = { ...inputs };
                if (event.target.value === 'field') { delete next.count_value; delete next.count_basis; next.count_field = COUNT_FIELDS[0].id; }
                // Unknown stays unknown: a self-declared count starts empty rather
                // than at an invented known zero.
                else { delete next.count_field; next.count_value = null; next.count_basis = ''; }
                patchModel({ inputs: next });
              }}>
              <option value="">{w('massModel.count.undeclared')}</option>
              <option value="field">{w('massModel.count.fromField')}</option>
              <option value="value">{w('massModel.count.ownValue')}</option>
            </select></label>
            {'count_field' in inputs && <label className="field-label">{w('massModel.count.field')}<select aria-label={w('massModel.count.fieldAria', { id: String(model.id) })} value={String(inputs.count_field ?? '')}
              onChange={event => patchModel({ inputs: { ...inputs, count_field: event.target.value } })}>
              {COUNT_FIELDS.map(field => <option key={field.id} value={field.id}>{w(field.label)}</option>)}
            </select></label>}
            {'count_value' in inputs && <>
              {field({ key: 'count_value', label: 'massModel.field.count', kind: 'integer' })}
              <label className="field-label">{w('massModel.count.basis')}<input aria-label={w('massModel.count.basisAria', { id: String(model.id) })} value={sourceText(inputs.count_basis)} placeholder={w('massModel.count.basisPlaceholder')}
                onChange={event => patchModel({ inputs: { ...inputs, count_basis: event.target.value } })} /></label>
            </>}
            {spec.ammunition && <p className="form-hint">{w('massModel.count.ammunition', { field: ROUNDS_FIELD })}</p>}
          </div>}
          <h4>{w('massModel.tolerance.title')}</h4>
          <div className="form-grid">
            {/* The relative tolerance is a dimensionless ratio. */}
            <label className="field-label">{w('massModel.tolerance.relative')}<input type="number" step="any" min="0" placeholder={w('form.required')} aria-label={w('massModel.tolerance.relativeAria', { id: String(model.id) })} value={number(tolerance.relative) ?? ''}
              onChange={event => patchModel(toleranceValue(model, 'relative', event.target.value))} /></label>
            <QuantityField label={w('massModel.tolerance.absolute')} aria-label={`${model.id} ${w('massModel.tolerance.absolute')}`} value={number(tolerance.absolute_t)} dimension="mass" storedUnit="t" kind="nonnegative"
              onChange={value => patchModel(toleranceValue(model, 'absolute_t', value === null ? '' : String(value)))} />
          </div>
          {hints.length > 0 && <p className="form-hint" role="status">{w('massModel.hints', { hints: hints.join(w('form.listSeparator')) })}</p>}
          <button className="text-button" type="button" onClick={() => patchModels(models.filter((_, i) => i !== index))}>{w('massModel.remove', { id: String(model.id) })}</button>
        </div></details>;
    })}

    <div className="form-card"><h3>{w('massModel.add.title')}</h3>
      <div className="form-grid">
        <label className="field-label">{w('massModel.method.label')}<select aria-label={w('massModel.method.addAria')} value={method} onChange={event => setMethod(event.target.value)}>
          {MASS_METHODS.map(entry => <option key={entry.id} value={entry.id}>{w('massModel.method.option', { label: w(entry.label), id: entry.id })}</option>)}
        </select></label>
        <label className="field-label">{w('massModel.add.id')}<input aria-label={w('massModel.add.idAria')} value={newId} onChange={event => setNewId(event.target.value)} /></label>
        <button className="button button--secondary" type="button" onClick={create} disabled={stringList(leaf.leaf.weight_item_ids).length === 0}>{w('massModel.add.action')}</button>
      </div>
      <p className="form-hint">{w('massModel.add.note')}</p>
    </div>

    <ResultSection available={!!run}>
      {rows(result.mass_models).length === 0 ? <p className="section-intro">{w('massModel.result.empty')}</p> : <>
        <div className="stage-table-scroll"><table className="stage-table"><caption>{w('massModel.result.caption', { id: leaf.id })}</caption>
          <thead><tr><th>{w('massModel.result.thModel')}</th><th>{w('massModel.result.thFormula')}</th><th>{w('massModel.result.thLedger')}</th><th>{w('massModel.result.thCalculated')}</th><th>{w('massModel.result.thDifference')}</th><th>{w('massModel.result.thTolerance')}</th><th>{w('massModel.result.thNature')}</th></tr></thead>
          <tbody>{rows(result.mass_models).map((check, index) => <tr key={String(check.id ?? index)}>
            <td>{String(check.id ?? index)}</td>
            <td>{String(check.formula ?? '—')}</td>
            <td>{units.text(check.ledger_mass_t, 'mass')}</td>
            <td>{units.text(check.calculated_mass_t, 'mass')}</td>
            <td>{units.text(check.difference_t, 'mass')}</td>
            <td>{units.text(check.comparison_tolerance_t, 'mass')}</td>
            <td>{check.estimate === true ? w('reading.estimate') : w('reading.notEstimate')}{typeof check.source === 'string' ? ` · ${check.source}` : ''}</td>
          </tr>)}</tbody></table></div>
        <p className="form-hint">{w('massModel.result.note')}</p>
        <Diagnostics value={result.diagnostics} />
      </>}
    </ResultSection>
  </div>;
}