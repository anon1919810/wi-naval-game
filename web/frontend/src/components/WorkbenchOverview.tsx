import { FactField } from './FactField';
import { declaredSource } from './InputTrace';
import { number, object, type Raw } from './formModel';
import { STAGE_LABELS, STAGE_ORDER, STATUS_LABELS } from './StageStatus';
import { StatusBadge } from './StatusBadge';
import type { Dimension } from './units';
import type { ProjectDocument, RunView, StageEnvelope } from '../types';

/**
 * The project readout. It separates three different things that used to share
 * one panel: values the reader typed (Input), the condition and revision the
 * draft is saved against, and the result of a saved run that still matches this
 * project, revision and condition (Result).
 *
 * No number here is computed in the browser: every reading is read from the
 * immutable `result` payload of the identity-guarded run, and a field that the
 * saved stage did not produce stays unknown with its reason.
 */

export interface OverviewReading {
  key: string;
  label: string;
  value: number | null;
  dimension?: Dimension;
  storedUnit?: string;
  state: 'known' | 'unknown' | 'unavailable';
  /** Why the number is missing, or which stage produced it. */
  note: string;
}

// Canonical saved keys only; nothing is derived from the inputs here.
const RESULT_FIELDS: Array<{ key: string; stage: string; label: string; dimension: Dimension; storedUnit: string; paths: string[] }> = [
  { key: 'loading.total_mass_t', stage: 'loading', label: '所选工况总质量', dimension: 'mass', storedUnit: 't', paths: ['values.total_mass_t'] },
  { key: 'equilibrium.waterline_above_keel_m', stage: 'equilibrium', label: '龙骨基准水线高度', dimension: 'length', storedUnit: 'm', paths: ['waterline_above_keel_m'] },
  { key: 'equilibrium.heel_deg', stage: 'equilibrium', label: '横倾角', dimension: 'angle', storedUnit: 'deg', paths: ['heel_deg', 'values.heel_deg'] },
  { key: 'hydrostatics.gm_t_m', stage: 'hydrostatics', label: '初稳性高 GM', dimension: 'length', storedUnit: 'm', paths: ['values.gm_t_m'] },
];

function readPath(data: Raw, path: string): unknown {
  return path.split('.').reduce<unknown>((node, key) => {
    if (!node || typeof node !== 'object' || Array.isArray(node)) return undefined;
    return (node as Raw)[key];
  }, data);
}

function stageOf(run: RunView | null, name: string): StageEnvelope | null {
  const stage = run?.result?.stages?.[name];
  return stage && typeof stage === 'object' ? stage : null;
}

// A stage that did not run, could not run or ran outside its method boundary is
// reported as such. It is never replaced by zero and never by an input value.
function stageReason(stage: StageEnvelope | null): string {
  if (!stage) return '该运行没有保存此阶段';
  if (!stage.requested && stage.status === 'not_requested') return '本次请求未运行该阶段';
  if (stage.status === 'unavailable') return stage.reason ? `资料不足：${stage.reason}` : '资料不足';
  if (stage.status === 'model_limit') return stage.reason ? `模型越界：${stage.reason}` : '模型越界';
  if (stage.status === 'failed') return stage.reason ? `计算失败：${stage.reason}` : '计算失败';
  if (stage.status === 'canceled') return '该阶段已取消';
  return '';
}

export function overviewReadings(run: RunView | null): OverviewReading[] {
  return RESULT_FIELDS.map(field => {
    const stage = stageOf(run, field.stage);
    const blocked = stageReason(stage);
    const stageName = STAGE_LABELS[field.stage] ?? field.stage;
    // A stage that could not deliver a number never shows one, whatever partial
    // data the envelope happens to carry: unknown, zero and unavailable differ.
    if (blocked) {
      return { key: field.key, label: field.label, value: null, dimension: field.dimension,
        storedUnit: field.storedUnit, state: 'unavailable', note: `${blocked} · 阶段 ${stageName}` };
    }
    let value: number | null = null;
    for (const path of field.paths) {
      const found = readPath(object(stage?.data), path);
      if (typeof found === 'number' && Number.isFinite(found)) { value = found; break; }
    }
    if (value === null) {
      return { key: field.key, label: field.label, value: null, dimension: field.dimension, storedUnit: field.storedUnit,
        state: 'unknown', note: `该运行未给出 ${field.key.split('.').pop()}（阶段 ${stageName}）` };
    }
    return { key: field.key, label: field.label, value, dimension: field.dimension, storedUnit: field.storedUnit,
      state: 'known', note: `已保存运行 · 阶段 ${stageName}` };
  });
}

/** Requested stages of the current run, in the canonical stage order. */
export function overviewStages(run: RunView | null): Array<{ name: string; status: StageEnvelope['status']; reason: string | null }> {
  const stages = run?.result?.stages ?? {};
  return Object.entries(stages).filter(([, stage]) => stage.requested || stage.status !== 'not_requested')
    .sort(([a], [b]) => STAGE_ORDER.indexOf(a) - STAGE_ORDER.indexOf(b))
    .map(([name, stage]) => ({ name, status: stage.status, reason: stage.reason ?? null }));
}

const SEVERE = new Set(['error', 'critical', 'severe', 'fatal']);

// Severe diagnostics stay visible: an interaction may never fold an error away.
export function severeDiagnostics(run: RunView | null): Array<{ stage: string | null; message: string }> {
  const found: Array<{ stage: string | null; message: string }> = [];
  const seen = new Set<string>();
  const append = (item: StageEnvelope['diagnostics'][number], fallback: string | null) => {
    if (!SEVERE.has(String(item?.severity ?? ''))) return;
    const stage = item.stage ?? fallback;
    const message = String(item.message ?? item.code ?? '严重诊断');
    const key = JSON.stringify([stage, item.code, item.source_path ?? item.path, message]);
    if (seen.has(key)) return;
    seen.add(key);
    found.push({ stage, message });
  };
  for (const [name, stage] of Object.entries(run?.result?.stages ?? {})) {
    for (const item of stage.diagnostics ?? []) {
      append(item, name);
    }
  }
  for (const item of run?.result?.diagnostics ?? []) append(item, null);
  return found;
}

export function WorkbenchOverview({ draft, revision, conditionId, runs, current, dirty, onChapter, onRun }: {
  draft: ProjectDocument; revision: number; conditionId: string; runs: RunView[]; current: RunView | null;
  dirty: boolean; onChapter: (chapter: 'hull') => void; onRun: (runId: string) => void;
}) {
  const hull = object(draft.hull);
  const condition = draft.loading_conditions.find(item => item.id === conditionId) ?? null;
  const ledgerCount = draft.weight_groups.reduce((sum, group) => sum + (Array.isArray(group.items) ? group.items.length : 0), 0);
  const readings = overviewReadings(current);
  const stages = overviewStages(current);
  const severe = severeDiagnostics(current);
  // Nothing here may claim a result identity the guard did not confirm.
  const absentReason = dirty
    ? '草稿有未保存修改：旧运行不是当前结果'
    : !conditionId ? '尚未选择工况'
      : `该修订与工况尚无已保存结果${runs.length ? '（下方运行记录仍可查看）' : ''}`;

  return <div className="overview-page">
    <section className="chapter-group">
      <div className="group-head"><span className="group-index" aria-hidden="true">01</span>
        <h2>输入 · Input</h2><span>草稿读数，未保存的修改也算</span></div>
      <div className="metric-grid">
        <FactField label="船长" value={number(hull.loa_m ?? hull.length_m)} dimension="length"
          status={number(hull.loa_m ?? hull.length_m) === null ? 'unknown' : 'known'} source={declaredSource(object(hull.sources).loa_m) ?? '未声明来源'} />
        <FactField label="型宽" value={number(hull.beam_m)} dimension="length"
          status={number(hull.beam_m) === null ? 'unknown' : 'known'} source={declaredSource(object(hull.sources).beam_m) ?? '未声明来源'} />
        <FactField label="设计吃水" value={number(hull.draught_normal_m ?? hull.draft_m)} dimension="length"
          status={number(hull.draught_normal_m ?? hull.draft_m) === null ? 'unknown' : 'known'} source={declaredSource(object(hull.sources).draught_normal_m) ?? '未声明来源'} />
        <FactField label="重量条目" value={ledgerCount} unit="项" status="known" source="当前输入账本" />
      </div>
      <p className="group-note">这些是输入，不是结果。留空表示未知，不会补零，也不参与结果身份判断。</p>
    </section>

    <section className="chapter-group">
      <div className="group-head"><span className="group-index" aria-hidden="true">02</span>
        <h2>当前工况与修订</h2><span>结果身份的唯一依据</span></div>
      <dl className="overview-identity">
        <div><dt>当前工况</dt><dd>{condition ? (condition.label || condition.id) : '尚未选择工况'}</dd></div>
        <div><dt>工况 id</dt><dd><code>{conditionId || '—'}</code></dd></div>
        <div><dt>已保存修订</dt><dd>修订 {revision}</dd></div>
        <div><dt>草稿状态</dt><dd>{dirty ? '未保存修改' : '与已保存修订一致'}</dd></div>
      </dl>
    </section>

    <section className="chapter-group">
      <div className="group-head"><span className="group-index" aria-hidden="true">03</span>
        <h2>当前结果 · Result</h2><span>只取匹配本项目、修订与工况的已保存运行</span></div>
      {current
        ? <>
          <div className="result-identity">
            <strong><StatusBadge status={current.status} /></strong>
            <span>运行 {current.id}</span>
            <span>修订 {current.revision}</span>
            <span>工况 {current.condition_id}</span>
            <span>请求指纹 <code>{current.request_fingerprint}</code></span>
            <span>完成 {current.finished_at ? new Date(current.finished_at).toLocaleString('zh-CN') : '未记录'}</span>
          </div>
          <div className="metric-grid">{readings.map(reading =>
            <FactField key={reading.key} label={reading.label} value={reading.value}
              dimension={reading.dimension} storedUnit={reading.storedUnit}
              status={reading.state} source={reading.note} />)}</div>
          {stages.length > 0 && <ul className="stage-status-list">{stages.map(stage =>
            <li key={stage.name}><span className={`stage-pill stage-pill--${stage.status}`}>{STATUS_LABELS[stage.status] ?? stage.status}</span>
              <span>{STAGE_LABELS[stage.name] ?? stage.name}</span>
              {stage.reason && <small>{stage.reason}</small>}</li>)}</ul>}
          {severe.length > 0 && <div className="stage-diagnostics-open" role="alert">
            <strong>严重诊断 · {severe.length} 条</strong>
            {severe.map((item, index) => <p key={index}>{item.stage ? `${STAGE_LABELS[item.stage] ?? item.stage}：` : '整体：'}{item.message}</p>)}
          </div>}
          <p className="group-note">计算完成只表示模型执行情况，不代表安全、适航或史实验证。</p>
        </>
        : <div className="result-absent">
          <p>尚无当前结果</p>
          <p className="group-note">{absentReason}</p>
        </div>}
    </section>

    <section className="chapter-group">
      <div className="group-head"><span className="group-index" aria-hidden="true">04</span>
        <h2>运行记录</h2><span>历史可查，身份必须明确</span></div>
      {runs.length === 0
        ? <p className="group-note">还没有任何运行记录。保存输入后即可运行计算。</p>
        : <div className="run-history">{runs.slice(0, 6).map(item => <button key={item.id} onClick={() => onRun(item.id)}>
          <span><span>修订 {item.revision}</span><span>工况 {item.condition_id}</span></span>
          <strong><StatusBadge status={item.status} /></strong>
          <small>{new Date(item.created_at).toLocaleString('zh-CN')}</small>
          <span aria-hidden="true">↗</span>
        </button>)}</div>}
      {current && <p className="group-note">上方“当前结果”只对应运行 {current.id}；其余记录保留其各自的修订与工况身份。</p>}
      <button className="text-button" onClick={() => onChapter('hull')}>编辑船型数据 ↗</button>
    </section>
  </div>;
}
