import { useState } from 'react';

import type { ProjectDocument } from '../types';
import { EstimateInput, FactInput } from './FactInput';
import { QuantityField } from './QuantityField';
import { number, numericProblem, numericValue, object, rows, uniqueId, type Raw } from './formModel';
import {
  addAppendage, appendages, APPENDAGE_AREA, APPENDAGE_FACTOR, ATTITUDE_POLICIES, bowThruster,
  FRICTION_METHOD, INTERPOLATION_METHOD, newScenario, patchAppendage, patchInput, patchInputValue, patchProvenance,
  patchThruster, presenceState, removeAppendage, RESISTANCE_INPUTS, RESISTANCE_METHODS, scenarioHints,
  scenarioSource, setPresence, SPEED_CONVERSION_METHOD, THRUSTER_COEFFICIENT, THRUSTER_DIAMETER,
  type InputSpec, type PresenceState, type StructuredKey,
} from './resistanceModel';
import { useWorkspaceCopy, type WorkspaceKey } from '../i18n/workspace';

// Named resistance scenarios are research inputs, not computed results. Every
// declared input carries its own source and three-state estimate; unknown stays
// unknown, and explicit absence (`[]`, `present: false`) differs from an omitted
// key. Nothing here fabricates bulb, transom, appendage, thruster or roughness
// geometry, and no method outside the two canonical ones is offered.

const TABLE_METHODS = [
  { key: 'friction_method', label: 'resistance.table.friction' as WorkspaceKey, value: FRICTION_METHOD },
  { key: 'interpolation_method', label: 'resistance.table.interpolation' as WorkspaceKey, value: INTERPOLATION_METHOD },
  { key: 'speed_conversion_method', label: 'resistance.table.speedConversion' as WorkspaceKey, value: SPEED_CONVERSION_METHOD },
] as const;

export function ResistanceEditor({ project, onChange }: {
  project: ProjectDocument; onChange: (project: ProjectDocument) => void;
}) {
  const w = useWorkspaceCopy();
  const scenarios = rows(project.resistance_scenarios);
  const [choice, setChoice] = useState<string | null>(null);
  const [problems, setProblems] = useState<Record<string, WorkspaceKey>>({});
  const [newId, setNewId] = useState('scenario_1');
  const selected = scenarios.find(row => String(row.id) === choice) ?? scenarios[0] ?? null;
  const id = selected ? String(selected.id) : '';

  function emit(list: Raw[]) { onChange({ ...project, resistance_scenarios: list }); }
  function patch(value: Raw) { if (selected) emit(scenarios.map(row => row === selected ? { ...row, ...value } : row)); }
  function replace(next: Raw) { if (selected) emit(scenarios.map(row => row === selected ? next : row)); }
  function create() {
    const next = uniqueId(newId.trim() || 'scenario_1', scenarios.map(row => row.id));
    setChoice(next);
    setProblems({});
    emit([...scenarios, newScenario(next)]);
  }

  // A refused value is never written, so the draft cannot carry an
  // out-of-domain number into the schema validator.
  function scalar(spec: InputSpec, raw: string): Raw | null {
    return numericProblem(spec.kind, raw, w) ? null : { [spec.key]: numericValue(raw) };
  }

  function inputField(spec: InputSpec) {
    const entry = object(object(selected?.input_provenance)[spec.key]);
    const value = object(selected?.inputs)[spec.key];
    const problem = problems[`${id}/${spec.key}`];
    const label = w(spec.label);
    // A convertible quantity is typed in the reader's unit and stored canonically;
    // a density, viscosity or dimensionless coefficient stays exactly as typed.
    const control = spec.dimension
      ? <QuantityField label={label} ariaLabel={`${id} ${label}`} value={number(value)}
        dimension={spec.dimension} storedUnit={spec.storedUnit} kind={spec.kind} invalid={Boolean(problem)}
        onChange={next => replace(patchInputValue(selected ?? {}, spec, next))} />
      : <label className="field-label">{label}
        <input type="number" step="any" placeholder={w('units.unknown')} aria-label={`${id} ${label}`}
          aria-invalid={Boolean(problem)} value={number(value) ?? ''}
          onChange={event => {
            const outcome = patchInput(selected ?? {}, spec, event.target.value, key => key);
            setProblems(previous => {
              const nextMap = { ...previous };
              const key = `${id}/${spec.key}`;
              if (outcome.problem) nextMap[key] = outcome.problem as WorkspaceKey; else delete nextMap[key];
              return nextMap;
            });
            if (!outcome.problem) replace(outcome.scenario);
          }} />
        {problem && <span className="field-error" role="alert">{w(problem)}</span>}
      </label>;
    return <div className="form-grid" key={spec.key}>
      {control}
      <label className="field-label">{w('fact.source')}
        <input aria-label={w('fact.sourceAria', { label: `${id} ${label}` })} placeholder={w('fact.sourcePlaceholder')}
          value={typeof entry.source === 'string' ? entry.source : ''}
          onChange={event => replace(patchProvenance(selected ?? {}, spec.key,
            { source: event.target.value.trim() === '' ? null : event.target.value }))} />
      </label>
      <EstimateInput label={w('fact.estimateAria', { label: `${id} ${label}` })} value={entry.estimate}
        onChange={estimate => replace(patchProvenance(selected ?? {}, spec.key, { estimate }))} />
    </div>;
  }

  function presence(label: string, key: StructuredKey, state: PresenceState) {
    return <label className="field-label">{label}
      <select aria-label={`${id} ${label}`} value={state}
        onChange={event => replace(setPresence(selected ?? {}, key, event.target.value as PresenceState))}>
        <option value="unknown">{w('form.triUnknown')}</option>
        <option value="absent">{w('form.absent')}</option>
        <option value="present">{w('form.present')}</option>
      </select>
    </label>;
  }

  const scenario = selected ?? {};
  const appendageState = presenceState(scenario, 'appendages');
  const thrusterState = presenceState(scenario, 'bow_thruster');
  const thruster = bowThruster(scenario);
  const appendageProvenance = object(object(scenario.input_provenance).appendages);
  const thrusterProvenance = object(object(scenario.input_provenance).bow_thruster);
  const hints = selected ? scenarioHints(selected, w) : [];

  return <div className="resistance-editor form-stack">
    <div className="form-card"><h3>{w('resistance.title')}</h3>
      <p>{w('resistance.intro')}</p>
      {scenarios.length === 0 && <p className="form-hint">{w('resistance.empty')}</p>}
      <div className="form-grid">
        <label className="field-label">{w('resistance.current')}<select aria-label={w('resistance.currentAria')} value={id} onChange={event => setChoice(event.target.value)}>
          {scenarios.length === 0 && <option value="">{w('resistance.none')}</option>}
          {scenarios.map(row => <option key={String(row.id)} value={String(row.id)}>{String(row.id)} · {String(row.method)}</option>)}
        </select></label>
        <label className="field-label">{w('resistance.newId')}<input aria-label={w('resistance.newIdAria')} value={newId} onChange={event => setNewId(event.target.value)} /></label>
        <button className="button button--secondary" type="button" onClick={create}>{w('resistance.add')}</button>
      </div>
    </div>

    {selected && <>
      <div className="form-card"><h3>{w('resistance.methods.title', { id })}</h3>
        <div className="form-grid">
          <label className="field-label">{w('resistance.methods.resistance')}<select aria-label={w('resistance.methods.resistanceAria', { id })} value={String(scenario.method)}
            onChange={event => patch({ method: event.target.value })}>
            {RESISTANCE_METHODS.map(method => <option key={method.id} value={method.id}>{w('massModel.method.option', { label: w(method.label), id: method.id })}</option>)}
          </select></label>
          <label className="field-label">{w('resistance.methods.policy')}<select aria-label={w('resistance.methods.policyAria', { id })} value={String(scenario.attitude_policy)}
            onChange={event => patch({ attitude_policy: event.target.value })}>
            {ATTITUDE_POLICIES.map(policy => <option key={policy.id} value={policy.id}>{w(policy.label)}</option>)}
          </select></label>
          <label className="field-label">{w('resistance.methods.source')}<input aria-label={w('resistance.methods.sourceAria', { id })} value={scenarioSource(scenario)} placeholder={w('fact.sourcePlaceholder')}
            onChange={event => patch({ source: event.target.value.trim() === '' ? null : event.target.value })} /></label>
          <EstimateInput label={w('fact.estimateAria', { label: id })} value={scenario.estimate} onChange={estimate => patch({ estimate })} />
        </div>
        {scenario.attitude_policy === 'selected_plane_longitudinal_trim_proxy_v1'
          && <p className="form-hint">{w('resistance.trimProxyNote')}</p>}
        {hints.length > 0 && <p className="form-hint" role="status">{w('resistance.hints', { hints: hints.join(w('form.listSeparator')) })}</p>}
      </div>

      <div className="form-card"><h3>{w('resistance.table.title')}</h3>
        <p>{w('resistance.table.note')}</p>
        <div className="form-grid">
          <label className="field-label">{w('resistance.table.id')}<input aria-label={w('resistance.table.idAria', { id })} value={scenario.table_id == null ? '' : String(scenario.table_id)}
            onChange={event => patch({ table_id: event.target.value.trim() === '' ? null : event.target.value })} /></label>
          <label className="field-label">{w('resistance.table.sha')}<input aria-label={w('resistance.table.shaAria', { id })} value={scenario.table_sha256 == null ? '' : String(scenario.table_sha256)}
            onChange={event => patch({ table_sha256: event.target.value.trim() === '' ? null : event.target.value.trim() })} /></label>
          {TABLE_METHODS.map(entry => {
            const label = w(entry.label);
            return <label className="field-label" key={entry.key}>{label}
            <select aria-label={`${id} ${label}`} value={scenario[entry.key] === undefined ? '' : String(scenario[entry.key])}
              onChange={event => {
                const next: Raw = { ...scenario };
                if (event.target.value === '') delete next[entry.key]; else next[entry.key] = event.target.value;
                emit(scenarios.map(row => row === selected ? next : row));
              }}>
              <option value="">{w('resistance.table.undeclared')}</option><option value={entry.value}>{entry.value}</option>
            </select></label>; })}
        </div>
      </div>

      <div className="form-card"><h3>{w('resistance.shape.title')}</h3>
        <p>{w('resistance.shape.note')}</p>
        {RESISTANCE_INPUTS.map(spec => inputField(spec))}
      </div>

      <div className="form-card"><h3>{w('resistance.appendages.title')}</h3>
        <p>{w('resistance.appendages.note')}</p>
        <div className="form-grid">
          {presence(w('resistance.appendages.declaration'), 'appendages', appendageState)}
          {presence(w('resistance.thruster.declaration'), 'bow_thruster', thrusterState)}
        </div>
        <div className="form-grid">
          <label className="field-label">{w('resistance.appendages.source')}<input aria-label={`${id} ${w('resistance.appendages.source')}`} placeholder={w('fact.sourcePlaceholder')}
            value={typeof appendageProvenance.source === 'string' ? appendageProvenance.source : ''}
            onChange={event => replace(patchProvenance(scenario, 'appendages', { source: event.target.value.trim() === '' ? null : event.target.value }))} /></label>
          <EstimateInput label={w('fact.estimateAria', { label: `${id} ${w('resistance.appendages.source')}` })} value={appendageProvenance.estimate}
            onChange={estimate => replace(patchProvenance(scenario, 'appendages', { estimate }))} />
          <label className="field-label">{w('resistance.thruster.source')}<input aria-label={`${id} ${w('resistance.thruster.source')}`} placeholder={w('fact.sourcePlaceholder')}
            value={typeof thrusterProvenance.source === 'string' ? thrusterProvenance.source : ''}
            onChange={event => replace(patchProvenance(scenario, 'bow_thruster', { source: event.target.value.trim() === '' ? null : event.target.value }))} /></label>
          <EstimateInput label={w('fact.estimateAria', { label: `${id} ${w('resistance.thruster.source')}` })} value={thrusterProvenance.estimate}
            onChange={estimate => replace(patchProvenance(scenario, 'bow_thruster', { estimate }))} />
        </div>
        {(appendageState === 'unknown' || thrusterState === 'unknown') && <p className="form-hint">
          {w('resistance.appendages.undeclaredNote')}
        </p>}
        {appendageState === 'present' && <div className="form-card-body">
          {appendages(scenario).map((item, index) => <div className="form-grid" key={index}>
            <QuantityField label={w('resistance.appendages.area', { index: index + 1 })} ariaLabel={w('resistance.appendages.areaAria', { id, index: index + 1 })} value={number(item.area_m2)}
              dimension="area" storedUnit="m" kind="nonnegative"
              onChange={next => replace(patchAppendage(scenario, index, { area_m2: next }))} />
            {/* The increment factor is dimensionless, so it is typed and shown as typed. */}
            <label className="field-label">{w('resistance.appendages.factor', { index: index + 1 })}<input type="number" step="any" placeholder={w('units.unknown')}
              aria-label={w('resistance.appendages.factorAria', { id, index: index + 1 })} value={number(item.factor) ?? ''}
              onChange={event => { const value = scalar(APPENDAGE_FACTOR, event.target.value); if (value) replace(patchAppendage(scenario, index, value)); }} /></label>
            <button className="text-button" type="button" onClick={() => replace(removeAppendage(scenario, index))}>{w('resistance.appendages.remove', { index: index + 1 })}</button>
          </div>)}
          <button className="button button--secondary" type="button" onClick={() => replace(addAppendage(scenario))}>{w('resistance.appendages.add')}</button>
        </div>}
        {appendageState === 'absent' && <p className="form-hint">{w('resistance.appendages.absentNote')}</p>}
        {thrusterState === 'present' && <div className="form-card-body"><div className="form-grid">
          {[THRUSTER_DIAMETER, THRUSTER_COEFFICIENT].map(spec => spec.dimension
            ? <QuantityField key={spec.key} label={w(spec.label)} ariaLabel={`${id} ${w(spec.label)}`} value={number(thruster[spec.key])}
              dimension={spec.dimension} storedUnit={spec.storedUnit} kind="positive"
              onChange={next => replace(patchThruster(scenario, { [spec.key]: next }))} />
            : <label className="field-label" key={spec.key}>{w(spec.label)}
              <input type="number" step="any" placeholder={w('units.unknown')} aria-label={`${id} ${w(spec.label)}`} value={number(thruster[spec.key]) ?? ''}
                onChange={event => { const value = scalar(spec, event.target.value); if (value) replace(patchThruster(scenario, value)); }} /></label>)}
        </div><p className="form-hint">{w('resistance.thruster.positiveNote')}</p></div>}
        {thrusterState === 'absent' && <p className="form-hint">{w('resistance.thruster.absentNote')}</p>}
      </div>

      <div className="form-card"><h3>{w('resistance.qpc.title')}</h3>
        <p>{w('resistance.qpc.note')}</p>
        <FactInput label={`${id} QPC`} value={scenario.qpc} onChange={value => patch({ qpc: value })} />
        {scenario.qpc_sensitivity === undefined
          ? <button className="button button--secondary" type="button"
            onClick={() => patch({ qpc_sensitivity: { values: [], source: null, estimate: null } })}>{w('resistance.qpc.add')}</button>
          : <div className="form-card-body">
            <label className="field-label">{w('resistance.qpc.samples')}
              <input aria-label={w('resistance.qpc.samplesAria', { id })} placeholder={w('resistance.qpc.samplesPlaceholder')}
                value={Array.isArray(object(scenario.qpc_sensitivity).values) ? (object(scenario.qpc_sensitivity).values as number[]).join(', ') : ''}
                onChange={event => patch({ qpc_sensitivity: { ...object(scenario.qpc_sensitivity), values: parseList(event.target.value) } })} /></label>
            <div className="form-grid">
              <label className="field-label">{w('resistance.qpc.source')}<input aria-label={w('resistance.qpc.sourceAria', { id })}
                value={typeof object(scenario.qpc_sensitivity).source === 'string' ? String(object(scenario.qpc_sensitivity).source) : ''}
                onChange={event => patch({ qpc_sensitivity: { ...object(scenario.qpc_sensitivity), source: event.target.value.trim() === '' ? null : event.target.value } })} /></label>
              <EstimateInput label={w('fact.estimateAria', { label: `${id} ${w('resistance.qpc.source')}` })} value={object(scenario.qpc_sensitivity).estimate}
                onChange={estimate => patch({ qpc_sensitivity: { ...object(scenario.qpc_sensitivity), estimate } })} />
            </div>
            <button className="text-button" type="button" onClick={() => { const next: Raw = { ...scenario }; delete next.qpc_sensitivity; emit(scenarios.map(row => row === selected ? next : row)); }}>{w('resistance.qpc.remove')}</button>
          </div>}
      </div>

      <div className="form-card"><h3>{w('resistance.remove.title')}</h3>
        <p>{w('resistance.remove.note')}</p>
        <button className="text-button" type="button" onClick={() => { emit(scenarios.filter(row => row !== selected)); setChoice(null); }}>{w('resistance.remove.action', { id })}</button>
      </div>
    </>}
  </div>;
}

function parseList(text: string): number[] {
  return text.split(/[\s,，]+/).filter(Boolean).map(Number);
}