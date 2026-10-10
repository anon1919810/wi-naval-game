import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';

import * as api from '../api';
import { outcome } from '../audio/feedback';
import { expectRunResult } from '../audio/interactionAudio';
import { DeckFreeboardEditor } from '../components/DeckFreeboardEditor';
import { DamageEditor } from '../components/DamageEditor';
import { GunsEditor } from '../components/GunsEditor';
import { MassModelEditor } from '../components/MassModelEditor';
import { ResistanceEditor } from '../components/ResistanceEditor';
import { WeaponsEditor } from '../components/WeaponsEditor';
import { ArmourEditor } from '../components/ArmourEditor';
import { EnginesEditor } from '../components/EnginesEditor';
import { HullSupplementEditor } from '../components/HullSupplementEditor';
import { BASE_STAGES, EMPTY_REQUEST, PerformanceInputs, PerformanceRequest, PerformanceResults, requestedExtraStages, buildOptions, type RequestDraft } from '../components/PerformanceEditor';
import { buildFloodingRequest, EMPTY_FLOODING_REQUEST, type FloodingRequest } from '../components/floodingModel';
import { CalculationReadiness } from '../components/CalculationReadiness';
import { currentRun, eligibleResultRun, latestOwnedRun, ledgerItems, RESULT_STATUSES } from '../components/formModel';
import { getDeck, type DeckInput } from '../components/deckModel';
import {
  CHAPTER_HEAD, hullGuidanceId, LEDGER_SECTION, ledgerGuidanceId, PROJECT_JSON,
  readDiagnosticTail, REQUEST_DAMAGE, REQUEST_PERFORMANCE, resolveDiagnosticPath,
  type DiagnosticLocation,
} from '../components/diagnosticGuidance';
import { declaredSource, InputTraceProvider, TracePanel, useInputTrace, TracedField, type TraceFact } from '../components/InputTrace';
import { CHAPTERS, chapterNumber, chapterOf, ProjectNav, type Chapter } from '../components/ProjectNav';
import { QuantityField } from '../components/QuantityField';
import { ReadFailure, ReadPending } from '../components/ReadPending';
import { UnitProvider } from '../components/UnitProvider';
import { useMotionToken } from '../components/useLocalMotion';
import { WorkbenchOverview } from '../components/WorkbenchOverview';
import type { ProjectDocument, ProjectView, RunView } from '../types';

// Dimensionless coefficients keep a plain number input; lengths speak the
// reader's unit while the project keeps metres.
const HULL_FIELDS = [
  { key: 'loa_m', alternate: 'length_m', label: '船长', hint: '全长（LOA），保留输入口径', dimension: 'length' },
  { key: 'lwl_m', label: '水线长', hint: '计算水线长度', dimension: 'length' },
  { key: 'beam_m', label: '型宽', hint: '最大型宽', dimension: 'length' },
  { key: 'draught_normal_m', alternate: 'draft_m', label: '设计吃水', hint: '正常工况参考值', dimension: 'length' },
  { key: 'block_coeff', label: '方形系数', hint: '无量纲', dimension: null },
  { key: 'waterplane_coeff', label: '水线面系数', hint: '无量纲', dimension: null },
] as const;

// The chapter that owns a raw-JSON view, and the project section it edits.
// A chapter without a `jsonKey` has no contract fragment of its own.
const CHAPTER_JSON: Partial<Record<Chapter, string>> = Object.fromEntries(
  CHAPTERS.filter(entry => entry[3]).map(entry => [entry[0], entry[3] as string]),
);

function numeric(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function errorMessage(cause: unknown): string {
  if (cause instanceof api.ApiError && Array.isArray(cause.detail)) {
    return cause.detail.map((item: { path?: string; message?: string }) => `${item.path ?? '输入'}：${item.message ?? '无效'}`).slice(0, 4).join('；');
  }
  return cause instanceof Error ? cause.message : '操作未完成，请检查输入';
}

function validationDetails(cause: unknown): Array<{ path: string; message: string }> {
  if (!(cause instanceof api.ApiError) || !Array.isArray(cause.detail)) return [];
  return cause.detail.map(item => {
    const path = typeof item.path === 'string' ? item.path : Array.isArray(item.loc) ? item.loc.join('.') : '项目';
    return { path, message: String(item.message ?? item.msg ?? '输入无效') };
  });
}

// A stored result may only be presented as "current" when it describes exactly
// this project, this saved revision, this condition, and it carries a payload.
// A condition switch, an edit or a foreign response fails this synchronously.
function matchesRun(run: RunView | null | undefined, projectId: string, revision: number, conditionId: string): boolean {
  return !!run && run.project_id === projectId && run.revision === revision
    && run.condition_id === conditionId && RESULT_STATUSES.includes(run.status) && !!run.result;
}

// History is checked at render time too: an effect cannot clear a previous
// condition's payload before the first render of the newly selected condition.
function matchesSavedCheck(run: RunView | null, candidate: RunView | null,
  projectId: string, revision: number, conditionId: string): boolean {
  if (!run || !candidate || run.id !== candidate.id || run.revision !== candidate.revision
    || run.revision > revision || !matchesRun(run, projectId, run.revision, conditionId)) return false;
  return run.result!.project_id === projectId && run.result!.condition_id === conditionId
    && run.result!.request_fingerprint === run.request_fingerprint;
}

/**
 * A numbered first-level group. The number and the thin rule do the dividing, so
 * nested cards inside a group do not need to repeat their own heavy frames.
 */
function InputGroup({ index, title, note }: { index: string; title: string; note?: string }) {
  return <div className="input-group-head">
    <span className="group-index" aria-hidden="true">{index}</span>
    <h2>{title}</h2>
    {note && <span className="group-note-inline">{note}</span>}
  </div>;
}

/**
 * The chapter heading follows the reader's context: the vessel names itself in
 * the Overview, while every other chapter leads with its English structural
 * title and keeps the vessel as a small, secondary identity line.
 */
function ChapterHead({ chapter, name, projectId, revision, proxy }: {
  chapter: Chapter; name: string; projectId: string; revision: number; proxy: boolean;
}) {
  const definition = chapterOf(chapter);
  if (chapter === 'overview') {
    return <header className="chapter-head chapter-head--vessel" id={CHAPTER_HEAD}>
      <span className="section-kicker">{definition.title.toUpperCase()} / {projectId.slice(0, 8).toUpperCase()}</span>
      <div className="vessel-title-row"><h1>{name}</h1>
        <span className="proxy-label">{proxy ? '工程代理 · 非史实认证' : '项目输入'}</span></div>
      <p>{definition.purpose}</p>
    </header>;
  }
  return <header className="chapter-head" id={CHAPTER_HEAD}>
    <span className="section-kicker">{chapterNumber(chapter)} / {definition.title.toUpperCase()}</span>
    <h1>{definition.title}</h1>
    <p className="chapter-context"><span className="chapter-vessel">{name}</span>
      <span>修订 {revision}</span>
      <span>{projectId.slice(0, 8).toUpperCase()}</span>
    </p>
    {definition.purpose && <p className="chapter-purpose">{definition.purpose}</p>}
  </header>;
}

function projectRenderError(value: unknown, projectId: string): string | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return '项目 JSON 根节点无效';
  const row = value as Record<string, unknown>;
  if (row.id !== projectId) return '项目 ID 必须与当前项目一致';
  if (row.schema !== 'plimsoll-project-1') return '项目 schema 无效';
  if (typeof row.name !== 'string' || !row.name.trim()) return '项目缺少有效舰名';
  if (!row.hull || typeof row.hull !== 'object' || Array.isArray(row.hull)) return '项目缺少船型 hull';
  if (!Array.isArray(row.loading_conditions) || !row.loading_conditions.every(
    item => item && typeof item === 'object' && typeof item.id === 'string'
      && (item.label === undefined || item.label === null || typeof item.label === 'string'),
  )) return '项目缺少有效工况 loading_conditions';
  if (!Array.isArray(row.weight_groups) || !row.weight_groups.every(
    group => group && typeof group === 'object' && typeof group.id === 'string'
      && (group.label === undefined || group.label === null || typeof group.label === 'string')
      && Array.isArray(group.items) && group.items.every((item: unknown) => item && typeof item === 'object' && !Array.isArray(item)),
  )) return '项目缺少有效重量分组 weight_groups';
  return null;
}

// Wide desktops have room for a third column; at 1024 the same panel opens above
// the inputs instead, so the trace never squeezes or covers the form.
function traceDefaultsOpen(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return true;
  return !window.matchMedia('(max-width: 1280px)').matches;
}

const FOCUSABLE = 'input, select, textarea, button, a[href], [tabindex]';

/**
 * Opens whatever disclosure folds the control away, moves the keyboard focus
 * onto the control itself, and centres it without an animation. Nothing here is
 * interpolated from a diagnostic path: the element was addressed by an id the
 * workspace mounted itself.
 */
function revealAndFocus(host: HTMLElement) {
  for (let node = host.parentElement; node; node = node.parentElement) {
    if (node.tagName === 'DETAILS' && !(node as HTMLDetailsElement).open) (node as HTMLDetailsElement).open = true;
  }
  const control = host.matches(FOCUSABLE) ? host : host.querySelector<HTMLElement>(FOCUSABLE) ?? host;
  if (!control.hasAttribute('tabindex') && !control.matches('input, select, textarea, button, a[href]')) {
    control.setAttribute('tabindex', '-1');
  }
  control.focus?.({ preventScroll: true });
  host.scrollIntoView?.({ block: 'center', behavior: 'instant' });
}

/**
 * Trace selection belongs to one project chapter. Switching either clears it, so
 * a fact can never be read against a chapter it does not belong to. This is view
 * state only: it never writes to the project or marks the draft as edited.
 */
function TraceScope({ scopeKey, children }: { scopeKey: string; children: ReactNode }) {
  const { clear } = useInputTrace();
  useEffect(() => { clear(); }, [scopeKey, clear]);
  return <>{children}</>;
}



/**
 * One of three named operations, or none. They are named apart on purpose: a
 * save is not a run, and neither is a reload. A reader who is told only that
 * "something is happening" cannot tell whether their revision reached the
 * server, and a save in progress must never be reported as a busy calculation.
 */
type Operation = 'saving' | 'starting' | 'reloading';

const OPERATION_TEXT: Record<Operation, string> = {
  saving: '正在保存修订…', starting: '正在提交计算请求…', reloading: '正在重新载入项目…',
};

export function Workbench({ projectId, onBack, onRun, onDirtyChange, onLab }: {
  projectId: string; onBack: () => void; onRun: (runId: string) => void; onDirtyChange?: (dirty: boolean) => void; onLab?: () => void;
}) {
  const [view, setView] = useState<ProjectView | null>(null);
  const [draft, setDraft] = useState<ProjectDocument | null>(null);
  const [chapter, setChapter] = useState<Chapter>('overview');
  const [traceOpen, setTraceOpen] = useState(traceDefaultsOpen);
  const [conditionId, setConditionId] = useState('');
  const [dirty, setDirty] = useState(false);
  const [operation, setOperation] = useState<Operation | null>(null);
  const [error, setError] = useState('');
  const [loadError, setLoadError] = useState('');
  const [load, setLoad] = useState<'loading' | 'failed'>('loading');
  const [attempt, setAttempt] = useState(0);
  const [conflict, setConflict] = useState<number | null>(null);
  const [jsonText, setJsonText] = useState('');
  const [jsonError, setJsonError] = useState('');
  // A hand-edited document that has not been applied yet. A jump that would
  // leave this chapter discards it, so the jump is refused instead.
  const [jsonEdited, setJsonEdited] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Array<{ path: string; message: string }>>([]);
  const [inspected, setInspected] = useState<{ label: string; source: string; estimate: boolean } | null>(null);
  const [runs, setRuns] = useState<RunView[]>([]);
  const [runResult, setRunResult] = useState<RunView | null>(null);
  const [pendingRunId, setPendingRunId] = useState<string | null>(null);
  const [performanceRequest, setPerformanceRequest] = useState<RequestDraft>(EMPTY_REQUEST);
  const [floodingRequest, setFloodingRequest] = useState<FloodingRequest>(EMPTY_FLOODING_REQUEST);
  // The flooding request joins the existing performance request only when a
  // saved scenario is chosen; otherwise the stage stays unrequested exactly as
  // before. Both requests use the same project revision and condition.
  const performanceOptions = buildOptions(performanceRequest);
  const floodingChoice = buildFloodingRequest(draft ?? {}, floodingRequest);
  // An explicit environment density belongs to the whole request: the flooding
  // stage is required to use the same equilibrium options as every other stage.
  const equilibrium = { ...(performanceOptions.options.equilibrium as Record<string, unknown> | undefined) };
  const runError = performanceOptions.error || floodingChoice.error;
  // An invalid request carries no assembled stage list at all, and the flooding
  // choice must never spread one. The panel therefore names the stages this
  // request *explicitly* selects — the existing shared base stages plus the
  // studies the reader picked — rather than reporting none.
  const assembledStages = Array.isArray(performanceOptions.options.stages) ? (performanceOptions.options.stages as string[]) : [];
  const runOptions = floodingChoice.flooding
    ? {
      ...performanceOptions.options,
      ...(floodingChoice.rho === null ? {} : { equilibrium: { ...equilibrium, rho_t_m3: floodingChoice.rho } }),
      stages: [...assembledStages, 'flooding'],
      flooding: floodingChoice.flooding,
    }
    : performanceOptions.options;
  /** The stages this request will actually submit, read from the request itself. */
  const requestStages = runError
    ? [...BASE_STAGES, ...requestedExtraStages(performanceRequest), ...(floodingRequest.scenario.trim() ? ['flooding'] : [])]
    : Array.isArray(runOptions.stages) ? (runOptions.stages as string[]) : [];
  /** The field a followed diagnostic is waiting to focus, and its own ticket. */
  const [focusRequest, setFocusRequest] = useState<{ target: string; seq: number } | null>(null);
  const [guidanceNotice, setGuidanceNotice] = useState('');
  const focusTicket = useRef(0);
  /** Every destination change retires the answer that was asked for the last one. */
  const arrivalTicket = useRef(0);
  /** The address this page has already acted on, so a re-render never replays it. */
  const handledArrival = useRef<string | null>(null);
  /** Always the newest draft: a jump resolves against what is on screen now. */
  const draftRef = useRef<ProjectDocument | null>(null);
  draftRef.current = draft;
  const chapterRef = useRef(chapter);
  chapterRef.current = chapter;
  const jsonEditedRef = useRef(jsonEdited);
  jsonEditedRef.current = jsonEdited;
  const conditionRef = useRef(conditionId);
  conditionRef.current = conditionId;
  const draftGeneration = useRef(0);
  const loadTicket = useRef(0);
  /**
   * The page's lifetime, and one ticket per write. A save, a reload or a queued
   * run that resolves after the reader has left belongs to a page that no longer
   * exists: it must not paint into an unmounted tree, must not navigate, and
   * must not leave the toolbar claiming an operation is still running.
   */
  const alive = useRef(true);
  const writeTicket = useRef(0);
  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; writeTicket.current += 1; loadTicket.current += 1; };
  }, []);
  const current = () => alive.current;
  const busy = operation !== null;
  // The chapter reveal is a local one-shot keyed on the chapter itself. The
  // container is never re-keyed, so a hand-edited JSON document, the focused
  // control and the reader's selection all survive the switch untouched.
  const chapterMotion = useMotionToken(chapter);

  useEffect(() => {
    let active = true;
    const mine = ++loadTicket.current;
    setLoad('loading');
    setLoadError('');
    setError('');
    api.getProject(projectId).then(saved => {
      if (!active || loadTicket.current !== mine) return;
      setView(saved);
      setDraft(structuredClone(saved.project));
      setPerformanceRequest(EMPTY_REQUEST);
      // A request draft belongs to the loaded revision: a different project must
      // never inherit a chosen scenario, environment density or limit.
      setFloodingRequest(EMPTY_FLOODING_REQUEST);
      setConditionId(saved.project.loading_conditions[0]?.id ?? '');
      setDirty(false);
      setError('');
    }).catch(cause => {
      // An older answer that arrives after a retry has started is not the one
      // this page is now waiting for.
      if (!active || loadTicket.current !== mine) return;
      setLoadError(errorMessage(cause));
      setLoad('failed');
    });
    return () => { active = false; };
  }, [projectId, attempt]);

  // The leave guard is told about edits, not about renders: one call when the
  // workspace stops matching what the reader can recover — an edited draft, or
  // hand-written JSON that has not been applied yet and would be lost by leaving.
  useEffect(() => { onDirtyChange?.(dirty || jsonEdited); }, [dirty, jsonEdited, onDirtyChange]);

  useEffect(() => {
    let active = true;
    api.listRuns(projectId).then(items => { if (active) setRuns(items); }).catch(() => { /* Project editing remains usable if history is unavailable. */ });
    return () => { active = false; };
  }, [projectId]);

  // The list endpoint never carries result payloads (the backend builds run
  // summaries with `include_result=False`), so retrieve exactly one run: the
  // newest completed/partial run of the saved revision and selected condition.
  //
  // Identity is re-checked synchronously at render time by `currentRun`, so a
  // condition switch or an unsaved draft hides the previous result immediately
  // rather than after the in-flight request resolves. The response is accepted
  // only when it still matches the candidate that requested it.
  //
  // An edited draft does not stop the read: the saved run stays available as
  // *history* — it is the previous check, and it is usually the most useful
  // thing on the page while an input is being corrected. What it may not do is
  // become the current result, and `currentRun` already refuses that outright.
  useEffect(() => {
    const revision = view?.revision ?? -1;
    const candidate = eligibleResultRun(runs, revision, conditionId);
    // A run list entry may already carry its payload; use it directly and make
    // no request. Only a payload-less entry needs the single bounded retrieval.
    setPendingRunId(candidate && !candidate.result ? candidate.id : null);
    if (!candidate) { setRunResult(null); return; }
    if (candidate.result) { setRunResult(matchesRun(candidate, projectId, revision, conditionId) ? candidate : null); return; }
    let active = true;
    api.getRun(candidate.id).then(full => {
      if (!active) return;
      setRunResult(full.id === candidate.id && matchesRun(full, projectId, revision, conditionId) ? full : null);
    }).catch(() => { if (active) setRunResult(null); });
    return () => { active = false; };
  }, [runs, view?.revision, conditionId, projectId]);

  /**
   * The last check that actually ran, kept across a save.
   *
   * The moment a corrected revision is saved, the new revision has no result at
   * all and the strict candidate above finds nothing — which would throw away
   * the very diagnostic the reader is following. This one is matched on project
   * and condition only, so the previous check survives the save and a fresh
   * load. It is never a current result: `currentRun` is untouched, and the panel
   * attributes it to its own run, revision and condition.
   */
  const historyCandidate = latestOwnedRun(runs, projectId, conditionId, view?.revision ?? -1);
  const historyKey = historyCandidate ? `${historyCandidate.id}|${historyCandidate.result ? 'full' : 'summary'}` : '';
  const currentResultId = eligibleResultRun(runs, view?.revision ?? -1, conditionId)?.id;
  const [historyRun, setHistoryRun] = useState<RunView | null>(null);
  useEffect(() => {
    if (!historyCandidate) { setHistoryRun(null); return; }
    const mine = historyCandidate;
    // The current-result read already retrieves this payload. Share it rather
    // than issue a second request for the same saved run.
    if (mine.id === currentResultId) { setHistoryRun(null); return; }
    if (mine.result) {
      setHistoryRun(matchesSavedCheck(mine, mine, projectId, view?.revision ?? -1, conditionId) ? mine : null);
      return;
    }
    let active = true;
    api.getRun(mine.id).then(full => {
      if (!active) return;
      setHistoryRun(matchesSavedCheck(full, mine, projectId, view?.revision ?? -1, conditionId) ? full : null);
    }).catch(() => { if (active) setHistoryRun(null); });
    return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [historyKey, projectId, conditionId, view?.revision, currentResultId]);

  /**
   * A jump to a real field: select the chapter, then focus and scroll once the
   * control is actually mounted. It is a view change and nothing else — no
   * input is written, nothing is saved, no run is queued, and the Workbench is
   * never remounted, so the draft and the leave guard survive it untouched.
   *
   * The path is re-resolved against the draft as it stands right now, so a
   * ledger item removed since the saved run is refused here instead of focusing
   * whatever now sits at that index. It says nothing about the notice: whatever
   * the caller wants the reader to keep reading stays on screen.
   */
  function jumpTo(location: DiagnosticLocation, snapshot: ProjectDocument | null = null): boolean {
    const target = resolveDiagnosticPath(location.path, { snapshot, live: draftRef.current }) ?? location;
    if (!target.chapter || !target.target) {
      setGuidanceNotice(`路径 ${target.path} 没有可定位的项目输入：${target.note}`);
      return false;
    }
    if (target.chapter !== chapterRef.current && jsonEditedRef.current) {
      // Refused, not consumed: the same jump is retried once the reader has
      // applied or discarded that edit.
      handledArrival.current = null;
      setGuidanceNotice('当前章节的项目 JSON 还没有“应用到草稿”。跳转会丢弃这段未应用的编辑，已拒绝：文本保持原样。');
      return false;
    }
    setChapter(target.chapter);
    setFocusRequest({ target: target.target, seq: ++focusTicket.current });
    setGuidanceNotice(target.note);
    return true;
  }

  /**
   * Following a diagnostic from a report. The address is read on mount and on
   * `hashchange`, so refreshing, copying and Back/Forward all arrive the same
   * way; the run behind it is fetched and checked against the address, against
   * itself and against the project before anything moves.
   *
   * Every destination change retires the previous answer, including a plain
   * return to the project's base address, and the address is re-read when the
   * answer arrives. A foreign run, a run that disagrees with its own result, a
   * condition that has since been removed, a malformed tail and a late answer
   * each end in a sentence that says so, never in a wrong focus.
   */
  useEffect(() => {
    if (!draft) return;
    const arrive = () => {
      const tail = readDiagnosticTail(window.location.hash, projectId);
      const key = tail.kind === 'target' ? `${tail.runId}|${tail.path}`
        : tail.kind === 'malformed' ? `malformed|${window.location.hash}` : null;
      // Whatever the destination, the previous answer is now retired.
      const mine = ++arrivalTicket.current;
      focusTicket.current += 1;
      setFocusRequest(null);
      handledArrival.current = key;
      if (tail.kind === 'none') return;
      if (tail.kind === 'malformed') { setGuidanceNotice(tail.reason); return; }
      const { runId, path } = tail;
      setGuidanceNotice('');
      api.getRun(runId).then(source => {
        if (!alive.current || arrivalTicket.current !== mine) return;
        // The answer must still belong to the address the reader is standing on.
        const still = readDiagnosticTail(window.location.hash, projectId);
        if (still.kind !== 'target' || still.runId !== runId || still.path !== path) return;
        if (source.id !== runId) {
          setGuidanceNotice(`读取到的运行 ${source.id} 与地址要求的 ${runId} 不一致，已拒绝跳转。`);
          return;
        }
        if (source.project_id !== projectId) {
          setGuidanceNotice(`运行 ${runId} 属于其他项目，已拒绝跳转。`);
          return;
        }
        if (!source.result) {
          setGuidanceNotice(`运行 ${runId} 尚无已保存结果，无法定位输入。`);
          return;
        }
        // The stored result has to be the same run's own result, or the
        // identity behind the link is not one we can trust.
        const result = source.result;
        const consistent = result.project_id === source.project_id
          && result.condition_id === source.condition_id
          && result.request_fingerprint === source.request_fingerprint;
        if (!consistent) {
          setGuidanceNotice(`运行 ${runId} 的项目、工况或请求指纹与其保存结果不一致，已拒绝跳转。`);
          return;
        }
        // An existing condition may be selected so the reader lands on the
        // inputs the run actually used. A condition that has since been removed
        // is never resurrected, and nothing is followed on its behalf.
        const conditions = draftRef.current?.loading_conditions ?? [];
        if (!conditions.some(item => item.id === source.condition_id)) {
          setGuidanceNotice(`运行 ${runId} 的工况 ${source.condition_id} 已不在当前项目，已拒绝跳转。`);
          return;
        }
        const snapshot = result.input_snapshot ?? null;
        const location = resolveDiagnosticPath(path, { snapshot, live: draftRef.current });
        if (!location || location.kind === 'evidence') {
          setGuidanceNotice(`路径 ${path} 没有可定位的项目输入：${location?.note ?? '这条诊断路径无法解析。'}`);
          return;
        }
        const notice = source.revision !== view?.revision
          ? `该诊断来自修订 ${source.revision}；当前项目已保存修订 ${view?.revision}，需要保存并重新运行后才会更新。`
          : '';
        if (source.condition_id !== conditionRef.current) setConditionId(source.condition_id);
        if (!jumpTo(location, snapshot)) return;
        // Stated after the jump, so the reader sees it next to where they landed.
        if (notice) setGuidanceNotice(`${notice} ${location.note}`);
      }).catch(() => {
        if (alive.current && arrivalTicket.current === mine) setGuidanceNotice(`无法读取诊断来源运行 ${runId}。`);
      });
    };
    // A re-render only acts when the address is one this page has not used.
    const reconcile = () => {
      const tail = readDiagnosticTail(window.location.hash, projectId);
      const key = tail.kind === 'target' ? `${tail.runId}|${tail.path}`
        : tail.kind === 'malformed' ? `malformed|${window.location.hash}` : null;
      if (key !== handledArrival.current) arrive();
    };
    reconcile();
    window.addEventListener('hashchange', arrive);
    return () => { window.removeEventListener('hashchange', arrive); arrivalTicket.current += 1; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, view?.revision, !!draft]);

  /**
   * Focus the addressed control as soon as it exists, opening whatever details
   * fold contains it, and scroll it to the middle of the view without an
   * animation. The retry is bounded: the chapter may still be mounting, but it
   * is never waited for forever.
   */
  useEffect(() => {
    if (!focusRequest) return;
    const seq = focusRequest.seq;
    const frame = typeof requestAnimationFrame === 'function'
      ? (task: () => void) => requestAnimationFrame(() => { task(); })
      : (task: () => void) => setTimeout(task, 16) as unknown as number;
    const cancel = typeof cancelAnimationFrame === 'function' ? cancelAnimationFrame : clearTimeout;
    let cancelled = false;
    let pending = 0;
    let attempts = 0;
    const attempt = () => {
      if (cancelled || focusTicket.current !== seq) return;
      const host = document.getElementById(focusRequest.target);
      if (host) { revealAndFocus(host); return; }
      if (attempts++ >= 30) return;
      pending = frame(attempt);
    };
    pending = frame(attempt);
    return () => { cancelled = true; cancel(pending); };
  }, [focusRequest]);

  useEffect(() => {
    // Hand-written text the reader has not applied is theirs: a save or a reload
    // replaces the draft, and that must never silently overwrite what is on
    // screen. Applying the text clears the flag first, so this refresh still
    // runs for the reader's own edit.
    if (!draft || jsonEditedRef.current) return;
    const section = CHAPTER_JSON[chapter];
    const value = chapter === 'json' ? draft : section ? draft[section] : null;
    setJsonText(JSON.stringify(value ?? (chapter === 'damage' ? [] : {}), null, 2));
    setJsonError('');
    setJsonEdited(false);
  }, [chapter, draft]);

  /** The chapter's own serialization of the draft, which is where a discard returns to. */
  function jsonSource(): string {
    if (!draft) return '';
    const section = CHAPTER_JSON[chapter];
    const value = chapter === 'json' ? draft : section ? draft[section] : null;
    return JSON.stringify(value ?? (chapter === 'damage' ? [] : {}), null, 2);
  }

  /** Throws away unapplied JSON explicitly. Invalid text can never trap a reader here. */
  function discardJson() {
    setJsonText(jsonSource());
    setJsonError('');
    setJsonEdited(false);
  }

  /**
   * A chapter change never discards unapplied JSON silently. The reader is told
   * what the chapter offers to keep it, and nothing is applied on their behalf.
   */
  function goChapter(next: Chapter) {
    if (next === chapterRef.current) return;
    if (jsonEditedRef.current) {
      handledArrival.current = null;
      setGuidanceNotice('当前章节有未应用的项目 JSON 文本，离开会丢弃它，已保留本章：可“放弃未应用的文本”后切换，或先“应用到草稿”。');
      return;
    }
    setChapter(next);
  }

  function updateDraft(next: ProjectDocument) {
    draftGeneration.current += 1;
    setDraft(next);
    if (!next.loading_conditions.some(c => c.id === conditionId)) setConditionId(next.loading_conditions[0]?.id ?? '');
    setDirty(true);
    setConflict(null);
    setError('');
    setFieldErrors([]);
  }

  function updateHull(key: string, value: string | number | null) {
    if (!draft) return;
    const next = structuredClone(draft);
    next.hull[key] = value === null || value === '' ? null : Number(value);
    updateDraft(next);
  }

  function updateMass(groupIndex: number, itemIndex: number, key: string, value: string | number | null) {
    if (!draft) return;
    const next = structuredClone(draft);
    next.weight_groups[groupIndex].items[itemIndex][key] = key === 'source' ? value : value === null || value === '' ? null : Number(value);
    updateDraft(next);
  }

  function patchDeck(next: DeckInput) {
    if (!draft) return;
    const prev = (draft as Record<string, unknown>).deck;
    const prevTop = prev && typeof prev === 'object' ? { ...(prev as Record<string, unknown>) } : {};
    const newDeck = {
      ...prevTop,
      estimate: next.estimate,
      source: next.source,
      points: next.points,
      segments: next.segments,
      reference_length_m: next.reference_length_m,
    };
    const clone = structuredClone(draft) as Record<string, unknown>;
    clone.deck = newDeck;
    updateDraft(clone as ProjectDocument);
  }

  function getWeapons(): Record<string, unknown> {
    const systems = (draft as Record<string, unknown>).systems;
    if (!systems || typeof systems !== 'object' || Array.isArray(systems)) return {};
    const weapons = (systems as Record<string, unknown>).weapons;
    return weapons && typeof weapons === 'object' && !Array.isArray(weapons) ? (weapons as Record<string, unknown>) : {};
  }

  function patchBattery(batteryId: string, next: Record<string, unknown>) {
    if (!draft) return;
    const clone = structuredClone(draft) as Record<string, unknown>;
    const systems = (clone.systems ?? {}) as Record<string, unknown>;
    const weapons = (systems.weapons ?? {}) as Record<string, unknown>;
    weapons[batteryId] = next;
    systems.weapons = weapons;
    clone.systems = systems;
    updateDraft(clone as ProjectDocument);
  }

  function patchWeapons(leafId: string, next: Record<string, unknown>) {
    if (!draft) return;
    const clone = structuredClone(draft) as Record<string, unknown>;
    const systems = (clone.systems ?? {}) as Record<string, unknown>;
    const weapons = (systems.weapons ?? {}) as Record<string, unknown>;
    weapons[leafId] = next;
    systems.weapons = weapons;
    clone.systems = systems;
    updateDraft(clone as ProjectDocument);
  }

  // Portable copy of the editable project document, not the calculation report:
  // a lost browser workspace can be recovered by pasting this JSON back in.
  function downloadProject() {
    if (!draft || !view) return;
    const payload = JSON.stringify(draft, null, 2);
    const url = URL.createObjectURL(new Blob([payload], { type: 'application/json' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = `${draft.name || 'project'}-r${view.revision}${dirty ? '-draft' : ''}.json`;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  async function copyDraft() {
    if (!draft) return;
    const ticket = writeTicket.current;
    try {
      if (!navigator.clipboard) throw new Error('浏览器暂不支持复制，请使用“下载项目 JSON”备份修改。');
      await navigator.clipboard.writeText(JSON.stringify(draft, null, 2));
      if (current() && writeTicket.current === ticket) outcome('resolve');
    } catch (cause) {
      if (current() && writeTicket.current === ticket) { setError(errorMessage(cause)); outcome('hold'); }
    }
  }

  async function save() {
    if (!view || !draft || !dirty || operation) return;
    const submittedGeneration = draftGeneration.current;
    const ticket = ++writeTicket.current;
    const mine = () => current() && writeTicket.current === ticket;
    setOperation('saving');
    setError('');
    try {
      const saved = await api.saveProject(projectId, { base_revision: view.revision, project: draft });
      // A newer write, or an unmounted page, has taken this answer away.
      if (!mine()) return;
      setView(saved);
      // Edits made while the save was in flight are still the reader's: the
      // draft is only replaced when nothing was touched, and otherwise stays
      // dirty against the revision that was just written.
      if (draftGeneration.current === submittedGeneration) {
        setDraft(structuredClone(saved.project));
        setDirty(false);
      } else {
        setDirty(true);
      }
      setConflict(null);
      setFieldErrors([]);
      outcome('resolve');
    } catch (cause) {
      if (!mine()) return;
      outcome('hold');
      if (cause instanceof api.ApiError && cause.status === 409) {
        const detail = cause.detail as { current_revision?: number };
        setConflict(detail.current_revision ?? -1);
      } else {
        setError(errorMessage(cause));
        setFieldErrors(validationDetails(cause));
      }
    } finally { if (mine()) setOperation(null); }
  }

  async function reload() {
    const ticket = ++writeTicket.current;
    const mine = () => current() && writeTicket.current === ticket;
    setOperation('reloading');
    setError('');
    try {
      const saved = await api.getProject(projectId);
      if (!mine()) return;
      setView(saved);
      setDraft(structuredClone(saved.project));
      setPerformanceRequest(EMPTY_REQUEST);
      setFloodingRequest(EMPTY_FLOODING_REQUEST);
      setDirty(false);
      setConflict(null);
      setError('');
      outcome('detent');
    } catch (cause) { if (mine()) { setError(errorMessage(cause)); outcome('hold'); } }
    finally { if (mine()) setOperation(null); }
  }

  async function run() {
    if (!view || !conditionId || dirty || runError || operation) return;
    const ticket = ++writeTicket.current;
    const mine = () => current() && writeTicket.current === ticket;
    setOperation('starting');
    setError('');
    try {
      const queued = await api.enqueueRun(projectId, { revision: view.revision, condition_id: conditionId, options: runOptions });
      // The queueing succeeded and this page is still the one that asked, so the
      // run it created is the destination. A page that has since been left does
      // not navigate anywhere.
      if (!mine()) return;
      expectRunResult(queued.id);
      onRun(queued.id);
    } catch (cause) { if (mine()) { setError(errorMessage(cause)); outcome('hold'); } }
    finally { if (mine()) setOperation(null); }
  }

  function applyJson() {
    if (!draft) return;
    try {
      const parsed: unknown = JSON.parse(jsonText);
      if (chapter === 'json') {
        const problem = projectRenderError(parsed, projectId);
        if (problem) throw new Error(problem);
        updateDraft(parsed as ProjectDocument);
      } else {
        const section = CHAPTER_JSON[chapter];
        if (!section) return;
        const next = structuredClone(draft);
        next[section] = parsed;
        updateDraft(next);
      }
      setJsonError('');
      setJsonEdited(false);
    } catch (cause) { setJsonError(cause instanceof Error ? cause.message : 'JSON 格式无效'); outcome('hold'); }
  }

  // A project that never loaded is its own content: the reason, one explicit
// retry, and the real way back to the library. There is no skeleton behind it.
if (!draft || !view) return <div className="page-pad"><p className="section-kicker">WORKSPACE / {load === 'failed' ? 'LOAD FAILED' : 'LOADING'}</p>
  {load === 'failed'
    ? <ReadFailure title={`无法读取舰船 ${projectId}`} detail={loadError} onRetry={() => setAttempt(current => current + 1)} onBack={onBack} backLabel="← 返回项目库" />
    : <ReadPending scope="workbench" object="舰船项目" />}</div>;

  const hull = draft.hull ?? {};
  const hullSources = (hull.sources && typeof hull.sources === 'object' ? hull.sources : {}) as Record<string, unknown>;
  // Validate identity here, in render, rather than relying on the effect having
  // run: a stale or in-flight result must never be displayed for the current
  // revision/condition.
  const selectedRun = currentRun(runResult, projectId, view.revision, conditionId, dirty);
  // History and result are two different things from two different runs: the
  // guarded result above is what the saved revision may present, and the owned
  // previous check below is what the reader still needs after a save.
  const latestCheck = runResult?.id === historyCandidate?.id ? runResult : historyRun;
  const historyOfSelected = matchesSavedCheck(latestCheck, historyCandidate, projectId, view.revision, conditionId)
    ? latestCheck : null;
  const ledger = ledgerItems(draft);
  const visibleRuns = selectedRun ? [selectedRun] : [];
  // Display units follow the edited draft. They change presentation only: the
  // saved revision, the request and every export stay canonical.
  const page = <div className="workbench-layout" data-trace={traceOpen ? 'open' : 'closed'}>
    <ProjectNav name={draft.name} active={chapter} onSelect={goChapter} onBack={onBack} />
    <main className="workbench-main">
      <div className="workbench-toolbar">
        <div className="operation-bar">
          <div className="operation-identity">
            <label htmlFor="condition">当前工况</label>
            <select id="condition" value={conditionId} onChange={event => setConditionId(event.target.value)}>
              {draft.loading_conditions.length === 0 ? <option value="">尚无工况</option>
                : draft.loading_conditions.map(item => <option key={item.id} value={item.id}>{item.label || item.id}</option>)}
            </select>
            {/* The saved revision stays visible while the draft is edited: an
                unsaved edits do not change the saved revision number. */}
            <span className="save-state">
              <span className={`save-dot ${dirty ? 'save-dot--dirty' : ''}`} aria-hidden="true" />
              <span>{dirty ? '未保存修改' : '已保存'}</span>
              <span className="save-revision">修订 {view.revision}</span>
            </span>
            {/* One live line for the operation actually in flight, so the bar
                answers "what is it doing" without being read off the buttons. */}
            {operation && <span className="operation-live" role="status">{OPERATION_TEXT[operation]}</span>}
          </div>
          <div className="toolbar-actions">
            {/* Each control names the operation it is actually waiting on. A save
                in progress keeps the run control reading as a run, because it is
                not one. */}
            <button className="button button--secondary" onClick={save} disabled={!dirty || busy}>{operation === 'saving' ? '保存中…' : '保存修订'}</button>
            <button className="button button--primary" onClick={run} disabled={dirty || !conditionId || busy || !!runError}
              title={dirty ? '先保存当前修改再运行计算' : runError || undefined}>{operation === 'starting' ? '正在启动计算…' : '运行计算 ↗'}</button>
            <details className="secondary-actions">
              <summary aria-label="更多操作">更多</summary>
              <div className="secondary-actions-panel">
                {onLab && <button className="button button--secondary" onClick={onLab} disabled={dirty || busy}
                  title={dirty ? '先保存当前修订再进入实验室' : '以已保存的舰船修订做命中后果试验'}>损伤实验室 ↗</button>}
                <button className="button button--secondary" onClick={downloadProject}
                  title={dirty ? '下载当前草稿文档（含未保存修改）' : `下载已保存的修订 ${view.revision} 项目文档`}>
                  下载项目 JSON
                </button>
                <p>项目文档是草稿备份，不是计算报告。</p>
              </div>
            </details>
          </div>
        </div>
        {/* Every blocking failure sits here, directly under the operation bar and
            above the chapter heading: request errors included, never folded away. */}
        <div className="workbench-alerts">
          {runError && <div className="notice notice--error" role="alert">{runError}</div>}
          {error && <div className="notice notice--error" role="alert">{error}</div>}
          {/* A refused jump is stated here, in the one place that is always on
              screen, and it changes neither the chapter nor the draft. */}
          {guidanceNotice && <div className="notice" role="status">{guidanceNotice}</div>}
          {conflict !== null && <div className="notice notice--conflict" role="alert"><strong>服务器已有修订 {conflict}</strong><p>你的修改仍留在此页。复制后再载入最新版本，避免覆盖他人的或另一标签页的工作。</p><div className="notice-actions"><button className="button button--secondary" onClick={() => { void copyDraft(); }}>复制我的修改</button><button className="button button--primary" disabled={operation !== null} onClick={() => { void reload(); }}>{operation === 'reloading' ? '正在重新载入…' : '重新载入'}</button></div></div>}
        </div>
      </div>
      {/* The chapter reveal is keyed on the chapter alone, and this container is
          never re-keyed: the operation bar and the chapter index stay put, and a
          hand-edited JSON document survives the switch with its value, its focus
          and its selection. */}
      <div className="workbench-content" data-motion={chapterMotion}>
        <ChapterHead chapter={chapter} name={draft.name} projectId={draft.id} revision={view.revision} proxy={draft.name.toLowerCase().includes('queen mary')} />
        {chapter === 'overview' && <WorkbenchOverview draft={draft} revision={view.revision} conditionId={conditionId}
          runs={runs} current={selectedRun} previous={historyOfSelected} requestStages={requestStages}
          requestError={runError} dirty={dirty} onChapter={goChapter} onRun={onRun} onNavigate={jumpTo} />}
        {chapter === 'hull' && <section className="editor-section"><InputGroup index="01" title="主尺度" note="显示单位可读，保存与计算仍为规范单位" />
          <p className="section-intro">主尺度只记录已知输入。留空表示未知，不自动补零。复杂型线可在“项目数据”中编辑。</p>
          <div className="field-grid">{HULL_FIELDS.map(field => { const alternate = 'alternate' in field ? field.alternate : undefined; const key = alternate && !(field.key in hull) ? alternate : field.key; const issue = fieldErrors.find(item => item.path.includes(`hull.${key}`) || item.path.includes(`hull['${key}']`));
            // A main dimension carries no per-field source of its own; only an
            // explicitly declared `hull.sources` entry is ever read as one.
            const declared = hullSources[key];
            const fact: TraceFact = { key: `hull.${key}`, label: field.label, value: numeric(hull[key]),
              dimension: field.dimension ?? undefined, storedUnit: field.dimension ? 'm' : undefined,
              // No per-dimension estimate flag is stored alongside hull.sources.
              source: declaredSource(declared),
              estimate: null, path: `hull.${key}` };
            return <TracedField fact={fact} className="hull-field" key={field.key} id={hullGuidanceId(field.key)}>
          {field.dimension
            ? <QuantityField label={field.label} ariaLabel={field.label} value={numeric(hull[key])} dimension={field.dimension} kind="positive" invalid={Boolean(issue)} hint={field.hint} onChange={next => updateHull(key, next === null ? null : String(next))} />
            : <label className="field-label">{field.label}<input type="number" step="any" aria-label={field.label} aria-invalid={Boolean(issue)} value={typeof hull[key] === 'number' ? hull[key] : ''} onChange={event => updateHull(key, event.target.value)} placeholder="未知" /><small>{field.hint}</small>{issue && <span className="field-error" role="alert">{issue.message}</span>}</label>}
          {field.dimension && issue && <span className="field-error" role="alert">{issue.message}</span>}
        </TracedField>; })}</div></section>}
        {chapter === 'hull' && <section className="editor-section"><InputGroup index="02" title="补充船型与显示" /><HullSupplementEditor project={draft} run={selectedRun} onChange={updateDraft} /></section>}
        {/* Reading order: every input first, then the optional request, then the
            results that request produces. Nothing is recomputed to reorder this. */}
        {chapter === 'performance' && <section className="editor-section"><InputGroup index="01" title="载荷工况与横摇输入" note="工况定义与派生扣除规则" />
          <PerformanceInputs project={draft} onChange={updateDraft} /></section>}
        {chapter === 'performance' && <section className="editor-section"><InputGroup index="02" title="阻力研究场景" note="两种既有方法 · 输入来源与敏感性" />
          <ResistanceEditor project={draft} onChange={updateDraft} /></section>}
        {chapter === 'performance' && <section className="editor-section" id={REQUEST_PERFORMANCE} tabIndex={-1}><InputGroup index="03" title="本次计算请求" note="可选 · 只决定这次运行计算什么" />
          <PerformanceRequest project={draft} request={performanceRequest} onRequestChange={setPerformanceRequest} /></section>}
        {chapter === 'performance' && <section className="editor-section"><InputGroup index="04" title="结果" note="当前修订 · 所选工况" />
          <PerformanceResults run={selectedRun} /></section>}
        {chapter === 'weights' && <section className="editor-section" id={LEDGER_SECTION} tabIndex={-1}><InputGroup index="01" title="载荷账本" note={`${draft.weight_groups.length} 个分组`} />
          {draft.weight_groups.length === 0 ? <div className="empty-state compact"><h3>还没有重量分组</h3><p>空白项目可先从项目数据中添加账本结构。</p></div> : draft.weight_groups.map((group, groupIndex) => <div className="weight-group" key={group.id}><div className="weight-group-title"><h3>{group.label || group.id}</h3><span>{group.items.length} 项</span></div><div className="weight-list">{group.items.map((item, itemIndex) => {
            const itemId = String(item.id ?? `条目 ${itemIndex + 1}`);
            const source = declaredSource(item.source);
            const estimate = item.estimate === true ? true : item.estimate === false ? false : null;
            // Mass and longitudinal position are two facts of one ledger item, and
            // each shows the item's own declared source rather than a shared note.
            const massFact: TraceFact = { key: `ledger.${group.id}.${itemId}.mass_t`, label: `${itemId} 质量`, value: numeric(item.mass_t), dimension: 'mass', storedUnit: 't', source, estimate, path: `weight_groups[${groupIndex}].items[${itemId}].mass_t` };
            const positionFact: TraceFact = { ...massFact, key: `ledger.${group.id}.${itemId}.x_m`, label: `${itemId} 纵向位置`, value: numeric(item.x_m), dimension: 'length', storedUnit: 'm', path: `weight_groups[${groupIndex}].items[${itemId}].x_m` };
            // A followed diagnostic addresses one ledger row by the ids the
            // source run saw, so only a row with a real id can be reached.
            const keyed = typeof item.id === 'string' && item.id !== '';
            const rowId = (field: string) => keyed ? ledgerGuidanceId(String(group.id), itemId, field) : undefined;
            return <div className="weight-row" key={String(item.id ?? itemIndex)}><strong>{itemId}</strong>
              <TracedField fact={massFact} id={rowId('mass_t')}><QuantityField small label="质量" ariaLabel={`${group.id} ${itemId} 质量`} value={numeric(item.mass_t)} dimension="mass" kind="nonnegative" onChange={next => updateMass(groupIndex, itemIndex, 'mass_t', next)} /></TracedField>
              <TracedField fact={positionFact} id={rowId('x_m')}><QuantityField small label="纵向位置" ariaLabel={`${group.id} ${itemId} 纵向位置`} value={numeric(item.x_m)} dimension="length" onChange={next => updateMass(groupIndex, itemIndex, 'x_m', next)} /></TracedField>
              <TracedField fact={{ ...massFact, key: `ledger.${group.id}.${itemId}.source`, label: `${itemId} 来源`, value: source, dimension: undefined, storedUnit: undefined, path: `weight_groups[${groupIndex}].items[${itemId}].source` }} id={rowId('source')}>
                <label>来源<input value={source ?? ''} onChange={event => updateMass(groupIndex, itemIndex, 'source', event.target.value)} /></label>
              </TracedField></div>;
          })}</div></div>)}</section>}
        {chapter === 'weights' && <section className="editor-section"><InputGroup index="02" title="系统质量模型" note="按已声明输入核算质量，不改写账本" /><MassModelEditor project={draft} run={selectedRun} onChange={updateDraft} /></section>}
        {chapter === 'stability' && <section className="editor-section"><InputGroup index="01" title="端点与干舷" note="端点、干舷与参考长度" /><DeckFreeboardEditor deck={getDeck(draft)} runs={visibleRuns} onPatchDeck={patchDeck} /><details className="advanced-json"><summary>高级：原始契约字段</summary><p className="section-intro">用于编辑表单未覆盖的字段（如 y_m / z_m）。应用后仍需点击“保存修订”。</p><label className="field-label" htmlFor="chapter-json">章节数据</label><textarea id="chapter-json" className="json-editor" spellCheck={false} value={jsonText} onChange={event => { setJsonEdited(true); setJsonText(event.target.value); }} /><div className="json-actions"><button className="button button--secondary" type="button" onClick={applyJson}>应用到草稿</button>{jsonEdited && <button className="button button--secondary" type="button" onClick={discardJson}>放弃未应用的文本</button>}<span>应用后仍须点击“保存修订”</span></div>{jsonError && <p className="form-error" role="alert">{jsonError}</p>}</details></section>}
        {chapter === 'guns' && <section className="editor-section"><InputGroup index="01" title="炮组声明" note="每个炮组声明输入 · 未知留空" /><p className="section-intro">{chapterOf(chapter).purpose}</p><GunsEditor weapons={getWeapons()} runs={visibleRuns} ledger={ledger} onPatchBattery={patchBattery} /><details className="advanced-json"><summary>高级：原始契约字段</summary><p className="section-intro">表单未覆盖的字段（如 mounts / armour 边界）可在此编辑 systems 原始 JSON。应用后仍需点击“保存修订”。</p><label className="field-label" htmlFor="chapter-json">章节数据</label><textarea id="chapter-json" className="json-editor" spellCheck={false} value={jsonText} onChange={event => { setJsonEdited(true); setJsonText(event.target.value); }} /><div className="json-actions"><button className="button button--secondary" type="button" onClick={applyJson}>应用到草稿</button>{jsonEdited && <button className="button button--secondary" type="button" onClick={discardJson}>放弃未应用的文本</button>}<span>应用后仍须点击“保存修订”</span></div>{jsonError && <p className="form-error" role="alert">{jsonError}</p>}</details></section>}
        {chapter === 'weapons' && <section className="editor-section"><InputGroup index="01" title="鱼雷与水雷分区" note="鱼雷 / 水雷 / 深弹 / 杂项分区 · 未知留空" /><p className="section-intro">{chapterOf(chapter).purpose}</p><WeaponsEditor weapons={getWeapons()} runs={visibleRuns} ledger={ledger} onPatchLeaf={patchWeapons} /><details className="advanced-json"><summary>高级：原始契约字段</summary><p className="section-intro">表单未覆盖的字段（如 torpedo 的 weight_item_ids 绑定）可在此编辑 systems 原始 JSON。应用后仍需点击“保存修订”。</p><label className="field-label" htmlFor="chapter-json">章节数据</label><textarea id="chapter-json" className="json-editor" spellCheck={false} value={jsonText} onChange={event => { setJsonEdited(true); setJsonText(event.target.value); }} /><div className="json-actions"><button className="button button--secondary" type="button" onClick={applyJson}>应用到草稿</button>{jsonEdited && <button className="button button--secondary" type="button" onClick={discardJson}>放弃未应用的文本</button>}<span>应用后仍须点击“保存修订”</span></div>{jsonError && <p className="form-error" role="alert">{jsonError}</p>}</details></section>}
        {chapter === 'armour' && <section className="editor-section"><InputGroup index="01" title="装甲输入与研究" /><ArmourEditor project={draft} run={selectedRun} onChange={updateDraft} /></section>}
        {chapter === 'propulsion' && <section className="editor-section"><InputGroup index="01" title="动力输入与研究" /><EnginesEditor project={draft} run={selectedRun} onChange={updateDraft} /></section>}
        {chapter === 'damage' && <section className="editor-section" id={REQUEST_DAMAGE} tabIndex={-1}><InputGroup index="01" title="场景草稿" note="场景草稿 · 请求与结果" /><DamageEditor project={draft} run={selectedRun} request={floodingRequest} onChange={updateDraft} onRequestChange={setFloodingRequest} requestError={floodingChoice.error} /></section>}
        {chapter === 'damage' && <section className="editor-section"><InputGroup index="02" title="高级场景数据" /><details className="advanced-json"><summary>高级：破损场景 JSON</summary><p className="section-intro">这里编辑表单未覆盖的场景字段（项目舱室几何已在下方表单编辑）。应用后仍需点击“保存修订”。</p><label className="field-label" htmlFor="chapter-json">场景数据</label><textarea id="chapter-json" className="json-editor" spellCheck={false} value={jsonText} onChange={event => { setJsonEdited(true); setJsonText(event.target.value); }} /><div className="json-actions"><button className="button button--secondary" type="button" onClick={applyJson}>应用到草稿</button>{jsonEdited && <button className="button button--secondary" type="button" onClick={discardJson}>放弃未应用的文本</button>}<span>应用后仍须点击“保存修订”</span></div>{jsonError && <p className="form-error" role="alert">{jsonError}</p>}</details></section>}
        {chapter === 'json' && <section className="editor-section"><InputGroup index="01" title="完整项目数据" note="结构化 JSON" /><p className="section-intro">这里可编辑所有符合 plimsoll-project-1 契约的字段。应用后请保存修订；服务端会验证并返回具体字段路径。</p><label className="field-label" htmlFor="chapter-json">项目 JSON</label><textarea id="chapter-json" className="json-editor" spellCheck={false} value={jsonText} onChange={event => { setJsonEdited(true); setJsonText(event.target.value); }} /><div className="json-actions"><button className="button button--secondary" type="button" onClick={applyJson}>应用到草稿</button>{jsonEdited && <button className="button button--secondary" type="button" onClick={discardJson}>放弃未应用的文本</button>}<span>应用后仍须点击“保存修订”</span></div>{jsonError && <p className="form-error" role="alert">{jsonError}</p>}</section>}
      </div>
    </main>
    <TracePanel open={traceOpen} onToggle={() => setTraceOpen(open => !open)} />
  </div>;
  return <UnitProvider preferences={draft.display_preferences}>
    <InputTraceProvider onReveal={() => setTraceOpen(true)}><TraceScope scopeKey={`${projectId}/${chapter}`}>{page}</TraceScope></InputTraceProvider>
  </UnitProvider>;
}
