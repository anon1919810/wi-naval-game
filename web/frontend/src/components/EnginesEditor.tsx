import type { ProjectDocument, RunView } from '../types';
import { EstimateInput, FactInput, IdPicker } from './FactInput';
import { Diagnostics, Metric, ResultSection } from './FormResults';
import { inputNumber, ledgerItems, number, object, rows, sourceText, stageData, type Raw } from './formModel';

const FIELDS: Array<[string, string, 'number' | 'integer' | 'text']> = [
  ['shafts', '轴数', 'integer'], ['boilers', '锅炉数量', 'integer'], ['design_power_kw', '设计轴功率 · kW', 'number'],
  ['trial_power_kw', '试航轴功率 · kW', 'number'], ['max_speed_kn', '声明最大航速 · kn', 'number'],
  ['cruise_speed_kn', '声明巡航航速 · kn', 'number'], ['engine_built_year', '主机建造年份', 'integer'],
  ['engine_description', '主机型式', 'text'], ['boiler_description', '锅炉型式', 'text'],
  ['energy_source', '能源类型', 'text'], ['transmission', '传动类型', 'text'],
];

export function EnginesEditor({ project, run, onChange }: { project: ProjectDocument; run: RunView | null; onChange: (project: ProjectDocument) => void }) {
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
  return <div className="form-stack"><div className="form-card"><h3>动力系统声明</h3>
    {FIELDS.map(([key, label, kind]) => <FactInput key={key} label={label} kind={kind} value={facts[key]} onChange={v => emit({ facts: { ...facts, [key]: v } })} />)}
    <IdPicker label="安装机械账本条目" selected={prop.weight_item_ids} options={options} onChange={ids => emit({ weight_item_ids: ids })} />
  </div><div className="form-card"><h3>燃料与可变载荷分类</h3><p>绑定现有账本条目或分组。以下分类用于展示和续航，不再次增加排水量。</p>
    {(['coal', 'oil'] as const).map(key => { const binding = object(fuels[key]); return <details key={key} open><summary>{key === 'coal' ? '煤' : '油'}库存绑定</summary>
      <IdPicker label={`${key} 燃料条目`} selected={binding.weight_item_ids} options={options} onChange={ids => patchFuel(key, { weight_item_ids: ids, absent: false })} />
      <label><input type="checkbox" checked={binding.absent === true} onChange={e => patchFuel(key, { absent: e.target.checked, ...(e.target.checked ? { weight_item_ids: [] } : {}) })} />明确不携带{key === 'coal' ? '煤' : '油'}</label>
      <div className="form-grid"><label className="field-label">来源<input aria-label={`${key} 燃料来源`} value={sourceText(binding.source)} onChange={e => patchFuel(key, { source: e.target.value || null })} /></label>
      <EstimateInput label={`${key} 燃料估算状态`} value={binding.estimate} onChange={estimate => patchFuel(key, { estimate })} /></div>
      {key in fuels && <button className="text-button" onClick={() => { const next = { ...fuels }; delete next[key]; emit({ fuel_bindings: next }); }}>撤销此燃料声明</button>}
    </details>; })}
    <IdPicker label="可变载荷分组" selected={variable.group_ids} options={project.weight_groups.map(g => ({ id: g.id, label: g.label || g.id }))} onChange={ids => patchVariable({ group_ids: ids })} />
    <div className="form-grid"><label className="field-label">分类来源<input aria-label="可变载荷分类来源" value={sourceText(variable.source)} onChange={e => patchVariable({ source: e.target.value || null })} /></label>
    <EstimateInput label="可变载荷分类估算状态" value={variable.estimate} onChange={estimate => patchVariable({ estimate })} /></div>
    {prop.variable_load_groups != null && <button className="text-button" onClick={() => { const next = { ...prop }; delete next.variable_load_groups;
      onChange({ ...project, systems: { ...systems, propulsion: next } }); }}>撤销可变载荷分类</button>}
  </div>
  <div className="form-card"><h3>稳态续航研究</h3><p>给定工作航速、轴功率和各燃料消耗率；按当前工况的库存计算。</p>
    {scenarios.map((s, index) => <details key={String(s.id)} open><summary>{String(s.id)}</summary><div className="form-grid">
      {(['speed_kn', 'power_kw'] as const).map((key, i) => <label className="field-label" key={key}>{i ? '工作功率 · kW' : '工作航速 · kn'}<input type="number" step="any" aria-label={`${s.id} ${key}`} placeholder="未知" value={number(s[key]) ?? ''} onChange={e => patchEndurance(index, { [key]: inputNumber(e.target.value) })} /></label>)}
      <label className="field-label">研究来源<input aria-label={`${s.id} 续航来源`} value={sourceText(s.source)} onChange={e => patchEndurance(index, { source: e.target.value || null })} /></label>
      <EstimateInput label={`${s.id} 续航估算状态`} value={s.estimate} onChange={estimate => patchEndurance(index, { estimate })} /></div>
      {(['coal', 'oil'] as const).map(key => { const f = object(object(s.fuels)[key]); return <div className="form-grid" key={key}>
        <label><input aria-label={`${s.id} ${key} 必需`} type="checkbox" checked={f.required === true} onChange={e => patchEndurance(index, { fuels: { ...object(s.fuels), [key]: { ...f, required: e.target.checked } } })} />{key} 持续消耗</label>
        {(['burn_t_per_day', 'reserve_t'] as const).map((field, i) => <label className="field-label" key={field}>{i ? '保留库存 · t' : '消耗率 · t/day'}<input type="number" step="any" aria-label={`${s.id} ${key} ${field}`} value={number(f[field]) ?? ''} placeholder="未知" onChange={e => patchEndurance(index, { fuels: { ...object(s.fuels), [key]: { ...f, [field]: inputNumber(e.target.value) } } })} /></label>)}
      </div>; })}<button className="text-button" onClick={() => onChange({ ...project, endurance_scenarios: scenarios.filter((_, i) => i !== index) })}>移除续航研究</button>
    </details>)}
    <button className="button button--secondary" onClick={() => { let n = 1; while (scenarios.some(s => s.id === `endurance_${n}`)) n++;
      onChange({ ...project, endurance_scenarios: [...scenarios, { id: `endurance_${n}`, method: 'steady_simultaneous_fuel_consumption', speed_kn: null, power_kw: null,
        source: null, estimate: null, fuels: { coal: { required: false, burn_t_per_day: null, reserve_t: null }, oil: { required: false, burn_t_per_day: null, reserve_t: null } } }] }); }}>添加续航研究</button>
  </div><ResultSection available={!!run}><div className="metric-grid"><Metric label="安装机械质量" value={page.machinery_mass_t} unit="t" /><Metric label="可变载荷合计" value={page.variable_load_t} unit="t" />
    <Metric label="煤库存" value={values.coal_t ?? object(data.effective_case).coal_t} unit="t" /><Metric label="油库存" value={values.oil_t ?? object(data.effective_case).oil_t} unit="t" />
    <Metric label="已声明燃料中的煤比例" value={page.coal_share_of_declared_fuel_pct} unit="%" /><Metric label="稳态续航" value={object(endurance.values).range_nm} unit="nm"
      estimate={object(endurance.values).estimate} source={sourceText(object(endurance.values).source) || null} />
  </div><Diagnostics value={data.diagnostics} /><Diagnostics value={endurance.diagnostics} /></ResultSection></div>;
}
