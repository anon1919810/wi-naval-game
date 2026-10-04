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

// Named resistance scenarios are research inputs, not computed results. Every
// declared input carries its own source and three-state estimate; unknown stays
// unknown, and explicit absence (`[]`, `present: false`) differs from an omitted
// key. Nothing here fabricates bulb, transom, appendage, thruster or roughness
// geometry, and no method outside the two canonical ones is offered.

const TABLE_METHODS = [
  { key: 'friction_method', label: '摩擦方法', value: FRICTION_METHOD },
  { key: 'interpolation_method', label: '插值方法', value: INTERPOLATION_METHOD },
  { key: 'speed_conversion_method', label: '航速换算', value: SPEED_CONVERSION_METHOD },
] as const;

export function ResistanceEditor({ project, onChange }: {
  project: ProjectDocument; onChange: (project: ProjectDocument) => void;
}) {
  const scenarios = rows(project.resistance_scenarios);
  const [choice, setChoice] = useState<string | null>(null);
  const [problems, setProblems] = useState<Record<string, string>>({});
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
    return numericProblem(spec.kind, raw) ? null : { [spec.key]: numericValue(raw) };
  }

  function inputField(spec: InputSpec) {
    const entry = object(object(selected?.input_provenance)[spec.key]);
    const value = object(selected?.inputs)[spec.key];
    const problem = problems[`${id}/${spec.key}`];
    // A convertible quantity is typed in the reader's unit and stored canonically;
    // a density, viscosity or dimensionless coefficient stays exactly as typed.
    const control = spec.dimension
      ? <QuantityField label={spec.label} ariaLabel={`${id} ${spec.label}`} value={number(value)}
        dimension={spec.dimension} storedUnit={spec.storedUnit} kind={spec.kind} invalid={Boolean(problem)}
        onChange={next => replace(patchInputValue(selected ?? {}, spec, next))} />
      : <label className="field-label">{spec.label}
        <input type="number" step="any" placeholder="未知" aria-label={`${id} ${spec.label}`}
          aria-invalid={Boolean(problem)} value={number(value) ?? ''}
          onChange={event => {
            const outcome = patchInput(selected ?? {}, spec, event.target.value);
            setProblems(previous => {
              const nextMap = { ...previous };
              const key = `${id}/${spec.key}`;
              if (outcome.problem) nextMap[key] = outcome.problem; else delete nextMap[key];
              return nextMap;
            });
            if (!outcome.problem) replace(outcome.scenario);
          }} />
        {problem && <span className="field-error" role="alert">{problem}</span>}
      </label>;
    return <div className="form-grid" key={spec.key}>
      {control}
      <label className="field-label">来源
        <input aria-label={`${id} ${spec.label} 来源`} placeholder="待补充来源"
          value={typeof entry.source === 'string' ? entry.source : ''}
          onChange={event => replace(patchProvenance(selected ?? {}, spec.key,
            { source: event.target.value.trim() === '' ? null : event.target.value }))} />
      </label>
      <EstimateInput label={`${id} ${spec.label} 估算状态`} value={entry.estimate}
        onChange={estimate => replace(patchProvenance(selected ?? {}, spec.key, { estimate }))} />
    </div>;
  }

  function presence(label: string, key: StructuredKey, state: PresenceState) {
    return <label className="field-label">{label}
      <select aria-label={`${id} ${label}`} value={state}
        onChange={event => replace(setPresence(selected ?? {}, key, event.target.value as PresenceState))}>
        <option value="unknown">未知（未声明）</option>
        <option value="absent">明确不存在</option>
        <option value="present">存在并声明数据</option>
      </select>
    </label>;
  }

  const scenario = selected ?? {};
  const appendageState = presenceState(scenario, 'appendages');
  const thrusterState = presenceState(scenario, 'bow_thruster');
  const thruster = bowThruster(scenario);
  const appendageProvenance = object(object(scenario.input_provenance).appendages);
  const thrusterProvenance = object(object(scenario.input_provenance).bow_thruster);
  const hints = selected ? scenarioHints(selected) : [];

  return <div className="resistance-editor form-stack">
    <div className="form-card"><h3>阻力研究场景</h3>
      <p>场景是研究输入：方法、姿态策略与每个形状增量都要各自声明来源。运行页按场景 ID 选择速度采样；缺来源或缺方法输入时运行会明确不可用，不会以零值代替。</p>
      {scenarios.length === 0 && <p className="form-hint">项目尚未声明任何阻力场景。空白项目可在此新建，再逐项声明形状与流体参数。</p>}
      <div className="form-grid">
        <label className="field-label">当前场景<select aria-label="选择阻力场景" value={id} onChange={event => setChoice(event.target.value)}>
          {scenarios.length === 0 && <option value="">（尚无场景）</option>}
          {scenarios.map(row => <option key={String(row.id)} value={String(row.id)}>{String(row.id)} · {String(row.method)}</option>)}
        </select></label>
        <label className="field-label">新场景 id<input aria-label="新阻力场景 id" value={newId} onChange={event => setNewId(event.target.value)} /></label>
        <button className="button button--secondary" type="button" onClick={create}>添加阻力场景</button>
      </div>
    </div>

    {selected && <>
      <div className="form-card"><h3>{id} · 方法与姿态</h3>
        <div className="form-grid">
          <label className="field-label">阻力方法<select aria-label={`${id} 阻力方法`} value={String(scenario.method)}
            onChange={event => patch({ method: event.target.value })}>
            {RESISTANCE_METHODS.map(method => <option key={method.id} value={method.id}>{method.label}（{method.id}）</option>)}
          </select></label>
          <label className="field-label">姿态策略<select aria-label={`${id} 姿态策略`} value={String(scenario.attitude_policy)}
            onChange={event => patch({ attitude_policy: event.target.value })}>
            {ATTITUDE_POLICIES.map(policy => <option key={policy.id} value={policy.id}>{policy.label}</option>)}
          </select></label>
          <label className="field-label">研究来源<input aria-label={`${id} 研究来源`} value={scenarioSource(scenario)} placeholder="待补充来源"
            onChange={event => patch({ source: event.target.value.trim() === '' ? null : event.target.value })} /></label>
          <EstimateInput label={`${id} 研究估算状态`} value={scenario.estimate} onChange={estimate => patch({ estimate })} />
        </div>
        {scenario.attitude_policy === 'selected_plane_longitudinal_trim_proxy_v1'
          && <p className="form-hint">纵倾代理的输出按契约强制为估算、非主工况且不在适用范围（model_applicable=false），与输入来源无关。</p>}
        {hints.length > 0 && <p className="form-hint" role="status">{hints.join('；')}。补齐后该场景才可作为阻力研究的可计算输入。</p>}
      </div>

      <div className="form-card"><h3>表身份与方法选择</h3>
        <p>表身份只登记来源表的编号与 SHA-256；摩擦、插值与航速换算只能选择已审查的规范方法。未声明即未知，不插入默认值。</p>
        <div className="form-grid">
          <label className="field-label">表 ID<input aria-label={`${id} 表 ID`} value={scenario.table_id == null ? '' : String(scenario.table_id)}
            onChange={event => patch({ table_id: event.target.value.trim() === '' ? null : event.target.value })} /></label>
          <label className="field-label">表 SHA-256<input aria-label={`${id} 表 SHA-256`} value={scenario.table_sha256 == null ? '' : String(scenario.table_sha256)}
            onChange={event => patch({ table_sha256: event.target.value.trim() === '' ? null : event.target.value.trim() })} /></label>
          {TABLE_METHODS.map(entry => <label className="field-label" key={entry.key}>{entry.label}
            <select aria-label={`${id} ${entry.label}`} value={scenario[entry.key] === undefined ? '' : String(scenario[entry.key])}
              onChange={event => {
                const next: Raw = { ...scenario };
                if (event.target.value === '') delete next[entry.key]; else next[entry.key] = event.target.value;
                emit(scenarios.map(row => row === selected ? next : row));
              }}>
              <option value="">未声明（未知）</option><option value={entry.value}>{entry.value}</option>
            </select></label>)}
        </div>
      </div>

      <div className="form-card"><h3>形状与流体输入</h3>
        <p>每个非空输入都需要自己的来源与估算状态；留空表示未知，不会补零。艏垂线必须位于艉垂线之前。</p>
        {RESISTANCE_INPUTS.map(spec => inputField(spec))}
      </div>

      <div className="form-card"><h3>附体与首侧推</h3>
        <p>“明确不存在”是已声明的结论，与“未知”不同。附体与首侧推各自保留自己的来源与估算状态；移除最后一条附体行等于声明本场景无附体。</p>
        <div className="form-grid">
          {presence('附体声明', 'appendages', appendageState)}
          {presence('首侧推声明', 'bow_thruster', thrusterState)}
        </div>
        <div className="form-grid">
          <label className="field-label">附体来源<input aria-label={`${id} 附体来源`} placeholder="待补充来源"
            value={typeof appendageProvenance.source === 'string' ? appendageProvenance.source : ''}
            onChange={event => replace(patchProvenance(scenario, 'appendages', { source: event.target.value.trim() === '' ? null : event.target.value }))} /></label>
          <EstimateInput label={`${id} 附体估算状态`} value={appendageProvenance.estimate}
            onChange={estimate => replace(patchProvenance(scenario, 'appendages', { estimate }))} />
          <label className="field-label">首侧推来源<input aria-label={`${id} 首侧推来源`} placeholder="待补充来源"
            value={typeof thrusterProvenance.source === 'string' ? thrusterProvenance.source : ''}
            onChange={event => replace(patchProvenance(scenario, 'bow_thruster', { source: event.target.value.trim() === '' ? null : event.target.value }))} /></label>
          <EstimateInput label={`${id} 首侧推估算状态`} value={thrusterProvenance.estimate}
            onChange={estimate => replace(patchProvenance(scenario, 'bow_thruster', { estimate }))} />
        </div>
        {(appendageState === 'unknown' || thrusterState === 'unknown') && <p className="form-hint">
          未声明的输入不写入场景；先在上方选择“明确不存在”或“存在并声明数据”，该输入与其来源、估算状态才一起保存。
        </p>}
        {appendageState === 'present' && <div className="form-card-body">
          {appendages(scenario).map((item, index) => <div className="form-grid" key={index}>
            <QuantityField label={`附体 ${index + 1} 面积`} ariaLabel={`${id} 附体 ${index + 1} 面积`} value={number(item.area_m2)}
              dimension="area" storedUnit="m" kind="nonnegative"
              onChange={next => replace(patchAppendage(scenario, index, { area_m2: next }))} />
            {/* The increment factor is dimensionless, so it is typed and shown as typed. */}
            <label className="field-label">附体 {index + 1} 阻力增量系数<input type="number" step="any" placeholder="未知"
              aria-label={`${id} 附体 ${index + 1} 系数`} value={number(item.factor) ?? ''}
              onChange={event => { const value = scalar(APPENDAGE_FACTOR, event.target.value); if (value) replace(patchAppendage(scenario, index, value)); }} /></label>
            <button className="text-button" type="button" onClick={() => replace(removeAppendage(scenario, index))}>移除附体 {index + 1}</button>
          </div>)}
          <button className="button button--secondary" type="button" onClick={() => replace(addAppendage(scenario))}>添加附体</button>
        </div>}
        {appendageState === 'absent' && <p className="form-hint">已声明本场景无附体增量（appendages: []）。</p>}
        {thrusterState === 'present' && <div className="form-card-body"><div className="form-grid">
          {[THRUSTER_DIAMETER, THRUSTER_COEFFICIENT].map(spec => spec.dimension
            ? <QuantityField key={spec.key} label={spec.label} ariaLabel={`${id} ${spec.label}`} value={number(thruster[spec.key])}
              dimension={spec.dimension} storedUnit={spec.storedUnit} kind="positive"
              onChange={next => replace(patchThruster(scenario, { [spec.key]: next }))} />
            : <label className="field-label" key={spec.key}>{spec.label}
              <input type="number" step="any" placeholder="未知" aria-label={`${id} ${spec.label}`} value={number(thruster[spec.key]) ?? ''}
                onChange={event => { const value = scalar(spec, event.target.value); if (value) replace(patchThruster(scenario, value)); }} /></label>)}
        </div><p className="form-hint">首侧推存在时，直径与增量系数都必须为正数；缺少任一项该场景不可计算。改为“明确不存在”会清除这些增量几何。</p></div>}
        {thrusterState === 'absent' && <p className="form-hint">已声明本场景无首侧推增量（present: false，不携带直径或系数）。</p>}
      </div>

      <div className="form-card"><h3>QPC 与敏感性</h3>
        <p>QPC 只在请求中显式给定或在此声明；不会为场景插入默认推进系数。敏感性样本按已声明值逐点计算。</p>
        <FactInput label={`${id} QPC`} value={scenario.qpc} onChange={value => patch({ qpc: value })} />
        {scenario.qpc_sensitivity === undefined
          ? <button className="button button--secondary" type="button"
            onClick={() => patch({ qpc_sensitivity: { values: [], source: null, estimate: null } })}>添加 QPC 敏感性</button>
          : <div className="form-card-body">
            <label className="field-label">QPC 样本（逗号分隔，严格递增）
              <input aria-label={`${id} QPC 敏感性样本`} placeholder="例如 0.5, 0.55, 0.6"
                value={Array.isArray(object(scenario.qpc_sensitivity).values) ? (object(scenario.qpc_sensitivity).values as number[]).join(', ') : ''}
                onChange={event => patch({ qpc_sensitivity: { ...object(scenario.qpc_sensitivity), values: parseList(event.target.value) } })} /></label>
            <div className="form-grid">
              <label className="field-label">敏感性来源<input aria-label={`${id} QPC 敏感性来源`}
                value={typeof object(scenario.qpc_sensitivity).source === 'string' ? String(object(scenario.qpc_sensitivity).source) : ''}
                onChange={event => patch({ qpc_sensitivity: { ...object(scenario.qpc_sensitivity), source: event.target.value.trim() === '' ? null : event.target.value } })} /></label>
              <EstimateInput label={`${id} QPC 敏感性估算状态`} value={object(scenario.qpc_sensitivity).estimate}
                onChange={estimate => patch({ qpc_sensitivity: { ...object(scenario.qpc_sensitivity), estimate } })} />
            </div>
            <button className="text-button" type="button" onClick={() => { const next: Raw = { ...scenario }; delete next.qpc_sensitivity; emit(scenarios.map(row => row === selected ? next : row)); }}>移除 QPC 敏感性</button>
          </div>}
      </div>

      <div className="form-card"><h3>移除</h3>
        <p>移除场景只影响当前草稿：已保存运行仍引用它当时的请求身份与指纹，不会被改写。移除后同名 ID 可以再次使用，请确认没有运行仍按该 ID 解释。</p>
        <button className="text-button" type="button" onClick={() => { emit(scenarios.filter(row => row !== selected)); setChoice(null); }}>移除场景 {id}</button>
      </div>
    </>}
  </div>;
}

function parseList(text: string): number[] {
  return text.split(/[\s,，]+/).filter(Boolean).map(Number);
}