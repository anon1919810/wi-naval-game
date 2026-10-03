import type { ProjectDocument, RunView } from '../types';
import { FactInput } from './FactInput';
import { DeclaredFact, Metric, ResultSection } from './FormResults';
import { inputNumber, number, object, stageData } from './formModel';

// display_preferences is an explicit read-only reading preference recorded in the
// project. It does NOT convert anything: every declared design input, the loading
// ledger, every stage result and every report stay in canonical SI
// (m / t / kW / kn / deg — see project_io.DEFAULT_UNITS). Claiming a conversion
// here would be false; only the stored preference is edited.
const DISPLAY_UNITS: Array<[string, string, Array<[string, string]>]> = [
  ['length', '长度', [['m', 'm'], ['ft', 'ft']]],
  ['mass', '质量', [['t', 't'], ['kg', 'kg'], ['long_ton', 'long ton']]],
  ['power', '功率', [['kW', 'kW'], ['shp', 'shp']]],
  ['speed', '航速', [['kn', 'kn'], ['m_s', 'm/s']]],
  ['angle', '角度', [['deg', 'deg'], ['rad', 'rad']]],
];

export function HullSupplementEditor({ project, run, onChange }: { project: ProjectDocument; run: RunView | null; onChange: (project: ProjectDocument) => void }) {
  const metadata = object(project.metadata); const hull = project.hull; const facts = object(hull.design_facts);
  const preferences = object(project.display_preferences);
  const data = stageData(run, 'l0'); const hydro = stageData(run, 'hydrostatics');
  const declared = object(data.declared_hull);
  function patchPreference(key: string, value: string) {
    const next = { ...preferences };
    if (value === 'project_default') delete next[key]; else next[key] = value;
    onChange({ ...project, display_preferences: next });
  }
  return <div className="form-stack"><div className="form-card"><h3>舰船身份与建造信息</h3>
    <label className="field-label">舰名<input aria-label="舰名" value={project.name} onChange={e => onChange({ ...project, name: e.target.value })} /></label>
    {([['country', '国家', 'text'], ['type', '舰船类型', 'text'], ['design_year', '设计年份', 'integer'], ['laid_down_year', '开工年份', 'integer'], ['engine_built_year', '主机建造年份', 'integer']] as const).map(([key, label, kind]) =>
      <FactInput key={key} label={label} kind={kind} value={metadata[key]} onChange={value => onChange({ ...project, metadata: { ...metadata, [key]: value } })} />)}
  </div><div className="form-card"><h3>最大吃水与独立设计声明</h3><p>参考排水量用于比较，计算排水量仍来自所选载荷账本。满载设计方形系数与实际浮态下的几何系数分开记录。</p>
    <label className="field-label">最大设计吃水 · m<input aria-label="最大设计吃水 · m" type="number" step="any" placeholder="未知" value={number(hull.draught_deep_m) ?? ''} onChange={e => onChange({ ...project, hull: { ...hull, draught_deep_m: inputNumber(e.target.value) } })} /></label>
    {([['block_coeff_deep', '满载设计方形系数'], ['reference_displacement_normal_t', '正常参考排水量 · t'], ['reference_displacement_deep_t', '满载参考排水量 · t']] as const).map(([key, label]) =>
      <FactInput key={key} label={label} value={facts[key]} onChange={value => onChange({ ...project, hull: { ...hull, design_facts: { ...facts, [key]: value } } })} />)}
    <p className="form-hint">这些是独立声明的设计事实，不是所选载荷账本的质量，也不会用来反推几何。</p>
  </div><div className="form-card"><h3>显示偏好</h3>
    <p>记录你阅读时偏好的单位。<strong>所有设计输入与计算结果仍为规范 SI</strong>（m / t / kW / kn / deg）；本偏好不在此处、也不在报告中做任何换算，报告按规范单位呈现。</p>
    <div className="form-grid">{DISPLAY_UNITS.map(([key, label, units]) => <label className="field-label" key={key}>{label}显示单位
      <select aria-label={`${label}显示单位`} value={typeof preferences[key] === 'string' ? String(preferences[key]) : 'project_default'}
        onChange={e => patchPreference(key, e.target.value)}>
        <option value="project_default">项目默认（规范单位）</option>
        {units.map(([value, text]) => <option key={value} value={value}>{text}</option>)}
      </select></label>)}</div>
  </div>
  <ResultSection available={!!run}>
    <div className="metric-grid">
      <Metric label="设计水线长宽比" value={object(data.hull_ratios).design_lwl_over_beam} />
      <Metric label="当前水线长宽比" value={object(hydro.selected_length_beam_ratio).value} />
      <Metric label="当前水线面面积" value={object(hydro.values).awp_m2} unit="m²" />
      <Metric label="当前湿表面积" value={object(hydro.wetted_surface).area_m2} unit="m²" />
      <Metric label="当前排水体积" value={object(hydro.values).volume_m3} unit="m³" />
      <Metric label="当前浮态排水量" value={object(hydro.values).displacement_t} unit="t" />
    </div>
    {Object.keys(object(declared.design_facts)).length > 0 && <div className="form-card"><h3>当前修订记录的设计声明</h3>
      <p className="form-hint">{String(declared.boundary ?? '独立设计声明；参考排水量不是所选账本质量，深水方形系数不是反推几何')}</p>
      <div className="metric-grid">
        {([['reference_displacement_normal_t', '正常参考排水量', 't'], ['reference_displacement_deep_t', '满载参考排水量', 't'],
          ['block_coeff_deep', '满载设计方形系数']] as const).map(([key, label, unit]) =>
          <DeclaredFact key={key} label={label} unit={unit ?? ''} fact={object(declared.design_facts)[key]} />)}
      </div>
    </div>}
  </ResultSection></div>;
}
