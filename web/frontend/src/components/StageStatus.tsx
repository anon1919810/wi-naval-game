import { useState } from 'react';
import type { StageEnvelope, StageStatus as StageStatusCode } from '../types';
import { DiagnosticAction, type GuidanceContext } from './DiagnosticAction';
import { FloodingResults } from './FloodingResults';
import { StabilityPlot } from './StabilityPlot';
import { useUnits } from './UnitProvider';
import { classifyKey, type Dimension, type QuantityKey } from './units';

export const STAGE_LABELS: Record<string, string> = {
  loading: '载荷与重心', systems: '系统与分项', l0: '设计基线', geometry: '型线几何',
  equilibrium: '浮态平衡', hydrostatics: '静水力', gz: '稳性曲线', deck: '甲板与干舷',
  hydrostatic_curve: '静水力曲线', bonjean: '邦戎曲线', resistance: '阻力与功率',
  propulsion: '动力装置', endurance: '续航', historical: '历史参照', flooding: '破损进水',
};

export const STAGE_ORDER = [
  'loading', 'systems', 'l0', 'geometry', 'equilibrium', 'hydrostatics', 'gz', 'deck',
  'hydrostatic_curve', 'bonjean', 'resistance', 'propulsion', 'endurance', 'historical', 'flooding',
];

export const STATUS_LABELS: Record<StageStatusCode, string> = {
  completed: '计算完成', not_requested: '未请求', unavailable: '暂不可计算', failed: '计算失败',
  canceled: '已取消', model_limit: '模型越界',
};

const DATA_LABELS: Record<string, string> = {
  total_mass_t: '总质量', known_mass_t: '已知质量', linked_total_mass_t: '绑定质量',
  lcg_m: '纵向重心', tcg_m: '横向重心', kg_m: '垂向重心', gm_m: '初稳性高',
  kb_m: '浮心高度', km_m: '横稳心高度', draught_m: '吃水', displacement_t: '排水量',
  heel_deg: '横倾角', trim_deg: '纵倾角', minimum_clearance_m: '最小净空',
  awp_m2: '水线面积', roll_period_s: '横摇周期',
  // The waterline and GM are the saved balance readings, in their own names.
  waterline_above_keel_m: '龙骨基准水线高度', waterline_d_m: '水线高度', gm_t_m: '初稳性高 GM',
  // Declared powers belong to the machinery declaration, not to the resistance
  // work point shown on the report's first screen.
  power_design_kw: '设计轴功率（设计声明）', power_trial_kw: '试航轴功率（试航声明）',
  power_design_shp: '设计轴功率（设计声明）', power_trial_shp: '试航轴功率（试航声明）',
};

// A severe diagnostic is a finding, not a footnote: it is shown in place. A
// warning that blocks the stage counts as severe even though its severity says
// "warning", because it decides whether the number may be shown at all.
const SEVERE = new Set(['error', 'critical', 'severe', 'fatal']);

function isBlocking(item: StageEnvelope['diagnostics'][number]): boolean {
  return (item as { blocking?: unknown }).blocking === true;
}

// Units are only inferred from reliable, unambiguous key names: a force in kN,
// a time in s, a density in kg/m³ and every other canonical-only quantity keeps
// its stored label and value instead of borrowing a convertible suffix.
function inferredUnit(key: string): { label: string; dimension?: Dimension; storedUnit?: string } | null {
  const kind: QuantityKey | null = classifyKey(key);
  if (kind) return { label: '', dimension: kind.dimension, storedUnit: kind.storedUnit };
  if (key === 'power_design_shp' || key === 'power_trial_shp') return { label: 'shp' };
  // Densities, viscosities and rates keep their canonical compound unit.
  if (key === 'rho_t_m3') return { label: 't/m³' };
  if (key.endsWith('_kg_m3')) return { label: 'kg/m³' };
  if (key.endsWith('_t_m3')) return { label: 't/m³' };
  if (key.endsWith('_m2_s')) return { label: 'm²/s' };
  if (key.endsWith('_t_per_day')) return { label: 't/day' };
  if (key.endsWith('_m3_s') || key.endsWith('_m3_per_s')) return { label: 'm³/s' };
  if (key.endsWith('_kg')) return { label: 'kg' };
  if (key.endsWith('_kn')) return { label: 'kN' };
  if (key.endsWith('_s')) return { label: 's' };
  if (key.startsWith('pct_')) return { label: '%' };
  if (key.endsWith('_nm')) return { label: 'nmi' };
  if (key.endsWith('_pa')) return { label: 'Pa' };
  return null;
}

function display(value: unknown): string {
  if (value === null || value === undefined) return '未知';
  if (typeof value === 'number') {
    if (value !== 0 && Math.abs(value) < 0.0000005) return '≈0';
    return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 6 }).format(Object.is(value, -0) ? 0 : value);
  }
  if (typeof value === 'boolean') return value ? '是' : '否';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

interface Datum { key: string; value: unknown; unit?: string; dimension?: Dimension; storedUnit?: string; source?: string; estimate?: boolean }

function datumFor(key: string, value: unknown): Datum {
  const unit = inferredUnit(key);
  return { key, value, unit: unit?.dimension ? undefined : unit?.label, dimension: unit?.dimension, storedUnit: unit?.storedUnit };
}

function extract(data: Record<string, unknown> | null): Datum[] {
  if (!data) return [];
  const found: Datum[] = [];
  for (const [key, value] of Object.entries(data)) {
    if (key === 'diagnostics' || key === 'assumptions' || key === 'method_version') continue;
    if (typeof value === 'number' || value === null) {
      found.push(datumFor(key, value));
    } else if (value && typeof value === 'object' && !Array.isArray(value)) {
      const row = value as Record<string, unknown>;
      if ('value' in row && (typeof row.value === 'number' || row.value === null)) {
        const declared = typeof row.unit === 'string' ? { label: row.unit } : inferredUnit(key);
        found.push({ key, value: row.value, unit: declared?.dimension ? undefined : declared?.label,
          dimension: declared?.dimension, storedUnit: declared?.storedUnit,
          source: typeof row.source === 'string' ? row.source : undefined, estimate: row.estimate === true });
      } else if (key === 'values') {
        for (const [subkey, subvalue] of Object.entries(row)) {
          if (typeof subvalue === 'number' || subvalue === null) found.push(datumFor(subkey, subvalue));
          if (found.length >= 8) break;
        }
      }
    }
    if (found.length >= 8) break;
  }
  return found;
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

// A table cell that follows the reader's units when the key is a reliable
// quantity name, and keeps the canonical unit otherwise (for example kN).
function tableValue(units: ReturnType<typeof useUnits>, key: string, value: unknown, canonicalUnit?: string): string {
  if (value === null || value === undefined) return '未知';
  const kind = classifyKey(key);
  if (kind) return units.keyed(key, value);
  return `${display(value)}${canonicalUnit ? ` ${canonicalUnit}` : ''}`;
}

function ResistanceTables({ data }: { data: Record<string, unknown> }) {
  const units = useUnits();
  const rows = Array.isArray(data.rows) ? data.rows.map(record) : [];
  const powerRows = Array.isArray(data.power_rows) ? data.power_rows.map(record) : [];
  const validity = record(data.validity);
  const scenario = record(data.scenario);
  if (rows.length === 0 && powerRows.length === 0) return null;
  const powerUnit = units.unit('power');
  return <div className="resistance-results">
    <p className="result-context">方法 {display(data.method)} · {data.estimate === true ? '工程估算' : '来源见输入'}
      {validity.model_applicable === false && ' · 不在经验适用范围，仅供方法试算'}
      {data.primary_result === false && ' · 非主结果'}</p>
    {typeof scenario.source === 'string' && <p className="result-source">来源：{scenario.source}</p>}
    {rows.length > 0 && <div className="stage-table-scroll"><table className="stage-table"><caption>速度与阻力</caption><thead><tr><th>速度</th><th>总阻力</th><th>有效功率</th><th>解释</th></tr></thead><tbody>{rows.map((row, index) => <tr key={`${row.speed_kn ?? 'unknown'}-${index}`}>
      <td>{tableValue(units, 'speed_kn', row.speed_kn)}</td><td>{tableValue(units, 'total_resistance_kn', row.total_resistance_kn, 'kN')}</td>
      <td>{tableValue(units, 'effective_power_kw', row.effective_power_kw)}</td>
      <td>{row.complete === false ? '未完整求得' : row.model_applicable === false ? '不在经验适用范围' : row.primary_result === false ? '非主结果' : '计算值'}{row.estimate === true && ' · 工程估算'}</td>
    </tr>)}</tbody></table></div>}
    {powerRows.length > 0 && <div className="stage-table-scroll"><table className="stage-table"><caption>轴功率与推进系数</caption><thead><tr><th>速度</th><th>QPC</th><th>轴功率</th><th>解释</th></tr></thead><tbody>{powerRows.map((row, index) => {
      const qpc = record(row.qpc);
      return <tr key={`${row.speed_kn ?? 'unknown'}-${index}`}>
        <td>{tableValue(units, 'speed_kn', row.speed_kn)}</td><td>{tableValue(units, 'qpc', qpc.value)}{typeof qpc.source === 'string' && <small>{qpc.source}</small>}</td>
        {/* One shaft-power column in the reader's unit; the stored kW and shp
            values are the same quantity and must not be shown side by side. */}
        <td>{tableValue(units, 'shaft_power_kw', row.shaft_power_kw)}<small>{powerUnit}</small></td>
        <td>{row.complete === false ? '未完整求得' : row.primary_result === false ? '非主结果' : '计算值'}{row.estimate === true && ' · 工程估算'}</td>
      </tr>;
    })}</tbody></table></div>}
  </div>;
}

/**
 * One finding line. The message reads once and every piece of evidence the saved
 * result attached to it stays on the line: the code, the path, the source path
 * and, when the page knows which project and run it is showing, a way to follow
 * the path into that project. The action is additive — it never replaces or
 * summarises the finding, and it is absent when the path leads nowhere
 * editable, so a fabricated link can never appear.
 */
function DiagnosticLine({ item, guidance, repeat }: {
  item: StageEnvelope['diagnostics'][number]; guidance: GuidanceContext | null; repeat?: boolean;
}) {
  return <p className={repeat ? 'stage-diagnostics-repeat' : undefined}>
    <strong>{repeat ? `${item.code ?? '诊断'} · 与上面的阶段原因相同` : (item.message ?? item.code)}</strong>
    {!repeat && item.code && item.message && <small>{item.code}</small>}
    {item.path && <code>{item.path}</code>}
    {item.source_path && item.source_path !== item.path && <small>来源 {item.source_path}</small>}
    <DiagnosticAction diagnostic={item} context={guidance} project={guidance?.snapshot ?? null} />
  </p>;
}

export function StageStatus({ name, stage, guidance }: {
  name: string; stage: StageEnvelope; guidance?: GuidanceContext | null;
}) {
  const [rawOpen, setRawOpen] = useState(false);
  const units = useUnits();
  // Only a requested stage that actually finished may show plain numbers. A
  // blocked or unrequested envelope may still hold partial values, and those
  // are not results: they stay reachable in the raw data, never in the reading
  // area.
  const delivered = stage.requested === true && stage.status === 'completed';
  const values = delivered ? extract(stage.data) : [];
  const diagnostics = stage.diagnostics ?? [];
  const serious = (item: StageEnvelope['diagnostics'][number]) => SEVERE.has(String(item.severity ?? '')) || isBlocking(item);
  const severe = diagnostics.filter(serious);
  // A diagnostic that repeats the stage reason is the reason, not a second
  // finding. Its message is not printed twice, but its code, path and source
  // path stay in the list, so no evidence is lost before it can be printed.
  const repeats = diagnostics.filter(item => !serious(item) && item.message === stage.reason);
  const ordinary = diagnostics.filter(item => !serious(item) && item.message !== stage.reason);
  const detailCount = ordinary.length + repeats.length;
  const reasonAlreadyVisible = severe.some(item => item.message === stage.reason);
  return <article id={`stage-${name}`} className={`stage-card stage-card--${stage.status}`}>
    <div className="stage-card-header"><div><span className="section-kicker">{name.toUpperCase()}</span><h3 tabIndex={-1}>{STAGE_LABELS[name] ?? name}</h3></div><span className={`stage-pill stage-pill--${stage.status}`}>{STATUS_LABELS[stage.status] ?? stage.status}</span></div>
    {stage.reason && stage.status !== 'not_requested' && !reasonAlreadyVisible && <p className="stage-reason">{stage.reason}</p>}
    {stage.status === 'not_requested' && <p className="stage-reason">这次请求没有运行该阶段。</p>}
    {severe.length > 0 && <div className="stage-diagnostics-open" role="alert">
      <strong>严重诊断 · {severe.length} 条</strong>
      {severe.map((item, index) => <DiagnosticLine key={`${item.code ?? ''}-${index}`} item={item} guidance={guidance ?? null} />)}
    </div>}
    {values.length > 0 && <div className="stage-values">{values.map(item => {
      const shown = item.dimension ? units.text(item.value, item.dimension, item.storedUnit) : display(item.value);
      return <div className="stage-value" key={item.key}><span title={item.key}>{DATA_LABELS[item.key] ?? item.key}</span>
        <strong>{shown}{!item.dimension && item.value !== null && item.unit ? ` ${item.unit}` : ''}</strong>
        {item.source && <small>{item.source}</small>}{item.estimate && <em>工程估算</em>}</div>;
    })}</div>}
    {name === 'resistance' && stage.requested && stage.data && (delivered || stage.status === 'model_limit') && <>
      {stage.status === 'model_limit' && <p className="stage-reason">以下为模型越界试算，不作为有效工作点。</p>}
      <ResistanceTables data={stage.data} />
    </>}
    {/* The GZ curve belongs to its own stage, and only a finished one carries a
        curve worth drawing. */}
    {name === 'gz' && delivered && <StabilityPlot stage={stage} />}
    {name === 'flooding' && stage.requested && stage.data && typeof record(stage.data).status === 'string' && <FloodingResults data={record(stage.data)} />}
    {detailCount > 0 && <details className="stage-diagnostics"><summary>诊断与缺项 · {detailCount} 条</summary><div>{ordinary.map((item, index) => <DiagnosticLine key={`${item.code ?? ''}-${index}`} item={item} guidance={guidance ?? null} />)}</div>
      {repeats.map((item, index) => <DiagnosticLine key={`repeat-${item.code ?? ''}-${index}`} item={item} guidance={guidance ?? null} repeat />)}</details>}
    {Object.keys(stage.method_versions).length > 0 && <p className="stage-method">方法版本 · {Object.entries(stage.method_versions).map(([key, value]) => `${key}: ${display(value)}`).join(' / ')}</p>}
    {stage.assumptions.length > 0 && <details className="stage-assumptions"><summary>假设与适用性</summary><pre>{JSON.stringify(stage.assumptions, null, 2)}</pre></details>}
    {/* The raw payload stays reachable on screen and stays off paper: a saved
        stage can carry megabytes of iteration and geometry arrays. */}
    {stage.data && <details className="stage-assumptions stage-raw-data no-print" onToggle={event => setRawOpen(event.currentTarget.open)}><summary>完整阶段数据与来源</summary>{rawOpen && <pre>{JSON.stringify(stage.data, null, 2)}</pre>}</details>}
  </article>;
}
