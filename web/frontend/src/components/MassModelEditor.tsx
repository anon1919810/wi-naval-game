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

// Physical mass models compare a declared formula against the selected loading
// ledger. This editor never computes a mass and never writes one: the ledger
// stays the only mass authority, and a difference is only a review-required
// proposal in the saved result.

export function MassModelEditor({ project, run, onChange }: {
  project: ProjectDocument; run: RunView | null; onChange: (project: ProjectDocument) => void;
}) {
  const units = useUnits();
  const systems = object(project.systems);
  const leaves = systemLeaves(systems);
  const [choice, setChoice] = useState<string | null>(null);
  const [method, setMethod] = useState<string>(MASS_METHODS[0].id);
  const [newId, setNewId] = useState('model_1');
  const [problems, setProblems] = useState<Record<string, string>>({});
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
    return <div className="form-card"><h3>系统物理质量模型</h3>
      <p>质量模型把声明的物理公式与所选载荷账本对比，用于检查账本质量。它不会改变账本质量。</p>
      <p className="form-hint">项目尚未声明任何系统叶（没有 weight_item_ids / status / mass_models 边界）。请先在火炮、鱼雷、装甲或动力页建立系统并绑定账本条目，再回来添加质量模型。</p>
    </div>;
  }

  const models = modelList(leaf.leaf);
  return <div className="mass-model-editor form-stack">
    <div className="form-card"><h3>系统选择</h3>
      <p>固定装甲、动力装置与各武备叶都是兼容的系统边界；模型必须绑定该叶已链接的账本条目，才能与账本质量比较。</p>
      <div className="form-grid">
        <label className="field-label">当前系统<select aria-label="选择系统叶" value={leaf.id} onChange={event => setChoice(event.target.value)}>
          {leaves.map(item => <option key={item.id} value={item.id}>{item.id}</option>)}
        </select></label>
        <label className="field-label">系统账本条目<input aria-label={`${leaf.id} 已绑定账本条目`} readOnly
          value={stringList(leaf.leaf.weight_item_ids).join(', ') || '（尚未绑定）'} /></label>
      </div>
      {stringList(leaf.leaf.weight_item_ids).length === 0
        && <p className="form-hint">该系统尚未绑定账本条目：运行时会出现 systems.present_without_weight_items，质量模型也无法比较。</p>}
    </div>

    {models.map((model, index) => {
      const spec = methodSpec(model.method);
      const hints = modelHints(model, leaf.leaf);
      const inputs = modelInputs(model);
      const provenance = modelProvenance(model);
      const tolerance = object(model.comparison_tolerance);
      function patchModel(value: Raw) { patchModels(models.map((row, i) => i === index ? { ...row, ...value } : row)); }
      function field(input: ModelField) {
        const problem = problems[`${model.id}/${input.key}`];
        // A density or other canonical quantity keeps a plain input; a geometry or
        // mass input is typed in the reader's unit and stored canonically.
        const valueControl = input.dimension
          ? <QuantityField label={input.label} ariaLabel={`${model.id} ${input.label}`} value={number(inputs[input.key])}
            dimension={input.dimension} storedUnit={input.storedUnit} kind={input.kind} invalid={Boolean(problem)}
            onChange={next => patchModel({ inputs: { ...inputs, [input.key]: next } })} />
          : <label className="field-label">{input.label}
            <input type="number" step="any" placeholder="未知" aria-label={`${model.id} ${input.label}`}
              aria-invalid={Boolean(problem)} value={number(inputs[input.key]) ?? ''}
              onChange={event => {
                const outcome = patchModelInput(model, input, event.target.value);
                setProblems(previous => {
                  const next = { ...previous };
                  const key = `${model.id}/${input.key}`;
                  if (outcome.problem) next[key] = outcome.problem; else delete next[key];
                  return next;
                });
                if (!outcome.problem) patchModel(outcome.model);
              }} />
            {problem && <span className="field-error" role="alert">{problem}</span>}
          </label>;
        return <div className="form-grid" key={input.key}>
          {valueControl}
          <label className="field-label">来源<input aria-label={`${model.id} ${input.label} 来源`} placeholder="待补充来源"
            value={sourceText(object(provenance[input.key]).source)}
            onChange={event => patchModel(patchInputProvenance(model, input.key, { source: event.target.value.trim() === '' ? null : event.target.value }))} /></label>
          <EstimateInput label={`${model.id} ${input.label} 估算状态`} value={object(provenance[input.key]).estimate}
            onChange={estimate => patchModel(patchInputProvenance(model, input.key, { estimate }))} />
        </div>;
      }
      return <details className="form-card" open key={String(model.id)}>
        <summary>{String(model.id)} · {String(model.method)}</summary><div className="form-card-body">
          <div className="form-grid">
            <label className="field-label">模型方法<select aria-label={`${model.id} 模型方法`} value={String(model.method)}
              onChange={event => { const linked = model.linked_weight_item_id;
              const next = newModel(String(model.id), event.target.value, typeof linked === 'string' ? linked : null);
                next.comparison_tolerance = tolerance;
                next.source = model.source ?? null;
                next.estimate = model.estimate ?? null;
                next.input_provenance = provenance;
                patchModel(next); }}>
              {MASS_METHODS.map(entry => <option key={entry.id} value={entry.id}>{entry.label}（{entry.id}）</option>)}
            </select></label>
            <label className="field-label">绑定账本条目<select aria-label={`${model.id} 绑定账本条目`} value={String(model.linked_weight_item_id ?? '')}
              onChange={event => patchModel({ linked_weight_item_id: event.target.value === '' ? null : event.target.value })}>
              <option value="">选择条目</option>
              {stringList(leaf.leaf.weight_item_ids).map(item => <option key={item} value={item}>{item}</option>)}
            </select></label>
            <label className="field-label">模型来源<input aria-label={`${model.id} 模型来源`} value={sourceText(model.source)} placeholder="待补充来源"
              onChange={event => patchModel({ source: event.target.value.trim() === '' ? null : event.target.value })} /></label>
            <EstimateInput label={`${model.id} 模型估算状态`} value={model.estimate} onChange={estimate => patchModel({ estimate })} />
            <label className="field-label">边界说明<input aria-label={`${model.id} 边界说明`} value={typeof model.boundary === 'string' ? model.boundary : ''}
              placeholder="可选：随结果保留的适用边界" onChange={event => patchModel({ boundary: event.target.value.trim() === '' ? undefined : event.target.value })} /></label>
          </div>
          <h4>公式输入</h4>
          {(spec?.fields ?? []).map(field)}
          {/* Count and rounds inputs are declared inputs too, so an estimated
              model needs their own source and estimate flag. */}
          {textInputsFor(String(model.method)).map(input => {
            const entry = object(provenance[input.key]);
            return <div className="form-grid" key={input.key}>
              <label className="field-label">{input.label}
                <input aria-label={`${model.id} ${input.label}`} placeholder="未声明" readOnly={input.key === 'rounds_field'}
                  value={String(inputs[input.key] ?? '')}
                  onChange={event => patchModel(patchTextInput(model, input.key, event.target.value.trim()))} />
              </label>
              <label className="field-label">来源<input aria-label={`${model.id} ${input.label} 来源`} placeholder="待补充来源"
                value={sourceText(entry.source)}
                onChange={event => patchModel(patchInputProvenance(model, input.key, { source: event.target.value.trim() === '' ? null : event.target.value }))} /></label>
              <EstimateInput label={`${model.id} ${input.label} 估算状态`} value={entry.estimate}
                onChange={estimate => patchModel(patchInputProvenance(model, input.key, { estimate }))} />
            </div>;
          })}
          {spec?.counted && <div className="form-grid">
            <label className="field-label">计数方式<select aria-label={`${model.id} 计数方式`}
              value={'count_field' in inputs ? 'field' : 'count_value' in inputs ? 'value' : ''}
              onChange={event => {
                const next = { ...inputs };
                if (event.target.value === 'field') { delete next.count_value; delete next.count_basis; next.count_field = COUNT_FIELDS[0].id; }
                // Unknown stays unknown: a self-declared count starts empty rather
                // than at an invented known zero.
                else { delete next.count_field; next.count_value = null; next.count_basis = ''; }
                patchModel({ inputs: next });
              }}>
              <option value="">未声明</option>
              <option value="field">读取系统装舰数量字段</option>
              <option value="value">本模型自带整数计数与依据</option>
            </select></label>
            {'count_field' in inputs && <label className="field-label">装舰数量字段<select aria-label={`${model.id} 装舰数量字段`} value={String(inputs.count_field ?? '')}
              onChange={event => patchModel({ inputs: { ...inputs, count_field: event.target.value } })}>
              {COUNT_FIELDS.map(field => <option key={field.id} value={field.id}>{field.label}</option>)}
            </select></label>}
            {'count_value' in inputs && <>
              {field({ key: 'count_value', label: '计数 · 件', kind: 'integer' })}
              <label className="field-label">计数依据<input aria-label={`${model.id} 计数依据`} value={sourceText(inputs.count_basis)} placeholder="必填：计数依据"
                onChange={event => patchModel({ inputs: { ...inputs, count_basis: event.target.value } })} /></label>
            </>}
            {spec.ammunition && <p className="form-hint">弹药模型固定读取 {ROUNDS_FIELD} 与本系统声明的装舰数量；这两项未知时模型不可计算。</p>}
          </div>}
          <h4>比较容差</h4>
          <div className="form-grid">
            {/* The relative tolerance is a dimensionless ratio. */}
            <label className="field-label">相对容差<input type="number" step="any" min="0" placeholder="必填" aria-label={`${model.id} 相对容差`} value={number(tolerance.relative) ?? ''}
              onChange={event => patchModel(toleranceValue(model, 'relative', event.target.value))} /></label>
            <QuantityField label="绝对容差" aria-label={`${model.id} 绝对容差`} value={number(tolerance.absolute_t)} dimension="mass" storedUnit="t" kind="nonnegative"
              onChange={value => patchModel(toleranceValue(model, 'absolute_t', value === null ? '' : String(value)))} />
          </div>
          {hints.length > 0 && <p className="form-hint" role="status">{hints.join('；')}。补齐后该模型才能计算并给出可复核的比较结果。</p>}
          <button className="text-button" type="button" onClick={() => patchModels(models.filter((_, i) => i !== index))}>移除模型 {String(model.id)}</button>
        </div></details>;
    })}

    <div className="form-card"><h3>添加质量模型</h3>
      <div className="form-grid">
        <label className="field-label">模型方法<select aria-label="新模型方法" value={method} onChange={event => setMethod(event.target.value)}>
          {MASS_METHODS.map(entry => <option key={entry.id} value={entry.id}>{entry.label}（{entry.id}）</option>)}
        </select></label>
        <label className="field-label">新模型 id<input aria-label="新模型 id" value={newId} onChange={event => setNewId(event.target.value)} /></label>
        <button className="button button--secondary" type="button" onClick={create} disabled={stringList(leaf.leaf.weight_item_ids).length === 0}>添加质量模型</button>
      </div>
      <p className="form-hint">模型只提出质量计算结果用于比较；编辑模型不会静默改写账本质量，也不会自动应用任何提案。</p>
    </div>

    <ResultSection available={!!run}>
      {rows(result.mass_models).length === 0 ? <p className="section-intro">保存并运行后显示账本质量与公式质量的比较。</p> : <>
        <div className="stage-table-scroll"><table className="stage-table"><caption>{leaf.id} · 账本与公式质量比较</caption>
          <thead><tr><th>模型</th><th>公式</th><th>账本质量</th><th>公式质量</th><th>差值</th><th>容差</th><th>性质</th></tr></thead>
          <tbody>{rows(result.mass_models).map((check, index) => <tr key={String(check.id ?? index)}>
            <td>{String(check.id ?? index)}</td>
            <td>{String(check.formula ?? '—')}</td>
            <td>{units.text(check.ledger_mass_t, 'mass')}</td>
            <td>{units.text(check.calculated_mass_t, 'mass')}</td>
            <td>{units.text(check.difference_t, 'mass')}</td>
            <td>{units.text(check.comparison_tolerance_t, 'mass')}</td>
            <td>{check.estimate === true ? '工程估算' : '有据非估算'}{typeof check.source === 'string' ? ` · ${check.source}` : ''}</td>
          </tr>)}</tbody></table></div>
        <p className="form-hint">比较结果只读自运行；差异超出容差时会给出需复核的提案，绝不自动写入 weight_groups。</p>
        <Diagnostics value={result.diagnostics} />
      </>}
    </ResultSection>
  </div>;
}
