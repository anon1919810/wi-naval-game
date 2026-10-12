import { DiagnosticAction, type GuidanceContext } from './DiagnosticAction';
import { resolveDiagnosticLocation, type Copy, type Diagnostic, type DiagnosticLocation } from './diagnosticGuidance';
import { stageLabel, STAGE_ORDER } from './StageStatus';
import { useWorkspaceCopy, type WorkspaceKey } from '../i18n/workspace';
import type { ProjectDocument, RunView, StageEnvelope } from '../types';

/**
 * What this request is actually ready to compute, said in the reader's terms.
 *
 * The stage names come from the request assembled on screen, so the list is the
 * one that will be submitted. Nothing here judges whether those stages can run:
 * the browser does no physics and certifies nothing. Before a run every stage
 * reads "not assessed", because an input nobody has checked is not a passing
 * stage.
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
const READINESS_LABEL: Record<StageEnvelope['status'], WorkspaceKey> = {
  completed: 'status.completed', not_requested: 'status.not_requested', unavailable: 'status.unavailable',
  failed: 'status.failed', canceled: 'status.canceled', model_limit: 'status.model_limit',
};

export interface ReadinessFinding { stage: string | null; item: Diagnostic; location: DiagnosticLocation }

const SEVERE = new Set(['error', 'critical', 'severe', 'fatal']);

function blocking(item: Diagnostic): boolean {
  return (item as { blocking?: unknown }).blocking === true;
}

/**
 * Findings that decide something, from every stage and from the run itself, each
 * paired with the location it can honestly reach in the project on screen.
 */
export function readinessFindings(run: RunView | null, live: ProjectDocument | null, w: Copy): ReadinessFinding[] {
  const source = { snapshot: run?.result?.input_snapshot ?? null, live };
  const found: ReadinessFinding[] = [];
  const seen = new Set<string>();
  const push = (stage: string | null, item: Diagnostic) => {
    if (!item || (!SEVERE.has(String(item.severity ?? '')) && !blocking(item))) return;
    const key = JSON.stringify([stage, item.code ?? '', item.path ?? '', item.source_path ?? '', item.message ?? '']);
    if (seen.has(key)) return;
    const location = resolveDiagnosticLocation(item, source, w);
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

export function CalculationReadiness({ stages, previous, live, dirty, revision, conditionId, invalidRequest, previousState = 'ready', onNavigate }: {
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
  previousState?: 'loading' | 'ready' | 'failed';
  onNavigate: (location: DiagnosticLocation) => void;
}) {
  const w = useWorkspaceCopy();
  const rows = readinessRows(stages, previous);
  const findings = readinessFindings(previous, live, w);
  const actionable = findings.filter(finding => finding.location.kind !== 'evidence');
  const guidance: GuidanceContext | null = previous
    ? { projectId: previous.project_id, runId: previous.id, conditionId: previous.condition_id, snapshot: previous.result?.input_snapshot ?? null }
    : null;

  return <section className="chapter-group" aria-label={w('readiness.label')}>
    <div className="group-head"><span className="group-index" aria-hidden="true">03</span>
      <h2>{w('readiness.title')}</h2><span>{w('readiness.note')}</span></div>
    {invalidRequest
      ? <div className="notice notice--error" role="alert">
        <strong>{w('readiness.invalid.title')}</strong>
        <p>{invalidRequest}</p>
        <p className="group-note">{w('readiness.invalid.note')}</p>
      </div>
      : <p className="group-note">{w('readiness.summary', {
        count: stages.length, revision,
        condition: conditionId || w('readiness.summaryNoCondition'),
      })}</p>}
    {previous
      ? <p className="readiness-attribution">{w('readiness.previous', { id: previous.id, revision: previous.revision, condition: previous.condition_id })}</p>
      : <p className="readiness-attribution">{w(previousState === 'loading' ? 'workbench.read.resultLoading' : previousState === 'failed' ? 'workbench.read.previousFailed' : 'readiness.unassessed')}</p>}
    {previous && <p className="readiness-history">{w('readiness.history')}
        {previous.revision !== revision && w('readiness.historyRevision', { source: previous.revision, current: revision })}
        {dirty ? w('readiness.historyDirty') : ''}{w('readiness.historyAdvice')}</p>}
    <ul className="readiness-stages">{rows.map(row => <li key={row.name}>
      <span className={`stage-pill stage-pill--${row.stage ? row.stage.status : 'unassessed'}`}>
        {row.stage ? w(READINESS_LABEL[row.stage.status]) : w('readiness.unassessedShort')}</span>
      <span>{stageLabel(w, row.name)}</span>
      <small className="readiness-selection">{row.selected ? w('readiness.selected') : w('readiness.notSelected')}</small>
      {/* The stage's own reason is the core's saved text and stays verbatim. */}
      {row.stage?.reason && <small>{row.stage.reason}</small>}
    </li>)}</ul>
    {findings.length > 0 && <>
      <p className="group-note">{w('readiness.findings', { total: findings.length, actionable: actionable.length })}</p>
      {actionable.length > 0 && <ul className="readiness-findings">{actionable.map(({ stage, item, location }, index) => <li key={`${item.code ?? ''}-${index}`}>
        {/* The diagnostic's own message and code are the core's text and are
            shown exactly as saved; the sentence around them is this panel's. */}
        <strong>{item.message ?? item.code}</strong>
        {item.code && item.message && <small>{item.code}</small>}
        {item.path && <code>{item.path}</code>}
        {item.source_path && item.source_path !== item.path && <small>{w('stage.diagnostics.source', { path: item.source_path })}</small>}
        {stage && <small>{w('reading.stageContext', { name: stageLabel(w, stage) })}</small>}
        <DiagnosticAction diagnostic={item} context={guidance} project={live} onNavigate={onNavigate} />
      </li>)}</ul>}
      {findings.length > actionable.length && <p className="group-note">{w('readiness.findingsRemainder', { count: findings.length - actionable.length })}</p>}
    </>}
  </section>;
}