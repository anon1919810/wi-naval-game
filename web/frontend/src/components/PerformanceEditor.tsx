import type { ProjectDocument, RunView } from '../types';
import { EstimateInput, FactInput, IdPicker } from './FactInput';
import { QuantityField, QuantityListField } from './QuantityField';
import { useUnits } from './UnitProvider';
import { Diagnostics, Metric, ResultSection, StudyResult } from './FormResults';
import { englishCopy, fact, inputNumber, number, object, rows, sourceText, stageData, type Raw } from './formModel';
import { useWorkspaceCopy } from '../i18n/workspace';
import type { Copy } from './diagnosticGuidance';

const BASE_STAGES = ['loading', 'systems', 'l0', 'geometry', 'equilibrium', 'hydrostatics', 'deck', 'propulsion'];
/** Exported because the readiness panel names the same base stages a request always selects. */
export { BASE_STAGES };
/** The stages a request builder adds on top of the base, by explicit choice. */
export function requestedExtraStages(request: RequestDraft): string[] {
  const extra: string[] = [];
  if (request.scenario) extra.push('resistance');
  if (request.endurance) extra.push('endurance');
  return extra;
}
export interface RequestDraft { scenario: string; mode: string; speeds: number[]; power: string; qpc: Raw; trim: string; endurance: string }
export const EMPTY_REQUEST: RequestDraft = { scenario: '', mode: 'predict_power', speeds: [], power: '', qpc: fact(null), trim: '', endurance: '' };

/** Split a typed sample list into canonical, strictly increasing positive values. */
export function parsePositiveSamples(values: number[], w: Copy = englishCopy): { values: number[]; error: string } {
  if (values.length > 201) return { values: [], error: w('performance.sample.tooMany') };
  if (values.some(v => !Number.isFinite(v) || v <= 0)) return { values: [], error: w('performance.sample.finite') };
  if (values.some((v, i) => i > 0 && v <= values[i - 1])) return { values: [], error: w('performance.sample.increasing') };
  return { values, error: '' };
}

export function buildOptions(request: RequestDraft, w: Copy = englishCopy): { options: Raw; error: string } {
  const options: Raw = {}; const stages = [...BASE_STAGES];
  if (request.trim.trim()) { const target = inputNumber(request.trim); if (target === null) return { options, error: w('performance.trim.finite') }; options.equilibrium = { target_trim_deg: target }; }
  if (request.scenario) {
    const sampled = parsePositiveSamples(request.speeds, w);
    if (!sampled.values.length || sampled.error) return { options, error: sampled.error || w('performance.speeds.invalid') };
    const speeds = sampled.values;
    const resistance: Raw = { scenario_id: request.scenario, mode: request.mode, speeds_kn: speeds };
    const qpc = number(request.qpc.value);
    if (request.mode === 'fixed_power' || qpc !== null) {
      if (qpc === null || qpc <= 0 || qpc > 1 || !sourceText(request.qpc.source).trim() || typeof request.qpc.estimate !== 'boolean') return { options, error: w('performance.qpc.invalid') };
      resistance.qpc_override = request.qpc;
    }
    if (request.mode === 'fixed_power') {
      const power = inputNumber(request.power);
      if (speeds.length < 2 || power === null || power <= 0) return { options, error: w('performance.fixedPower.invalid') };
      resistance.fixed_shaft_power_kw = power;
    }
    options.resistance = resistance; stages.push('resistance');
  }
  if (request.endurance) { options.endurance_scenario_id = request.endurance; stages.push('endurance'); }
  options.stages = stages;
  return { options, error: '' };
}

interface EditorProps {
  project: ProjectDocument; run: RunView | null; request: RequestDraft;
  onChange: (project: ProjectDocument) => void; onRequestChange: (request: RequestDraft) => void;
}

/**
 * Loading conditions, roll parameters and the display preference. Everything
 * here is project input; nothing in this part reads or writes a run request.
 */
export function PerformanceInputs({ project, onChange }: Pick<EditorProps, 'project' | 'onChange'>) {
  const w = useWorkspaceCopy();
  const items = project.weight_groups.flatMap(g => g.items.map(i => ({ id: String(i.id), label: String(i.id) })));
  const bases = project.loading_conditions.filter(c => !c.definition);
  function patchCondition(index: number, patch: Raw) { onChange({ ...project, loading_conditions: project.loading_conditions.map((c, i) => i === index ? { ...c, ...patch } : c) }); }
  function addDefinition(kind: 'standard' | 'light') {
    let id: string = kind; let n = 2; while (project.loading_conditions.some(c => c.id === id)) id = `${kind}_${n++}`;
    // `Standard` / `Light` is the label saved *into the project document*, so it
    // is stored condition data rather than a translatable string on this page.
    onChange({ ...project, loading_conditions: [...project.loading_conditions, { id, label: `${kind === 'standard' ? 'Standard' : 'Light'} · 明确扣除研究`, overrides: {}, reference_displacement_t: null,
      definition: { kind, base_condition_id: bases[0]?.id ?? null, excluded_item_ids: [], source: null, estimate: null } }] });
  }
  return <>
    <div className="form-card"><h3>{w('performance.conditions.title')}</h3><p>{w('performance.conditions.note')}</p>
      {project.loading_conditions.map((c, index) => { const definition = object(c.definition);
        const baseKnown = bases.some(base => base.id === definition.base_condition_id);
        const sourceKnown = typeof definition.source === 'string' && definition.source.trim() !== '';
        const estimateKnown = typeof definition.estimate === 'boolean';
        const incomplete = c.definition ? [!baseKnown && w('performance.conditions.noBase'), !sourceKnown && w('performance.conditions.noSource'), !estimateKnown && w('performance.conditions.noEstimate')].filter(Boolean) : [];
        return <details className="form-card" key={c.id} open><summary>{c.label || c.id} · {c.id}</summary><div className="form-card-body">
        <label className="field-label">{w('performance.conditions.label')}<input aria-label={w('performance.conditions.labelAria', { id: c.id })} value={c.label} onChange={e => patchCondition(index, { label: e.target.value })} /></label>
        {c.definition ? <><label className="field-label">{w('performance.conditions.base')}<select aria-label={w('performance.conditions.baseAria', { id: c.id })} value={String(definition.base_condition_id ?? '')} onChange={e => patchCondition(index, { definition: { ...definition, base_condition_id: e.target.value } })}>{bases.map(base => <option key={base.id} value={base.id}>{base.label || base.id}</option>)}</select></label>
          <IdPicker label={w('performance.conditions.exclude', { id: c.id })} selected={definition.excluded_item_ids} options={items} onChange={ids => patchCondition(index, { definition: { ...definition, excluded_item_ids: ids } })} />
          <div className="form-grid"><label className="field-label">{w('performance.conditions.source')}<input aria-label={w('performance.conditions.sourceAria', { id: c.id })} value={sourceText(definition.source)} onChange={e => patchCondition(index, { definition: { ...definition, source: e.target.value || null } })} /></label>
            <EstimateInput label={w('performance.conditions.estimateAria', { id: c.id })} value={definition.estimate} onChange={estimate => patchCondition(index, { definition: { ...definition, estimate } })} /></div>
          {/* A rule that cannot run keeps its reason visible, not folded away. */}
          {incomplete.length > 0 && <p className="form-hint" role="status">{w('performance.conditions.incomplete', { hints: incomplete.join(w('form.listSeparator')) })}</p>}
          <button className="text-button" onClick={() => onChange({ ...project, loading_conditions: project.loading_conditions.filter((_, i) => i !== index) })}>{w('performance.conditions.remove')}</button>
        </> : <><QuantityField label={w('performance.conditions.displacement')} aria-label={w('performance.conditions.displacementAria', { id: c.id })} value={number(c.reference_displacement_t)} dimension="mass" storedUnit="t" kind="nonnegative"
                onChange={value => patchCondition(index, { reference_displacement_t: value })} />
          {Object.entries(object(c.overrides)).map(([id, supplied]) => { const override = object(supplied); const provenance = object(object(c.override_provenance)[id]); return <details key={id}><summary>{w('performance.conditions.override', { id })}</summary>
            {(['mass_t', 'x_m', 'y_m', 'kg_m'] as const).map(key => <FactInput key={key} label={`${c.id} ${id} ${key}`}
              dimension={key === 'mass_t' ? 'mass' : 'length'} storedUnit={key === 'mass_t' ? 't' : 'm'}
              value={{ value: override[key], ...object(provenance[key]) }}
              onChange={f => patchCondition(index, { overrides: { ...object(c.overrides), [id]: { ...override, [key]: f.value } },
                override_provenance: { ...object(c.override_provenance), [id]: { ...provenance, [key]: { source: f.source, estimate: f.estimate } } } })} />)}
          </details>; })}
        </>}
      </div></details>; })}
      <div className="notice-actions"><button className="button button--secondary" disabled={!bases.length} onClick={() => addDefinition('standard')}>{w('performance.conditions.addStandard')}</button><button className="button button--secondary" disabled={!bases.length} onClick={() => addDefinition('light')}>{w('performance.conditions.addLight')}</button></div>
    </div>
    <div className="form-card"><h3>{w('performance.roll.title')}</h3><p>{w('performance.roll.note')}</p><div className="form-grid">
      {/* A radius-of-gyration ratio: dimensionless, so it never converts. */}
      <label className="field-label">{w('performance.roll.coeff')}<input aria-label={w('performance.roll.coeffAria')} type="number" step="any" placeholder={w('units.unknown')} value={number(project.hull.roll_gyration_coeff) ?? ''} onChange={e => onChange({ ...project, hull: { ...project.hull, roll_gyration_coeff: inputNumber(e.target.value) } })} /></label>
      <label className="field-label">{w('performance.roll.source')}<input aria-label={w('performance.roll.sourceAria')} value={sourceText(object(project.hull.sources).roll_gyration_coeff)} onChange={e => onChange({ ...project, hull: { ...project.hull, sources: { ...object(project.hull.sources), roll_gyration_coeff: e.target.value || null } } })} /></label>
    </div></div>
  </>;
}

/**
 * The optional research request. It follows every input it depends on and
 * precedes the results it produces, so a reader meets the question before the
 * numbers and the answer.
 */
export function PerformanceRequest({ project, request, onRequestChange }: Pick<EditorProps, 'project' | 'request' | 'onRequestChange'>) {
  const w = useWorkspaceCopy();
  function patchRequest(patch: Partial<RequestDraft>) { onRequestChange({ ...request, ...patch }); }
  return <div className="form-card"><h3>{w('editor.group.request')}</h3><p>{w('performance.request.note')}</p><div className="form-grid">
    <QuantityField label={w('performance.request.trim')} aria-label={w('performance.request.trim')} value={inputNumber(request.trim)} dimension="angle" placeholder={w('performance.request.notRequested')}
      onChange={value => patchRequest({ trim: value === null ? '' : String(value) })} />
    <label className="field-label">{w('performance.request.scenario')}<select aria-label={w('performance.request.scenario')} value={request.scenario} onChange={e => patchRequest({ scenario: e.target.value })}><option value="">{w('performance.request.noResistance')}</option>{rows(project.resistance_scenarios).map(s => <option value={String(s.id)} key={String(s.id)}>{String(s.id)} · {String(s.method)}</option>)}</select></label>
    <label className="field-label">{w('performance.request.mode')}<select aria-label={w('performance.request.mode')} value={request.mode} onChange={e => patchRequest({ mode: e.target.value })}><option value="predict_power">{w('performance.request.modePredictPower')}</option><option value="fixed_power">{w('performance.request.modeFixedPower')}</option></select></label>
    <QuantityListField label={w('performance.request.speeds')} value={request.speeds} dimension="speed" placeholder={w('performance.request.speedsPlaceholder')}
      onChange={values => patchRequest({ speeds: values })} />
    {request.mode === 'fixed_power' && <QuantityField label={w('performance.request.fixedPower')} aria-label={w('performance.request.fixedPower')} value={inputNumber(request.power)} dimension="power" kind="positive"
      onChange={value => patchRequest({ power: value === null ? '' : String(value) })} />}
    <label className="field-label">{w('performance.request.endurance')}<select aria-label={w('performance.request.enduranceAria')} value={request.endurance} onChange={e => patchRequest({ endurance: e.target.value })}><option value="">{w('performance.request.noEndurance')}</option>{rows(project.endurance_scenarios).map(s => <option key={String(s.id)}>{String(s.id)}</option>)}</select></label>
  </div><FactInput label={w('resistance.th.qpc')} value={request.qpc} onChange={qpc => patchRequest({ qpc })} />
    {/* The operation bar announces the request failure once; this copy sits with
        the controls that produced it. */}
    {buildOptions(request, w).error && <p className="form-error">{buildOptions(request, w).error}</p>}</div>;
}

/** Results of the current revision and condition, read from the saved run. */
export function PerformanceResults({ run }: Pick<EditorProps, 'run'>) {
  const w = useWorkspaceCopy();
  const units = useUnits();
  const loading = stageData(run, 'loading'); const hydro = stageData(run, 'hydrostatics');
  const equilibrium = stageData(run, 'equilibrium'); const resistance = stageData(run, 'resistance');
  return <ResultSection available={!!run}>{run && <p>{w('performance.result.context', { id: run.id, fingerprint: run.request_fingerprint.slice(0, 16) })}</p>}<div className="metric-grid"><Metric label={w('reading.mass')} value={object(loading.values).total_mass_t} dimension="mass" storedUnit="t" /><Metric label={w('reading.gm')} value={object(hydro.values).gm_t_m} dimension="length" storedUnit="m" /></div>
    <StudyResult label={w('performance.result.roll')} data={hydro.loaded_roll} metrics={[["period_s", w('performance.result.rollPeriod'), "s"]]} />
    <StudyResult label={w('performance.result.trimStudy')} data={equilibrium.trim_target_study} metrics={[["required_longitudinal_moment_kNm", w('performance.result.trimMoment'), "kN·m"]]} />
    <StudyResult label={w('performance.result.fixedPower')} data={resistance.fixed_power_study} metrics={[["speed_kn", w('performance.result.studySpeed'), "kn", "speed"]]} />
    <div className="metric-grid">{rows(resistance.power_rows).map((r, i) => <Metric key={i} label={w('performance.result.powerAtSpeed', { speed: units.number(r.speed_kn, "speed") })} value={r.shaft_power_kw} dimension="power" storedUnit="kW"
      estimate={r.estimate} source={r.complete === false ? w('performance.result.pointIncomplete') : r.primary_result === false ? w('performance.result.nonPrimary') : w('formResults.sourceRun')} />)}</div><Diagnostics value={resistance.diagnostics} />
  </ResultSection>;
}

/** Inputs, then the optional request, then the results they produce. */
export function PerformanceEditor({ project, run, request, onChange, onRequestChange }: EditorProps) {
  return <div className="form-stack">
    <PerformanceInputs project={project} onChange={onChange} />
    <PerformanceRequest project={project} request={request} onRequestChange={onRequestChange} />
    <PerformanceResults run={run} />
  </div>;
}