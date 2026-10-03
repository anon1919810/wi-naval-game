import { useState } from 'react';

import type { RunView } from '../types';
import { FactField } from './FactField';

// Declared torpedo / mines / depth-charge / miscellaneous-zone inputs and the
// aggregated weapon-page rows. `null` always means "unknown" — it must never be
// coerced to 0 when saved, and unknown aggregates are never recomputed here.

type Raw = Record<string, unknown>;
export type Weapons = Record<string, unknown>;

interface WeaponsRow {
  row: string;
  label?: string;
  group?: string;
  weight_t: number | null;
  mass_status?: string;
  typed?: Record<string, unknown> | null;
  typed_status?: string;
  typed_unknown_fields?: string[];
  item_ids?: string[];
}

interface WeaponsView {
  rows?: WeaponsRow[];
  values?: Record<string, unknown>;
  diagnostics?: Array<{ code?: string; message?: string; [key: string]: unknown }>;
}

const TYPED_SPEC: Record<string, { label: string; kind: 'number' | 'text' }> = {
  tubes: { label: '管数', kind: 'number' },
  carried: { label: '携带数', kind: 'number' },
  sets: { label: '组数', kind: 'number' },
  diameter_mm: { label: '雷径 · mm', kind: 'number' },
  length_m: { label: '雷长 · m', kind: 'number' },
  count: { label: '数量', kind: 'number' },
  reloads: { label: '再装填', kind: 'number' },
  arrangement: { label: '布置', kind: 'text' },
  kind: { label: '类型', kind: 'text' },
  mass_t: { label: '质量 · t', kind: 'number' },
};

function numeric(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

// Most recent run carrying a weapons page_rows view for the selected leaf.
// The aggregate values come from the backend computation — never recomputed here.
function pickWeaponsView(runs: RunView[], leafId: string): WeaponsView | null {
  const key = `weapons.${leafId}`;
  const withData = runs
    .filter(run => {
      const data = run.result?.stages?.systems?.data;
      if (!data || typeof data !== 'object') return false;
      const pageRows = (data as Raw).page_rows;
      if (!pageRows || typeof pageRows !== 'object') return false;
      const view = (pageRows as Raw)[key];
      return !!view && typeof view === 'object';
    })
    .sort((a, b) => String(b.created_at ?? '').localeCompare(String(a.created_at ?? '')));
  if (withData.length === 0) return null;
  const data = withData[0].result!.stages.systems!.data as Raw;
  return ((data.page_rows as Raw)[key] as WeaponsView) ?? null;
}

export function WeaponsEditor({ weapons, runs, onPatchLeaf }: {
  weapons: Weapons;
  runs: RunView[];
  onPatchLeaf: (leafId: string, next: Raw) => void;
}) {
  const torpedo = (weapons.torpedo as Raw | undefined) ?? null;
  const misc = (weapons.misc_weight as Raw | undefined) ?? null;
  const torpedoRows = Array.isArray(torpedo?.page_rows) ? (torpedo!.page_rows as Raw[]) : [];
  const miscRows = Array.isArray(misc?.page_rows) ? (misc!.page_rows as Raw[]) : [];
  const [selected, setSelected] = useState<'torpedo' | 'misc_weight'>(
    torpedo ? 'torpedo' : 'misc_weight');

  function patchRow(leafId: string, rowIndex: number, mutate: (row: Raw) => Raw) {
    const leaf = weapons[leafId] as Raw | undefined;
    if (!leaf) return;
    const rows = Array.isArray(leaf.page_rows) ? (leaf.page_rows as Raw[]).map(r => ({ ...r })) : [];
    if (rowIndex < 0 || rowIndex >= rows.length) return;
    rows[rowIndex] = mutate(rows[rowIndex]);
    onPatchLeaf(leafId, { ...leaf, page_rows: rows });
  }

  function setTyped(leafId: string, rowIndex: number, field: string, raw: string) {
    const spec = TYPED_SPEC[field];
    const isText = spec ? spec.kind === 'text' : true;
    const value = raw.trim() === '' ? null : isText ? raw : Number(raw);
    patchRow(leafId, rowIndex, row => {
      const typed = { ...(row.typed as Raw | null ?? {}) } as Raw;
      typed[field] = value;
      return { ...row, typed };
    });
  }

  function renderTypedInputs(leafId: string, rowIndex: number, row: Raw) {
    const typed = (row.typed as Raw | null) ?? {};
    const fields = Object.keys(TYPED_SPEC).filter(f => f in typed);
    if (fields.length === 0) {
      return <p className="section-intro">该行无可编辑的类型化输入。</p>;
    }
    return <>{fields.map(field => {
      const spec = TYPED_SPEC[field];
      const value = typed[field];
      const display = value === null || value === undefined ? '' : String(value);
      return <label key={field}>{spec.label}
        <input
          type={spec.kind === 'text' ? 'text' : 'number'}
          step={spec.kind === 'text' ? undefined : 'any'}
          aria-label={`${leafId} ${String(row.row)} ${spec.label}`}
          value={display}
          placeholder="未知"
          onChange={e => setTyped(leafId, rowIndex, field, e.target.value)}
        />
      </label>;
    })}</>;
  }

  function renderAggregate(leafId: string, view: WeaponsView | null) {
    if (!view) {
      return <p className="section-intro">
        {leafId === 'misc_weight' ? '杂项分区' : '鱼雷'}：保存并运行后显示聚合值
      </p>;
    }
    const rows = view.rows ?? [];
    return <>
      <div className="metric-grid">
        {rows.map((r, i) => {
          const known = r.mass_status === 'ledger_bound' && r.weight_t !== null;
          return <FactField
            key={String(r.row ?? i)}
            label={typeof r.label === 'string' ? r.label : String(r.row)}
            value={numeric(r.weight_t)}
            unit="t"
            status={known ? 'known' : 'unknown'}
          />;
        })}
      </div>
      {Array.isArray(view.diagnostics) && view.diagnostics.length > 0 && (
        <ul className="diagnostics-list">
          {view.diagnostics.map((d, i) => <li key={i}><code>{d.code ?? '诊断'}</code>{d.message ? `：${d.message}` : ''}</li>)}
        </ul>
      )}
    </>;
  }

  if (!torpedo && !misc) {
    return <div className="deck-empty"><p>项目尚未声明任何武器页分区（systems.weapons 缺少 torpedo 或 misc_weight）。可在“高级：原始契约字段”中粘贴。</p></div>;
  }

  const showTorpedo = selected === 'torpedo' && torpedo;
  const showMisc = selected === 'misc_weight' && misc;
  const torpedoView = pickWeaponsView(runs, 'torpedo');
  const miscView = pickWeaponsView(runs, 'misc_weight');

  return <div className="weapons-editor">
    <div className="deck-group">
      <div className="deck-group-title"><h3>分区</h3>
        <label>选择分区<select aria-label="选择武器分区" value={selected} onChange={e => setSelected(e.target.value as 'torpedo' | 'misc_weight')}>
          {torpedo && <option value="torpedo">鱼雷 / 水雷 / 深弹</option>}
          {misc && <option value="misc_weight">杂项位置分区质量</option>}
        </select></label>
      </div>
    </div>

    {showTorpedo ? (
      <div className="deck-group">
        <div className="deck-group-title"><h3>鱼雷 / 水雷 / 深弹</h3><span>管数 / 携带 / 雷径 / 布置；雷长无来源留空</span></div>
        {torpedoRows.map((row, i) => (
          <div className="deck-row" key={String(row.row ?? i)}>
            <span className="row-label">{typeof row.label === 'string' ? row.label : String(row.row)}</span>
            {renderTypedInputs('torpedo', i, row)}
          </div>
        ))}
      </div>
    ) : showMisc ? (
      <div className="deck-group">
        <div className="deck-group-title"><h3>杂项位置分区质量</h3><span>五个分区；未知保持空缺，绝不按排水量倒填</span></div>
        {miscRows.map((row, i) => (
          <div className="deck-row" key={String(row.row ?? i)}>
            <span className="row-label">{typeof row.label === 'string' ? row.label : String(row.row)}</span>
            {renderTypedInputs('misc_weight', i, row)}
          </div>
        ))}
      </div>
    ) : null}

    <div className="section-heading"><h2>聚合结果</h2><span>取自最近一次运行（不在此处复算）</span></div>
    {showTorpedo && renderAggregate('torpedo', torpedoView)}
    {showMisc && renderAggregate('misc_weight', miscView)}
  </div>;
}
