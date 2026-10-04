import { useState } from 'react';

import type { ProjectDocument, RunView } from '../types';
import { EstimateInput } from './FactInput';
import { Diagnostics, ResultSection } from './FormResults';
import { number, numericProblem, numericValue, object, rows, stageData, uniqueId, type Raw } from './formModel';
import {
  APERTURE_HEIGHT, CONNECTION_FIELDS, connections, environmentDensity, EQUILIBRIUM_RHO_T_M3, newConnection, newOpening,
  newScenario, newTank, sea, TANK_FIELDS, tanks, tankFromCompartment, withApertureHeight,
  type FieldSpec, type FloodingRequest,
} from './floodingModel';
import { QuantityField, QuantityListField } from './QuantityField';
import { FloodingResults } from './FloodingResults';

// Saved flooding scenario drafts plus the project's own compartment geometry.
//
// A scenario is research input, not a second weight ledger: it holds tank
// geometry, declared initial liquid, connections and openings for one damage
// case. Nothing here solves anything, copies no water into the ledger, and
// borrows no geometry that the project or the user did not declare.

type TriState = 'unknown' | 'yes' | 'no';

function tri(value: unknown): TriState { return typeof value === 'boolean' ? (value ? 'yes' : 'no') : 'unknown'; }
function triValue(state: TriState): boolean | null { return state === 'unknown' ? null : state === 'yes'; }

function metadataFields(prefix: string, entry: Raw, onPatch: (patch: Raw) => void) {
  return <div className="form-grid">
    <label className="field-label">来源<input aria-label={`${prefix} 来源`} placeholder="待补充来源"
      value={typeof entry.source === 'string' ? entry.source : ''}
      onChange={event => onPatch({ source: event.target.value.trim() === '' ? null : event.target.value })} /></label>
    <EstimateInput label={`${prefix} 估算状态`} value={entry.estimate} onChange={estimate => onPatch({ estimate })} />
  </div>;
}

// A convertible quantity is typed in the reader's unit and stored canonically;
// a dimensionless or density entry keeps the plain canonical number input.
function numericField(spec: FieldSpec, prefix: string, value: unknown, onChange: (raw: string) => void, problem: string | null) {
  if (spec.dimension) return <QuantityField key={spec.key} label={spec.label} ariaLabel={`${prefix} ${spec.label}`}
    value={number(value)} dimension={spec.dimension} storedUnit={spec.storedUnit} kind={spec.kind} invalid={Boolean(problem)}
    onChange={next => onChange(next === null ? '' : String(next))} />;
  return <label className="field-label" key={spec.key}>{spec.label}
    <input type="number" step="any" placeholder="未知" aria-label={`${prefix} ${spec.label}`}
      aria-invalid={Boolean(problem)} value={number(value) ?? ''} onChange={event => onChange(event.target.value)} />
    {problem && <span className="field-error" role="alert">{problem}</span>}
  </label>;
}

export function DamageEditor({ project, run, request, onChange, onRequestChange, requestError }: {
  project: ProjectDocument; run: RunView | null; request: FloodingRequest;
  onChange: (project: ProjectDocument) => void; onRequestChange: (request: FloodingRequest) => void;
  requestError: string;
}) {
  const scenarios = rows(project.flooding_scenarios);
  const compartments = rows(project.compartments);
  const [choice, setChoice] = useState<string | null>(null);
  const [newId, setNewId] = useState('flooding_1');
  const [newTankId, setNewTankId] = useState('tank_1');
  const [newConnectionId, setNewConnectionId] = useState('opening_1');
  const [newOpeningId, setNewOpeningId] = useState('opening_1');
  const [newCompartmentId, setNewCompartmentId] = useState('compartment_1');
  const [problems, setProblems] = useState<Record<string, string>>({});
  const [copyNote, setCopyNote] = useState('');
  const selected = scenarios.find(row => String(row.id) === choice) ?? scenarios[0] ?? null;
  const id = selected ? String(selected.id) : '';
  const data = stageData(run, 'flooding');

  function emit(list: Raw[]) { onChange({ ...project, flooding_scenarios: list }); }
  function patch(value: Raw) { if (selected) emit(scenarios.map(row => row === selected ? { ...row, ...value } : row)); }
  function emitCompartments(list: Raw[]) { onChange({ ...project, compartments: list }); }
  function create() {
    const next = uniqueId(newId.trim() || 'flooding_1', scenarios.map(row => row.id));
    setChoice(next);
    setProblems({});
    setCopyNote('');
    emit([...scenarios, newScenario(next)]);
  }

  const scenario = selected ?? {};
  const water = sea(scenario);
  const tankRows = tanks(scenario);
  const connectionRows = connections(scenario);
  const openingRows = rows(scenario.openings);
  const nodeIds = [String(water.id ?? ''), ...tankRows.map(tank => String(tank.id))]
    .filter(value => value.trim() !== '');
  const openingState: TriState = !('openings' in scenario) ? 'unknown'
    : scenario.openings === null ? 'unknown' : openingRows.length === 0 ? 'yes' : 'no';
  const environment = request.rho.trim() === '' ? EQUILIBRIUM_RHO_T_M3 : environmentDensity(request) ?? '无效输入';
  function compartmentReferences(compartmentId: unknown): string[] {
    const protectedIds = object(object(object(project.systems).armour).fixed).minimum_main_belt;
    const references = Array.isArray(object(protectedIds).protected_compartment_ids)
      && (object(protectedIds).protected_compartment_ids as unknown[]).includes(compartmentId) ? ['主装甲带研究'] : [];
    for (const preset of rows(project.damage_presets)) {
      if (String(compartmentId) in object(preset.initial_water_volumes_m3)) references.push(`破损预设 ${String(preset.id)}`);
    }
    return references;
  }

  function refuse(key: string, kind: FieldSpec['kind'], raw: string): boolean {
    const problem = numericProblem(kind, raw);
    setProblems(previous => {
      const next = { ...previous };
      if (problem) next[key] = problem; else delete next[key];
      return next;
    });
    return problem !== null;
  }
  function patchTank(index: number, patchValue: Raw) {
    patch({ tanks: tankRows.map((tank, i) => i === index ? { ...tank, ...patchValue } : tank) });
  }
  // A row replacement, not a merge: removing an optional key (the requested
  // aperture height) must really drop it instead of keeping the previous value.
  function replaceConnection(index: number, row: Raw) {
    patch({ connections: connectionRows.map((edge, i) => i === index ? row : edge) });
  }
  function patchConnection(index: number, patchValue: Raw) {
    replaceConnection(index, { ...connectionRows[index], ...patchValue });
  }
  function tankField(index: number, spec: FieldSpec, raw: string) {
    if (refuse(`${id}/tank${index}/${spec.key}`, spec.kind, raw)) return;
    patchTank(index, { [spec.key]: numericValue(raw) });
  }
  function connectionField(index: number, spec: FieldSpec, raw: string) {
    if (refuse(`${id}/conn${index}/${spec.key}`, spec.kind, raw)) return;
    patchConnection(index, { [spec.key]: numericValue(raw) });
  }
  function patchOpening(index: number, patchValue: Raw) {
    patch({ openings: openingRows.map((row, i) => i === index ? { ...row, ...patchValue } : row) });
  }
  function replaceOpening(index: number, row: Raw) {
    patch({ openings: openingRows.map((entry, i) => i === index ? row : entry) });
  }
  function compartmentField(index: number, spec: FieldSpec, raw: string) {
    if (refuse(`compartment${index}/${spec.key}`, spec.kind, raw)) return;
    emitCompartments(compartments.map((row, i) => i === index ? { ...row, [spec.key]: numericValue(raw) } : row));
  }
  // Removing a referenced tank would leave a dangling edge, so the removal states
  // the connections it takes with it instead of leaving a broken reference.
  function removeTank(index: number) {
    const victim = String(tankRows[index].id);
    const referencing = connectionRows.filter(edge => edge.from === victim || edge.to === victim).map(edge => String(edge.id));
    patch({ tanks: tankRows.filter((_, i) => i !== index),
      connections: referencing.length ? connectionRows.filter(edge => !referencing.includes(String(edge.id))) : connectionRows });
    setCopyNote(referencing.length ? `已移除舱室 ${victim} 及引用它的连接：${referencing.join('、')}` : '');
  }
  function copyCompartments() {
    const seaDensity = number(water.fluid_density_t_m3);
    const taken = new Set(nodeIds);
    const copies: Raw[] = [];
    const skipped: string[] = [];
    for (const compartment of compartments) {
      const copy = tankFromCompartment(compartment, seaDensity);
      if (!copy) { skipped.push(`${String(compartment.id)}（缺少舱室几何）`); continue; }
      if (taken.has(String(copy.id))) { skipped.push(`${String(copy.id)}（与已有节点同名）`); continue; }
      taken.add(String(copy.id));
      copies.push(copy);
    }
    if (copies.length === 0) {
      setCopyNote(`没有可复制的项目舱室：${skipped.join('、') || '项目未声明舱室'}`);
      return;
    }
    patch({ tanks: [...tankRows, ...copies] });
    setCopyNote(`已复制项目舱室 ${copies.map(tank => String(tank.id)).join('、')} 的几何到场景（不含水量，未改动账本）。${skipped.length ? `跳过：${skipped.join('、')}` : ''}`);
  }

  return <div className="damage-editor form-stack">
    <div className="form-card"><h3>破损场景草稿</h3>
      <p>场景是研究输入，不是第二份重量账本：舱室几何、连接与开口随项目修订保存，运行只读取所选场景。空白项目可在此新建；旧项目没有该字段时按“无场景”处理。</p>
      {scenarios.length === 0 && <p className="form-hint">项目尚未声明破损场景。新建后可显式复制项目舱室作为场景舱室，但不会复制任何水量或账本质量。</p>}
      <div className="form-grid">
        <label className="field-label">当前场景<select aria-label="选择破损场景" value={id} onChange={event => setChoice(event.target.value)}>
          {scenarios.length === 0 && <option value="">（尚无场景）</option>}
          {scenarios.map(row => <option key={String(row.id)} value={String(row.id)}>{String(row.id)}</option>)}
        </select></label>
        <label className="field-label">新场景 id<input aria-label="新破损场景 id" value={newId} onChange={event => setNewId(event.target.value)} /></label>
        <button className="button button--secondary" type="button" onClick={create}>添加破损场景</button>
      </div>
    </div>

    {selected && <>
      <div className="form-card"><h3>{id} · 时长与来源</h3>
        <div className="form-grid">
          <label className="field-label">场景名称<input aria-label={`${id} 场景名称`} value={typeof scenario.label === 'string' ? scenario.label : ''}
            onChange={event => patch({ label: event.target.value })} /></label>
          {numericField({ key: 'duration_s', label: '进水时长 · s', kind: 'nonnegative' }, id, scenario.duration_s,
          raw => { if (!refuse(`${id}/duration_s`, 'nonnegative', raw)) patch({ duration_s: numericValue(raw) }); },
          problems[`${id}/duration_s`] ?? null)}
          {numericField({ key: 'time_step_s', label: '时间步长 · s', kind: 'positive' }, id, scenario.time_step_s,
          raw => { if (!refuse(`${id}/time_step_s`, 'positive', raw)) patch({ time_step_s: numericValue(raw) }); },
          problems[`${id}/time_step_s`] ?? null)}
        </div>
        {metadataFields(`${id} 场景`, scenario, patch)}
        <p className="form-hint">时长必须是已知非负数、步长必须是已知正数；缺任一项时场景可以保存为草稿，但不能提交运行。</p>
      </div>

      <div className="form-card"><h3>海水节点</h3>
        <div className="form-grid">
          <label className="field-label">海水节点 id<input aria-label={`${id} 海水节点 id`} value={water.id == null ? '' : String(water.id)}
            onChange={event => patch({ sea: { ...water, id: event.target.value } })} /></label>
          <label className="field-label">海水密度 · t/m³<input type="number" step="any" placeholder="未知" aria-label={`${id} 海水密度`}
            value={number(water.fluid_density_t_m3) ?? ''}
            onChange={event => patch({ sea: { ...water, fluid_density_t_m3: numericValue(event.target.value) } })} /></label>
        </div>
        {metadataFields(`${id} 海水`, water, patchValue => patch({ sea: { ...water, ...patchValue } }))}
        <p className="form-hint">海水、舱室与连接的液体密度必须一致，并等于本次请求的环境密度（当前 {environment} t/m³）。不匹配时运行会被拒绝，而不是换算或取默认。</p>
      </div>

      <div className="form-card"><h3>场景舱室</h3>
        <p>每个舱室声明长宽高、位置、渗透率、自由液面状态与初始水量。初始水量是物理体积，不是百分比；0 表示已知空舱，未知则留空。</p>
        {tankRows.length === 0 && <p className="form-hint">该场景还没有舱室。可手动添加，或显式复制项目舱室几何（不复制水量）。</p>}
        <div className="form-grid">
          <label className="field-label">新增舱室 id<input aria-label="新增舱室 id" value={newTankId} onChange={event => setNewTankId(event.target.value)} /></label>
          <button className="button button--secondary" type="button"
            onClick={() => patch({ tanks: [...tankRows, newTank(uniqueId(newTankId.trim() || 'tank_1', nodeIds))] })}>添加舱室</button>
          <button className="button button--secondary" type="button" onClick={copyCompartments}>从项目舱室复制</button>
        </div>
        {copyNote && <p className="form-hint" role="status">{copyNote}</p>}
        {tankRows.map((tank, index) => {
          const references = connectionRows.filter(edge => edge.from === tank.id || edge.to === tank.id).map(edge => String(edge.id));
          return <details className="form-card" open key={String(tank.id ?? index)}>
            <summary>舱室 {String(tank.id)}</summary><div className="form-card-body">
              <div className="form-grid">
                {TANK_FIELDS.map(spec => numericField(spec, `${id} 舱室 ${String(tank.id)}`, tank[spec.key],
                  raw => tankField(index, spec, raw), problems[`${id}/tank${index}/${spec.key}`] ?? null))}
                <label className="field-label">自由液面<select aria-label={`${id} 舱室 ${String(tank.id)} 自由液面`} value={tri(tank.free_surface)}
                  onChange={event => patchTank(index, { free_surface: triValue(event.target.value as TriState) })}>
                  <option value="unknown">未知（未声明）</option><option value="yes">存在自由液面</option><option value="no">无自由液面</option>
                </select></label>
                <label className="field-label">液体密度 · t/m³<input type="number" step="any" placeholder="未知"
                  aria-label={`${id} 舱室 ${String(tank.id)} 液体密度 · t/m³`} value={number(tank.fluid_density_t_m3) ?? ''}
                  onChange={event => patchTank(index, { fluid_density_t_m3: numericValue(event.target.value) })} /></label>
              </div>
              {metadataFields(`${id} 舱室 ${String(tank.id)}`, tank, patchValue => patchTank(index, patchValue))}
              {references.length > 0 && <p className="form-hint">被连接引用：{references.join('、')}。移除此舱室会同时移除这些连接。</p>}
              <button className="text-button" type="button" onClick={() => removeTank(index)}>
                移除舱室 {String(tank.id)}{references.length ? `（同时移除 ${references.length} 条连接）` : ''}</button>
            </div></details>;
        })}
        <p className="form-hint">重复计重提醒：场景初始水量是相对所选载荷账本的附加质量。若该舱室的水已作为账本条目（如舱底水）计入，就不能再作为初始水量填入；舱室 id 也不得与账本条目同名。</p>
      </div>

      <div className="form-card"><h3>连接</h3>
        <p>连接是唯一的流动通道：端点只能是海水节点或已声明舱室，两端必须不同。Cd 缺失不会被补默认值；面积或 Cd 的显式 0 表示零流量。</p>
        <div className="form-grid">
          <label className="field-label">新增连接 id<input aria-label="新增连接 id" value={newConnectionId} onChange={event => setNewConnectionId(event.target.value)} /></label>
          <button className="button button--secondary" type="button"
            onClick={() => {
              const nextId = uniqueId(newConnectionId.trim() || 'opening_1', connectionRows.map(edge => edge.id));
              setNewConnectionId('opening_1');
              patch({ connections: [...connectionRows, { ...newConnection(nextId), from: nodeIds[0] ?? '', to: nodeIds[1] ?? '' }] });
            }}>添加连接</button>
        </div>
        {connectionRows.map((edge, index) => <details className="form-card" open key={String(edge.id ?? index)}>
          <summary>连接 {String(edge.id)}</summary><div className="form-card-body">
            <div className="form-grid">
              {(['from', 'to'] as const).map((side, position) => <label className="field-label" key={side}>{position ? '终点' : '起点'}
                <select aria-label={`${id} 连接 ${String(edge.id)} ${position ? '终点' : '起点'}`} value={String(edge[side] ?? '')}
                  onChange={event => patchConnection(index, { [side]: event.target.value })}>
                  <option value="">未选择节点</option>
                  {nodeIds.map(node => <option key={node} value={node}>{node === String(water.id) ? `${node}（海水）` : node}</option>)}
                </select></label>)}
              {CONNECTION_FIELDS.filter(spec => spec.key !== 'aperture_height_m').map(spec => numericField(spec, `${id} 连接 ${String(edge.id)}`, edge[spec.key],
                raw => connectionField(index, spec, raw), problems[`${id}/conn${index}/${spec.key}`] ?? null))}
              <label className="field-label">液体密度 · t/m³<input type="number" step="any" placeholder="未知"
                aria-label={`${id} 连接 ${String(edge.id)} 液体密度 · t/m³`} value={number(edge.fluid_density_t_m3) ?? ''}
                onChange={event => patchConnection(index, { fluid_density_t_m3: numericValue(event.target.value) })} /></label>
              <label className="field-label">开启状态<select aria-label={`${id} 连接 ${String(edge.id)} 开启状态`} value={tri(edge.open)}
                onChange={event => patchConnection(index, { open: triValue(event.target.value as TriState) })}>
                <option value="unknown">未知（未声明）</option><option value="yes">开启</option><option value="no">关闭</option>
              </select></label>
            </div>
            {/* The finite-aperture check is optional: the key exists only when it
                is requested, so a default null can never block a complete edge. */}
            <label><input type="checkbox" aria-label={`${id} 连接 ${String(edge.id)} 请求有限开口高度检查`}
              checked={'aperture_height_m' in edge}
              onChange={event => replaceConnection(index, withApertureHeight(edge, event.target.checked))} />请求有限开口高度检查（液面越过时停止）</label>
            {'aperture_height_m' in edge && numericField(APERTURE_HEIGHT, `${id} 连接 ${String(edge.id)}`, edge.aperture_height_m,
              raw => connectionField(index, APERTURE_HEIGHT, raw), problems[`${id}/conn${index}/aperture_height_m`] ?? null)}
            {metadataFields(`${id} 连接 ${String(edge.id)}`, edge, patchValue => patchConnection(index, patchValue))}
            <button className="text-button" type="button"
              onClick={() => { patch({ connections: connectionRows.filter((_, i) => i !== index) }); setCopyNote(''); }}>移除连接 {String(edge.id)}</button>
          </div></details>)}
      </div>

      <div className="form-card"><h3>场景开口声明</h3>
        <p>场景开口覆盖项目开口定义。未声明表示沿用项目定义；“明确无开口”表示已声明没有开放点；逐点声明可增删任意多个开口点。</p>
        <label className="field-label">开口知识<select aria-label={`${id} 场景开口知识`} value={openingState}
          onChange={event => {
            const state = event.target.value as TriState;
            if (state === 'unknown') { const next: Raw = { ...scenario }; delete next.openings; emit(scenarios.map(row => row === selected ? next : row)); }
            else if (state === 'yes') patch({ openings: [] });
            else patch({ openings: [newOpening('opening_1')] });
          }}>
          <option value="unknown">沿用项目定义（未声明）</option>
          <option value="yes">明确无开放点（[]）</option>
          <option value="no">逐点声明开放口</option>
        </select></label>
        {openingState === 'no' && <div className="form-grid">
          <label className="field-label">新增开口 id<input aria-label="新增开口 id" value={newOpeningId} onChange={event => setNewOpeningId(event.target.value)} /></label>
          <button className="button button--secondary" type="button"
            onClick={() => {
              const nextId = uniqueId(newOpeningId.trim() || 'opening_1', openingRows.map(item => item.id));
              setNewOpeningId('opening_1');
              patch({ openings: [...openingRows, newOpening(nextId)] });
            }}>添加开口</button>
        </div>}
        {openingRows.map((opening, index) => <div className="form-card" key={String(opening.id ?? index)}>
          <div className="form-card-body"><div className="form-grid">
            <label className="field-label">开口 id<input aria-label={`${id} 开口 ${String(opening.id)} id`} value={String(opening.id ?? '')}
              onChange={event => patchOpening(index, { id: event.target.value })} /></label>
            <label className="field-label">类型<input aria-label={`${id} 开口 ${String(opening.id)} 类型`} placeholder="可选"
              value={typeof opening.kind === 'string' ? opening.kind : ''}
              onChange={event => {
              const kind = event.target.value.trim();
              const next: Raw = { ...opening };
              if (kind) next.kind = kind; else delete next.kind;
              replaceOpening(index, next);
            }} /></label>
            {(['x_m', 'y_m', 'z_m'] as const).map(field => <QuantityField key={field} label={field === 'x_m' ? '纵向' : field === 'y_m' ? '横向' : '高度'}
              ariaLabel={`${id} 开口 ${String(opening.id)} ${field}`} value={number(opening[field])} dimension="length" storedUnit="m"
              onChange={next => patchOpening(index, { [field]: next })} />)}
            <label className="field-label">开启<select aria-label={`${id} 开口 ${String(opening.id)} 开启`} value={tri(opening.open)}
              onChange={event => patchOpening(index, { open: triValue(event.target.value as TriState) })}>
              <option value="unknown">未知</option><option value="yes">开启</option><option value="no">关闭</option></select></label>
            {metadataFields(`${id} 开口 ${String(opening.id)}`, opening, patchValue => patchOpening(index, patchValue))}
            <button className="text-button" type="button"
              onClick={() => patch({ openings: openingRows.filter((_, i) => i !== index) })}>移除开口 {String(opening.id)}</button>
          </div></div>
        </div>)}
      </div>

      <div className="form-card"><h3>本次破损计算请求</h3>
        <p>请求随运行记录保存，不会改动场景本身。未选择场景时不请求破损阶段；选择后按同一修订与工况提交。</p>
        <div className="form-grid">
          <label className="field-label">破损场景<select aria-label="请求破损场景" value={request.scenario}
            onChange={event => onRequestChange({ ...request, scenario: event.target.value })}>
            <option value="">不请求破损研究</option>
            {scenarios.map(row => <option key={String(row.id)} value={String(row.id)}>{String(row.id)}</option>)}
          </select></label>
          {/* Density is canonical: it is never scaled by a display preference. */}
          <label className="field-label">环境与海水密度 · t/m³<input type="number" step="any" placeholder={`默认 ${EQUILIBRIUM_RHO_T_M3}`}
            aria-label="破损环境密度" value={request.rho}
            onChange={event => onRequestChange({ ...request, rho: event.target.value })} /></label>
          <label className="field-label">最大接受步数<input type="number" step="1" placeholder="内核默认 10000" aria-label="破损最大接受步数"
            value={request.steps} onChange={event => onRequestChange({ ...request, steps: event.target.value })} /></label>
          <label className="field-label">每步减半重试次数<input type="number" step="1" placeholder="内核默认 40" aria-label="破损减半重试次数"
            value={request.halvings} onChange={event => onRequestChange({ ...request, halvings: event.target.value })} /></label>
          <label className="field-label">重力加速度 · m/s²<input type="number" step="any" placeholder="内核默认 9.80665" aria-label="破损重力加速度"
            value={request.gravity} onChange={event => onRequestChange({ ...request, gravity: event.target.value })} /></label>
          <QuantityListField label="剩余稳性采样" value={request.gzAngles} dimension="angle" placeholder="例如 10, 20, 30, 40, 50"
            onChange={values => onRequestChange({ ...request, gzAngles: values })} />
          <label className="field-label">剩余稳性快照<select aria-label="破损剩余稳性快照" value={request.gzSnapshot}
            onChange={event => onRequestChange({ ...request, gzSnapshot: event.target.value as FloodingRequest['gzSnapshot'] })}>
            <option value="final">仅最终状态</option><option value="each_state">每个已接受状态</option>
          </select></label>
        </div>
        {requestError && <p className="form-error" role="alert">{requestError}</p>}
        <p className="form-hint">环境密度是显式请求选择：留空时内核对本次请求的全部阶段使用默认海水密度 {EQUILIBRIUM_RHO_T_M3} t/m³（淡水等研究需显式填写，并与海水节点一致）。剩余稳性使用与进水相同的密度、基准与边界条件；曲线是剩余稳性事实，不是安全性结论。</p>
      </div>

      <div className="form-card"><h3>移除场景</h3>
        <p>移除只影响当前草稿；已保存运行仍引用它当时的请求身份与指纹，不会被改写。</p>
        <button className="text-button" type="button"
          onClick={() => { emit(scenarios.filter(row => row !== selected)); setChoice(null); setCopyNote(''); }}>移除场景 {id}</button>
      </div>
    </>}

    <div className="form-card"><h3>项目舱室几何</h3>
      <p>项目舱室是主装甲带研究与场景复制的来源：主带研究按这里声明的范围取舱段，端部余量另行声明。这里只登记几何与来源，不产生质量。</p>
      {compartments.length === 0 && <p className="form-hint">项目尚未声明舱室。可在此建立；几何未知时请留空，不要填 0。</p>}
      <div className="form-grid">
        <label className="field-label">新增舱室 id<input aria-label="新增项目舱室 id" value={newCompartmentId}
          onChange={event => setNewCompartmentId(event.target.value)} /></label>
        <button className="button button--secondary" type="button"
          onClick={() => {
            const nextId = uniqueId(newCompartmentId.trim() || 'compartment_1', compartments.map(row => row.id));
            setNewCompartmentId('compartment_1');
            emitCompartments([...compartments, { id: nextId, label: nextId, ...Object.fromEntries(
              TANK_FIELDS.filter(field => field.key !== 'initial_volume_m3').map(field => [field.key, null])), free_surface: null, source: null, estimate: null }]);
          }}>添加项目舱室</button>
      </div>
      {compartments.map((compartment, index) => <details className="form-card" open key={String(compartment.id ?? index)}>
        <summary>项目舱室 {String(compartment.label ?? compartment.id)}</summary><div className="form-card-body">
          <div className="form-grid">
            <label className="field-label">舱室 id<input aria-label={`项目舱室 ${String(compartment.id)} id`} value={String(compartment.id ?? '')} readOnly />
              <small>建立后保持不变，避免破坏研究引用。</small></label>
            <label className="field-label">名称<input aria-label={`项目舱室 ${String(compartment.id)} 名称`} value={String(compartment.label ?? '')}
              onChange={event => emitCompartments(compartments.map((row, i) => i === index ? { ...row, label: event.target.value } : row))} /></label>
            {TANK_FIELDS.filter(field => field.key !== 'initial_volume_m3').map(spec => numericField(spec,
              `项目舱室 ${String(compartment.id)}`, compartment[spec.key], raw => compartmentField(index, spec, raw),
              problems[`compartment${index}/${spec.key}`] ?? null))}
            <label className="field-label">自由液面<select aria-label={`项目舱室 ${String(compartment.id)} 自由液面`} value={tri(compartment.free_surface)}
              onChange={event => emitCompartments(compartments.map((row, i) => i === index ? { ...row, free_surface: triValue(event.target.value as TriState) } : row))}>
              <option value="unknown">未知（未声明）</option><option value="yes">存在自由液面</option><option value="no">无自由液面</option>
            </select></label>
          </div>
          {metadataFields(`项目舱室 ${String(compartment.id)}`, compartment,
            patchValue => emitCompartments(compartments.map((row, i) => i === index ? { ...row, ...patchValue } : row)))}
          {compartmentReferences(compartment.id).length > 0 && <p className="form-hint">被引用：{compartmentReferences(compartment.id).join('、')}。先在对应研究中移除引用，才能删除舱室。</p>}
          <button className="text-button" type="button" disabled={compartmentReferences(compartment.id).length > 0}
            onClick={() => emitCompartments(compartments.filter((_, i) => i !== index))}>移除项目舱室 {String(compartment.id)}</button>
        </div></details>)}
    </div>

    <ResultSection available={!!run}>
      {!!run && data.status != null && <p className="result-context">已保存运行 {run.id} · 场景 {String(object(data.scenario).id ?? '未知')} · 请求指纹 {run.request_fingerprint}。下方是该运行的结果；修改当前场景选择或请求不会重算这些结果。</p>}
      {data.status == null
        ? <p className="section-intro">选择场景并运行后显示停止原因、守恒误差与时间序列。</p>
        : <FloodingResults data={data} />}
      <Diagnostics value={data.diagnostics} />
    </ResultSection>
  </div>;
}
