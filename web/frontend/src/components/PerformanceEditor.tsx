import type { ProjectDocument, RunView } from '../types';
import { EstimateInput, FactInput, IdPicker } from './FactInput';
import { QuantityField, QuantityListField } from './QuantityField';
import { useUnits } from './UnitProvider';
import { Diagnostics, Metric, ResultSection, StudyResult } from './FormResults';
import { fact, inputNumber, number, object, rows, sourceText, stageData, type Raw } from './formModel';

const BASE_STAGES = ['loading', 'systems', 'l0', 'geometry', 'equilibrium', 'hydrostatics', 'deck', 'propulsion'];
export interface RequestDraft { scenario: string; mode: string; speeds: number[]; power: string; qpc: Raw; trim: string; endurance: string }
export const EMPTY_REQUEST: RequestDraft = { scenario: '', mode: 'predict_power', speeds: [], power: '', qpc: fact(null), trim: '', endurance: '' };

/** Split a typed sample list into canonical, strictly increasing positive values. */
export function parsePositiveSamples(values: number[]): { values: number[]; error: string } {
  if (values.length > 201) return { values: [], error: '采样最多 201 个' };
  if (values.some(v => !Number.isFinite(v) || v <= 0)) return { values: [], error: '采样须为有限正数' };
  if (values.some((v, i) => i > 0 && v <= values[i - 1])) return { values: [], error: '采样必须严格递增' };
  return { values, error: '' };
}

export function buildOptions(request: RequestDraft): { options: Raw; error: string } {
  const options: Raw = {}; const stages = [...BASE_STAGES];
  if (request.trim.trim()) { const target = inputNumber(request.trim); if (target === null) return { options, error: '目标纵倾需要有限数值' }; options.equilibrium = { target_trim_deg: target }; }
  if (request.scenario) {
    const sampled = parsePositiveSamples(request.speeds);
    if (!sampled.values.length || sampled.error) return { options, error: sampled.error || '速度采样须为 1–201 个递增正数' };
    const speeds = sampled.values;
    const resistance: Raw = { scenario_id: request.scenario, mode: request.mode, speeds_kn: speeds };
    const qpc = number(request.qpc.value);
    if (request.mode === 'fixed_power' || qpc !== null) {
      if (qpc === null || qpc <= 0 || qpc > 1 || !sourceText(request.qpc.source).trim() || typeof request.qpc.estimate !== 'boolean') return { options, error: 'QPC 需要 (0, 1] 的值、来源和明确估算状态' };
      resistance.qpc_override = request.qpc;
    }
    if (request.mode === 'fixed_power') {
      const power = inputNumber(request.power);
      if (speeds.length < 2 || power === null || power <= 0) return { options, error: '给定功率模式需要至少两个包围速度和正轴功率' };
      resistance.fixed_shaft_power_kw = power;
    }
    options.resistance = resistance; stages.push('resistance');
  }
  if (request.endurance) { options.endurance_scenario_id = request.endurance; stages.push('endurance'); }
  options.stages = stages;
  return { options, error: '' };
}

export function PerformanceEditor({ project, run, request, onChange, onRequestChange }: {
  project: ProjectDocument; run: RunView | null; request: RequestDraft; onChange: (project: ProjectDocument) => void; onRequestChange: (request: RequestDraft) => void;
}) {
  function patchRequest(patch: Partial<RequestDraft>) { onRequestChange({ ...request, ...patch }); }
  const items = project.weight_groups.flatMap(g => g.items.map(i => ({ id: String(i.id), label: String(i.id) })));
  const bases = project.loading_conditions.filter(c => !c.definition);
  function patchCondition(index: number, patch: Raw) { onChange({ ...project, loading_conditions: project.loading_conditions.map((c, i) => i === index ? { ...c, ...patch } : c) }); }
  function addDefinition(kind: 'standard' | 'light') {
    let id: string = kind; let n = 2; while (project.loading_conditions.some(c => c.id === id)) id = `${kind}_${n++}`;
    onChange({ ...project, loading_conditions: [...project.loading_conditions, { id, label: `${kind === 'standard' ? 'Standard' : 'Light'} · 明确扣除研究`, overrides: {}, reference_displacement_t: null,
      definition: { kind, base_condition_id: bases[0]?.id ?? null, excluded_item_ids: [], source: null, estimate: null } }] });
  }
  const units = useUnits();
  const loading = stageData(run, 'loading'); const hydro = stageData(run, 'hydrostatics'); const equilibrium = stageData(run, 'equilibrium'); const resistance = stageData(run, 'resistance');
  return <div className="form-stack"><div className="form-card"><h3>载荷工况与明确扣除规则</h3><p>Standard/Light 是本项目定义的扣除研究。请选择基准工况、扣除的具体账本条目，并记录来源；留空来源的规则不能运行。扣除清单为空表示不扣除任何载荷。</p>
    {project.loading_conditions.map((c, index) => { const definition = object(c.definition);
      const baseKnown = bases.some(base => base.id === definition.base_condition_id);
      const sourceKnown = typeof definition.source === 'string' && definition.source.trim() !== '';
      const estimateKnown = typeof definition.estimate === 'boolean';
      const incomplete = c.definition ? [!baseKnown && '基准工况未选择', !sourceKnown && '缺少规则来源', !estimateKnown && '估算状态未声明'].filter(Boolean) : [];
      return <details className="form-card" key={c.id} open><summary>{c.label || c.id} · {c.id}</summary><div className="form-card-body">
      <label className="field-label">工况名称<input aria-label={`${c.id} 工况名称`} value={c.label} onChange={e => patchCondition(index, { label: e.target.value })} /></label>
      {c.definition ? <><label className="field-label">基准工况<select aria-label={`${c.id} 基准工况`} value={String(definition.base_condition_id ?? '')} onChange={e => patchCondition(index, { definition: { ...definition, base_condition_id: e.target.value } })}>{bases.map(base => <option key={base.id} value={base.id}>{base.label || base.id}</option>)}</select></label>
        <IdPicker label={`${c.id} 扣除`} selected={definition.excluded_item_ids} options={items} onChange={ids => patchCondition(index, { definition: { ...definition, excluded_item_ids: ids } })} />
        <div className="form-grid"><label className="field-label">规则来源<input aria-label={`${c.id} 规则来源`} value={sourceText(definition.source)} onChange={e => patchCondition(index, { definition: { ...definition, source: e.target.value || null } })} /></label>
        <EstimateInput label={`${c.id} 规则估算状态`} value={definition.estimate} onChange={estimate => patchCondition(index, { definition: { ...definition, estimate } })} /></div>
        {incomplete.length > 0 && <p className="form-hint" role="status">{incomplete.join('；')}。补齐后该规则才能保存并运行。</p>}
        <button className="text-button" onClick={() => onChange({ ...project, loading_conditions: project.loading_conditions.filter((_, i) => i !== index) })}>移除此派生工况</button>
      </> : <><QuantityField label="参考排水量" aria-label={`${c.id} 参考排水量`} value={number(c.reference_displacement_t)} dimension="mass" storedUnit="t" kind="nonnegative"
              onChange={value => patchCondition(index, { reference_displacement_t: value })} />
        {Object.entries(object(c.overrides)).map(([id, supplied]) => { const override = object(supplied); const provenance = object(object(c.override_provenance)[id]); return <details key={id}><summary>{id} 工况覆盖</summary>
          {(['mass_t', 'x_m', 'y_m', 'kg_m'] as const).map(key => <FactInput key={key} label={`${c.id} ${id} ${key}`}
            dimension={key === 'mass_t' ? 'mass' : 'length'} storedUnit={key === 'mass_t' ? 't' : 'm'}
            value={{ value: override[key], ...object(provenance[key]) }}
            onChange={f => patchCondition(index, { overrides: { ...object(c.overrides), [id]: { ...override, [key]: f.value } },
              override_provenance: { ...object(c.override_provenance), [id]: { ...provenance, [key]: { source: f.source, estimate: f.estimate } } } })} />)}
        </details>; })}
      </>}
    </div></details>; })}
    <div className="notice-actions"><button className="button button--secondary" disabled={!bases.length} onClick={() => addDefinition('standard')}>添加 Standard 工况</button><button className="button button--secondary" disabled={!bases.length} onClick={() => addDefinition('light')}>添加 Light 工况</button></div>
  </div><div className="form-card"><h3>横摇研究参数</h3><p>横摇周期使用所选工况 GM 与水线宽度。回转半径系数须有来源，结果保持工程估算。</p><div className="form-grid">
    {/* A radius-of-gyration ratio: dimensionless, so it never converts. */}
        <label className="field-label">回转半径系数<input aria-label="横摇回转半径系数" type="number" step="any" placeholder="未知" value={number(project.hull.roll_gyration_coeff) ?? ''} onChange={e => onChange({ ...project, hull: { ...project.hull, roll_gyration_coeff: inputNumber(e.target.value) } })} /></label>
    <label className="field-label">参数来源<input aria-label="横摇参数来源" value={sourceText(object(project.hull.sources).roll_gyration_coeff)} onChange={e => onChange({ ...project, hull: { ...project.hull, sources: { ...object(project.hull.sources), roll_gyration_coeff: e.target.value || null } } })} /></label>
  </div></div><div className="form-card"><h3>本次计算请求</h3><p>请求选项随运行记录保存。目标纵倾只计算所需纵向力矩；固定功率求速度只在有效采样包围内求解。</p><div className="form-grid">
    <QuantityField label="目标纵倾" aria-label="目标纵倾" value={inputNumber(request.trim)} dimension="angle" placeholder="不请求"
            onChange={value => patchRequest({ trim: value === null ? '' : String(value) })} />
    <label className="field-label">阻力研究场景<select aria-label="阻力研究场景" value={request.scenario} onChange={e => patchRequest({ scenario: e.target.value })}><option value="">不请求阻力研究</option>{rows(project.resistance_scenarios).map(s => <option value={String(s.id)} key={String(s.id)}>{String(s.id)} · {String(s.method)}</option>)}</select></label>
    <label className="field-label">功率请求模式<select aria-label="功率请求模式" value={request.mode} onChange={e => patchRequest({ mode: e.target.value })}><option value="predict_power">按速度预测功率</option><option value="fixed_power">按给定轴功率求速度</option></select></label>
    <QuantityListField label="速度采样" value={request.speeds} dimension="speed" placeholder="例如 10, 15, 20"
            onChange={values => patchRequest({ speeds: values })} />
    {request.mode === 'fixed_power' && <QuantityField label="给定轴功率" aria-label="给定轴功率" value={inputNumber(request.power)} dimension="power" kind="positive"
              onChange={value => patchRequest({ power: value === null ? '' : String(value) })} />}
    <label className="field-label">续航研究<select aria-label="续航研究场景" value={request.endurance} onChange={e => patchRequest({ endurance: e.target.value })}><option value="">不请求续航研究</option>{rows(project.endurance_scenarios).map(s => <option key={String(s.id)}>{String(s.id)}</option>)}</select></label>
  </div><FactInput label="QPC" value={request.qpc} onChange={qpc => patchRequest({ qpc })} />{buildOptions(request).error && <p className="form-error" role="alert">{buildOptions(request).error}</p>}</div>
  <ResultSection available={!!run}>{run && <p>运行 {run.id} · 请求 {run.request_fingerprint.slice(0, 16)}</p>}<div className="metric-grid"><Metric label="所选工况总质量" value={object(loading.values).total_mass_t} dimension="mass" storedUnit="t" /><Metric label="所选工况 GM" value={object(hydro.values).gm_t_m} dimension="length" storedUnit="m" /></div>
    <StudyResult label="所选工况横摇" data={hydro.loaded_roll} metrics={[["period_s", "小角度周期", "s"]]} />
    <StudyResult label="目标纵倾约束研究" data={equilibrium.trim_target_study} metrics={[["required_longitudinal_moment_kNm", "所需纵向力矩", "kN·m"]]} />
    <StudyResult label="给定轴功率求速度" data={resistance.fixed_power_study} metrics={[["speed_kn", "研究航速", "kn", "speed"]]} />
    <div className="metric-grid">{rows(resistance.power_rows).map((r, i) => <Metric key={i} label={`${units.number(r.speed_kn, "speed")} 轴功率`} value={r.shaft_power_kw} dimension="power" storedUnit="kW"
      estimate={r.estimate} source={r.complete === false ? '该采样点不完整' : r.primary_result === false ? '非主工况结果' : '当前工况运行结果'} />)}</div><Diagnostics value={resistance.diagnostics} />
  </ResultSection></div>;
}
