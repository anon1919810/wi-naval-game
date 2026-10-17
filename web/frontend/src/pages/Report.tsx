import { useCopyMessage } from '../i18n/useCopyMessage';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { flushSync } from 'react-dom';

import * as api from '../api';
import { outcome } from '../audio/feedback';
import { DiagnosticAction, type GuidanceContext } from '../components/DiagnosticAction';
import { ReadFailure, ReadPending } from '../components/ReadPending';
import { ReportReadings } from '../components/ReportReadings';
import { requestedStages } from '../components/resultReading';
import { SourceInspector } from '../components/SourceInspector';
import { StageIndex } from '../components/StageIndex';
import { StageStatus, stageLabel, dataLabel } from '../components/StageStatus';
import { compareReports, validReportIdentity } from '../components/reportComparison';
import { UnitProvider, useUnits } from '../components/UnitProvider';
import { useReportPrint } from '../components/useReportPrint';
import { CHOICES, classifyKey, DIMENSION_KEYS, type DisplayPreferences } from '../components/units';
import { useWorkspaceCopy, type WorkspaceKey } from '../i18n/workspace';
import type { AnalysisResult, RunView, StageEnvelope } from '../types';

/** The whole workspace lookup, for the plain functions this page also calls. */
type Copy = (key: WorkspaceKey, params?: any) => string;

const RESULT_KEY: Record<AnalysisResult['status'], WorkspaceKey> = {
  completed: 'report.status.completed', partial: 'report.status.partial', canceled: 'report.status.canceled',
};

type Diagnostic = StageEnvelope['diagnostics'][number];

/** A finding that decides whether a number may be shown at all. */
const SEVERE = new Set(['error', 'critical', 'severe', 'fatal']);

/** How much a finding insists, so a stronger restatement is never folded away. */
const SEVERITY_RANK: Record<string, number> = { info: 0, note: 1, warning: 2, severe: 3, critical: 4, error: 5, fatal: 6 };

function blockingOf(item: Diagnostic): boolean {
  return (item as { blocking?: unknown }).blocking === true;
}

function isSerious(item: Diagnostic): boolean {
  return SEVERE.has(String(item.severity ?? '')) || blockingOf(item);
}

function severityRank(item: Diagnostic): number {
  return SEVERITY_RANK[String(item.severity ?? '').toLowerCase()] ?? 0;
}

/**
 * Evidence on two axes, never as one score: a blocking finding and a fatal
 * finding are different facts, so neither can cancel the other out.
 */
function strongerThan(candidate: Diagnostic, current: Diagnostic): boolean {
  if (blockingOf(candidate) !== blockingOf(current)) return blockingOf(candidate);
  return severityRank(candidate) > severityRank(current);
}

/** True when `child` carries this finding at least as firmly as the root copy. */
function dominated(child: Diagnostic, root: Diagnostic): boolean {
  return severityRank(child) >= severityRank(root) && (blockingOf(child) || !blockingOf(root));
}

/** What a finding says and where it belongs, by name, never by property order. */
function findingKey(item: Diagnostic, stage: string | null): string {
  return [stage ?? '', item.code ?? '', item.message ?? '', item.path ?? '', item.source_path ?? ''].join('|');
}

/**
 * The root findings that add something this report does not already show.
 *
 * A finding is matched by what it says and by the stage it belongs to, so a
 * stage's own copy of the same finding is not repeated above it — including when
 * the stage's copy carries no stage field of its own, and only when that copy is
 * at least as firm. Everything else stays: a root finding about a requested
 * stage that the stage never recorded, a restatement stronger than the stage's,
 * and of repeated root copies of one finding only the firmest is shown.
 */
function rootFindings(result: AnalysisResult, stages: Array<{ name: string; stage: StageEnvelope }>): Diagnostic[] {
  const found = new Map<string, Diagnostic>();
  for (const item of result.diagnostics ?? []) {
    const owner = item.stage ? stages.find(candidate => candidate.name === item.stage) : undefined;
    const children = owner?.stage.diagnostics ?? [];
    const key = findingKey(item, item.stage ?? null);
    if (children.some(child => findingKey(child, item.stage ?? null) === key && dominated(child, item))) continue;
    const current = found.get(key);
    // The same finding twice is one line, and it is the firmest reading of it.
    if (!current || strongerThan(item, current)) found.set(key, item);
  }
  return [...found.values()];
}

/**
 * One finding line: the message reads once, and its evidence stays beside it.
 *
 * The message is the core's own finding text and is shown as saved; only the
 * frames around it — which stage it belongs to and which source path it came
 * from — are this page's own words.
 */
function Finding({ item, fallback, guidance }: { item: Diagnostic; fallback: WorkspaceKey; guidance: GuidanceContext | null }) {
  const w = useWorkspaceCopy();
  const message = item.message ?? item.code ?? w(fallback);
  // A code is evidence too, so it is kept rather than dropped whenever a message
  // happens to exist. Identical text is printed once, not twice.
  const code = item.code && item.code !== item.message ? item.code : null;
  return <p><strong>{message}</strong>
    {code && <code className="report-diagnostic-code">{code}</code>}
    {item.stage && <span className="report-diagnostic-stage">{w('report.diagnostics.stage', { name: stageLabel(w, item.stage) })}</span>}
    {item.path && <code>{item.path}</code>}
    {item.source_path && item.source_path !== item.path && <small>{w('report.diagnostics.source', { path: item.source_path })}</small>}
    <DiagnosticAction diagnostic={item} context={guidance} project={guidance?.snapshot ?? null} />
  </p>;
}

function triState(w: Copy, value: boolean | null | undefined): string {
  return value === true ? w('report.tri.yes') : value === false ? w('report.tri.no') : w('report.tri.unknown');
}

export function Report({ result, runId, revision, compareResult, compareError, run, compareRun, onBack }: {
  result: AnalysisResult; runId?: string; revision?: number; compareResult?: AnalysisResult;
  compareError?: string; run?: RunView; compareRun?: RunView; onBack?: () => void;
}) {
  // A report is immutable: this local choice only re-wraps the page content in a
  // display provider. It never edits the stored snapshot, fingerprint or export.
  const [override, setOverride] = useState<Partial<DisplayPreferences>>({});
  return <UnitProvider preferences={{ ...(result.input_snapshot?.display_preferences as object ?? {}), ...override }}>
    <ReportBody result={result} runId={runId} revision={revision} compareResult={compareResult}
      compareError={compareError} run={run} compareRun={compareRun} onBack={onBack} override={override} onOverrideChange={setOverride} />
  </UnitProvider>;
}

function ReportBody({ result, runId, revision, compareResult, compareError, run, compareRun, onBack, override, onOverrideChange }: {
  result: AnalysisResult; runId?: string; revision?: number; compareResult?: AnalysisResult; compareError?: string;
  run?: RunView; compareRun?: RunView;
  onBack?: () => void; override: Partial<DisplayPreferences>; onOverrideChange: (next: Partial<DisplayPreferences>) => void;
}) {
  const units = useUnits();
  const w = useWorkspaceCopy();
  const host = useRef<HTMLDivElement>(null);
  // The provenance appendix is mounted when the reader opens it, or here for a
  // print. Once mounted it stays: it is read from one saved result, and the
  // disclosure it sits in returns to the state the reader left it in.
  const [auditMounted, setAuditMounted] = useState(false);
  const mountAudit = useCallback(() => setAuditMounted(true), []);
  useReportPrint(host, { mount: () => flushSync(() => setAuditMounted(true)) });
  const stages = useMemo(() => requestedStages(result), [result]);
  // The comparison is derived on every render and writes nothing back: both
  // snapshots, their fingerprints and the exports stay exactly as saved.
  const comparison = compareResult ? compareReports({ result, revision, run }, { result: compareResult, run: compareRun }, w) : null;
  const snapshot = result.input_snapshot;
  const shipName = snapshot?.name || result.project_id;
  const condition = snapshot?.loading_conditions?.find(item => item.id === result.condition_id);
  const savedRevision = revision ?? snapshot?.revision;
  // Root diagnostics only. A stage's own findings are already shown inside that
  // stage, so repeating them here would double both the count and the reading.
  const root = rootFindings(result, stages);
  const rootSevere = root.filter(isSerious);
  const rootOrdinary = root.filter(item => !isSerious(item));
  // A diagnostic only becomes a link where this page can name the project it
  // belongs to and the run that produced it. A standalone preview has neither,
  // and renders every finding exactly as it always has.
  const guidance: GuidanceContext | null = runId && result.project_id
    ? { projectId: result.project_id, runId, conditionId: result.condition_id, snapshot }
    : null;

  return <div className="report-page page-pad" ref={host}>
    <div className="report-actions no-print">
      {onBack && <button className="text-button" data-audio="manual" onClick={onBack}>{w('report.back')}</button>}
      <div className="report-action-group">
        {runId && <><a className="button button--secondary" href={api.exportUrl(runId, 'json')} download={`plimsoll-${runId}.json`}>{w('report.exportJson')}</a><a className="button button--secondary" href={api.exportUrl(runId, 'csv')} download={`plimsoll-${runId}.csv`}>{w('report.exportCsv')}</a></>}
        <button className="button button--secondary" onClick={() => window.print()}>{w('report.print')}</button>
      </div>
    </div>

    <header className="report-cover report-identity">
      <span className="section-kicker">REPORT / {runId ? w('report.kickerRun', { id: runId.slice(0, 8).toUpperCase() }) : w('report.kickerPreview')}</span>
      <h1>{shipName}</h1>
      <p>{w('report.condition', { label: condition?.label || result.condition_id })}
        {condition?.label && condition.label !== result.condition_id ? ` · ${result.condition_id}` : ''}
        {savedRevision ? ` · ${w('report.revision', { revision: savedRevision })}` : ''} · {runId ? w('report.runLabel', { id: runId }) : w('report.previewLabel')}</p>
      <div className="report-status-row">
        <span className={`stage-pill stage-pill--${result.status}`}>{w(RESULT_KEY[result.status])}</span>
        <span>{w('report.stagesRequested', { count: stages.length })}</span>
        <span>{w('report.fact', { label: w('report.complete.label') })}{result.validity.complete ? w('report.complete.all') : w('report.complete.some')}</span>
        <span>{w('report.fact', { label: w('report.converged') })}{triState(w, result.validity.converged)}</span>
        <span>{w('report.fact', { label: w('report.applicable') })}{triState(w, result.validity.model_applicable)}</span>
        <span>{w('report.fact', { label: w('report.historical') })}{triState(w, result.validity.historical_validated)}</span>
      </div>
      <p className="report-caveat">{w('report.caveat')}</p>
      {/* Reading order for a report nobody has read before: status, then
          diagnostics, then the identity the numbers belong to, then the values.
          Screen-only, so it never joins the printed record. */}
      <details className="first-use no-print">
        <summary>{w('report.firstUse.summary')}</summary>
        <ol className="first-use-steps">
          <li><strong>{w('report.firstUse.1.title')}</strong>{w('report.firstUse.1.text')}</li>
          <li><strong>{w('report.firstUse.2.title')}</strong>{w('report.firstUse.2.text')}</li>
          <li><strong>{w('report.firstUse.3.title')}</strong>{w('report.firstUse.3.text')}</li>
          <li><strong>{w('report.firstUse.4.title')}</strong>{w('report.firstUse.4.text')}</li>
          <li><strong>{w('report.firstUse.5.title')}</strong>{w('report.firstUse.5.text')}</li>
        </ol>
      </details>
      <ReportUnitControls override={override} onChange={onOverrideChange} />
    </header>

    <ReportReadings result={result} />

    {(rootSevere.length > 0 || rootOrdinary.length > 0) && <section className="report-root-diagnostics" aria-label={w('report.diagnostics.label')}>
      {rootSevere.length > 0 && <div className="stage-diagnostics-open" role="alert">
        <strong>{w('report.diagnostics.severe', { count: rootSevere.length })}</strong>
        {rootSevere.map((item, index) => <Finding key={`${item.code ?? ''}-${index}`} item={item} fallback="report.diagnostics.severeFallback" guidance={guidance} />)}
      </div>}
      {rootOrdinary.length > 0 && <details className="report-root-diagnostics-fold"><summary>{w('report.diagnostics.ordinary', { count: rootOrdinary.length })}</summary>
        {rootOrdinary.map((item, index) => <Finding key={`${item.code ?? ''}-${index}`} item={item} fallback="report.diagnostics.fallback" guidance={guidance} />)}
      </details>}
    </section>}

    <div className="report-columns">
      {/* Locating only: the stages below stay one continuous body. */}
      <StageIndex page="reports" runId={runId} stages={stages} />
      <main className="report-main">
        <section className="report-section">
          <div className="section-heading"><h2>{w('report.section.title')}</h2><span>{w('report.section.count', { count: stages.length })}</span></div>
          <p className="report-intro">{w('report.section.intro')}</p>
          <div className="report-stage-list">{stages.map(({ name, stage }) =>
            <StageStatus key={name} name={name} stage={stage} guidance={guidance} />)}</div>
          {stages.length === 0 && <p>{w('report.section.empty')}</p>}
        </section>

        {(comparison || compareError) && <section className="report-section comparison-section">
          <div className="section-heading"><h2>{w('report.compare.title')}</h2><span>{w('report.compare.note')}</span></div>
          {compareError
            ? <div className="notice notice--error" role="alert">{compareError}</div>
            : comparison && <>
              <div className="comparison-meta">
                <div><strong>{w('report.compare.current')}</strong><span>{w('workbench.save.revision', { revision: comparison.current.revision ?? w('units.unknown') })}</span>{comparison.current.runId && <span>{w('overview.result.run',{id:comparison.current.runId})}</span>}<span>{w('report.compare.condition', { id: comparison.current.condition })}</span><span>{w('report.compare.units', { value: JSON.stringify(result.units) })}</span><span>{w('report.compare.method', { value: JSON.stringify(result.method_versions) })}</span><code>{comparison.current.fingerprint}</code></div>
                <div><strong>{w('report.compare.other')}</strong>{comparison.comparison.runId && <span>{w('overview.result.run',{id:comparison.comparison.runId})}</span>}<span>{w('workbench.save.revision', { revision: comparison.comparison.revision ?? w('units.unknown') })}</span><span>{w('report.compare.condition', { id: comparison.comparison.condition })}</span><span>{w('report.compare.units', { value: JSON.stringify(compareResult!.units) })}</span><span>{w('report.compare.method', { value: JSON.stringify(compareResult!.method_versions) })}</span><code>{comparison.comparison.fingerprint}</code></div>
              </div>
              {/* A refusal that does not say what differs leaves the reader hunting
                  for it, so every fact that breaks the shared basis is named. */}
              {comparison.inputChanges.length > 0 && <ul className="comparison-changes">{comparison.inputChanges.map(change => <li key={change}>{change}</li>)}</ul>}
              {comparison.warnings.map(warning => <p className="comparison-warning" key={warning}>{warning}</p>)}
              {comparison.compatible && comparison.groups.length > 0 && <table className="comparison-table" tabIndex={0} aria-label={w('report.compare.title')}>
                <thead><tr><th>{w('report.compare.metric')}</th><th>{w('report.compare.currentCol')}</th><th>{w('report.compare.otherCol')}</th><th title={w('report.compare.diffOrder')}>{w('report.compare.diffCol')}</th></tr></thead>
                <tbody>{comparison.groups.flatMap(group => group.cells.map(cell => <tr key={cell.path}>
                  <th>{group.label} / {dataLabel(w, cell.key)}{cell.point === undefined ? '' : ` · ${cell.point}${group.stage === 'gz' ? '°' : ' kn'}`}</th>
                  {/* A cell with no number says why: unknown, not run, or a quantity
                      whose unit this interface cannot resolve. Nothing is coerced. */}
                  <td>{cell.current === null ? w(`report.compare.state.${cell.state}` as WorkspaceKey) : compareCell(units, cell, cell.current)}</td>
                  <td>{cell.comparison === null ? w(`report.compare.state.${cell.state}` as WorkspaceKey) : compareCell(units, cell, cell.comparison)}</td>
                  <td>{cell.delta === null ? w(cell.state === 'known' ? 'report.compare.noDelta' : `report.compare.state.${cell.state}` as WorkspaceKey) : compareCell(units, cell, cell.delta)}</td>
                </tr>))}</tbody></table>}
            </>}
        </section>}

        <SourceInspector result={result} deferred={auditMounted} onOpen={mountAudit} />
        <footer className="report-footer">{w('report.footer')}</footer>
      </main>
    </div>
  </div>;
}

// Both sides and the difference use the row's own key: an area stays an area, a
// volume stays a volume, and a stored kilogram mass is not read as tonnes.
function compareCell(units: ReturnType<typeof useUnits>, row: { key: string; dimension?: import('../components/units').Dimension; storedUnit?: string; canonicalUnit?: string }, value: number): string {
  return row.dimension ? units.text(value, row.dimension, row.storedUnit) : `${value}${row.canonicalUnit ? ` ${row.canonicalUnit}` : ''}`;
}

// Report-local display controls. They change only what this page prints: the
// stored snapshot, its fingerprints and the exports stay exactly as saved.
function ReportUnitControls({ override, onChange }: {
  override: Partial<DisplayPreferences>; onChange: (next: Partial<DisplayPreferences>) => void;
}) {
  const units = useUnits();
  const w = useWorkspaceCopy();
  return <div className="report-units no-print">
    <span className="section-kicker">{w('report.units.kicker')}</span>
    {DIMENSION_KEYS.map(key => <label className="field-label" key={key}>
      {{ length: w('report.units.length'), mass: w('report.units.mass'), power: w('report.units.power'), speed: w('report.units.speed'), angle: w('report.units.angle') }[key]}
      <select aria-label={w('report.units.select', { dimension: w(`report.units.${key}` as WorkspaceKey) })} value={String(override[key] ?? units.prefs[key])}
        onChange={event => {
          const value = event.target.value as DisplayPreferences[typeof key];
          const next: Record<string, string> = { ...override };
          if (value === units.prefs[key]) delete next[key]; else next[key] = value;
          onChange(next as Partial<DisplayPreferences>);
        }}>
        {CHOICES[key].map(choice => <option key={choice.value} value={choice.value}>{choice.label}</option>)}
      </select>
    </label>)}
    <small>{w('report.units.note')}</small>
  </div>;
}

export function ReportPage({ runId, onBack }: { runId: string; onBack: () => void }) {
  const w = useWorkspaceCopy();
  const [run, setRun] = useState<RunView | null>(null);
  const [history, setHistory] = useState<RunView[]>([]);
  const [compareId, setCompareId] = useState('');
  const [compareRun, setCompareRun] = useState<RunView | undefined>();
  const compareResult = compareRun?.result ?? undefined;
  const [historyError, setHistoryError] = useCopyMessage();
  const [compareError, setCompareError] = useCopyMessage();
  const [compareBusy, setCompareBusy] = useState(false);
  const [error, setError] = useCopyMessage();
  const [attempt, setAttempt] = useState(0);
  // Late answers are rejected by ticket: a comparison that arrives after the
  // reader changed or cleared the selection is not the one they asked for.
  const comparison = useRef(0);
  const loading = useRef(0);

  useEffect(() => {
    let active = true;
    const ticket = ++loading.current;
    comparison.current += 1;
    // A different run starts from nothing: its own result, its own history and
    // its own comparison, with no error or unit choice carried over.
    setRun(null);
    setHistory([]); setHistoryError('');
    setCompareId('');
    setCompareRun(undefined);
    setCompareError('');
    setCompareBusy(false);
    setError('');
    api.getRun(runId).then(current => {
      if (!active || loading.current !== ticket) return;
      if (current.id !== runId || (current.result && !validReportIdentity({result:current.result,run:current}))) { setError(copy=>copy('report.compare.identityMismatch')); return; }
      setRun(current);
      void api.listRuns(current.project_id).then(items => {
        if (!active || loading.current !== ticket) return;
        setHistory(items.filter(item => item.id !== runId && (item.status === 'completed' || item.status === 'partial')));
      }).catch(cause => { if (active && loading.current === ticket) setHistoryError(w => cause instanceof Error ? cause.message : w('report.compare.historyFailed')); });
    }).catch(cause => { if (active && loading.current === ticket) setError(w => cause instanceof Error ? cause.message : w('report.readFailedGeneric')); });
    return () => { active = false; loading.current += 1; comparison.current += 1; };
  }, [runId, attempt]);

  async function selectComparison(id: string) {
    const ticket = ++comparison.current;
    setCompareId(id);
    setCompareRun(undefined);
    setCompareError('');
    if (!id) { setCompareBusy(false); return; }
    setCompareBusy(true);
    try {
      const other = await api.getRun(id);
      if (comparison.current !== ticket) return;
      if (other.id !== id || other.project_id !== run?.project_id) { setCompareError(w => w('report.compare.identityMismatch')); return; }
      if (!other.result) { setCompareError(w => w('report.compare.noResult')); outcome('hold'); return; }
      setCompareRun(other);
    } catch (cause) {
      if (comparison.current !== ticket) return;
      outcome('hold');
      setCompareError(w => cause instanceof Error ? cause.message : w('report.compare.unreadable'));
    } finally {
      if (comparison.current === ticket) setCompareBusy(false);
    }
  }

  if (error) return <div className="page-pad">
    <ReadFailure title={w('report.readFailed', { id: runId })} detail={error} retryLabel={w('report.readFailedRetry')}
      onRetry={() => { setError(''); setAttempt(current => current + 1); }} onBack={onBack} backLabel={w('report.back')} /></div>;
  if (!run) return <div className="page-pad"><ReadPending scope="report" object={w('report.pending.object')} /></div>;
  if (!run.result) return <div className="page-pad"><h1>{w('report.empty.title')}</h1><p>{w('report.empty.body', { status: run.status })}</p><button className="text-button" data-audio="manual" onClick={onBack}>{w('report.back')}</button></div>;
  // A stored report is immutable: display units come from its own input snapshot.
  const preferences = run.result.input_snapshot?.display_preferences;
  return <>
    {historyError && <div className="notice notice--error" role="alert">{w('report.compare.historyFailed')} {historyError}<button className="text-button" onClick={() => { setHistoryError(''); setAttempt(value => value + 1); }}>{w('workbench.read.refresh')}</button></div>}
    <div className="report-compare-control no-print">
      <label htmlFor="compare-run">{w('report.compare.control')}</label>
      <select id="compare-run" value={compareId} onChange={event => { void selectComparison(event.target.value); }}>
        <option value="">{w('report.compare.noneSelected')}</option>
        {history.map(item => <option key={item.id} value={item.id}>{w('report.compare.revisionOption', { revision: item.revision, condition: item.condition_id, id: item.id.slice(0, 8) })}</option>)}
      </select>
      {compareBusy && <small className="report-compare-busy">{w('report.compare.busy')}</small>}
    </div>
    <UnitProvider preferences={preferences}>
      {/* The page's own unit choice belongs to one saved result. Keying by its
          identity resets it for a different run, even when the next run loads so
          quickly that nothing ever unmounts. */}
      <Report key={`${runId}:${run.result.request_fingerprint}`} result={run.result} revision={run.revision} runId={runId}
        compareResult={compareResult} compareError={compareError} run={run} compareRun={compareRun} onBack={onBack} />
    </UnitProvider></>;
}
