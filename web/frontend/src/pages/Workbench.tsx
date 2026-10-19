import { useCopyMessage } from '../i18n/useCopyMessage';
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

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
import { ConceptDesignEditor } from '../components/ConceptDesignEditor';
import { DesignBalanceDiagnostics, DesignBalanceResults, ConceptDesignLink } from '../components/DesignBalanceResults';
import { ConceptReviewGuide } from '../components/ConceptReviewGuide';
import { MassProposalPanel } from '../components/MassProposalPanel';
import { conceptEnabled, IDLE_APPLY, resultIdentity, requestOptionsMatch, withDesignBalance, type ApplyState } from '../components/conceptDesign';
import { buildFloodingRequest, EMPTY_FLOODING_REQUEST, type FloodingRequest } from '../components/floodingModel';
import { currentRun, eligibleResultRun, latestOwnedRun, ledgerItems, RESULT_STATUSES } from '../components/formModel';
import { getDeck, type DeckInput } from '../components/deckModel';
import {
  CHAPTER_HEAD, hullGuidanceId, LEDGER_SECTION, ledgerGuidanceId,
  readDiagnosticTail, REQUEST_DAMAGE, REQUEST_PERFORMANCE, resolveDiagnosticPath,
  type DiagnosticLocation,
} from '../components/diagnosticGuidance';
import { declaredSource, InputTraceProvider, TracePanel, useInputTrace, TracedField, type TraceFact } from '../components/InputTrace';
import { chapterJsonKeys, chapterNumber, chapterOf, ProjectNav, type Chapter } from '../components/ProjectNav';
import { QuantityField } from '../components/QuantityField';
import { ReadFailure, ReadPending } from '../components/ReadPending';
import { UnitProvider } from '../components/UnitProvider';
import { useMotionToken } from '../components/useLocalMotion';
import { WorkbenchOverview } from '../components/WorkbenchOverview';
import { useWorkspaceCopy, type WorkspaceKey } from '../i18n/workspace';
import { useConceptCopy } from '../i18n/concept';
import { useShipDesignCopy } from '../i18n/shipDesign';
import {
  ShipDesignChapter, ShipDesignLedgerSection, ShipDesignOverview, useShipDesignHost,
} from '../components/ShipDesignEditor';
import { shipDesignEnabled, shipDesignOf, shipDesignRunOptions } from '../components/sps3b3Model';
import { DesignFeedback } from '../components/DesignFeedback';
import { useSavedDesignPreview } from '../components/useSavedDesignPreview';
import type { DraftSide } from '../components/designFeedbackModel';
import type { ProjectDocument, ProjectView, RunView, ShipDesign } from '../types';

/** The anchor the concept screen keeps for a project that still declares one. */
const CONCEPT_SECTION = 'concept-design';

// Dimensionless coefficients keep a plain number input; lengths speak the
// reader's unit while the project keeps metres. Each entry names the dictionary
// keys for its label and its hint rather than carrying the words itself.
const HULL_FIELDS = [
  { key: 'loa_m', alternate: 'length_m', label: 'field.loa_m', hint: 'field.loa_m.hint', dimension: 'length' },
  { key: 'lwl_m', label: 'field.lwl_m', hint: 'field.lwl_m.hint', dimension: 'length' },
  { key: 'beam_m', label: 'field.beam_m', hint: 'field.beam_m.hint', dimension: 'length' },
  { key: 'draught_normal_m', alternate: 'draft_m', label: 'field.draught_normal_m', hint: 'field.draught_normal_m.hint', dimension: 'length' },
  { key: 'block_coeff', label: 'field.block_coeff', hint: 'field.block_coeff.hint', dimension: null },
  { key: 'waterplane_coeff', label: 'field.waterplane_coeff', hint: 'field.waterplane_coeff.hint', dimension: null },
] as const;

// The chapter that owns a raw-JSON view, and the project section it edits.
// A chapter without a `jsonKey` has no contract fragment of its own.
const CHAPTER_JSON = chapterJsonKeys();

function numeric(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function record(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

/**
 * Which ledger items the native declaration manages, and how.
 *
 * A managed item's mass belongs to the core: an estimated role carries a scoped
 * overlay, and a declared role keeps the reader's own mass but is still bound.
 * Binding every `item_ids` entry of every role — declared included — is what
 * makes the row's mass read-only instead of hand-editable.
 */
function bindingModes(design: ShipDesign | null): Map<string, 'estimated' | 'declared'> {
  const modes = new Map<string, 'estimated' | 'declared'>();
  const bindings = design?.mass_bindings;
  if (!bindings) return modes;
  for (const entry of Object.values(bindings)) {
    const mode: 'estimated' | 'declared' = entry?.mode === 'estimated' ? 'estimated' : 'declared';
    for (const id of entry?.item_ids ?? []) if (typeof id === 'string') modes.set(id, mode);
  }
  return modes;
}

/**
 * The effective selected mass of one managed item for the design's own case.
 *
 * This mirrors the core's own precedence exactly and computes nothing: the
 * scoped estimated overlay first, then any ordinary owner-condition override
 * (whatever its provenance), then the item's base mass. An unbound item is not
 * managed and is never read through this path.
 */
function effectiveMass(item: Record<string, unknown>, mode: 'estimated' | 'declared' | undefined,
  condition: Record<string, unknown> | null, itemId: string): number | null {
  if (mode === 'estimated') {
    const overlay = record(item.design_mass)?.mass_t;
    if (typeof overlay === 'number' && Number.isFinite(overlay)) return overlay;
  }
  const override = record(record(condition?.overrides)?.[itemId])?.mass_t;
  if (typeof override === 'number' && Number.isFinite(override)) return override;
  return numeric(item.mass_t);
}

function errorMessage(w: (key: WorkspaceKey, params?: any) => string, cause: unknown): string {
  if (cause instanceof api.ApiError && Array.isArray(cause.detail)) {
    return cause.detail.map((item: { path?: string; message?: string }) =>
      w('workbench.error.validation', {
        path: item.path ?? w('workbench.error.validationPath'),
        message: item.message ?? w('workbench.error.validationMessage'),
      })).slice(0, 4).join('；');
  }
  // An unknown failure keeps the server's own sentence inside a localized frame,
  // so the reader is never left with an untranslated error and never with an
  // error that has lost its original wording.
  return cause instanceof Error ? cause.message : w('workbench.error.generic');
}

function validationDetails(w: (key: WorkspaceKey, params?: any) => string, cause: unknown): Array<{ path: string; message: string }> {
  if (!(cause instanceof api.ApiError) || !Array.isArray(cause.detail)) return [];
  return cause.detail.map(item => {
    const path = typeof item.path === 'string' ? item.path : Array.isArray(item.loc) ? item.loc.join('.') : w('workbench.error.validationProject');
    return { path, message: String(item.message ?? item.msg ?? w('workbench.error.validationMessage')) };
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
  const w = useWorkspaceCopy();
  const definition = chapterOf(chapter, w);
  if (chapter === 'overview') {
    return <header className="chapter-head chapter-head--vessel" id={CHAPTER_HEAD}>
      <span className="section-kicker">{definition.label.toUpperCase()} / {projectId.slice(0, 8).toUpperCase()}</span>
      <div className="vessel-title-row"><h1>{name}</h1>
        <span className="proxy-label">{proxy ? w('workbench.chapter.proxy') : w('workbench.chapter.input')}</span></div>
      <p>{definition.purpose}</p>
    </header>;
  }
  return <header className="chapter-head" id={CHAPTER_HEAD}>
    <span className="section-kicker">{chapterNumber(chapter)} / {definition.label.toUpperCase()}</span>
    <h1>{definition.label}</h1>
    <p className="chapter-context"><span className="chapter-vessel">{name}</span>
      <span>{w('workbench.save.revision', { revision })}</span>
      <span>{projectId.slice(0, 8).toUpperCase()}</span>
    </p>
    {definition.purpose && <p className="chapter-purpose">{definition.purpose}</p>}
  </header>;
}

/**
 * Why a hand-written project document cannot replace the visible draft.
 *
 * These are refusals about the document the reader typed, so they are owned by
 * this module and read in the reader's language. The path in a message is the
 * document's own field name and stays as written.
 */
function projectRenderError(w: (key: WorkspaceKey, params?: any) => string, value: unknown, projectId: string): string | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return w('editor.json.projectError.root');
  const row = value as Record<string, unknown>;
  if (row.id !== projectId) return w('editor.json.projectError.id');
  if (row.schema !== 'plimsoll-project-1') return w('editor.json.projectError.schema');
  if (typeof row.name !== 'string' || !row.name.trim()) return w('editor.json.projectError.name');
  if (!row.hull || typeof row.hull !== 'object' || Array.isArray(row.hull)) return w('editor.json.projectError.hull');
  if (!Array.isArray(row.loading_conditions) || !row.loading_conditions.every(
    item => item && typeof item === 'object' && typeof item.id === 'string'
      && (item.label === undefined || item.label === null || typeof item.label === 'string'),
  )) return w('editor.json.projectError.conditions');
  if (!Array.isArray(row.weight_groups) || !row.weight_groups.every(
    group => group && typeof group === 'object' && typeof group.id === 'string'
      && (group.label === undefined || group.label === null || typeof group.label === 'string')
      && Array.isArray(group.items) && group.items.every((item: unknown) => item && typeof item === 'object' && !Array.isArray(item)),
  )) return w('editor.json.projectError.groups');
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

const OPERATION_TEXT: Record<Operation, WorkspaceKey> = {
  saving: 'workbench.op.saving', starting: 'workbench.op.starting', reloading: 'workbench.op.reloading',
};

/**
 * The raw contract fields a chapter's form does not cover.
 *
 * Six chapters own one of these, all of them the same panel with a different
 * sentence: the text is the reader's own until they apply it, the apply button
 * is the only thing that writes to the draft, and the saved revision is still
 * required afterwards. One component rather than six copies, so the wording
 * follows the language in all six at once and a change reaches all of them.
 *
 * An empty `summary` renders the panel open, which is what the project-data
 * chapter wants: there the raw document *is* the page.
 */
function ChapterJson({ w, text, onEdit, edited, onApply, onDiscard, error, summary, note, label }: {
  w: (key: WorkspaceKey, params?: any) => string;
  text: string; onEdit: (text: string) => void; edited: boolean;
  onApply: () => void; onDiscard: () => void; error: string;
  summary: string; note: string; label: string;
}) {
  const body = <>
    {note && <p className="section-intro">{note}</p>}
    <label className="field-label" htmlFor="chapter-json">{label}</label>
    <textarea id="chapter-json" className="json-editor" spellCheck={false} value={text} onChange={event => onEdit(event.target.value)} />
    <div className="json-actions">
      <button className="button button--secondary" type="button" onClick={onApply}>{w('editor.json.apply')}</button>
      {edited && <button className="button button--secondary" type="button" onClick={onDiscard}>{w('editor.json.discard')}</button>}
      <span>{w('editor.json.stillSave')}</span>
    </div>
    {error && <p className="form-error" role="alert">{error}</p>}
  </>;
  if (!summary) return <>{body}</>;
  return <details className="advanced-json"><summary>{summary}</summary>{body}</details>;
}

export function Workbench({ projectId, onBack, onRun, onDirtyChange, onLab }: {
  projectId: string; onBack: () => void; onRun: (runId: string) => void; onDirtyChange?: (dirty: boolean) => void; onLab?: () => void;
}) {
  // The one language state, owned by the shell above this route. Reading it here
  // changes words and nothing else: the draft, the selected chapter, the unsaved
  // marker, the scroll position and the trace panel all live in the state below
  // and none of them is touched by a dictionary changing.
  const w = useWorkspaceCopy();
  const c = useConceptCopy();
  const d = useShipDesignCopy();
  const [view, setView] = useState<ProjectView | null>(null);
  const [draft, setDraft] = useState<ProjectDocument | null>(null);
  const [chapter, setChapter] = useState<Chapter>('overview');
  // One shared disclosure for the whole native editor: the changes panel is
  // reachable from every chapter and rendered once, never duplicated per page.
  const [showChanges, setShowChanges] = useState(false);
  const [traceOpen, setTraceOpen] = useState(traceDefaultsOpen);
  const [conditionId, setConditionId] = useState('');
  const [dirty, setDirty] = useState(false);
  const [operation, setOperation] = useState<Operation | null>(null);
  const [error, setError] = useCopyMessage();
  const [loadError, setLoadError] = useCopyMessage();
  const [load, setLoad] = useState<'loading' | 'failed'>('loading');
  const [attempt, setAttempt] = useState(0);
  const [conflict, setConflict] = useState<number | null>(null);
  const [jsonText, setJsonText] = useState('');
  const [jsonError, setJsonError] = useCopyMessage();
  // A hand-edited document that has not been applied yet. A jump that would
  // leave this chapter discards it, so the jump is refused instead.
  const [jsonEdited, setJsonEdited] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Array<{ path: string; message: string }>>([]);
  const [inspected, setInspected] = useState<{ label: string; source: string; estimate: boolean } | null>(null);
  const [runs, setRuns] = useState<RunView[]>([]);
  const runsScope = useRef(projectId);
  const [runsState, setRunsState] = useState<'loading' | 'ready' | 'failed'>('loading');
  const [runsError, setRunsError] = useCopyMessage();
  const [runsAttempt, setRunsAttempt] = useState(0);
  const [resultState, setResultState] = useState<'loading' | 'ready' | 'failed'>('ready');
  const [resultError, setResultError] = useCopyMessage();
  const [previousState, setPreviousState] = useState<'loading' | 'ready' | 'failed'>('ready');
  const [previousError, setPreviousError] = useCopyMessage();
  const [resultAttempt, setResultAttempt] = useState(0);
  const [runResult, setRunResult] = useState<RunView | null>(null);
  const [pendingRunId, setPendingRunId] = useState<string | null>(null);
  const [performanceRequest, setPerformanceRequest] = useState<RequestDraft>(EMPTY_REQUEST);
  const [floodingRequest, setFloodingRequest] = useState<FloodingRequest>(EMPTY_FLOODING_REQUEST);
  // The optional additional physical checks belong to this request and nothing
  // else: they add existing analysis stages on top of the native design stage,
  // and they are not a data mode or a second product mode.
  const [physicalChecks, setPhysicalChecks] = useState(false);
  // The native host's own outstanding edits. They are counted by the host and
  // block a save or a run until every confirmed reply has settled.
  const [hostPending, setHostPending] = useState(0);
  const hostPendingRef = useRef(0);
  const hostBusyRef = useRef(false);

  // The unified declaration. A project that declares the native design is edited
  // through the native host; a project that still declares only the old
  // compatibility section becomes a pending-save native draft once, and a plain
  // physical project simply offers to start one. The old physical request and
  // its results are preserved for a project that keeps them.
  const native = shipDesignEnabled(draft);
  const conceptOn = !native && conceptEnabled(draft);
  const physicalRequest = !native || physicalChecks;

  // The flooding request joins the existing performance request only when a
  // saved scenario is chosen; otherwise the stage stays unrequested exactly as
  // before. Both requests use the same project revision and condition.
  const performanceOptions = buildOptions(performanceRequest, w);
  const floodingChoice = buildFloodingRequest(draft ?? {}, floodingRequest, w);
  // An explicit environment density belongs to the whole request: the flooding
  // stage is required to use the same equilibrium options as every other stage.
  const equilibrium = { ...(performanceOptions.options.equilibrium as Record<string, unknown> | undefined) };
  // An invalid request carries no assembled stage list at all, and the flooding
  // choice must never spread one. The panel therefore names the stages this
  // request *explicitly* selects — the existing shared base stages plus the
  // studies the reader picked — rather than reporting none.
  const assembledStages = Array.isArray(performanceOptions.options.stages) ? (performanceOptions.options.stages as string[]) : [];
  // The concept screen is requested only while the section exists and only for a
  // project that still declares one. A native design never asks for a second
  // adoption authority, so its balance is never requested either.
  const performanceWithConcept = conceptOn
    ? { ...performanceOptions.options, stages: withDesignBalance(assembledStages, draft) }
    : performanceOptions.options;
  const runOptions = !physicalRequest
    ? shipDesignRunOptions()
    : floodingChoice.flooding
      ? {
        ...performanceWithConcept,
        ...(floodingChoice.rho === null ? {} : { equilibrium: { ...equilibrium, rho_t_m3: floodingChoice.rho } }),
        stages: [...(native ? ['ship_design'] : []), ...assembledStages, ...(conceptOn ? ['design_balance'] : []), 'flooding'],
        flooding: floodingChoice.flooding,
      }
      : native
        ? { ...performanceWithConcept, stages: ['ship_design', ...assembledStages] }
        : performanceWithConcept;
  // The native-only request never carries a request error: it has no fields to
  // assemble. The physical request builder owns its own refusal.
  const runError = physicalRequest ? (performanceOptions.error || floodingChoice.error) : '';
  /** The stages this request will actually submit, read from the request itself. */
  const requestStages = !physicalRequest ? ['ship_design']
    : runError
      ? [...(native ? ['ship_design'] : []), ...BASE_STAGES, ...requestedExtraStages(performanceRequest), ...(conceptOn ? ['design_balance'] : []), ...(floodingRequest.scenario.trim() ? ['flooding'] : [])]
      : Array.isArray(runOptions.stages) ? (runOptions.stages as string[]) : [];
  /** The field a followed diagnostic is waiting to focus, and its own ticket. */
  const [focusRequest, setFocusRequest] = useState<{ target: string; seq: number } | null>(null);
  const [guidanceNotice, setGuidanceNotice] = useCopyMessage();
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
  /**
   * The reviewed-batch apply, guarded at every asynchronous boundary.
   *
   * `applyTicket` retires a whole apply chain the moment a newer one starts or
   * the page goes away; `applyInFlight` is what makes a double click physically
   * unable to produce two revisions, because the second click finds an apply
   * already in progress and returns without issuing a request.
   *
   * `revisionRef`, `conditionRef`, `optionsRef` and `draftGeneration` are the
   * rest of the guard. An answer that arrives after the reader moved to another
   * project, another revision, another condition, another request, or after they
   * typed into the draft or into the raw JSON, is an answer to a question this
   * page is no longer asking, and it is dropped at each await rather than
   * written into whatever is on screen now.
   */
  const [applyState, setApplyState] = useState<ApplyState>(IDLE_APPLY);
  const applyOwner = useRef(projectId);
  const applyTicket = useRef(0);
  const applyInFlight = useRef(false);
  const revisionRef = useRef(view?.revision ?? -1);
  revisionRef.current = view?.revision ?? -1;
  const optionsKey = JSON.stringify(runOptions ?? {});
  const optionsRef = useRef(optionsKey);
  optionsRef.current = optionsKey;
  const projectIdRef = useRef(projectId);
  const contextGeneration = useRef(0);
  if (projectIdRef.current !== projectId) contextGeneration.current += 1;
  projectIdRef.current = projectId;
  const busy = operation !== null || applyState.phase === 'applying' || applyState.phase === 'queueing';
  // The chapter reveal is a local one-shot keyed on the chapter itself. The
  // container is never re-keyed, so a hand-edited JSON document, the focused
  // control and the reader's selection all survive the switch untouched.
  const chapterMotion = useMotionToken(chapter);

  /**
   * The one native host, called once and persistent across chapters.
   *
   * It is created before any early return so a chapter switch never remounts the
   * queue: the host owns the serial/optimistic edit queue, the catalogue and the
   * single legacy upgrade, and a confirmed reply is applied to the draft through
   * `updateDraft` exactly like any other edit. Its outstanding-edits count is
   * what blocks a save or a run.
   */
  const host = useShipDesignHost({
    project: draft,
    onChange: updateDraft,
    disabled: busy,
    onPendingChange: count => { hostPendingRef.current = count; setHostPending(count); },
  });
  hostBusyRef.current = host.busy;
  const hostBlocked = hostPending > 0 || host.busy;

  /**
   * The saved revision's own preview, read once per saved identity.
   *
   * The host previews the draft; this answers the other half of the comparison
   * question — what the reader actually saved — without sending a command. It is
   * keyed to the saved project and revision, so a save reads the new revision
   * once and a project switch discards the old answer.
   */
  const saved = useSavedDesignPreview(view);
  const savedSide = useMemo<DraftSide>(() => ({
    result: saved.result, project: view?.project ?? null, state: saved.state,
  }), [saved.result, saved.state, view]);
  // A pending edit or an in-flight preview is not the draft: the readings are
  // withheld until the queue settles, while the declared inputs below stay.
  const draftSide = useMemo<DraftSide>(() => ({
    result: host.nativePreview, project: draft,
    state: host.state.error ? 'failed' : (hostPending > 0 || host.state.busy) ? 'pending' : 'ready',
  }), [host.nativePreview, host.state.error, host.state.busy, hostPending, draft]);

  useEffect(() => {
    let active = true;
    const mine = ++loadTicket.current;
    writeTicket.current += 1;
    applyTicket.current += 1;
    applyInFlight.current = false;
    setOperation(null);
    setPhysicalChecks(false);
    setHostPending(0); hostPendingRef.current = 0;
    setApplyState(IDLE_APPLY);
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
      setLoadError(w => errorMessage(w, cause));
      setLoad('failed');
    });
    return () => { active = false; };
  }, [projectId, attempt]);

  // The leave guard is told about edits, not about renders: one call when the
  // workspace stops matching what the reader can recover — an edited draft, or
  // hand-written JSON that has not been applied yet and would be lost by leaving.
  useEffect(() => { onDirtyChange?.(dirty || jsonEdited || hostPending > 0); }, [dirty, jsonEdited, hostPending, onDirtyChange]);

  useEffect(() => {
    let active = true;
    setRunsState('loading'); setRunsError('');
    if (runsScope.current !== projectId) { runsScope.current = projectId; setRuns([]); }
    api.listRuns(projectId).then(items => { if (active) { setRuns(items); setRunsState('ready'); } }).catch(cause => {
      if (active) { setRunsState('failed'); setRunsError(w => errorMessage(w, cause)); }
    });
    return () => { active = false; };
  }, [projectId, runsAttempt]);

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
    setResultError(''); setResultState(candidate && !candidate.result ? 'loading' : 'ready');
    // A run list entry may already carry its payload; use it directly and make
    // no request. Only a payload-less entry needs the single bounded retrieval.
    setPendingRunId(candidate && !candidate.result ? candidate.id : null);
    if (!candidate) { setRunResult(null); return; }
    if (candidate.result) { setRunResult(matchesRun(candidate, projectId, revision, conditionId) ? candidate : null); return; }
    let active = true;
    api.getRun(candidate.id).then(full => {
      if (!active) return;
      setResultState('ready');
      setRunResult(full.id === candidate.id && matchesRun(full, projectId, revision, conditionId) ? full : null);
    }).catch(cause => { if (active) { setResultState('failed'); setResultError(w => errorMessage(w, cause)); } });
    return () => { active = false; };
  }, [runs, view?.revision, conditionId, projectId, resultAttempt]);

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
    setPreviousError(''); setPreviousState('ready');
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
    setPreviousState('loading');
    api.getRun(mine.id).then(full => {
      if (!active) return;
      setPreviousState('ready');
      setHistoryRun(matchesSavedCheck(full, mine, projectId, view?.revision ?? -1, conditionId) ? full : null);
    }).catch(cause => { if (active) { setPreviousState('failed'); setPreviousError(w => errorMessage(w, cause)); } });
    return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [historyKey, projectId, conditionId, view?.revision, currentResultId, resultAttempt]);

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
    const target = resolveDiagnosticPath(location.path, { snapshot, live: draftRef.current }, w) ?? location;
    if (!target.chapter || !target.target) {
      setGuidanceNotice(w => w('workbench.guidance.unlocatable', { path: target.path, note: target.note }));
      return false;
    }
    if (target.chapter !== chapterRef.current && jsonEditedRef.current) {
      // Refused, not consumed: the same jump is retried once the reader has
      // applied or discarded that edit.
      handledArrival.current = null;
      setGuidanceNotice(w => w('workbench.guidance.jsonUnapplied'));
      return false;
    }
    setChapter(target.chapter);
    setFocusRequest({ target: target.target, seq: ++focusTicket.current });
    setGuidanceNotice(w => resolveDiagnosticPath(location.path, { snapshot, live: draftRef.current }, w)?.note ?? location.note);
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
      const tail = readDiagnosticTail(window.location.hash, projectId, w);
      const key = tail.kind === 'target' ? `${tail.runId}|${tail.path}`
        : tail.kind === 'malformed' ? `malformed|${window.location.hash}` : null;
      // Whatever the destination, the previous answer is now retired.
      const mine = ++arrivalTicket.current;
      focusTicket.current += 1;
      setFocusRequest(null);
      handledArrival.current = key;
      if (tail.kind === 'none') return;
      if (tail.kind === 'malformed') { const hash = window.location.hash; setGuidanceNotice(w => { const value = readDiagnosticTail(hash, projectId, w); return value.kind === 'malformed' ? value.reason : ''; }); return; }
      const { runId, path } = tail;
      setGuidanceNotice('');
      api.getRun(runId).then(source => {
        if (!alive.current || arrivalTicket.current !== mine) return;
        // The answer must still belong to the address the reader is standing on.
        const still = readDiagnosticTail(window.location.hash, projectId, w);
        if (still.kind !== 'target' || still.runId !== runId || still.path !== path) return;
        if (source.id !== runId) {
          setGuidanceNotice(w => w('workbench.guidance.runMismatch', { actual: source.id, expected: runId }));
          return;
        }
        if (source.project_id !== projectId) {
          setGuidanceNotice(w => w('workbench.guidance.foreignRun', { id: runId }));
          return;
        }
        if (!source.result) {
          setGuidanceNotice(w => w('workbench.guidance.noResult', { id: runId }));
          return;
        }
        // The stored result has to be the same run's own result, or the
        // identity behind the link is not one we can trust.
        const result = source.result;
        const consistent = result.project_id === source.project_id
          && result.condition_id === source.condition_id
          && result.request_fingerprint === source.request_fingerprint;
        if (!consistent) {
          setGuidanceNotice(w => w('workbench.guidance.inconsistent', { id: runId }));
          return;
        }
        // An existing condition may be selected so the reader lands on the
        // inputs the run actually used. A condition that has since been removed
        // is never resurrected, and nothing is followed on its behalf.
        const conditions = draftRef.current?.loading_conditions ?? [];
        if (!conditions.some(item => item.id === source.condition_id)) {
          setGuidanceNotice(w => w('workbench.guidance.conditionGone', { id: runId, condition: source.condition_id }));
          return;
        }
        const snapshot = result.input_snapshot ?? null;
        const location = resolveDiagnosticPath(path, { snapshot, live: draftRef.current }, w);
        if (!location || location.kind === 'evidence') {
          setGuidanceNotice(w => w('workbench.guidance.unlocatable', { path, note: location?.note ?? w('workbench.guidance.unresolvable') }));
          return;
        }
        const notice = source.revision !== view?.revision
          ? w('workbench.guidance.staleRevision', { source: source.revision, current: String(view?.revision ?? '') })
          : '';
        if (source.condition_id !== conditionRef.current) setConditionId(source.condition_id);
        if (!jumpTo(location, snapshot)) return;
        // Stated after the jump, so the reader sees it next to where they landed.
        if (notice) setGuidanceNotice(w => `${w('workbench.guidance.staleRevision', { source: source.revision, current: String(view?.revision ?? '') })} ${resolveDiagnosticPath(path, { snapshot, live: draftRef.current }, w)?.note ?? ''}`);
      }).catch(() => {
        if (alive.current && arrivalTicket.current === mine) setGuidanceNotice(w => w('workbench.guidance.unreadableRun', { id: runId }));
      });
    };
    // A re-render only acts when the address is one this page has not used.
    const reconcile = () => {
      const tail = readDiagnosticTail(window.location.hash, projectId, w);
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
    draftGeneration.current += 1;
    setJsonText(jsonSource());
    setJsonError('');
    setJsonEdited(false);
  }

  function editJson(text: string) {
    draftGeneration.current += 1;
    jsonEditedRef.current = true;
    setJsonEdited(true); setJsonText(text);
  }

  /**
   * A chapter change never discards unapplied JSON silently. The reader is told
   * what the chapter offers to keep it, and nothing is applied on their behalf.
   */
  function goChapter(next: Chapter) {
    if (next === chapterRef.current) return;
    if (jsonEditedRef.current) {
      handledArrival.current = null;
      setGuidanceNotice(w => w('workbench.guidance.leaveUnapplied'));
      return;
    }
    setChapter(next);
  }

  /**
   * The entry links from the chapters a concept design touches.
   *
   * A project that still declares the old concept section keeps its way in from
   * guns, machinery and performance. The jump is a view change and nothing else:
   * no input is written, nothing is saved and the Workbench is never remounted.
   */
  function openConceptDesign() {
    if (chapterRef.current !== 'weights') goChapter('weights');
    focusTicket.current += 1;
    setFocusRequest({ target: CONCEPT_SECTION, seq: focusTicket.current });
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

  function updateMass(groupIndex: number, itemIndex: number, key: string, value: string | number | null) {
    if (!draft) return;
    const next = structuredClone(draft);
    next.weight_groups[groupIndex].items[itemIndex][key] = key === 'source' ? value : value === null || value === '' ? null : Number(value);
    updateDraft(next);
  }

  function updateHull(key: string, value: string | number | null) {
    if (!draft) return;
    const next = structuredClone(draft);
    next.hull[key] = value === null || value === '' ? null : Number(value);
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
      if (!navigator.clipboard) throw new Error(w('workbench.error.copyUnsupported'));
      await navigator.clipboard.writeText(JSON.stringify(draft, null, 2));
      if (current() && writeTicket.current === ticket) outcome('resolve');
    } catch (cause) {
      if (current() && writeTicket.current === ticket) { setError(w => errorMessage(w, cause)); outcome('hold'); }
    }
  }

  async function save() {
    if (!view || view.project_id !== projectId || !draft || !dirty || operation || applyInFlight.current
      || hostPendingRef.current > 0 || hostBusyRef.current) return;
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
        setError(w => errorMessage(w, cause));
        setFieldErrors(validationDetails(w, cause));
      }
    } finally { if (mine()) setOperation(null); }
  }

  async function reload() {
    if (hostPendingRef.current > 0 || hostBusyRef.current) return;
    if (operation || applyInFlight.current) return;
    if (jsonEditedRef.current) { setError(w => w('workbench.reload.unapplied')); return; }
    const submittedGeneration = draftGeneration.current;
    const ticket = ++writeTicket.current;
    const mine = () => current() && writeTicket.current === ticket;
    setOperation('reloading');
    setError('');
    try {
      const saved = await api.getProject(projectId);
      if (!mine()) return;
      if (draftGeneration.current !== submittedGeneration || jsonEditedRef.current) {
        setError(w => w('workbench.reload.newEdits')); return;
      }
      setView(saved);
      setDraft(structuredClone(saved.project));
      setPerformanceRequest(EMPTY_REQUEST);
      setFloodingRequest(EMPTY_FLOODING_REQUEST);
      setPhysicalChecks(false);
      setDirty(false);
      setConflict(null);
      setError('');
      outcome('detent');
    } catch (cause) { if (mine()) { setError(w => errorMessage(w, cause)); outcome('hold'); } }
    finally { if (mine()) setOperation(null); }
  }

  async function run() {
    if (!view || !conditionId || dirty || jsonEditedRef.current || runError || operation || applyInFlight.current
      || hostPendingRef.current > 0 || hostBusyRef.current) return;
    if (view.project_id !== projectId) return;
    const ticket = ++writeTicket.current;
    const mine = () => current() && writeTicket.current === ticket;
    const scope = { projectId, revision: view.revision, conditionId, options: optionsRef.current,
      context: contextGeneration.current, generation: draftGeneration.current };
    const unchanged = () => projectIdRef.current === scope.projectId
      && revisionRef.current === scope.revision && conditionRef.current === scope.conditionId
      && optionsRef.current === scope.options && contextGeneration.current === scope.context
      && draftGeneration.current === scope.generation && !jsonEditedRef.current;
    setOperation('starting');
    setError('');
    try {
      const queued = await api.enqueueRun(projectId, { revision: view.revision, condition_id: conditionId, options: runOptions });
      // The queue entry stands even if the reader has moved on; only the page
      // that still shows its submitted context follows the delayed answer.
      if (!mine() || !unchanged()) return;
      expectRunResult(queued.id);
      onRun(queued.id);
    } catch (cause) { if (mine() && unchanged()) { setError(w => errorMessage(w, cause)); outcome('hold'); } }
    finally { if (mine()) setOperation(null); }
  }

  /**
   * Apply a reviewed batch and recompute it, as one guarded operation.
   *
   * Three things are deliberately separate. The *save* is the change: once the
   * server has written the new revision it is real, and nothing afterwards —
   * including a failed re-run — is described as undoing it. The *recompute* is a
   * convenience that re-queues the very same options against the new revision;
   * if it fails the reader is told the save stands and offered the run again.
   * And the *navigation* to the new run only happens while this page is still
   * the page that asked, so a late enqueue cannot drag the reader onto a
   * calculation for a project, revision, condition or request they have left.
   */
  async function applyProposals(proposals: Array<Record<string, unknown>>) {
    // One apply at a time. A second click returns without issuing anything.
    if (applyInFlight.current) return;
    const source = selectedRun;
    if (!view || view.project_id !== projectId || !source || !conditionId || dirty || jsonEditedRef.current || proposals.length === 0 || operation || runError) return;
    if (source.revision !== view.revision || source.condition_id !== conditionId) return;
    if (!requestOptionsMatch(source, runOptions)) return;
    applyInFlight.current = true;
    applyOwner.current = projectId;
    const ticket = ++applyTicket.current;
    const baseline = {
      projectId, revision: view.revision, conditionId,
      optionsKey: optionsRef.current, generation: draftGeneration.current, context: contextGeneration.current,
    };
    const matches = () => alive.current && applyTicket.current === ticket
      && projectIdRef.current === baseline.projectId
      && revisionRef.current === baseline.revision
      && conditionRef.current === baseline.conditionId
      && optionsRef.current === baseline.optionsKey
      && draftGeneration.current === baseline.generation
      && contextGeneration.current === baseline.context
      && !jsonEditedRef.current;
    setApplyState({ phase: 'applying', revision: null, reason: null });
    try {
      let saved: Awaited<ReturnType<typeof api.applyMassProposals>>;
      try {
        saved = await api.applyMassProposals(projectId, {
          base_revision: baseline.revision, run_id: source.id, condition_id: baseline.conditionId,
          current_options: runOptions as Record<string, unknown>, proposals,
        });
      } catch (cause) {
        if (!matches()) return;
        if (cause instanceof api.ApiError && cause.status === 409) {
          const detail = cause.detail as { current_revision?: number };
          setApplyState({ phase: 'conflict', revision: detail.current_revision ?? null, reason: null });
        } else {
          setApplyState({ phase: 'failed', revision: null, reason: errorMessage(w, cause) });
        }
        return;
      }
      if (!matches()) {
        // The save happened, but this page is no longer the page that asked for
        // it. The newer draft is the reader's and is left alone; the known
        // revision is raised so the ordinary conflict notice offers a reload
        // instead of pretending the page and the server still agree.
        if (alive.current && projectIdRef.current === baseline.projectId && applyTicket.current === ticket) {
          setConflict(saved.revision);
        }
        return;
      }
      setView(saved);
      revisionRef.current = saved.revision;
      setDraft(structuredClone(saved.project));
      setDirty(false);
      setConflict(null);
      setFieldErrors([]);
      setRunsAttempt(value => value + 1);
      outcome('resolve');
      // Re-baseline: the revision this page is now looking at is the saved one,
      // and the request it will re-queue is the same one it just applied.
      const next = { ...baseline, revision: saved.revision, generation: draftGeneration.current };
      const stillCurrent = () => alive.current && applyTicket.current === ticket
        && projectIdRef.current === next.projectId
        && revisionRef.current === next.revision
        && conditionRef.current === next.conditionId
        && optionsRef.current === next.optionsKey
        && draftGeneration.current === next.generation
        && contextGeneration.current === next.context
        && !jsonEditedRef.current;
      setApplyState({ phase: 'queueing', revision: saved.revision, reason: null });
      try {
        const queued = await api.enqueueRun(projectId, {
          revision: saved.revision, condition_id: baseline.conditionId,
          options: runOptions as Record<string, unknown>,
        });
        if (!stillCurrent()) return;
        setApplyState({ phase: 'saved', revision: saved.revision, reason: null });
        expectRunResult(queued.id);
        onRun(queued.id);
      } catch (cause) {
        if (!stillCurrent()) return;
        // The batch is saved. Only the recompute failed, and it is reported as
        // exactly that, with the run offered again.
        setApplyState({ phase: 'queueFailed', revision: saved.revision, reason: errorMessage(w, cause) });
      }
    } finally {
      // Released whatever happened, so a failed apply cannot leave the panel
      // permanently disabled. A newer apply owns the flag by then and is not
      // released by this one.
      if (applyTicket.current === ticket) {
        applyInFlight.current = false;
        if (alive.current) setApplyState(previous => previous.phase === 'applying' || previous.phase === 'queueing' ? IDLE_APPLY : previous);
      }
    }
  }

  /** Run the saved revision again with the options now on screen. */
  function rerunAfterApply() {
    if (!view || !conditionId || dirty || jsonEditedRef.current) return;
    if (applyInFlight.current) return;
    void run();
  }

  function applyJson() {
    if (!draft) return;
    try {
      const parsed: unknown = JSON.parse(jsonText);
      if (chapter === 'json') {
        const problem = projectRenderError(w, parsed, projectId);
        if (problem) { setJsonError(w => projectRenderError(w, parsed, projectId) ?? ''); outcome('hold'); return; }
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
    } catch (cause) { setJsonError(w => cause instanceof Error ? cause.message : w('workbench.error.json')); outcome('hold'); }
  }

  // A project that never loaded is its own content: the reason, one explicit
  // retry, and the real way back to the library. There is no skeleton behind it.
  if (!draft || !view || view.project_id !== projectId) return <div className="page-pad"><p className="section-kicker">WORKSPACE / {w(load === 'failed' ? 'workbench.load.kickerFailed' : 'workbench.load.kickerLoading')}</p>
  {load === 'failed'
    ? <ReadFailure title={w('workbench.load.failed', { id: projectId })} detail={loadError} onRetry={() => setAttempt(current => current + 1)} onBack={onBack} backLabel={w('workbench.load.back')} />
    : <ReadPending scope="workbench" object={w('workbench.load.pending')} />}</div>;

  // Validate identity here, in render, rather than relying on the effect having
  // run: a stale or in-flight result must never be displayed for the current
  // revision/condition.
  const selectedRun = currentRun(runResult, projectId, view.revision, conditionId, dirty || jsonEdited);
  // The reviewed proposals belong to exactly this saved result; a different
  // revision, condition or run retires the reader's selection along with it.
  const proposalIdentity = resultIdentity(selectedRun, projectId, view.revision, conditionId);
  const proposalRequestCurrent = !runError && requestOptionsMatch(selectedRun, runOptions);
  // History and result are two different things from two different runs: the
  // guarded result above is what the saved revision may present, and the owned
  // previous check below is what the reader still needs after a save.
  const latestCheck = runResult?.id === historyCandidate?.id ? runResult : historyRun;
  const historyOfSelected = matchesSavedCheck(latestCheck, historyCandidate, projectId, view.revision, conditionId)
    ? latestCheck : null;
  const visibleRuns = selectedRun ? [selectedRun] : [];
  // The authoritative native declaration, its owner condition and the items it
  // manages. A managed row shows the core's own case value and can never be
  // typed over; every other item is the reader's own.
  const nativeDesign = shipDesignOf(draft);
  const ownerCondition = nativeDesign?.condition_id
    ? draft.loading_conditions.find(item => item.id === nativeDesign.condition_id) as Record<string, unknown> | undefined ?? null
    : null;
  const boundModes = bindingModes(nativeDesign);
  const hull = draft.hull ?? {};
  const hullSources = (hull.sources && typeof hull.sources === 'object' ? hull.sources : {}) as Record<string, unknown>;
  const ledger = ledgerItems(draft);
  // The reader's own raw ledger rows: one row per item, showing its longitudinal
  // position and its declared source. For a native design these sit underneath
  // the core's managed ledger, folded away; a plain physical project shows them
  // directly, because they are the only ledger it has.
  const ledgerRows = draft.weight_groups.length === 0
    ? <div className="empty-state compact"><h3>{w('editor.ledger.empty.title')}</h3><p>{w('editor.ledger.empty.text')}</p></div>
    : draft.weight_groups.map((group, groupIndex) => <div className="weight-group" key={group.id}><div className="weight-group-title"><h3>{group.label || group.id}</h3><span>{w('editor.ledger.items', { count: group.items.length })}</span></div><div className="weight-list">{group.items.map((item, itemIndex) => {
      // An entry with no id of its own still needs a name on screen; the
      // fallback is positional furniture, not a stored label.
      const itemId = String(item.id ?? w('editor.ledger.itemFallback', { index: itemIndex + 1 }));
      const source = declaredSource(item.source);
      const estimate = item.estimate === true ? true : item.estimate === false ? false : null;
      // A managed item's mass is the core's own: it is read for the design's
      // own condition and shown, never edited through this old row field.
      // Declared bindings are managed too, so they are matched by item id.
      const boundMode = typeof item.id === 'string' ? boundModes.get(item.id) : undefined;
      const managed = boundMode !== undefined;
      const managedValue = managed ? effectiveMass(item, boundMode, ownerCondition, itemId) : numeric(item.mass_t);
      // Mass and longitudinal position are two facts of one ledger item, and
      // each shows the item's own declared source rather than a shared note.
      const massFact: TraceFact = { key: `ledger.${group.id}.${itemId}.mass_t`, label: w('editor.ledger.massLabel', { item: itemId }), value: managedValue, dimension: 'mass', storedUnit: 't', source, estimate, path: `weight_groups[${groupIndex}].items[${itemId}].mass_t` };
      const positionFact: TraceFact = { ...massFact, key: `ledger.${group.id}.${itemId}.x_m`, label: w('editor.ledger.positionLabel', { item: itemId }), value: numeric(item.x_m), dimension: 'length', storedUnit: 'm', path: `weight_groups[${groupIndex}].items[${itemId}].x_m` };
      // A followed diagnostic addresses one ledger row by the ids the
      // source run saw, so only a row with a real id can be reached.
      const keyed = typeof item.id === 'string' && item.id !== '';
      const rowId = (field: string) => keyed ? ledgerGuidanceId(String(group.id), itemId, field) : undefined;
      return <div className="weight-row" key={String(item.id ?? itemIndex)}><strong>{itemId}</strong>
        <TracedField fact={massFact} id={rowId('mass_t')}>{managed
          // A managed mass is the core's: it is shown read-only for the
          // design's own condition and can never be typed over here.
          ? <QuantityField small readOnly label={w('editor.ledger.mass')} ariaLabel={w('editor.ledger.massLabel', { item: `${group.id} ${itemId}` })} value={managedValue} dimension="mass" kind="nonnegative" onChange={() => {}} />
          : <QuantityField small label={w('editor.ledger.mass')} ariaLabel={w('editor.ledger.massLabel', { item: `${group.id} ${itemId}` })} value={numeric(item.mass_t)} dimension="mass" kind="nonnegative" onChange={next => updateMass(groupIndex, itemIndex, 'mass_t', next)} />}</TracedField>
        <TracedField fact={positionFact} id={rowId('x_m')}><QuantityField small label={w('editor.ledger.position')} ariaLabel={w('editor.ledger.positionLabel', { item: `${group.id} ${itemId}` })} value={numeric(item.x_m)} dimension="length" onChange={next => updateMass(groupIndex, itemIndex, 'x_m', next)} /></TracedField>
        <TracedField fact={{ ...massFact, key: `ledger.${group.id}.${itemId}.source`, label: w('editor.ledger.sourceLabel', { item: itemId }), value: source, dimension: undefined, storedUnit: undefined, path: `weight_groups[${groupIndex}].items[${itemId}].source` }} id={rowId('source')}>
          <label>{w('editor.ledger.source')}<input value={source ?? ''} onChange={event => updateMass(groupIndex, itemIndex, 'source', event.target.value)} /></label>
        </TracedField></div>;
    })}</div></div>);
  // The saved native stage of the selected run is no longer rendered here: the
  // live overview states its own facts from the settled preview above.
  // Display units follow the edited draft. They change presentation only: the
  // saved revision, the request and every export stay canonical.
  const page = <div className="workbench-layout" data-trace={traceOpen ? 'open' : 'closed'}>
    <ProjectNav name={draft.name} active={chapter} onSelect={goChapter} onBack={onBack} />
    <main className="workbench-main">
      <div className="workbench-toolbar">
        <div className="operation-bar">
          <div className="operation-identity">
            <label htmlFor="condition">{w('workbench.condition.label')}</label>
            <select id="condition" value={conditionId} onChange={event => {
              contextGeneration.current += 1; conditionRef.current = event.target.value; setConditionId(event.target.value);
            }}>
              {draft.loading_conditions.length === 0 ? <option value="">{w('workbench.condition.none')}</option>
                : draft.loading_conditions.map(item => <option key={item.id} value={item.id}>{item.label || item.id}</option>)}
            </select>
            {/* The saved revision stays visible while the draft is edited: an
                unsaved edits do not change the saved revision number. */}
            <span className="save-state">
              <span className={`save-dot ${dirty || jsonEdited ? 'save-dot--dirty' : ''}`} aria-hidden="true" />
              <span>{jsonEdited ? w('workbench.save.unapplied') : dirty ? w('workbench.save.dirty') : w('workbench.save.saved')}</span>
              <span className="save-revision">{w('workbench.save.revision', { revision: view.revision })}</span>
            </span>
            {/* One live line for the operation actually in flight, so the bar
                answers "what is it doing" without being read off the buttons. */}
            {operation && <span className="operation-live" role="status">{w(OPERATION_TEXT[operation])}</span>}
          </div>
          <div className="toolbar-actions">
            {/* One compact entry to the comparison, on every native chapter: the
                panel itself is rendered once below this bar, never per page. */}
            {native && <button type="button" className="button button--secondary" aria-expanded={showChanges} aria-controls="design-changes"
              onClick={() => setShowChanges(value => !value)}>
              {showChanges ? w('workbench.changes.hide') : w('workbench.changes.show')}
            </button>}
            {/* Each control names the operation it is actually waiting on. A save
                in progress keeps the run control reading as a run, because it is
                not one. A pending native edit blocks both, because a save or a
                run submitted before it settles would carry a stale draft. */}
            <button className="button button--secondary" onClick={save} disabled={!dirty || busy || hostBlocked}>{operation === 'saving' ? w('workbench.save.busy') : w('workbench.save.action')}</button>
            <button className="button button--primary" onClick={run} disabled={dirty || jsonEdited || !conditionId || busy || hostBlocked || !!runError}
              title={jsonEdited ? w('workbench.reload.unapplied') : dirty ? w('workbench.run.blockedDirty') : runError || undefined}>{operation === 'starting' ? w('workbench.run.busy') : w('workbench.run.action')}</button>
            <details className="secondary-actions">
              <summary aria-label={w('workbench.more.label')}>{w('workbench.more.summary')}</summary>
              <div className="secondary-actions-panel">
                {onLab && <button className="button button--secondary" onClick={onLab} disabled={dirty || jsonEdited || busy}
                  title={dirty ? w('workbench.more.labBlocked') : w('workbench.more.labTitle')}>{w('workbench.more.lab')}</button>}
                <button className="button button--secondary" onClick={downloadProject}
                  title={dirty ? w('workbench.more.downloadDraft') : w('workbench.more.downloadSaved', { revision: view.revision })}>
                  {w('workbench.more.download')}
                </button>
                <p>{w('workbench.more.downloadNote')}</p>
              </div>
            </details>
          </div>
        </div>
        {/* Every blocking failure sits here, directly under the operation bar and
            above the chapter heading: request errors included, never folded away. */}
        <div className="workbench-alerts">
          {/* The native queue's state is global, not chapter-local: an edit being
              confirmed blocks save and run from anywhere, and a failure stays
              visible after the reader moves to another chapter. */}
          {native && hostPending > 0 && <p className="sps-pending" role="status">{d('shipDesign.pending', { count: hostPending })}</p>}
          {native && host.state.error && <div className="notice notice--error" role="alert">
            <span>{d('shipDesign.failed', { message: host.state.error })}</span>
            <button type="button" className="button button--secondary" disabled={host.busy} onClick={host.retry}>{d('shipDesign.retry')}</button>
          </div>}
          {native && host.error && <div className="notice notice--error" role="alert">{d('shipDesign.failed', { message: host.error })}</div>}
          {runsState === 'failed' && <ReadFailure title={w('workbench.read.historyFailed')} detail={runsError}
            onRetry={() => setRunsAttempt(value => value + 1)} />}
          {resultState === 'failed' && <ReadFailure title={w('workbench.read.resultFailed')} detail={resultError}
            onRetry={() => setResultAttempt(value => value + 1)} />}
          {previousState === 'failed' && <ReadFailure title={w('workbench.read.previousFailed')} detail={previousError}
            onRetry={() => setResultAttempt(value => value + 1)} />}
          {runError && <div className="notice notice--error" role="alert">{runError}</div>}
          {error && <div className="notice notice--error" role="alert">{error}</div>}
          {/* A refused jump is stated here, in the one place that is always on
              screen, and it changes neither the chapter nor the draft. */}
          {guidanceNotice && <div className="notice" role="status">{guidanceNotice}</div>}
          {conflict !== null && <div className="notice notice--conflict" role="alert"><strong>{w('workbench.conflict.title', { revision: conflict })}</strong><p>{w('workbench.conflict.body')}</p><div className="notice-actions"><button className="button button--secondary" onClick={() => { void copyDraft(); }}>{w('workbench.conflict.copy')}</button><button className="button button--primary" disabled={operation !== null} onClick={() => { void reload(); }}>{operation === 'reloading' ? w('workbench.conflict.reloadBusy') : w('workbench.conflict.reload')}</button></div></div>}
        </div>
      </div>
      {/* The chapter reveal is keyed on the chapter alone, and this container is
          never re-keyed: the operation bar and the chapter index stay put, and a
          hand-edited JSON document survives the switch with its value, its focus
          and its selection. */}
      <div className="workbench-content" data-motion={chapterMotion}>
        {showChanges && native && <div id="design-changes">
          <DesignFeedback before={savedSide} after={draftSide} catalogue={host.catalogue} onRetry={saved.retry} onOpenChapter={next => goChapter(next as Chapter)} />
        </div>}
        <ChapterHead chapter={chapter} name={draft.name} projectId={draft.id} revision={view.revision} proxy={draft.name.toLowerCase().includes('queen mary')} />
        {chapter === 'overview' && <>
          {/* The native design is always reachable: a project that declares none
              is offered a setup, and a project that only carried the old
              compatibility section is upgraded into a pending-save draft once. */}
          <ShipDesignOverview host={host} disabled={busy} onOpenChapter={next => goChapter(next as Chapter)} />
          <WorkbenchOverview draft={draft} revision={view.revision} conditionId={conditionId}
            runs={runs} current={selectedRun} previous={historyOfSelected} requestStages={requestStages}
            requestError={runError} dirty={dirty || jsonEdited} historyState={runsState} resultState={resultState} previousState={historyCandidate?.id === currentResultId ? resultState : previousState} onRefreshRuns={() => setRunsAttempt(value => value + 1)} onChapter={goChapter} onRun={onRun} onNavigate={jumpTo} />
        </>}
        {chapter === 'hull' && <>
          <section className="editor-section"><InputGroup index="01" title={w('editor.group.mainDimensions')} note={w('editor.group.mainDimensions.note')} />
            {native
              // The native declaration owns the overlapping principal dimensions;
              // the recovered field form is never shown beside it. A plain
              // physical project keeps its own form.
              ? <ShipDesignChapter page="hull" host={host} disabled={busy}
                baseline={saved.state === 'ready' ? saved.result : null} />
              : <><p className="section-intro">{w('editor.hull.intro')}</p>
                <div className="field-grid">{HULL_FIELDS.map(field => { const alternate = 'alternate' in field ? field.alternate : undefined; const key = alternate && !(field.key in hull) ? alternate : field.key; const issue = fieldErrors.find(item => item.path.includes(`hull.${key}`) || item.path.includes(`hull['${key}']`));
                  // A main dimension carries no per-field source of its own; only
                  // an explicitly declared `hull.sources` entry is ever read as one.
                  const declared = hullSources[key];
                  const label = w(field.label as WorkspaceKey), hint = w(field.hint as WorkspaceKey);
                  const fact: TraceFact = { key: `hull.${key}`, label, value: numeric(hull[key]),
                    dimension: field.dimension ?? undefined, storedUnit: field.dimension ? 'm' : undefined,
                    source: declaredSource(declared), estimate: null, path: `hull.${key}` };
                  return <TracedField fact={fact} className="hull-field" key={field.key} id={hullGuidanceId(field.key)}>
                    {field.dimension
                      ? <QuantityField label={label} ariaLabel={label} value={numeric(hull[key])} dimension={field.dimension} kind="positive" invalid={Boolean(issue)} hint={hint} onChange={next => updateHull(key, next === null ? null : String(next))} />
                      : <label className="field-label">{label}<input type="number" step="any" aria-label={label} aria-invalid={Boolean(issue)} value={typeof hull[key] === 'number' ? hull[key] : ''} onChange={event => updateHull(key, event.target.value)} placeholder={w('editor.unknown')} /><small>{hint}</small>{issue && <span className="field-error" role="alert">{issue.message}</span>}</label>}
                    {field.dimension && issue && <span className="field-error" role="alert">{issue.message}</span>}
                  </TracedField>; })}</div></>}
          </section>
          <section className="editor-section"><InputGroup index="02" title={w('editor.group.hullSupplement')} /><HullSupplementEditor project={draft} run={selectedRun} onChange={updateDraft} /></section>
        </>}
        {chapter === 'freeboard' && (native
          ? <section className="editor-section"><ShipDesignChapter page="freeboard" host={host} disabled={busy}
            baseline={saved.state === 'ready' ? saved.result : null} /></section>
          // A plain physical project has no native freeboard to edit; the design
          // is started from the overview, where the setup lives. It is never left
          // as a blank chapter.
          : <section className="editor-section"><p className="section-intro">{d('shipDesign.setup.hint')}</p><ConceptDesignLink label={d('shipDesign.setup.fresh')} onOpen={() => goChapter('overview')} /></section>)}
        {chapter === 'guns' && <section className="editor-section"><InputGroup index="01" title={w('editor.group.guns')} note={w('editor.group.guns.note')} /><p className="section-intro">{chapterOf(chapter, w).purpose}</p>
          {native
            ? <ShipDesignChapter page="guns" host={host} disabled={busy}
              baseline={saved.state === 'ready' ? saved.result : null} />
            : <><GunsEditor weapons={getWeapons()} runs={visibleRuns} ledger={ledger} onPatchBattery={patchBattery} /><ConceptDesignLink label={c('concept.enable')} onOpen={openConceptDesign} /></>}
          <ChapterJson w={w} text={jsonText} onEdit={editJson} edited={jsonEdited} onApply={applyJson} onDiscard={discardJson} error={jsonError} summary={w('editor.json.systems')} note={w('editor.json.systemsText')} label={w('editor.json.label')} /></section>}
        {chapter === 'weapons' && <section className="editor-section"><InputGroup index="01" title={w('editor.group.weapons')} note={w('editor.group.weapons.note')} /><p className="section-intro">{chapterOf(chapter, w).purpose}</p>
          {native
            ? <ShipDesignChapter page="weapons" host={host} disabled={busy} />
            : <WeaponsEditor weapons={getWeapons()} runs={visibleRuns} ledger={ledger} onPatchLeaf={patchWeapons} />}
          <ChapterJson w={w} text={jsonText} onEdit={editJson} edited={jsonEdited} onApply={applyJson} onDiscard={discardJson} error={jsonError} summary={w('editor.json.weapons')} note={w('editor.json.weaponsText')} label={w('editor.json.label')} /></section>}
        {chapter === 'armour' && <section className="editor-section"><InputGroup index="01" title={w('editor.group.armour')} />
          {native ? <ShipDesignChapter page="armour" host={host} disabled={busy}
            baseline={saved.state === 'ready' ? saved.result : null} /> : <ArmourEditor project={draft} run={selectedRun} onChange={updateDraft} />}</section>}
        {chapter === 'propulsion' && <section className="editor-section"><InputGroup index="01" title={w('editor.group.propulsion')} />
          {native ? <ShipDesignChapter page="engine" host={host} disabled={busy} />
            : <><EnginesEditor project={draft} run={selectedRun} onChange={updateDraft} /><ConceptDesignLink label={c('concept.group.machinery')} onOpen={openConceptDesign} /></>}</section>}
        {/* Reading order: the native performance fields lead the chapter; the
            optional request and the results that request produces follow, and
            nothing is recomputed to reorder them. */}
        {chapter === 'performance' && native && <section className="editor-section">
          {/* The native performance fields lead the chapter and carry no group
              number of their own; the physical request and its results follow. */}
          <ShipDesignChapter page="performance" host={host} disabled={busy} onOpenChapter={next => goChapter(next as Chapter)} />
          {/* Additional physical checks are request tasks, not a data mode: they
              add the ordinary physical stages on top of the native design stage
              for this run only, and they never change the declaration. */}
          <label className="field-label">
            <input type="checkbox" checked={physicalChecks} disabled={busy || hostBlocked}
              onChange={event => { contextGeneration.current += 1; setPhysicalChecks(event.target.checked); }} />
            {' '}附加物理检查 / Additional physical checks
          </label></section>}
        {chapter === 'performance' && physicalRequest && <>
          <section className="editor-section"><InputGroup index="01" title={w('editor.group.performanceInputs')} note={w('editor.group.performanceInputs.note')} />
            <PerformanceInputs project={draft} onChange={updateDraft} /></section>
          <section className="editor-section"><InputGroup index="02" title={w('editor.group.resistance')} note={w('editor.group.resistance.note')} />
            <ResistanceEditor project={draft} onChange={updateDraft} /></section>
          <section className="editor-section" id={REQUEST_PERFORMANCE} tabIndex={-1}><InputGroup index="03" title={w('editor.group.request')} note={w('editor.group.request.note')} />
            <PerformanceRequest project={draft} request={performanceRequest} onRequestChange={next => {
              contextGeneration.current += 1; setPerformanceRequest(next);
            }} /></section>
          <section className="editor-section"><InputGroup index="04" title={w('editor.group.results')} note={w('editor.group.results.note')} />
            <PerformanceResults run={selectedRun} />{!native && <ConceptDesignLink label={c('balance.title')} onOpen={openConceptDesign} />}</section>
        </>}
        {chapter === 'weights' && native && <>
          {/* The managed ledger and its balance are the authority for a native
              design, so they lead the chapter. The reader's own raw ledger rows
              follow, folded away: they are the position and source facts that sit
              underneath the core's managed mass. */}
          <section className="editor-section"><InputGroup index="01" title={w('editor.group.ledger')} note={w('editor.ledger.groups', { count: draft.weight_groups.length })} />
            <ShipDesignLedgerSection host={host} disabled={busy}
              baseline={saved.state === 'ready' ? saved.result : null} /></section>
          <section className="editor-section" id={LEDGER_SECTION} tabIndex={-1}>
            <details className="advanced-json"><summary>{d('shipDesign.ledger.positions')}</summary>
              <p className="section-intro">{d('shipDesign.ledger.positionsHint')}</p>
              <InputGroup index="02" title={w('editor.group.ledger')} note={w('editor.ledger.groups', { count: draft.weight_groups.length })} />
              {ledgerRows}
            </details></section>
        </>}
        {chapter === 'weights' && !native && <section className="editor-section" id={LEDGER_SECTION} tabIndex={-1}><InputGroup index="01" title={w('editor.group.ledger')} note={w('editor.ledger.groups', { count: draft.weight_groups.length })} />
          {ledgerRows}
        </section>}
        {chapter === 'weights' && !native && <section className="editor-section" id={CONCEPT_SECTION} tabIndex={-1}><InputGroup index="02" title={c('concept.enable')} note={c('concept.enableHint')} />
          {/* One compact reading of state this page already owns: enabled, saved,
              run for this saved revision and condition, and reviewable against the
              options now on screen. It adds no request and changes nothing. */}
          <ConceptReviewGuide enabled={conceptOn} dirty={dirty || jsonEdited} revision={view.revision}
            conditionId={conditionId} current={selectedRun}
            requested={requestStages.includes('design_balance')}
            requestCurrent={proposalRequestCurrent} />
          <ConceptDesignEditor project={draft} onChange={updateDraft}
            run={proposalRequestCurrent ? selectedRun : null}
            identity={`${proposalIdentity}|${optionsKey}`}
            dirty={dirty || jsonEdited} requestCurrent={proposalRequestCurrent} />
          <DesignBalanceDiagnostics run={selectedRun} />
        </section>}
        {chapter === 'weights' && !native && <section className="editor-section"><InputGroup index="03" title={c('proposals.title')} note={c('proposals.order')} />
          <MassProposalPanel run={proposalRequestCurrent ? selectedRun : null} identity={`${proposalIdentity}|${optionsKey}`} dirty={dirty || jsonEdited}
            requestChanged={!!selectedRun && !proposalRequestCurrent}
            apply={applyOwner.current === projectId ? applyState : IDLE_APPLY} onApply={applyProposals} onRerun={rerunAfterApply} />
        </section>}
        {chapter === 'weights' && !native && <section className="editor-section"><InputGroup index="04" title={w('editor.group.massModel')} note={w('editor.group.massModel.note')} /><MassModelEditor project={draft} run={selectedRun} onChange={updateDraft} /></section>}
        {chapter === 'weights' && !native && <section className="editor-section"><InputGroup index="05" title={c('balance.title')} note={c('balance.intro')} />
          <DesignBalanceResults run={selectedRun} available={conceptOn && !dirty && !jsonEdited} />
        </section>}
        {chapter === 'stability' && <section className="editor-section"><InputGroup index="01" title={w('editor.group.endpoints')} note={w('editor.group.endpoints.note')} /><DeckFreeboardEditor deck={getDeck(draft)} runs={visibleRuns} onPatchDeck={patchDeck} /><ChapterJson w={w} text={jsonText} onEdit={editJson} edited={jsonEdited} onApply={applyJson} onDiscard={discardJson} error={jsonError} summary={w('editor.json.advanced')} note={w('editor.json.advancedText')} label={w('editor.json.label')} /></section>}
        {chapter === 'damage' && <section className="editor-section" id={REQUEST_DAMAGE} tabIndex={-1}><InputGroup index="01" title={w('editor.group.damage')} note={w('editor.group.damage.note')} /><DamageEditor project={draft} run={selectedRun} request={floodingRequest} onChange={updateDraft} onRequestChange={next => {
          contextGeneration.current += 1; setFloodingRequest(next);
        }} requestError={floodingChoice.error} /></section>}
        {chapter === 'damage' && <section className="editor-section"><InputGroup index="02" title={w('editor.group.damageAdvanced')} /><ChapterJson w={w} text={jsonText} onEdit={editJson} edited={jsonEdited} onApply={applyJson} onDiscard={discardJson} error={jsonError} summary={w('editor.json.damage')} note={w('editor.json.damageText')} label={w('editor.json.damageLabel')} /></section>}
        {chapter === 'json' && <section className="editor-section"><InputGroup index="01" title={w('editor.group.projectJson')} note={w('editor.group.projectJson.note')} /><p className="section-intro">{w('editor.json.projectIntro')}</p><ChapterJson w={w} text={jsonText} onEdit={editJson} edited={jsonEdited} onApply={applyJson} onDiscard={discardJson} error={jsonError} summary="" note="" label={w('editor.json.projectLabel')} /></section>}
      </div>
    </main>
    <TracePanel open={traceOpen} onToggle={() => setTraceOpen(open => !open)} />
  </div>;
  return <UnitProvider preferences={draft.display_preferences}>
    <InputTraceProvider onReveal={() => setTraceOpen(true)}><TraceScope scopeKey={`${projectId}/${chapter}`}>{page}</TraceScope></InputTraceProvider>
  </UnitProvider>;
}
