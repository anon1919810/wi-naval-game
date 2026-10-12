import type { ProjectDocument, RunView } from '../types';
import { EstimateInput, FactInput, IdPicker } from './FactInput';
import { QuantityField } from './QuantityField';
import { Diagnostics, Metric, ResultSection } from './FormResults';
import { inputNumber, ledgerItems, number, object, rows, sourceText, stageData, type Raw } from './formModel';
import { useWorkspaceCopy, type WorkspaceKey } from '../i18n/workspace';
import type { Dimension } from './units';

const FIELDS: Array<[string, WorkspaceKey, 'number' | 'integer' | 'text', Dimension | undefined, string?]> = [
  ['shafts', 'engines.shafts', 'integer', undefined], ['boilers', 'engines.boilers', 'integer', undefined],
  ['design_power_kw', 'engines.designPower', 'number', 'power', 'kW'],
  ['trial_power_kw', 'engines.trialPower', 'number', 'power', 'kW'],
  ['max_speed_kn', 'engines.maxSpeed', 'number', 'speed', 'kn'],
  ['cruise_speed_kn', 'engines.cruiseSpeed', 'number', 'speed', 'kn'],
  ['engine_built_year', 'engines.engineYear', 'integer', undefined],
  ['engine_description', 'engines.engineType', 'text', undefined],
  ['boiler_description', 'engines.boilerType', 'text', undefined],
  ['energy_source', 'engines.energySource', 'text', undefined],
  ['transmission', 'engines.transmission', 'text', undefined],
];

export function EnginesEditor({ project, run, onChange }: { project: ProjectDocument; run: RunView | null; onChange: (project: ProjectDocument) => void }) {
  const w = useWorkspaceCopy();
  const systems = object(project.systems); const prop = object(systems.propulsion); const facts = object(prop.facts);
  const options = ledgerItems(project);
  const fuels = object(prop.fuel_bindings); const variable = object(prop.variable_load_groups);
  const data = stageData(run, 'propulsion'); const page = object(data.engine_page); const values = object(data.values);
  const endurance = stageData(run, 'endurance');
  function emit(patch: Raw) { onChange({ ...project, systems: { ...systems, propulsion: { weight_item_ids: [], ...prop, ...patch } } }); }
  function patchFuel(key: string, patch: Raw) { emit({ fuel_bindings: { ...fuels, [key]: { weight_item_ids: [], source: null, estimate: null, ...object(fuels[key]), ...patch } } }); }
  function patchVariable(patch: Raw) { emit({ variable_load_groups: { group_ids: [], source: null, estimate: null, ...variable, ...patch } }); }
  const scenarios = rows(project.endurance_scenarios);
  function patchEndurance(index: number, patch: Raw) { onChange({ ...project, endurance_scenarios: scenarios.map((s, i) => i === index ? { ...s, ...patch } : s) }); }
  return <div className="form-stack"><div className="form-card"><h3>{w('engines.facts.title')}</h3>
    {FIELDS.map(([key, label, kind, dimension, storedUnit]) => <FactInput key={key} label={w(label)} kind={kind} dimension={dimension} storedUnit={storedUnit}
      value={facts[key]} onChange={v => emit({ facts: { ...facts, [key]: v } })} />)}
    <IdPicker label={w('engines.leafBinding')} selected={prop.weight_item_ids} options={options} onChange={ids => emit({ weight_item_ids: ids })} />
  </div><div className="form-card"><h3>{w('engines.fuels.title')}</h3><p>{w('engines.fuels.note')}</p>
    {(['coal', 'oil'] as const).map(key => { const binding = object(fuels[key]);
      const fuel = w(key === 'coal' ? 'engines.fuel.coal' : 'engines.fuel.oil');
      return <details key={key} open><summary>{w('engines.fuels.summary', { fuel })}</summary>
      <IdPicker label={w('engines.fuels.entry', { fuel })} selected={binding.weight_item_ids} options={options} onChange={ids => patchFuel(key, { weight_item_ids: ids, absent: false })} />
      <label><input type="checkbox" checked={binding.absent === true} onChange={e => patchFuel(key, { absent: e.target.checked, ...(e.target.checked ? { weight_item_ids: [] } : {}) })} />{w('engines.fuels.notCarried', { fuel })}</label>
      <div className="form-grid"><label className="field-label">{w('fact.source')}<input aria-label={w('fact.sourceAria', { label: fuel })} value={sourceText(binding.source)} onChange={e => patchFuel(key, { source: e.target.value || null })} /></label>
      <EstimateInput label={w('fact.estimateAria', { label: fuel })} value={binding.estimate} onChange={estimate => patchFuel(key, { estimate })} /></div>
      {key in fuels && <button className="text-button" onClick={() => { const next = { ...fuels }; delete next[key]; emit({ fuel_bindings: next }); }}>{w('engines.fuels.revoke')}</button>}
    </details>; })}
    <IdPicker label={w('engines.variable.group')} selected={variable.group_ids} options={project.weight_groups.map(g => ({ id: g.id, label: g.label || g.id }))} onChange={ids => patchVariable({ group_ids: ids })} />
    <div className="form-grid"><label className="field-label">{w('engines.variable.source')}<input aria-label={w('engines.variable.sourceAria')} value={sourceText(variable.source)} onChange={e => patchVariable({ source: e.target.value || null })} /></label>
    <EstimateInput label={w('engines.variable.estimateAria')} value={variable.estimate} onChange={estimate => patchVariable({ estimate })} /></div>
    {prop.variable_load_groups != null && <button className="text-button" onClick={() => { const next = { ...prop }; delete next.variable_load_groups;
      onChange({ ...project, systems: { ...systems, propulsion: next } }); }}>{w('engines.variable.revoke')}</button>}
  </div>
  <div className="form-card"><h3>{w('engines.endurance.title')}</h3><p>{w('engines.endurance.note')}</p>
    {scenarios.map((s, index) => <details key={String(s.id)} open><summary>{String(s.id)}</summary><div className="form-grid">
      {(['speed_kn', 'power_kw'] as const).map((key, i) => <QuantityField key={key} label={i ? w('engines.endurance.power') : w('engines.endurance.speed')}
        aria-label={`${s.id} ${key}`} value={number(s[key])} dimension={i ? 'power' : 'speed'} storedUnit={i ? 'kW' : 'kn'} kind="positive"
        onChange={value => patchEndurance(index, { [key]: value })} />)}
      <label className="field-label">{w('engines.endurance.source')}<input aria-label={w('engines.endurance.sourceAria', { id: String(s.id) })} value={sourceText(s.source)} onChange={e => patchEndurance(index, { source: e.target.value || null })} /></label>
      <EstimateInput label={w('fact.estimateAria', { label: String(s.id) })} value={s.estimate} onChange={estimate => patchEndurance(index, { estimate })} /></div>
      {(['coal', 'oil'] as const).map(key => { const f = object(object(s.fuels)[key]); return <div className="form-grid" key={key}>
        <label><input aria-label={w('engines.endurance.requiredAria', { id: String(s.id), fuel: key })} type="checkbox" checked={f.required === true} onChange={e => patchEndurance(index, { fuels: { ...object(s.fuels), [key]: { ...f, required: e.target.checked } } })} />{w('engines.endurance.consumed', { fuel: w(key === 'coal' ? 'engines.fuel.coal' : 'engines.fuel.oil') })}</label>
        <QuantityField label={w('engines.endurance.burnRate')} aria-label={`${s.id} ${key} burn_t_per_day`} value={number(f.burn_t_per_day)} dimension="mass" storedUnit="t" kind="nonnegative" unitSuffix="/day"
          onChange={value => patchEndurance(index, { fuels: { ...object(s.fuels), [key]: { ...f, burn_t_per_day: value } } })} />
        <QuantityField label={w('engines.endurance.reserve')} aria-label={`${s.id} ${key} reserve_t`} value={number(f.reserve_t)} dimension="mass" storedUnit="t" kind="nonnegative"
          onChange={value => patchEndurance(index, { fuels: { ...object(s.fuels), [key]: { ...f, reserve_t: value } } })} />
      </div>; })}<button className="text-button" onClick={() => onChange({ ...project, endurance_scenarios: scenarios.filter((_, i) => i !== index) })}>{w('engines.endurance.remove')}</button>
    </details>)}
    <button className="button button--secondary" onClick={() => { let n = 1; while (scenarios.some(s => s.id === `endurance_${n}`)) n++;
      onChange({ ...project, endurance_scenarios: [...scenarios, { id: `endurance_${n}`, method: 'steady_simultaneous_fuel_consumption', speed_kn: null, power_kw: null,
        source: null, estimate: null, fuels: { coal: { required: false, burn_t_per_day: null, reserve_t: null }, oil: { required: false, burn_t_per_day: null, reserve_t: null } } }] }); }}>{w('engines.endurance.add')}</button>
  </div><ResultSection available={!!run}><div className="metric-grid"><Metric label={w('engines.result.machinery')} value={page.machinery_mass_t} dimension="mass" storedUnit="t" /><Metric label={w('engines.result.variable')} value={page.variable_load_t} dimension="mass" storedUnit="t" />
    <Metric label={w('engines.result.coal')} value={values.coal_t ?? object(data.effective_case).coal_t} dimension="mass" storedUnit="t" /><Metric label={w('engines.result.oil')} value={values.oil_t ?? object(data.effective_case).oil_t} dimension="mass" storedUnit="t" />
    <Metric label={w('engines.result.coalShare')} value={page.coal_share_of_declared_fuel_pct} unit="%" /><Metric label={w('reading.endurance')} value={object(endurance.values).range_nm} unit="nm"
      estimate={object(endurance.values).estimate} source={sourceText(object(endurance.values).source) || null} />
  </div>
    <Diagnostics value={data.diagnostics} /><Diagnostics value={endurance.diagnostics} /></ResultSection></div>;
}