import type { StageEnvelope, StageStatus as StageStatusCode } from '../types';

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
  completed: '计算完成', not_requested: '未请求', unavailable: '资料不足', failed: '计算失败',
  canceled: '已取消', model_limit: '模型越界',
};

const DATA_LABELS: Record<string, string> = {
  total_mass_t: '总质量', known_mass_t: '已知质量', linked_total_mass_t: '绑定质量',
  lcg_m: '纵向重心', tcg_m: '横向重心', kg_m: '垂向重心', gm_m: '初稳性高',
  kb_m: '浮心高度', km_m: '横稳心高度', draught_m: '吃水', displacement_t: '排水量',
  heel_deg: '横倾角', trim_deg: '纵倾角', minimum_clearance_m: '最小净空',
  awp_m2: '水线面积', roll_period_s: '横摇周期',
};

function inferredUnit(key: string): string | undefined {
  if (key === 'rho_t_m3') return 't/m³';
  if (key.startsWith('pct_')) return '%';
  if (key.endsWith('_kn')) return 'kn';
  if (key.endsWith('_nm')) return 'nmi';
  if (key.endsWith('_kw')) return 'kW';
  if (key.endsWith('_m4')) return 'm⁴';
  if (key.endsWith('_m')) return 'm';
  if (key.endsWith('_t')) return 't';
  if (key.endsWith('_deg')) return '°';
  if (key.endsWith('_m2')) return 'm²';
  if (key.endsWith('_m3')) return 'm³';
  if (key.endsWith('_s')) return 's';
  return undefined;
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

interface Datum { key: string; value: unknown; unit?: string; source?: string; estimate?: boolean }

function extract(data: Record<string, unknown> | null): Datum[] {
  if (!data) return [];
  const found: Datum[] = [];
  for (const [key, value] of Object.entries(data)) {
    if (key === 'diagnostics' || key === 'assumptions' || key === 'method_version') continue;
    if (typeof value === 'number' || value === null) {
      found.push({ key, value, unit: inferredUnit(key) });
    } else if (value && typeof value === 'object' && !Array.isArray(value)) {
      const row = value as Record<string, unknown>;
      if ('value' in row && (typeof row.value === 'number' || row.value === null)) {
        found.push({ key, value: row.value, unit: typeof row.unit === 'string' ? row.unit : inferredUnit(key),
          source: typeof row.source === 'string' ? row.source : undefined, estimate: row.estimate === true });
      } else if (key === 'values') {
        for (const [subkey, subvalue] of Object.entries(row)) {
          if (typeof subvalue === 'number' || subvalue === null) found.push({ key: subkey, value: subvalue, unit: inferredUnit(subkey) });
          if (found.length >= 8) break;
        }
      }
    }
    if (found.length >= 8) break;
  }
  return found;
}

export function StageStatus({ name, stage }: { name: string; stage: StageEnvelope }) {
  const values = extract(stage.data);
  return <article className={`stage-card stage-card--${stage.status}`}>
    <div className="stage-card-header"><div><span className="section-kicker">{name.toUpperCase()}</span><h3>{STAGE_LABELS[name] ?? name}</h3></div><span className={`stage-pill stage-pill--${stage.status}`}>{STATUS_LABELS[stage.status] ?? stage.status}</span></div>
    {stage.reason && stage.status !== 'not_requested' && <p className="stage-reason">{stage.reason}</p>}
    {stage.status === 'not_requested' && <p className="stage-reason">这次请求没有运行该阶段。</p>}
    {values.length > 0 && <div className="stage-values">{values.map(item => <div className="stage-value" key={item.key}><span title={item.key}>{DATA_LABELS[item.key] ?? item.key}</span><strong>{display(item.value)}{item.value !== null && item.unit ? ` ${item.unit}` : ''}</strong>{item.source && <small>{item.source}</small>}{item.estimate && <em>工程估算</em>}</div>)}</div>}
    {stage.diagnostics.length > 0 && <details className="stage-diagnostics"><summary>诊断与缺项 · {stage.diagnostics.length} 条</summary><div>{stage.diagnostics.map((item, index) => <p key={`${item.code ?? ''}-${index}`}><strong>{item.message === stage.reason ? item.code ?? '诊断' : item.message ?? item.code}</strong>{item.path && <code>{item.path}</code>}{item.source_path && item.source_path !== item.path && <small>来源 {item.source_path}</small>}</p>)}</div></details>}
    {Object.keys(stage.method_versions).length > 0 && <p className="stage-method">方法版本 · {Object.entries(stage.method_versions).map(([key, value]) => `${key}: ${display(value)}`).join(' / ')}</p>}
    {stage.assumptions.length > 0 && <details className="stage-assumptions"><summary>假设与适用性</summary><pre>{JSON.stringify(stage.assumptions, null, 2)}</pre></details>}
  </article>;
}
