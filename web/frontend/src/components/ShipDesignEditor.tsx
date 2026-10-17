import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import * as api from '../api';
import { useShipDesignCopy, useShipDesignRoleLabel, type ShipDesignKey } from '../i18n/shipDesign';
import { useSps3b3Copy } from '../i18n/sps3b3';
import type {
  DesignReply, ProjectDocument, ShipDesign, ShipDesignLedgerEntry, ShipDesignResult,
  Sps3b3Design, Sps3b3Field,
} from '../types';
import {
  SHIP_DESIGN_SECTION, SPS_SECTION, Sps3b3Queue, allScalesCommand, armourDefaultsCommand,
  bindMassCommand, commandForField, depthLockCommand, displacementDriverCommand,
  freeboardPresetCommand, groupsForPage, lengthDriverCommand, lockShellsCommand, notesCommand,
  parameterCommand, powerLockCommand, readSps3b3Catalog, recalculatePowerCommand,
  setDeclaredMassCommand, shipDesignOf, sourceViewOfShipDesign, unlockShellsCommand,
  withShipDesign,
  type Sps3b3Catalogue, type Sps3b3QueueState, type SpsCommand,
} from './sps3b3Model';
import {
  Choice, DriverGroup, NotesField, PageReadings, SourceField, Sps3b3GroupView, TAB_LABEL,
  TextControl, Toggle, pageUnitLabel,
} from './Sps3b3Editor';
import { SpsFreeboardProfile } from './Sps3b3Readings';
import { formatNumber } from './units';
import {
  balanceOf, basisConditionId, bindingProblem, conditionLabel, effectiveItemMass, isUnresolved,
  ledgerComplete, ledgerEntries, needsBinding, projectItemIds, projectSettledReply, sameGovernedSlice,
  unresolvedEntries,
} from './shipDesign';
import './../styles/Sps3b3.css';

/**
 * The native ship-design host.
 *
 * The one authoritative declaration lives at `$.ship_design` and is edited as an
 * ordinary draft through `onChange`. Every edit is a queued core command, and the
 * confirmed reply replaces the governed projection — hull, ledger and the eight
 * SI dimensions — while the reader's own unrelated edits stay exactly where they
 * were. Nothing here computes a ship number: the core answers with the whole
 * governed project, and this host only decides when that answer may be applied.
 */

const EMPTY_CATALOGUE: Sps3b3Catalogue = {
  entries: [], byName: {}, pageOrder: [], pageLabels: {}, pageFields: {}, controls: {},
  fieldCount: 0, scaleNames: new Set<string>(),
};

const EMPTY_STATE: Sps3b3QueueState = {
  confirmed: null, display: null, preview: null, diagnostics: [], status: null,
  pending: 0, busy: false, error: null,
};

function scaleRefs(catalogue: Sps3b3Catalogue | null, page: string): string[] {
  if (!catalogue) return [];
  const refs = new Set<string>();
  for (const field of (catalogue.pageFields[page] ?? []).map(name => catalogue.byName[name])) {
    if (field?.scale_ref) refs.add(field.scale_ref);
  }
  return [...refs];
}

function reason(cause: unknown): string {
  return cause instanceof Error ? cause.message : String(cause);
}

async function fileToBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = '';
  for (let index = 0; index < bytes.length; index += 1) binary += String.fromCharCode(bytes[index]);
  return btoa(binary);
}

export interface ShipDesignHost {
  project: ProjectDocument | null;
  design: ShipDesign | null;
  /** The temporary source-view the existing field widgets read. */
  source: Sps3b3Design | null;
  state: Sps3b3QueueState;
  /** The queued preview read as the native result, for the ledger. */
  nativePreview: ShipDesignResult | null;
  catalogue: Sps3b3Catalogue | null;
  catalogError: string | null;
  hasMigration: boolean;
  busy: boolean;
  pending: number;
  error: string | null;
  submitCommand: (command: SpsCommand) => void;
  commitField: (field: Sps3b3Field, value: unknown) => void;
  replaceSource: (mutate: (design: Sps3b3Design) => Sps3b3Design) => void;
  initialize: () => void;
  importFile: (file: File) => void;
  fromMigration: () => void;
  retry: () => void;
}

export function useShipDesignHost(options: {
  project: ProjectDocument | null;
  onChange: (next: ProjectDocument) => void;
  disabled?: boolean;
  onPendingChange?: (pending: number) => void;
}): ShipDesignHost {
  const { project, onChange, onPendingChange } = options;

  const [state, setState] = useState<Sps3b3QueueState>(EMPTY_STATE);
  const [catalogue, setCatalogue] = useState<Sps3b3Catalogue | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const projectRef = useRef(project);
  const onChangeRef = useRef(onChange);
  const pendingRef = useRef(onPendingChange);
  const catalogueRef = useRef<Sps3b3Catalogue | null>(null);
  const queueRef = useRef<Sps3b3Queue<DesignReply> | null>(null);
  /** The exact section object the draft currently holds, for identity checks. */
  const echoRef = useRef<unknown>(null);
  const legacyAttemptRef = useRef<{ project: ProjectDocument; reply: Promise<DesignReply> } | null>(null);
  /** The project id + revision the queue baseline belongs to. */
  const scopeRef = useRef<string | null>(null);
  /** One ticket per setup operation, so a stale reply never ends a newer one. */
  const setupTicket = useRef(0);
  const liveRef = useRef(true);

  projectRef.current = project;
  onChangeRef.current = onChange;
  pendingRef.current = onPendingChange;

  const section = useMemo(() => {
    if (!project) return null;
    const raw = (project as Record<string, unknown>)[SHIP_DESIGN_SECTION];
    return raw && typeof raw === 'object' && !Array.isArray(raw) ? raw : null;
  }, [project]);
  const design = useMemo(() => (project ? shipDesignOf(project) : null), [project]);
  const source = useMemo(() => (design ? sourceViewOfShipDesign(design) : null), [design]);
  const hasDesign = section !== null;
  // A setup operation in flight counts as pending too: save and run stay blocked
  // while the core is being asked to add or replace the declaration.
  const reportedPending = state.pending + (busy ? 1 : 0);
  const scope = project ? `${project.id}|${project.revision}` : null;

  if (!queueRef.current) {
    queueRef.current = new Sps3b3Queue<DesignReply>({
      // The request is always the current project, the last confirmed source
      // view and the queued command — never a draft captured when the reader
      // clicked.
      confirm: request => {
        const current = projectRef.current;
        if (!current) return Promise.reject(new Error('no project'));
        return api.designPreview(current, request.command, request.design);
      },
      catalogue: () => catalogueRef.current ?? EMPTY_CATALOGUE,
      scaleRefsOf: page => scaleRefs(catalogueRef.current, page),
      allScaleNames: () => [...(catalogueRef.current?.scaleNames ?? [])],
      // Applied only when the reply belongs to the generation still on screen and
      // to the project that asked for it.
      onSettled: reply => {
        const current = projectRef.current;
        if (!current) return;
        if (reply.project.id !== current.id) return;
        const display = queueRef.current?.getState().display ?? null;
        const next = projectSettledReply(current, reply.project, display);
        if (sameGovernedSlice(next, current)) return;
        echoRef.current = (next as Record<string, unknown>)[SHIP_DESIGN_SECTION] ?? null;
        onChangeRef.current(next);
      },
    });
  }

  useEffect(() => {
    liveRef.current = true;
    queueRef.current?.activate();
    return () => { liveRef.current = false; queueRef.current?.dispose(); };
  }, []);

  // The catalogue is a property of the recovered program, read once.
  useEffect(() => {
    if (!hasDesign) return;
    let live = true;
    api.designCatalog().then(raw => {
      if (!live) return;
      const next = readSps3b3Catalog(raw);
      catalogueRef.current = next;
      setCatalogue(next);
    }).catch(() => { if (live) setCatalogError('catalog'); });
    return () => { live = false; };
  }, [hasDesign]);

  // The queue's subscription is where an optimistic edit reaches the draft.
  useEffect(() => {
    const queue = queueRef.current as Sps3b3Queue<DesignReply>;
    const unsubscribe = queue.subscribe(next => {
      setState(next);
      const current = projectRef.current;
      const display = next.display;
      if (!current || !display) return;
      const currentDesign = shipDesignOf(current);
      if (!currentDesign) return;
      const projected: ShipDesign = {
        ...currentDesign,
        source: display.source ?? null,
        parameters: { ...currentDesign.parameters, ...display.parameters },
        editing: { ...currentDesign.editing, ...display.editing },
        notes: display.notes ?? null,
      };
      const nextProject = withShipDesign(current, projected);
      if (sameGovernedSlice(nextProject, current)) return;
      echoRef.current = projected;
      onChangeRef.current(nextProject);
    });
    return () => { unsubscribe(); };
  }, []);

  // Report the whole pending count — queued edits plus a setup operation — so the
  // parent blocks save and run until everything has settled.
  useEffect(() => { pendingRef.current?.(reportedPending); }, [reportedPending]);
  useEffect(() => () => { pendingRef.current?.(0); }, []);

  /**
   * Follow the authoritative declaration.
   *
   * A new project id or revision resets the queue outright — even when the design
   * looks identical — because a reply that was asked for under the old scope must
   * never settle onto the new one. A section object this host did not write
   * itself is adopted as the new baseline even when its values are equal: a new
   * identity means the parent replaced the declaration (an initialize, an import,
   * a reload), and any request against the old one is void.
   */
  useEffect(() => {
    const queue = queueRef.current;
    if (!queue) return;
    const scopeChanged = scopeRef.current !== scope;
    if (scopeChanged) {
      scopeRef.current = scope;
      echoRef.current = null;
      setupTicket.current += 1;
      setBusy(false);
      setError(null);
    }
    if (scope === null || section === null || !source) {
      if (scopeChanged) queue.reset();
      return;
    }
    if (!scopeChanged && echoRef.current === section) return;
    echoRef.current = section;
    queue.start(source);
  }, [scope, section, source]);

  /**
   * An old compatibility project becomes a native draft once.
   *
   * The upgrade is a pending-save draft: the core owns the conversion, the old
   * run identity is untouched, and if the upgrade fails the reader keeps the old
   * physical forms rather than losing the project.
   */
  useEffect(() => {
    if (!project || section !== null) return;
    const legacy = (project as Record<string, unknown>)[SPS_SECTION];
    if (legacy === undefined || legacy === null) return;
    // Re-subscribe to the same pure request after a StrictMode effect cleanup.
    // The cleanup invalidates adoption, not the request itself.
    if (legacyAttemptRef.current?.project !== project) {
      legacyAttemptRef.current = { project, reply: api.designInitialize(project) };
    }
    const ticket = ++setupTicket.current;
    setBusy(true);
    setError(null);
    let live = true;
    legacyAttemptRef.current.reply.then(reply => {
      if (!live || setupTicket.current !== ticket || projectRef.current !== project) return;
      if (reply.project.id !== project.id) return;
      onChangeRef.current(reply.project);
    }).catch(cause => {
      if (live && setupTicket.current === ticket) setError(reason(cause));
    }).finally(() => {
      if (liveRef.current && setupTicket.current === ticket) setBusy(false);
    });
    return () => { live = false; };
  }, [project, section]);

  /**
   * Adopt a setup reply, but only while it is still the operation in flight and
   * for the project that sent it.
   */
  const adopt = useCallback((sent: ProjectDocument, ticket: number, reply: DesignReply) => {
    if (!liveRef.current || setupTicket.current !== ticket) return;
    if (projectRef.current !== sent) return;
    if (reply.project.id !== sent.id) return;
    onChangeRef.current(reply.project);
  }, []);

  const beginSetup = useCallback((): number => {
    const ticket = setupTicket.current + 1;
    setupTicket.current = ticket;
    setBusy(true);
    setError(null);
    return ticket;
  }, []);

  const failSetup = useCallback((ticket: number, cause: unknown) => {
    if (!liveRef.current || setupTicket.current !== ticket) return;
    setError(reason(cause));
  }, []);

  const endSetup = useCallback((ticket: number) => {
    if (!liveRef.current || setupTicket.current !== ticket) return;
    setBusy(false);
  }, []);

  const initialize = useCallback(() => {
    const current = projectRef.current;
    if (!current) return;
    const ticket = beginSetup();
    api.designInitialize(current)
      .then(reply => adopt(current, ticket, reply))
      .catch(cause => failSetup(ticket, cause))
      .finally(() => endSetup(ticket));
  }, [adopt, beginSetup, endSetup, failSetup]);

  const importFile = useCallback((file: File) => {
    const current = projectRef.current;
    if (!current) return;
    const ticket = beginSetup();
    fileToBase64(file)
      .then(base64 => api.designImportPreview(current, file.name, base64))
      .then(reply => adopt(current, ticket, reply))
      .catch(cause => failSetup(ticket, cause))
      .finally(() => endSetup(ticket));
  }, [adopt, beginSetup, endSetup, failSetup]);

  const fromMigration = useCallback(() => {
    const current = projectRef.current;
    if (!current) return;
    const migration = (current as Record<string, unknown>).migration;
    if (migration === undefined) return;
    const ticket = beginSetup();
    api.designFromMigration(current, migration as Record<string, unknown>)
      .then(reply => adopt(current, ticket, reply))
      .catch(cause => failSetup(ticket, cause))
      .finally(() => endSetup(ticket));
  }, [adopt, beginSetup, endSetup, failSetup]);

  const submitCommand = useCallback((command: SpsCommand) => {
    queueRef.current?.submit(command);
  }, []);

  const commitField = useCallback((field: Sps3b3Field, value: unknown) => {
    const cat = catalogueRef.current;
    if (!cat) return;
    queueRef.current?.submit(commandForField(cat, field, value));
  }, []);

  const replaceSource = useCallback((mutate: (design: Sps3b3Design) => Sps3b3Design) => {
    queueRef.current?.replace(mutate);
  }, []);

  const retry = useCallback(() => { queueRef.current?.retry(); }, []);

  return {
    project,
    design,
    source,
    state,
    nativePreview: (state.preview ?? null) as ShipDesignResult | null,
    catalogue,
    catalogError,
    hasMigration: project ? (project as Record<string, unknown>).migration !== undefined : false,
    busy: busy || state.busy,
    pending: reportedPending,
    error,
    submitCommand,
    commitField,
    replaceSource,
    initialize,
    importFile,
    fromMigration,
    retry,
  };
}

/* -------------------------------------------------------------------- views */

/** The ordinary chapters that host native controls, and their control set. */
type ControlId = 'lengthDriver' | 'displacementDriver' | 'freeboardPreset' | 'depthLock' | 'powerLock' | 'units' | 'shells' | 'armourDefaults';

const CHAPTER_CONTROLS: Record<string, ControlId[]> = {
  hull: ['lengthDriver', 'displacementDriver', 'units', 'depthLock'],
  freeboard: ['freeboardPreset', 'depthLock'],
  guns: ['shells'],
  weapons: ['shells'],
  armour: ['armourDefaults'],
  engine: ['powerLock', 'units'],
};

export function ShipDesignControls({ page, host, disabled }: {
  page: string; host: ShipDesignHost; disabled: boolean;
}) {
  const w = useSps3b3Copy();
  const source = host.source;
  const ids = CHAPTER_CONTROLS[page] ?? [];
  if (!source || ids.length === 0) return null;
  const locked = disabled || host.busy;
  const editing = source.editing;
  return <div className="sps-drivers" aria-label={w('sps.controls.title')}>
    {ids.includes('lengthDriver') && <DriverGroup label={w('sps.controls.lengthDriver')}>
      <Choice name={`length-driver-${page}`} value={driverValue(editing.length_driver, 'waterline')}
        options={[['waterline', w('sps.controls.lengthDriver.waterline')], ['overall', w('sps.controls.lengthDriver.overall')]]}
        disabled={locked}
        onChange={value => host.submitCommand(lengthDriverCommand(value as 'waterline' | 'overall'))} />
      {editing.length_driver === 'overall' && <label>{w('sps.controls.overallLength')}
        <TextControl kind="number" value={editing.overall_length} disabled={locked} label={w('sps.controls.overallLength')}
          onCommit={value => host.submitCommand(parameterCommand('length_overall', value))} /></label>}
    </DriverGroup>}
    {ids.includes('displacementDriver') && <DriverGroup label={w('sps.controls.displacementDriver')}>
      <Choice name={`displacement-driver-${page}`} value={driverValue(editing.displacement_driver, 'block')}
        options={[['block', w('sps.controls.displacementDriver.block')], ['displacement', w('sps.controls.displacementDriver.displacement')]]}
        disabled={locked}
        onChange={value => host.submitCommand(displacementDriverCommand(value as 'block' | 'displacement'))} />
      {editing.displacement_driver === 'displacement' && <label>{w('sps.controls.normalDisplacement')}
        <TextControl kind="number" value={editing.normal_displacement_lt} disabled={locked} label={w('sps.controls.normalDisplacement')}
          onCommit={value => host.submitCommand(parameterCommand('normal_displacement_lt', value))} /></label>}
      <label>{w('sps.controls.hullform')}
        <input type="range" min="0.3" max="1" step="0.001" disabled={locked}
          value={typeof source.parameters.block_coefficient_normal === 'number' ? source.parameters.block_coefficient_normal : 0.55}
          onChange={event => host.submitCommand(parameterCommand('block_coefficient_normal', Number(event.target.value)))} /></label>
    </DriverGroup>}
    {ids.includes('freeboardPreset') && <DriverGroup label={w('sps.controls.freeboardPreset')}>
      <div className="sps-row">
        <button type="button" className="sps-button" disabled={locked}
          onClick={() => host.submitCommand(freeboardPresetCommand('flush'))}>{w('sps.controls.preset.flush')}</button>
        <button type="button" className="sps-button" disabled={locked}
          onClick={() => host.submitCommand(freeboardPresetCommand('raised'))}>{w('sps.controls.preset.raised')}</button>
      </div>
    </DriverGroup>}
    {ids.includes('depthLock') && <DriverGroup label={w('sps.controls.depthLock')}>
      <Toggle checked={editing.depth_locked === true} disabled={locked} label={w('sps.controls.depthLock')}
        onChange={next => host.submitCommand(depthLockCommand(next))} />
      {editing.depth_locked === true ? <p className="sps-hint">{w('sps.controls.depthLocked')}</p> : null}
    </DriverGroup>}
    {ids.includes('powerLock') && <DriverGroup label={w('sps.controls.powerLock')}>
      <Toggle checked={editing.power_locked === true} disabled={locked} label={w('sps.controls.powerLock')}
        onChange={next => host.submitCommand(powerLockCommand(next))} />
      {editing.power_locked === true && <label>{w('sps.controls.powerHp')}
        <TextControl kind="number" value={editing.power_hp} disabled={locked} label={w('sps.controls.powerHp')}
          onCommit={value => host.submitCommand(parameterCommand('power_hp', value))} /></label>}
      <div className="sps-row"><button type="button" className="sps-button" disabled={locked}
        onClick={() => host.submitCommand(recalculatePowerCommand())}>{w('sps.controls.recalculatePower')}</button></div>
    </DriverGroup>}
    {ids.includes('units') && <DriverGroup label={w('sps.controls.units')}>
      <div className="sps-row">
        <button type="button" className="sps-button" disabled={locked}
          onClick={() => host.submitCommand(allScalesCommand(1))}>{w('sps.controls.allMetric')}</button>
        <button type="button" className="sps-button" disabled={locked}
          onClick={() => host.submitCommand(allScalesCommand(0))}>{w('sps.controls.allImperial')}</button>
      </div>
    </DriverGroup>}
    {ids.includes('shells') && <DriverGroup label={w('sps.controls.lockShells')}>
      <div className="sps-row">
        <button type="button" className="sps-button" disabled={locked}
          onClick={() => host.submitCommand(lockShellsCommand())}>{w('sps.controls.lockShells')}</button>
        <button type="button" className="sps-button" disabled={locked}
          onClick={() => host.submitCommand(unlockShellsCommand())}>{w('sps.controls.unlockShells')}</button>
      </div>
    </DriverGroup>}
    {ids.includes('armourDefaults') && <DriverGroup label={w('sps.controls.outfit')}>
      <div className="sps-row"><button type="button" className="sps-button" disabled={locked}
        onClick={() => host.submitCommand(armourDefaultsCommand())}>{w('sps.controls.armourDefaults')}</button></div>
    </DriverGroup>}
  </div>;
}

function driverValue(value: unknown, fallback: string): string {
  return typeof value === 'string' ? value : fallback;
}

/** The source fields of one chapter, in the ordinary page body. */
export function ShipDesignFields({ page, host, disabled }: {
  page: string; host: ShipDesignHost; disabled: boolean;
}) {
  const w = useSps3b3Copy();
  const source = host.source;
  const groups = useMemo(
    () => (host.catalogue && source ? groupsForPage(host.catalogue, page) : []),
    [host.catalogue, source, page],
  );
  if (!source) return null;
  if (!host.catalogue) return <p className="sps-hint">{w('sps.error.catalog')}</p>;
  const label = TAB_LABEL[page] ? w(TAB_LABEL[page]) : w('sps.title');
  return <div className="sps-page" role="group" aria-label={label}>
    <p className="sps-count">{w('sps.page.fieldCount', { count: groups.reduce((n, g) => n + g.fields.length, 0) })}</p>
    {groups.map(group => (
      <Sps3b3GroupView key={group.id} group={group} design={source} copy={w} disabled={disabled}
        onCommand={host.submitCommand} onCommitField={host.commitField} />
    ))}
  </div>;
}

/**
 * One native chapter: its drivers, its source fields, its freeboard profile and
 * its own derived reading. There are no inner source-page tabs: the chapter *is*
 * the page.
 */
export function ShipDesignChapter({ page, host, disabled }: {
  page: string; host: ShipDesignHost; disabled: boolean;
}) {
  const w = useSps3b3Copy();
  const source = host.source;
  if (!source) return null;
  const state = host.state;
  const unit = host.catalogue ? pageUnitLabel(host.catalogue, page, source) : null;
  return <>
    {state.error ? <div className="sps-error" role="alert">{w('sps.queue.failed', { message: state.error })}
      <button type="button" onClick={host.retry}>Retry / 重试</button></div> : null}
    {host.error ? <p className="sps-error" role="alert">{w('sps.error.generic', { message: host.error })}</p> : null}
    {state.pending > 0 ? <p className="sps-pending" role="status">{w('sps.queue.pending', { count: state.pending })}</p> : null}
    <ShipDesignControls page={page} host={host} disabled={disabled} />
    <ShipDesignFields page={page} host={host} disabled={disabled} />
    {page === 'freeboard' ? <SpsFreeboardProfile result={state.preview} /> : null}
    <PageReadings result={state.preview} page={page} unit={unit} copy={w}
      status={state.preview?.status ?? state.status} diagnostics={state.diagnostics}
      pending={state.pending} busy={state.busy} />
  </>;
}

/** The ordinary-overview block: setup when absent, design facts when present. */
export function ShipDesignOverview({ host, disabled }: { host: ShipDesignHost; disabled: boolean }) {
  const w = useSps3b3Copy();
  const d = useShipDesignCopy();
  if (!host.design) return <ShipDesignSetup host={host} disabled={disabled} />;
  const design = host.design;
  const locked = disabled || host.busy;
  const basis = conditionLabel(host.project, design.condition_id);
  return <section className="ship-design" aria-label={d('shipDesign.title')}>
    <header className="sps-head">
      <p className="sps-kicker">{d('shipDesign.kicker')}</p>
      <h2>{d('shipDesign.title')}</h2>
      <p className="sps-note">{d('shipDesign.intro')}</p>
      <p className="sps-empirical">{d('shipDesign.empiricalNote')}</p>
    </header>
    {host.catalogError ? <p className="sps-error" role="alert">{w('sps.error.catalog')}</p> : null}
    {host.error ? <p className="sps-error" role="alert">{d('shipDesign.failed', { message: host.error })}</p> : null}
    <p className="sps-hint">{d('shipDesign.condition')}: {basis ?? d('shipDesign.conditionUnset')}</p>
    <p className="sps-hint">{d('shipDesign.conditionHint')}</p>
    <div className="sps-meta">
      <label className="sps-text">
        <span>{d('shipDesign.source')}</span>
        <SourceField value={design.source ?? ''} disabled={disabled}
          placeholder={d('shipDesign.sourcePlaceholder')}
          commit={text => host.replaceSource(current => ({ ...current, source: text === '' ? null : text }))} />
      </label>
      <label className="sps-text">
        <span>{d('shipDesign.notes')}</span>
        <NotesField value={design.notes ?? ''} disabled={locked}
          commit={text => host.submitCommand(notesCommand(text === '' ? null : text))} />
      </label>
      <p className="sps-hint">{d('shipDesign.notesHint')}</p>
      <label className="sps-file">
        <span>{d('shipDesign.setup.replace')}</span>
        <input type="file" accept=".sship,.dat,.txt,text/plain" disabled={locked}
          onChange={event => { const file = event.target.files?.[0]; event.target.value = ''; if (file) host.importFile(file); }} />
      </label>
      <p className="sps-hint">{d('shipDesign.setup.importHint')}</p>
      {host.busy ? <p className="sps-pending" role="status">{d('shipDesign.setup.pending')}</p> : null}
      {host.state.pending > 0 ? <p className="sps-pending" role="status">{d('shipDesign.pending', { count: host.state.pending })}</p> : null}
    </div>
  </section>;
}

function ShipDesignSetup({ host, disabled }: { host: ShipDesignHost; disabled: boolean }) {
  const w = useSps3b3Copy();
  const d = useShipDesignCopy();
  return <section className="ship-design" aria-label={d('shipDesign.title')}>
    <header className="sps-head">
      <p className="sps-kicker">{d('shipDesign.kicker')}</p>
      <h2>{d('shipDesign.setup.title')}</h2>
      <p className="sps-note">{d('shipDesign.setup.hint')}</p>
    </header>
    {host.catalogError ? <p className="sps-error" role="alert">{w('sps.error.catalog')}</p> : null}
    <div className="sps-enable">
      <button type="button" className="sps-button" disabled={disabled || host.busy}
        onClick={host.initialize}>{d('shipDesign.setup.fresh')}</button>
      <label className="sps-file">
        <span>{d('shipDesign.setup.import')}</span>
        <input type="file" accept=".sship,.dat,.txt,text/plain" disabled={disabled || host.busy}
          onChange={event => { const file = event.target.files?.[0]; event.target.value = ''; if (file) host.importFile(file); }} />
      </label>
      <p className="sps-hint">{d('shipDesign.setup.importHint')}</p>
      <button type="button" className="sps-button" disabled={disabled || host.busy || !host.hasMigration}
        onClick={host.fromMigration}>{d('shipDesign.setup.fromMigration')}</button>
      <p className="sps-hint">{host.hasMigration ? w('sps.enable.fromMigrationHint') : d('shipDesign.setup.noMigration')}</p>
      {host.busy ? <p className="sps-pending" role="status">{d('shipDesign.setup.pending')}</p> : null}
      {host.error ? <p className="sps-error" role="alert">{d('shipDesign.failed', { message: host.error })}</p> : null}
    </div>
  </section>;
}

/**
 * The managed ledger and its explicit bindings.
 *
 * Every source role estimate is shown with its target ids, its mode, whether it
 * is resolved, and the selected/estimated/target/difference figures. Binding a
 * role is an explicit core command; a declared mass is only editable once the
 * role is bound in declared mode, so an estimated mass is never overwritten as
 * if it were the reader's own.
 */
export function ShipDesignLedgerSection({ host, disabled }: { host: ShipDesignHost; disabled: boolean }) {
  const d = useShipDesignCopy();
  const role = useShipDesignRoleLabel();
  const preview = host.nativePreview;
  const entries = ledgerEntries(preview);
  const balance = balanceOf(preview);
  const basis = conditionLabel(host.project, basisConditionId(preview));
  const unbound = needsBinding(preview);
  const unresolved = unresolvedEntries(entries).length;
  const locked = disabled || host.busy;
  return <section className="ship-design-ledger" aria-label={d('shipDesign.ledger.title')}>
    <header className="sps-head">
      <h3>{d('shipDesign.ledger.title')}</h3>
      <p className="sps-note">{d('shipDesign.ledger.intro')}</p>
    </header>
    {balance ? <dl className="sps-readings" aria-label={d('shipDesign.balance.title')}>
      <div className="sps-reading"><dt>{d('shipDesign.ledger.selected')}</dt><dd>{renderTonnes(balance.selected_mass_t)}</dd></div>
      <div className="sps-reading"><dt>{d('shipDesign.ledger.estimate')}</dt><dd>{renderTonnes(balance.estimated_mass_t)}</dd></div>
      <div className="sps-reading"><dt>{d('shipDesign.ledger.target')}</dt><dd>{renderTonnes(balance.target_displacement_t)}</dd></div>
      <div className="sps-reading"><dt>{d('shipDesign.ledger.difference')}</dt><dd>{renderTonnes(balance.difference_t)}</dd></div>
      <div className="sps-reading"><dt>{d('shipDesign.balance.basis', { condition: '' }).trim()}</dt><dd>{basis ?? d('shipDesign.conditionUnset')}</dd></div>
    </dl> : null}
    {entries.length === 0 ? <p className="sps-hint">{d('shipDesign.ledger.none')}</p> : null}
    {preview && entries.length > 0 ? <p className="sps-hint">
      {ledgerComplete(preview) ? d('shipDesign.ledger.complete') : d('shipDesign.ledger.unresolved', { count: unresolved })}</p> : null}
    {/* The unbound *items* come from the ledger's own `needs_binding` list, never
        from an empty per-role target: the optional `other` classification carries
        no source estimate and is not itself a missing binding. */}
    {unbound.length > 0 ? <p className="sps-hint">{d('shipDesign.ledger.unboundItems', { items: unbound.join(', ') })}</p> : null}
    {entries.length > 0 ? <>
      <table className="sps-ledger-table">
        <caption className="sps-hint">{d('shipDesign.ledger.roleTable')}</caption>
        <thead><tr>
          <th scope="col">{d('shipDesign.ledger.role')}</th>
          <th scope="col">{d('shipDesign.ledger.mode')}</th>
          <th scope="col">{d('shipDesign.ledger.estimate')}</th>
          <th scope="col">{d('shipDesign.ledger.selected')}</th>
          <th scope="col">{d('shipDesign.ledger.items')}</th>
        </tr></thead>
        <tbody>
          {entries.map(entry => <tr key={entry.role} data-role={entry.role} data-mode={entry.mode ?? 'none'}>
            <th scope="row">{role(entry.role)}</th>
            <td>{modeLabel(d, entry.mode, entry.role)}</td>
            <td>{renderTonnes(entry.estimate_t)}</td>
            <td>{renderTonnes(entry.selected_mass_t)}</td>
            <td>{(entry.item_ids ?? []).join(', ') || '—'}</td>
          </tr>)}
        </tbody>
      </table>
    </> : null}
    {/* Binding is an explicit command per role, so the forms stay collapsed to
        one disclosure rather than exposing every candidate item at once. */}
    <details className="sps-bindings">
      <summary>{d('shipDesign.bind.summary', { count: entries.length })}</summary>
      <p className="sps-note">{d('shipDesign.bind.intro')}</p>
      {entries.map(entry => <article key={entry.role} className="sps-ledger-role" data-role={entry.role} data-mode={entry.mode ?? 'none'}>
        <div className="sps-ledger-head">
          <h4>{role(entry.role)}</h4>
          <span className="sps-ledger-mode">{modeLabel(d, entry.mode, entry.role)}</span>
        </div>
        {isUnresolved(entry) ? <p className="sps-hint" role="status">{d('shipDesign.ledger.needsBinding')}</p> : null}
        <RoleBinding entry={entry} host={host} disabled={locked} />
        <DeclaredMass entry={entry} host={host} disabled={locked} />
      </article>)}
    </details>
  </section>;
}

function modeLabel(d: (key: ShipDesignKey) => string, mode: string | null | undefined, role: string): string {
  if (role === 'other' && !mode) return d('shipDesign.ledger.optional');
  return mode === 'declared' ? d('shipDesign.ledger.mode.declared')
    : mode === 'estimated' ? d('shipDesign.ledger.mode.estimated') : d('shipDesign.ledger.needsBinding');
}

function RoleBinding({ entry, host, disabled }: {
  entry: ShipDesignLedgerEntry; host: ShipDesignHost; disabled: boolean;
}) {
  const d = useShipDesignCopy();
  const role = useShipDesignRoleLabel();
  const idsKey = (entry.item_ids ?? []).join('\u0000');
  // The form starts on the binding the core already reports, so applying it
  // again is a no-op rather than a silent re-declaration.
  const [selected, setSelected] = useState<string[]>(() => (idsKey === '' ? [] : idsKey.split('\u0000')));
  const [mode, setMode] = useState<'estimated' | 'declared'>(entry.mode === 'declared' ? 'declared' : 'estimated');
  const [mass, setMass] = useState('');
  const candidates = useMemo(() => projectItemIds(host.project), [host.project]);
  useEffect(() => { setSelected(idsKey === '' ? [] : idsKey.split('\u0000')); }, [idsKey]);
  useEffect(() => { setMode(entry.mode === 'declared' ? 'declared' : 'estimated'); }, [entry.mode]);
  // Every ledger item in the draft stays reachable, plus the current binding's
  // own targets, so an existing target is never dropped from the picker.
  const options = useMemo(() => {
    const set = new Set<string>(candidates);
    for (const id of entry.item_ids ?? []) set.add(id);
    return [...set];
  }, [candidates, entry.item_ids]);
  const problem = bindingProblem(host.design, entry.role, selected, mode);
  const apply = () => {
    if (problem) return;
    const parsed = mass.trim() === '' ? undefined : Number(mass);
    host.submitCommand(bindMassCommand(entry.role, selected, mode, parsed !== undefined && Number.isFinite(parsed) ? parsed : undefined));
  };
  return <div className="sps-bind" data-role={entry.role}>
    <p className="sps-driver-label">{d('shipDesign.bind.title')}</p>
    <div className="sps-row" role="radiogroup" aria-label={`${role(entry.role)} ${d('shipDesign.ledger.mode')}`}>
      <label className="sps-choice"><input type="radio" name={`bind-mode-${entry.role}`} checked={mode === 'estimated'} disabled={disabled}
        onChange={() => setMode('estimated')} aria-label={`${role(entry.role)} ${d('shipDesign.ledger.mode.estimated')}`} />
        <span>{d('shipDesign.ledger.mode.estimated')}</span></label>
      <label className="sps-choice"><input type="radio" name={`bind-mode-${entry.role}`} checked={mode === 'declared'} disabled={disabled}
        onChange={() => setMode('declared')} aria-label={`${role(entry.role)} ${d('shipDesign.ledger.mode.declared')}`} />
        <span>{d('shipDesign.ledger.mode.declared')}</span></label>
    </div>
    {options.length === 0 ? <p className="sps-hint">{d('shipDesign.ledger.none')}</p> : <label className="sps-field">
      <span className="sps-field-label">{d('shipDesign.bind.items')}</span>
      <span className="sps-field-control">
        <select className="sps-input" multiple size={Math.min(Math.max(options.length, 2), 6)} value={selected} disabled={disabled}
          aria-label={`${role(entry.role)} ${d('shipDesign.bind.items')}`}
          onChange={event => setSelected([...event.target.selectedOptions].map(option => option.value))}>
          {options.map(id => <option key={id} value={id}>{id}</option>)}
        </select>
      </span>
    </label>}
    {mode === 'declared' ? <label className="sps-field">
      <span className="sps-field-label">{d('shipDesign.bind.mass')}</span>
      <span className="sps-field-control"><input className="sps-input" type="number" step="any" value={mass} disabled={disabled}
        aria-label={`${d('shipDesign.bind.mass')} ${role(entry.role)}`} onChange={event => setMass(event.target.value)} /></span>
      <span className="sps-field-unit"><small>{d('shipDesign.bind.massHint')}</small></span>
    </label> : null}
    {problem ? <p className="sps-hint" role="status">{d(`shipDesign.bind.problem.${problem}` as ShipDesignKey)}</p> : null}
    <button type="button" className="sps-button" disabled={disabled || problem !== null || selected.length === 0}
      onClick={apply}>{d('shipDesign.bind.apply')}</button>
  </div>;
}

function DeclaredMass({ entry, host, disabled }: {
  entry: ShipDesignLedgerEntry; host: ShipDesignHost; disabled: boolean;
}) {
  const d = useShipDesignCopy();
  const role = useShipDesignRoleLabel();
  const ids = entry.item_ids ?? [];
  const declared = entry.mode === 'declared';
  if (ids.length === 0) return null;
  return <div className="sps-declared" data-role={entry.role} data-mode={declared ? 'declared' : 'estimated'}>
    <p className="sps-hint">{declared ? d('shipDesign.declared.hint') : d('shipDesign.declared.disabled')}</p>
    {ids.map(id => <DeclaredMassRow key={id} id={id} role={role(entry.role)} host={host} disabled={disabled || !declared} />)}
  </div>;
}

function DeclaredMassRow({ id, role, host, disabled }: {
  id: string; role: string; host: ShipDesignHost; disabled: boolean;
}) {
  const d = useShipDesignCopy();
  // The effective mass the core currently gives this item: its own declared
  // override when the role is declared, the managed estimate when it is
  // estimated, and the item's base mass otherwise. These are the core's own
  // numbers in the core's own order — nothing is computed here.
  const current = useMemo(() => effectiveItemMass(host.project, id), [host.project, id]);
  const [text, setText] = useState(current === null ? '' : String(current));
  useEffect(() => { setText(current === null ? '' : String(current)); }, [current]);
  const commit = () => {
    const value = text.trim() === '' ? null : Number(text);
    if (value !== null && !Number.isFinite(value)) return;
    host.submitCommand(setDeclaredMassCommand(id, value));
  };
  return <label className="sps-field" data-item={id}>
    <span className="sps-field-label">{d('shipDesign.declared.title')} · {id}</span>
    <span className="sps-field-control">
      <input className="sps-input" type="number" step="any" value={text} disabled={disabled}
        aria-label={`${d('shipDesign.declared.title')} ${role} ${id}`}
        onChange={event => setText(event.target.value)} onBlur={commit} />
    </span>
  </label>;
}

function renderTonnes(value: number | null | undefined): string {
  return typeof value === 'number' && Number.isFinite(value) ? `${formatNumber(value)} t` : '—';
}
