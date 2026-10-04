import type { ProjectDocument, RunView } from '../types';
import { FactInput } from './FactInput';
import { QuantityField } from './QuantityField';
import { DeclaredFact, Metric, ResultSection } from './FormResults';
import { inputNumber, number, object, stageData } from './formModel';
import { CHOICES, DIMENSION_KEYS } from './units';

// `display_preferences` is a reading preference recorded in the project. It
// converts presentation only: every declared input, the ledger, every stage
// result, every export and every fingerprint stays canonical (m / t / kW / kn /
// deg, and kg or mm where the contract stores those units).
const PREFERENCE_LABELS: Record<string, string> = { length: '长度', mass: '质量', power: '功率', speed: '航速', angle: '角度' };

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
    <QuantityField label="最大设计吃水" ariaLabel="最大设计吃水" value={number(hull.draught_deep_m)} dimension="length" kind="nonnegative"
      onChange={value => onChange({ ...project, hull: { ...hull, draught_deep_m: value } })} />
    {([['block_coeff_deep', '满载设计方形系数', undefined], ['reference_displacement_normal_t', '正常参考排水量', 'mass'],
      ['reference_displacement_deep_t', '满载参考排水量', 'mass']] as const).map(([key, label, dimension]) =>
      <FactInput key={key} label={label} value={facts[key]} dimension={dimension}
        onChange={value => onChange({ ...project, hull: { ...hull, design_facts: { ...facts, [key]: value } } })} />)}
    <p className="form-hint">这些是独立声明的设计事实，不是所选载荷账本的质量，也不会用来反推几何。</p>
  </div><div className="form-card"><h3>显示偏好</h3>
    <p>记录你阅读时偏好的单位。输入框按该偏好显示与接收数值，保存、计算、JSON/CSV 导出与请求指纹<strong>始终为规范单位</strong>；密度、黏度、时间与力保持各自的规范单位。</p>
    <div className="form-grid">{DIMENSION_KEYS.map(key => <label className="field-label" key={key}>{PREFERENCE_LABELS[key]}显示单位
      <select aria-label={`${PREFERENCE_LABELS[key]}显示单位`} value={typeof preferences[key] === 'string' ? String(preferences[key]) : 'project_default'}
        onChange={e => patchPreference(key, e.target.value)}>
        <option value="project_default">项目默认（规范单位）</option>
        {CHOICES[key].map(choice => <option key={choice.value} value={choice.value}>{choice.label}</option>)}
      </select></label>)}</div>
  </div>
  <ResultSection available={!!run}>
    <div className="metric-grid">
      <Metric label="设计水线长宽比" value={object(data.hull_ratios).design_lwl_over_beam} />
      <Metric label="当前水线长宽比" value={object(hydro.selected_length_beam_ratio).value} />
      <Metric label="当前水线面面积" value={object(hydro.values).awp_m2} dimension="area" />
      <Metric label="当前湿表面积" value={object(hydro.wetted_surface).area_m2} dimension="area" />
      <Metric label="当前排水体积" value={object(hydro.values).volume_m3} dimension="volume" />
      <Metric label="当前浮态排水量" value={object(hydro.values).displacement_t} dimension="mass" />
    </div>
    {Object.keys(object(declared.design_facts)).length > 0 && <div className="form-card"><h3>当前修订记录的设计声明</h3>
      <p className="form-hint">{String(declared.boundary ?? '独立设计声明；参考排水量不是所选账本质量，深水方形系数不是反推几何')}</p>
      <div className="metric-grid">
        {([['reference_displacement_normal_t', '正常参考排水量', 'mass'], ['reference_displacement_deep_t', '满载参考排水量', 'mass']] as const).map(([key, label, dimension]) =>
          <DeclaredFact key={key} label={label} unit="" fact={object(declared.design_facts)[key]} dimension={dimension} />)}
      </div>
    </div>}
  </ResultSection></div>;
}
