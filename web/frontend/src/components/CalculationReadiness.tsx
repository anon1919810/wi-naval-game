import { DiagnosticAction, type GuidanceContext } from './DiagnosticAction';
import { resolveDiagnosticLocation, type Diagnostic, type DiagnosticLocation } from './diagnosticGuidance';
import { STAGE_LABELS, STAGE_ORDER, STATUS_LABELS } from './StageStatus';
import type { ProjectDocument, RunView, StageEnvelope } from '../types';

/**
 * What this request is actually ready to compute, said in the reader's terms.
 *
 * The stage names come from the request assembled on screen, so the list is the
 * one that will be submitted. Nothing here judges whether those stages can run:
 * the browser does no physics and certifies nothing. Before a run every stage
 * reads 未评估, because an input nobody has checked is not a passing stage.
 *
 * Once a saved run of this exact project, revision and condition exists, its
 * stages are shown as *that run's reading* — always as the previous check, and
 * never as a statement about the request in front of the reader. Whether the
 * request since moved on is not decided here: this component holds no request
 * fingerprint and compares no request. It says which stages the current request
 * selects, shows the previous run's states under the previous run's identity,
 * and leaves the reader to save and run again when they want a new answer.
 *
 * A finding is resolved against the live draft, so a ledger item that has since
 * been removed is refused here rather than sent to a neighbour that happens to
 * sit at the same index.
 */

/**
 * `unavailable` is not universally a missing input, so the general label is
 * "not computable right now" and the run's own reason stays beside it. A
 * failure, a model limit, a cancellation and a stage that was never requested
 * stay four separate facts.
 */
const READINESS_LABELS: Record<StageEnvelope['status'], string> = { ...STATUS_LABELS, unavailable: '暂不可计算' };

const UNASSESSED = '未评估';

export interface ReadinessFinding { stage: string | null; item: Diagnostic; location: DiagnosticLocation }

const SEVERE = new Set(['error', 'critical', 'severe', 'fatal']);

function blocking(item: Diagnostic): boolean {
  return (item as { blocking?: unknown }).blocking === true;
}

/**
 * Findings that decide something, from every stage and from the run itself, each
 * paired with the location it can honestly reach in the project on screen.
 */
export function readinessFindings(run: RunView | null, live: ProjectDocument | null): ReadinessFinding[] {
  const source = { snapshot: run?.result?.input_snapshot ?? null, live };
  const found: ReadinessFinding[] = [];
  const seen = new Set<string>();
  const push = (stage: string | null, item: Diagnostic) => {
    if (!item || (!SEVERE.has(String(item.severity ?? '')) && !blocking(item))) return;
    const key = JSON.stringify([stage, item.code ?? '', item.path ?? '', item.source_path ?? '', item.message ?? '']);
    if (seen.has(key)) return;
    const location = resolveDiagnosticLocation(item, source);
    if (!location) return;
    seen.add(key);
    found.push({ stage, item, location });
  };
  for (const [name, stage] of Object.entries(run?.result?.stages ?? {})) {
    for (const item of stage.diagnostics ?? []) push(name, item);
  }
  for (const item of run?.result?.diagnostics ?? []) push(item.stage ?? null, item);
  return found;
}

interface Row { name: string; stage: StageEnvelope | null; selected: boolean }

/**
 * The stages this request selects, plus any stage the previous run recorded that
 * the current request does not ask for, in the canonical order.
 */
function readinessRows(requested: readonly string[], run: RunView | null): Row[] {
  const saved = Object.entries(run?.result?.stages ?? {}) as Array<[string, StageEnvelope]>;
  const names = [...new Set([...requested, ...saved.map(([name]) => name)])];
  const rank = (name: string) => { const index = STAGE_ORDER.indexOf(name); return index === -1 ? STAGE_ORDER.length : index; };
  return names
    .sort((left, right) => rank(left) - rank(right))
    .map(name => ({ name, stage: saved.find(([candidate]) => candidate === name)?.[1] ?? null, selected: requested.includes(name) }));
}

export function CalculationReadiness({ stages, previous, live, dirty, revision, conditionId, invalidRequest, onNavigate }: {
  /** The stages the current request selects, base stages plus explicit extras. */
  stages: readonly string[];
  /** The saved run of this project and condition the panel may read as history. */
  previous: RunView | null;
  /** The project on screen; findings are resolved against it. */
  live: ProjectDocument | null;
  dirty: boolean;
  revision: number;
  conditionId: string;
  /** The request builder's own refusal, when the request cannot be submitted. */
  invalidRequest: string;
  onNavigate: (location: DiagnosticLocation) => void;
}) {
  const rows = readinessRows(stages, previous);
  const findings = readinessFindings(previous, live);
  const actionable = findings.filter(finding => finding.location.kind !== 'evidence');
  const guidance: GuidanceContext | null = previous
    ? { projectId: previous.project_id, runId: previous.id, conditionId: previous.condition_id, snapshot: previous.result?.input_snapshot ?? null }
    : null;

  return <section className="chapter-group" aria-label="计算就绪">
    <div className="group-head"><span className="group-index" aria-hidden="true">03</span>
      <h2>计算就绪 · Readiness</h2><span>当前请求的阶段与上一次检查</span></div>
    {invalidRequest
      ? <div className="notice notice--error" role="alert">
        <strong>本次请求无效，不会提交</strong>
        <p>{invalidRequest}</p>
        <p className="group-note">下方列出的是这次请求明确选择的阶段，不代表它可以运行；修正请求后需要重新运行计算。</p>
      </div>
      : <p className="group-note">本次请求选择 {stages.length} 个阶段，针对修订 {revision} · 工况 {conditionId || '尚未选择'}。
        就绪状态只来自已保存的运行结果，浏览器不做任何物理判定，也不替代史实或适航认证。</p>}
    {previous
      ? <p className="readiness-attribution">上一次检查 · 已保存运行 <code>{previous.id}</code> · 修订 {previous.revision} · 工况 {previous.condition_id}</p>
      : <p className="readiness-attribution">尚未评估：保存修订并运行计算后，这里才按阶段给出已保存结果。</p>}
    {previous && <p className="readiness-history">以下是上一次检查的记录，不是本次请求的结论。
        {previous.revision !== revision && `该运行来自修订 ${previous.revision}，而当前已保存修订是 ${revision}：`}
        {dirty ? '草稿有未保存修改：' : ''}需要保存修订并重新运行后，才会有属于当前请求的就绪状态。</p>}
    <ul className="readiness-stages">{rows.map(row => <li key={row.name}>
      <span className={`stage-pill stage-pill--${row.stage ? row.stage.status : 'unassessed'}`}>
        {row.stage ? READINESS_LABELS[row.stage.status] ?? row.stage.status : UNASSESSED}</span>
      <span>{STAGE_LABELS[row.name] ?? row.name}</span>
      <small className="readiness-selection">{row.selected ? '本次请求已选择' : '本次请求未选择'}</small>
      {row.stage?.reason && <small>{row.stage.reason}</small>}
    </li>)}</ul>
    {findings.length > 0 && <>
      <p className="group-note">上一次检查中可直接处理的严重诊断 {findings.length} 条，其中 {actionable.length} 条能定位到当前项目的可编辑输入。</p>
      {actionable.length > 0 && <ul className="readiness-findings">{actionable.map(({ stage, item, location }, index) => <li key={`${item.code ?? ''}-${index}`}>
        <strong>{item.message ?? item.code}</strong>
        {item.code && item.message && <small>{item.code}</small>}
        {item.path && <code>{item.path}</code>}
        {item.source_path && item.source_path !== item.path && <small>来源 {item.source_path}</small>}
        {stage && <small>阶段 {STAGE_LABELS[stage] ?? stage}</small>}
        <DiagnosticAction diagnostic={item} context={guidance} project={live} onNavigate={onNavigate} />
      </li>)}</ul>}
      {findings.length > actionable.length && <p className="group-note">另有 {findings.length - actionable.length} 条严重诊断没有可定位的项目输入，其原始路径与消息保留在报告页。</p>}
    </>}
  </section>;
}
