import { FactField } from './FactField';
import { CalculationReadiness } from './CalculationReadiness';
import { declaredSource } from './InputTrace';
import { number, object, type Raw } from './formModel';
import type { DiagnosticLocation } from './diagnosticGuidance';
import { stageLabel, STAGE_ORDER } from './StageStatus';
import { StatusBadge } from './StatusBadge';
import { useWorkspaceCopy, type WorkspaceKey } from '../i18n/workspace';
import { useLanguage, type SiteLanguage } from '../portfolio/LanguageProvider';
import { workspaceCopy } from '../i18n/workspace';
import { useDateText, useMomentText } from '../i18n/format';
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
const RESULT_FIELDS: Array<{ key: string; stage: string; label: WorkspaceKey; dimension: Dimension; storedUnit: string; paths: string[] }> = [
  { key: 'loading.total_mass_t', stage: 'loading', label: 'overview.reading.mass', dimension: 'mass', storedUnit: 't', paths: ['values.total_mass_t'] },
  { key: 'equilibrium.waterline_above_keel_m', stage: 'equilibrium', label: 'overview.reading.waterline', dimension: 'length', storedUnit: 'm', paths: ['waterline_above_keel_m'] },
  { key: 'equilibrium.heel_deg', stage: 'equilibrium', label: 'overview.reading.heel', dimension: 'angle', storedUnit: 'deg', paths: ['heel_deg', 'values.heel_deg'] },
  { key: 'hydrostatics.gm_t_m', stage: 'hydrostatics', label: 'overview.reading.gm', dimension: 'length', storedUnit: 'm', paths: ['values.gm_t_m'] },
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
// The stage's own reason text is the core's and stays verbatim inside the frame.
function stageReason(language: SiteLanguage, stage: StageEnvelope | null): string {
  const say = (key: WorkspaceKey, params?: Record<string, string>) => workspaceCopy(language, key, params);
  if (!stage) return say('stage.reason.missing');
  if (!stage.requested && stage.status === 'not_requested') return say('stage.reason.notRequested');
  if (stage.status === 'unavailable') return stage.reason ? say('stage.reason.unavailable', { reason: stage.reason }) : say('stage.reason.unavailableBare');
  if (stage.status === 'model_limit') return stage.reason ? say('stage.reason.modelLimit', { reason: stage.reason }) : say('stage.reason.modelLimitBare');
  if (stage.status === 'failed') return stage.reason ? say('stage.reason.failed', { reason: stage.reason }) : say('stage.reason.failedBare');
  if (stage.status === 'canceled') return say('stage.reason.canceled');
  return '';
}

export function overviewReadings(run: RunView | null, language: SiteLanguage): OverviewReading[] {
  const say = (key: WorkspaceKey, params?: Record<string, string>) => workspaceCopy(language, key, params);
  return RESULT_FIELDS.map(field => {
    const stage = stageOf(run, field.stage);
    const blocked = stageReason(language, stage);
    const stageName = say(`stage.${field.stage}` as WorkspaceKey);
    // A stage that could not deliver a number never shows one, whatever partial
    // data the envelope happens to carry: unknown, zero and unavailable differ.
    if (blocked) {
      return { key: field.key, label: say(field.label), value: null, dimension: field.dimension,
        storedUnit: field.storedUnit, state: 'unavailable', note: say('overview.reading.blocked', { reason: blocked, stage: stageName }) };
    }
    let value: number | null = null;
    for (const path of field.paths) {
      const found = readPath(object(stage?.data), path);
      if (typeof found === 'number' && Number.isFinite(found)) { value = found; break; }
    }
    if (value === null) {
      return { key: field.key, label: say(field.label), value: null, dimension: field.dimension, storedUnit: field.storedUnit,
        state: 'unknown', note: say('overview.reading.unknown', { field: field.key.split('.').pop() ?? '', stage: stageName }) };
    }
    return { key: field.key, label: say(field.label), value, dimension: field.dimension, storedUnit: field.storedUnit,
      state: 'known', note: say('overview.reading.known', { stage: stageName }) };
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
export function severeDiagnostics(language: SiteLanguage, run: RunView | null): Array<{ stage: string | null; message: string }> {
  const fallback = workspaceCopy(language, 'overview.reading.fallbackSevere');
  const found: Array<{ stage: string | null; message: string }> = [];
  const seen = new Set<string>();
  const append = (item: StageEnvelope['diagnostics'][number], fallbackStage: string | null) => {
    if (!SEVERE.has(String(item?.severity ?? ''))) return;
    const stage = item.stage ?? fallbackStage;
    // The message is the core's own finding text and is shown as saved.
    const message = String(item.message ?? item.code ?? fallback);
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

export function WorkbenchOverview({ draft, revision, conditionId, runs, current, previous, requestStages, requestError, dirty, historyState = 'ready', resultState = 'ready', previousState = 'ready', onRefreshRuns, onChapter, onRun, onNavigate }: {
  draft: ProjectDocument; revision: number; conditionId: string; runs: RunView[]; current: RunView | null;
  /** The owned previous check of this condition, kept across a save. */
  previous: RunView | null;
  /** The stages the request assembled on screen selects, base stages plus extras. */
  requestStages: string[];
  /** The request builder's own refusal, when the request cannot be submitted. */
  requestError: string;
  historyState?: 'loading' | 'ready' | 'failed';
  resultState?: 'loading' | 'ready' | 'failed';
  previousState?: 'loading' | 'ready' | 'failed';
  onRefreshRuns?: () => void;
  dirty: boolean; onChapter: (chapter: 'hull') => void; onRun: (runId: string) => void;
  onNavigate: (location: DiagnosticLocation) => void;
}) {
  const w = useWorkspaceCopy();
  const { language } = useLanguage();
  const moment = useMomentText();
  const date = useDateText();
  const hull = object(draft.hull);
  const condition = draft.loading_conditions.find(item => item.id === conditionId) ?? null;
  const ledgerCount = draft.weight_groups.reduce((sum, group) => sum + (Array.isArray(group.items) ? group.items.length : 0), 0);
  const readings = overviewReadings(current, language);
  const stages = overviewStages(current);
  const severe = severeDiagnostics(language, current);
  // Nothing here may claim a result identity the guard did not confirm.
  const absentReason = dirty
    ? w('overview.result.absentDirty')
    : !conditionId ? w('overview.result.absentNoCondition')
      : w('overview.result.absentNone') + (runs.length ? w('overview.result.absentHistory') : '');

  return <div className="overview-page">
    {/* First calculation, as a short disclosure above the groups. It states the
        order the page is already laid out in and points at the existing report
        link; it changes no control, no request and no guard. */}
    <details className="first-use">
      <summary>{w('overview.firstUse.summary')}</summary>
      <ol className="first-use-steps">
        <li><strong>{w('overview.firstUse.1.title')}</strong>{w('overview.firstUse.1.text')}</li>
        <li><strong>{w('overview.firstUse.2.title')}</strong>{w('overview.firstUse.2.text')}</li>
        <li><strong>{w('overview.firstUse.3.title')}</strong>{w('overview.firstUse.3.text')}</li>
        <li><strong>{w('overview.firstUse.4.title')}</strong>{w('overview.firstUse.4.text')}</li>
      </ol>
    </details>
    <section className="chapter-group">
      <div className="group-head"><span className="group-index" aria-hidden="true">01</span>
        <h2>{w('overview.input.title')}</h2><span>{w('overview.input.note')}</span></div>
      <div className="metric-grid">
        <FactField label={w('field.loa_m')} value={number(hull.loa_m ?? hull.length_m)} dimension="length"
          status={number(hull.loa_m ?? hull.length_m) === null ? 'unknown' : 'known'} source={declaredSource(object(hull.sources).loa_m) ?? w('overview.input.sourceUndeclared')} />
        <FactField label={w('field.beam_m')} value={number(hull.beam_m)} dimension="length"
          status={number(hull.beam_m) === null ? 'unknown' : 'known'} source={declaredSource(object(hull.sources).beam_m) ?? w('overview.input.sourceUndeclared')} />
        <FactField label={w('field.draught_normal_m')} value={number(hull.draught_normal_m ?? hull.draft_m)} dimension="length"
          status={number(hull.draught_normal_m ?? hull.draft_m) === null ? 'unknown' : 'known'} source={declaredSource(object(hull.sources).draught_normal_m) ?? w('overview.input.sourceUndeclared')} />
        <FactField label={w('overview.input.label.items')} value={ledgerCount} unit={w('overview.input.items')} status="known" source={w('overview.input.itemsSource')} />
      </div>
      <p className="group-note">{w('overview.input.note2')}</p>
    </section>

    <section className="chapter-group">
      <div className="group-head"><span className="group-index" aria-hidden="true">02</span>
        <h2>{w('overview.identity.title')}</h2><span>{w('overview.identity.note')}</span></div>
      <dl className="overview-identity">
        <div><dt>{w('overview.identity.condition')}</dt><dd>{condition ? (condition.label || condition.id) : w('overview.identity.none')}</dd></div>
        <div><dt>{w('overview.identity.conditionId')}</dt><dd><code>{conditionId || '—'}</code></dd></div>
        <div><dt>{w('overview.identity.revision')}</dt><dd>{w('workbench.save.revision', { revision })}</dd></div>
        <div><dt>{w('overview.identity.draft')}</dt><dd>{dirty ? w('overview.identity.draftDirty') : w('overview.identity.draftClean')}</dd></div>
      </dl>
    </section>

    <CalculationReadiness stages={requestStages} previous={previous} live={draft} dirty={dirty}
      revision={revision} conditionId={conditionId} invalidRequest={requestError} previousState={previousState} onNavigate={onNavigate} />

    <section className="chapter-group">
      <div className="group-head"><span className="group-index" aria-hidden="true">04</span>
        <h2>{w('overview.result.title')}</h2><span>{w('overview.result.note')}</span></div>
      {current
        ? <>
          <div className="result-identity">
            <strong><StatusBadge status={current.status} /></strong>
            <span>{w('overview.result.run', { id: current.id })}</span>
            <span>{w('workbench.save.revision', { revision: current.revision })}</span>
            <span>{w('overview.result.condition', { id: current.condition_id })}</span>
            <span>{w('overview.result.fingerprint', { fingerprint: current.request_fingerprint })}</span>
            <span>{w('overview.result.finished', { date: moment(current.finished_at) ?? w('overview.result.finishedUnknown') })}</span>
          </div>
          <div className="metric-grid">{readings.map(reading =>
            <FactField key={reading.key} label={reading.label} value={reading.value}
              dimension={reading.dimension} storedUnit={reading.storedUnit}
              status={reading.state} source={reading.note} />)}</div>
          {stages.length > 0 && <ul className="stage-status-list">{stages.map(stage =>
            <li key={stage.name}><span className={`stage-pill stage-pill--${stage.status}`}><StatusBadge status={stage.status} /></span>
              <span>{stageLabel(w, stage.name)}</span>
              {/* The stage's own stop reason is the core's saved text. */}
              {stage.reason && <small>{stage.reason}</small>}</li>)}</ul>}
          {severe.length > 0 && <div className="stage-diagnostics-open" role="alert">
            <strong>{w('overview.result.severeTitle', { count: severe.length })}</strong>
            {severe.map((item, index) => <p key={index}>{item.stage ? `${w('reading.stageContext', { name: stageLabel(w, item.stage) })}：` : w('overview.result.severeOverall')}{item.message}</p>)}
          </div>}
          <p className="group-note">{w('overview.result.caveat')}</p>
        </>
        : <div className="result-absent">
          <p>{w(resultState === 'loading' ? 'workbench.read.resultLoading' : resultState === 'failed' ? 'workbench.read.resultFailed' : 'overview.result.absent')}</p>
          <p className="group-note">{absentReason}</p>
        </div>}
    </section>

    <section className="chapter-group">
      <div className="group-head"><span className="group-index" aria-hidden="true">05</span>
        <h2>{w('overview.history.title')}</h2><span>{w('overview.history.note')}</span></div>
      {runs.length > 0 && historyState !== 'ready' && <p className="group-note" role="status">{w('workbench.read.historyStale')}</p>}
      {onRefreshRuns && <button className="text-button" disabled={historyState === 'loading'} onClick={onRefreshRuns}>{w('workbench.read.refresh')}</button>}
      {runs.length === 0
        ? <p className="group-note">{w(historyState === 'loading' ? 'workbench.read.historyLoading' : historyState === 'failed' ? 'workbench.read.historyFailed' : 'overview.history.empty')}</p>
        : <div className="run-history">{runs.slice(0, 6).map(item => <button key={item.id} data-audio="manual" onClick={() => onRun(item.id)}>
          <span><span>{w('workbench.save.revision', { revision: item.revision })}</span><span>{w('overview.history.condition', { id: item.condition_id })}</span></span>
          <strong><StatusBadge status={item.status} /></strong>
          <small>{date(item.created_at)}</small>
          <span aria-hidden="true">↗</span>
        </button>)}</div>}
      {current && <p className="group-note">{w('overview.history.caveat', { id: current.id })}</p>}
      <button className="text-button" data-audio="detent" onClick={() => onChapter('hull')}>{w('overview.history.editHull')}</button>
    </section>
  </div>;
}