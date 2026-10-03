import { useState } from 'react';

import type { RunView } from '../types';
import { EstimateInput, IdPicker } from './FactInput';
import { ResultSection } from './FormResults';
import { object, rows, sourceText, stringList, unassignedIds, uniqueId, type Raw } from './formModel';
import {
  declaredMass, declaredRows, MISC_LEAF, rowBoundIds, TYPED_FIELDS,
  templatesFor, TORPEDO_LEAF, typedProblem, typedValue,
  WEAPONS_PAGE_LEAVES, withBoundary, withRows, type WeaponsLeafId,
} from './weaponsModel';

// Declared torpedo / mines / depth-charge / miscellaneous-zone inputs and the
// aggregated weapon-page rows. `null` always means "unknown" — it must never be
// coerced to 0 when saved, and unknown aggregates are never recomputed here.
//
// Ledger mass is read only from the selected loading ledger through the rows'
// `weight_item_ids`. A declared zone mass (`typed.mass_t`) is an informational
// design input shown separately; it is never added into displacement and a row
// without a binding is reported as unknown, not as 0 t.

export type Weapons = Record<string, unknown>;

interface WeaponsView {
  rows?: Array<Record<string, unknown>>;
  values?: Record<string, unknown>;
  weapons?: Record<string, unknown>;
  diagnostics?: Array<{ code?: string; message?: string; [key: string]: unknown }>;
}

function numeric(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

// Most recent run carrying a weapons page_rows view for the selected leaf.
// The aggregate values come from the backend computation — never recomputed here.
function pickWeaponsView(runs: RunView[], leafId: string): WeaponsView | null {
  const key = `weapons.${leafId}`;
  const withData = runs.filter(run => {
    const pageRows = (run.result?.stages?.systems?.data as Raw | undefined)?.page_rows;
    return !!object(pageRows)[key];
  });
  if (withData.length === 0) return null;
  const data = withData[0].result!.stages.systems!.data as Raw;
  return object(object(data.page_rows)[key]) as WeaponsView;
}

const LEAF_TITLES: Record<WeaponsLeafId, string> = { torpedo: '鱼雷 / 水雷 / 深弹', misc_weight: '杂项位置分区质量' };

export function WeaponsEditor({ weapons, runs, ledger, onPatchLeaf }: {
  weapons: Weapons;
  runs: RunView[];
  ledger: Array<{ id: string; label?: string }>;
  onPatchLeaf: (leafId: string, next: Raw) => void;
}) {
  const available = WEAPONS_PAGE_LEAVES.filter(id => weapons[id] && typeof weapons[id] === 'object');
  const [choice, setChoice] = useState<WeaponsLeafId | null>(null);
  const leafId = (choice && available.includes(choice) ? choice : available[0]) ?? TORPEDO_LEAF;
  const leaf = object(weapons[leafId]);
  const declared = declaredRows(leaf);
  const [problems, setProblems] = useState<Record<string, string>>({});
  const bound = rowBoundIds(declared);
  const unassigned = unassignedIds(stringList(leaf.weight_item_ids), bound);
  const leafAbsent = leaf.status === 'absent';
  const view = pickWeaponsView(runs, leafId);
  const run = runs[0] ?? null;

  function emit(next: Raw) { onPatchLeaf(leafId, next); }
  function commitRows(nextRows: Raw[], extra?: string[]) {
    const nextBound = rowBoundIds(nextRows);
    const ids = extra
      ? [...new Set([...nextBound, ...extra])]
      : [...new Set([...nextBound, ...unassignedIds(stringList(leaf.weight_item_ids), nextBound)])];
    emit(withBoundary(withRows(leaf, nextRows), ids));
  }
  function patchRow(index: number, patch: Raw) {
    commitRows(declared.map((row, i) => i === index ? { ...row, ...patch } : row));
  }
  function addRow(templateId: string) {
    const template = templatesFor(leafId).find(item => item.id === templateId) ?? templatesFor(leafId)[0];
    const row: Raw = {
      row: uniqueId(template.id, declared.map(item => item.row)),
      label: template.label,
      weight_item_ids: [],
      typed: { ...template.typed },
      source: null,
      estimate: null,
    };
    commitRows([...declared, row]);
  }
  function removeRow(index: number) {
    commitRows(declared.filter((_, i) => i !== index));
  }
  function setTyped(index: number, field: string, raw: string) {
    const key = `${leafId}/${declared[index]?.row ?? index}/${field}`;
    const problem = typedProblem(field, raw);
    setProblems(previous => {
      const next = { ...previous };
      if (problem) next[key] = problem; else delete next[key];
      return next;
    });
    if (problem) return;
    patchRow(index, { typed: { ...object(declared[index].typed), [field]: typedValue(field, raw) } });
  }
  function createLeaf(id: WeaponsLeafId) {
    setChoice(id);
    setProblems({});
    onPatchLeaf(id, { weight_item_ids: [] });
  }
  function patchLeaf(patch: Raw) { emit({ ...leaf, ...patch }); }

  const templates = templatesFor(leafId);
  const [template, setTemplate] = useState(templates[0].id);

  return <div className="weapons-editor form-stack">
    <div className="form-card"><h3>武器页分区</h3>
      <p>鱼雷与杂项分区是声明输入。质量只取自所选载荷账本；未知保持空缺，不按排水量倒填。</p>
      {available.length === 0 && <p className="form-hint">空白项目尚未声明任何分区。请先建立分区，再逐行声明数量与来源。</p>}
      <div className="form-grid">
        <label className="field-label">当前分区<select aria-label="选择武器分区" value={leafId}
          onChange={e => setChoice(e.target.value as WeaponsLeafId)}>
          {WEAPONS_PAGE_LEAVES.map(id => <option key={id} value={id} disabled={!available.includes(id)}>
            {LEAF_TITLES[id]}{available.includes(id) ? '' : '（未声明）'}</option>)}
        </select></label>
        {!available.includes(TORPEDO_LEAF) && <button className="button button--secondary" type="button"
          onClick={() => createLeaf(TORPEDO_LEAF)}>添加鱼雷分区</button>}
        {!available.includes(MISC_LEAF) && <button className="button button--secondary" type="button"
          onClick={() => createLeaf(MISC_LEAF)}>添加杂项分区</button>}
      </div>
    </div>

    <div className="form-card"><h3>{LEAF_TITLES[leafId]}</h3>
      <p>每行都需要自己的来源；行标识固定，账本绑定决定该行质量是否已知。</p>
      {declared.length === 0 && <p className="form-hint">该分区还没有声明行。鱼雷分区可声明多组鱼雷管、水雷与深弹；杂项分区声明五个位置分区。</p>}
      {declared.map((row, index) => {
        const typed = object(row.typed);
        const fields = Object.keys(typed).filter(field => field in TYPED_FIELDS);
        return <details className="form-card" open key={String(row.row ?? index)}>
          <summary>{String(row.label ?? row.row)}</summary><div className="form-card-body">
            <div className="form-grid">
              {fields.map(field => {
                const spec = TYPED_FIELDS[field];
                const key = `${leafId} ${String(row.row)} ${spec.label}`;
                const value = typed[field];
                const problem = problems[`${leafId}/${String(row.row)}/${field}`];
                return <label className="field-label" key={field}>{spec.label}
                  <input type={spec.kind === 'text' ? 'text' : 'number'} step={spec.kind === 'integer' ? 1 : 'any'}
                    min={spec.kind === 'signed' ? undefined : 0} placeholder="未知" aria-label={key}
                    aria-invalid={Boolean(problem)} value={value == null ? '' : String(value)}
                    onChange={e => setTyped(index, field, e.target.value)} />
                  {problem && <span className="field-error" role="alert">{problem}</span>}</label>;
              })}
              <label className="field-label">行来源<input aria-label={`${leafId} ${String(row.row)} 行来源`}
                value={sourceText(row.source)} placeholder="待补充来源"
                onChange={e => patchRow(index, { source: e.target.value.trim() === '' ? null : e.target.value })} /></label>
              <EstimateInput label={`${leafId} ${String(row.row)} 估算状态`} value={row.estimate}
                onChange={estimate => patchRow(index, { estimate })} />
            </div>
            <IdPicker label={`${leafId} ${String(row.row)} 账本绑定`} selected={row.weight_item_ids} options={ledger}
              onChange={ids => patchRow(index, { weight_item_ids: ids })} />
            <button className="text-button" type="button" onClick={() => removeRow(index)}>移除声明行</button>
          </div></details>;
      })}
      <div className="form-grid">
        <label className="field-label">新增行模板<select aria-label="新增行模板" value={template}
          onChange={e => setTemplate(e.target.value)}>
          {templates.map(item => <option key={item.id} value={item.id}>{item.label}（{item.id}）</option>)}
        </select></label>
        <button className="button button--secondary" type="button" onClick={() => addRow(template)}>添加声明行</button>
      </div>
    </div>

    <div className="form-card"><h3>分区账本绑定</h3>
      <p>分区账本条目 = 各行绑定之和（自动同步）。未分配到行的条目仍计入分区质量，运行时会以 page_rows.item_uncovered 明确报告。</p>
      <IdPicker label="未分配到行的分区账本条目" selected={unassigned} options={ledger}
        onChange={ids => commitRows(declared, ids)} />
      <p className="form-hint">
        {leafAbsent
          ? '该分区已显式声明为不存在（status=absent），不参与系统质量。'
          : bound.length + unassigned.length === 0
            ? '该分区尚未绑定账本条目：运行时会报告 systems.present_without_weight_items。'
            : `分区账本条目 ${bound.length + unassigned.length} 项，其中 ${unassigned.length} 项未分配到行。`}
      </p>
      <label className="field-label">分区状态<select aria-label={`${leafId} 分区状态`} value={leafAbsent ? 'absent' : 'present'}
        onChange={e => {
          const absent = e.target.value === 'absent';
          const next: Raw = { ...leaf, status: absent ? 'absent' : 'present' };
          if (absent) next.reason = typeof leaf.reason === 'string' && leaf.reason ? leaf.reason : '该分区未在本项目声明';
          else delete next.reason;
          emit(next);
        }}>
        <option value="present">存在（present）</option><option value="absent">显式不存在（absent）</option>
      </select></label>
      {leafAbsent && <label className="field-label">不存在原因<input aria-label={`${leafId} 不存在原因`}
        value={sourceText(leaf.reason)} placeholder="必填：分区不存在的依据"
        onChange={e => patchLeaf({ reason: e.target.value.trim() === '' ? null : e.target.value })} /></label>}
    </div>

    <ResultSection available={true}>
      {view
        ? <>
          <div className="metric-grid">
            {(view.rows ?? []).map((row, index) => {
              const name = String(row.label ?? row.row ?? index);
              const mass = numeric(row.weight_t);
              const declaredValue = declaredMass(row);
              return <div key={String(row.row ?? index)} className="metric-grid">
                <ResultFact label={`${name} · 账本质量`} value={mass} unit="t"
                  note={row.mass_status === 'ledger_bound' ? null : '未绑定账本条目'} />
                {declaredValue !== null && <ResultFact label={`${name} · 声明质量`} value={declaredValue} unit="t"
                  note="仅信息，不计入排水量" />}
              </div>;
            })}
          </div>
          <p className="form-hint">账本质量来自所选载荷账本。声明质量是设计输入，仅供参考：不参与排水量计算，也不会自动生成账本条目。</p>
          <Diagnostics value={view.diagnostics} />
        </>
        : <p className="section-intro">{leafId === MISC_LEAF ? '杂项分区：保存并运行后显示聚合值' : '鱼雷：保存并运行后显示聚合值'}</p>}
    </ResultSection>
  </div>;
}

function ResultFact({ label, value, unit, note }: { label: string; value: number | null; unit: string; note: string | null }) {
  return <div className={`fact-field fact-field--${value === null ? 'unknown' : 'known'}`}>
    <span className="fact-label">{label}</span>
    <strong className="fact-value">{value === null ? '未知' : `${value} ${unit}`}</strong>
    <span className="fact-meta">{note ?? '当前工况运行结果'}</span>
  </div>;
}

function Diagnostics({ value }: { value: unknown }) {
  const items = rows(value);
  if (items.length === 0) return null;
  return <ul className="diagnostics-list">
    {items.map((item, index) => <li key={index}><code>{String(item.code ?? '诊断')}</code>{item.message ? `：${String(item.message)}` : ''}</li>)}
  </ul>;
}
