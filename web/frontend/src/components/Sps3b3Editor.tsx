import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import * as api from '../api';
import { useSps3b3Copy, sps3b3FieldLabel, type Sps3b3Key } from '../i18n/sps3b3';
import type { CopyParams } from '../portfolio/LanguageProvider';
import type { ProjectDocument, Sps3b3Design, Sps3b3Field, Sps3b3Result } from '../types';
import { formatNumber } from './units';
import { SpsFreeboardProfile } from './Sps3b3Readings';
import {
  SPS_SECTION, Sps3b3Queue, allScalesCommand, armourDefaultsCommand, commandForField,
  depthLockCommand, displacementDriverCommand, freeboardPresetCommand, groupsForPage, lengthDriverCommand,
  lockShellsCommand, notesCommand, pageSectionId, parameterCommand, powerLockCommand,
  readSps3b3Catalog, recalculatePowerCommand, resolvedUnit, sameDesign, sps3b3DesignOf,
  sps3b3Enabled, splitDiagnostics, unlockShellsCommand, withSps3b3Design,
  type Sps3b3Catalogue, type Sps3b3Group, type Sps3b3QueueState, type SpsCommand,
} from './sps3b3Model';
import './../styles/Sps3b3.css';

/**
 * The SPS 3b3 compatibility editor.
 *
 * Seven source pages, in the source's own units, edited as a declaration and
 * confirmed one command at a time by the core. Every keystroke the reader makes
 * is an ordinary design draft edit through `onChange`, so the section rides the
 * workbench's existing save and revision rules; the only extra guarantee is that
 * a save or a run is refused while a command is still in the air, because an
 * optimistic value is not yet the core's answer.
 */

const EMPTY_CATALOGUE: Sps3b3Catalogue = {
  entries: [], byName: {}, pageOrder: [], pageLabels: {}, pageFields: {}, controls: {},
  fieldCount: 0, scaleNames: new Set<string>(),
};

const EMPTY_STATE: Sps3b3QueueState = {
  confirmed: null, display: null, preview: null, diagnostics: [], status: null,
  pending: 0, busy: false, error: null,
};

export const TAB_LABEL: Record<string, Sps3b3Key> = {
  hull: 'sps.tab.hull', freeboard: 'sps.tab.freeboard', guns: 'sps.tab.guns',
  weapons: 'sps.tab.weapons', armour: 'sps.tab.armour', engine: 'sps.tab.engine',
  performance: 'sps.tab.performance',
};

export interface Sps3b3EditorProps {
  project: ProjectDocument;
  onChange: (next: ProjectDocument) => void;
  /** Called with the number of declared edits still unconfirmed. */
  onPendingChange?: (pending: number) => void;
  disabled?: boolean;
}

export function Sps3b3Editor({ project, onChange, onPendingChange, disabled = false }: Sps3b3EditorProps) {
  const w = useSps3b3Copy();
  const design = sps3b3DesignOf(project);
  const section = (project as Record<string, unknown>)[SPS_SECTION] ?? null;

  const [catalogue, setCatalogue] = useState<Sps3b3Catalogue | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [page, setPage] = useState('hull');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sourceName, setSourceName] = useState<string | null>(null);
  const [state, setState] = useState<Sps3b3QueueState>(EMPTY_STATE);

  const catalogueRef = useRef<Sps3b3Catalogue | null>(null);
  const projectRef = useRef(project);
  const onChangeRef = useRef(onChange);
  const pendingRef = useRef(onPendingChange);
  const echoRef = useRef<unknown>(null);
  const queueRef = useRef<Sps3b3Queue | null>(null);
  const liveRef=useRef(true);
  useEffect(()=>{
    liveRef.current=true;queueRef.current?.activate();
    return ()=>{liveRef.current=false;queueRef.current?.dispose();};
  },[]);

  projectRef.current = project;
  onChangeRef.current = onChange;
  pendingRef.current = onPendingChange;

  if (!queueRef.current) {
    queueRef.current = new Sps3b3Queue({
      confirm: request => api.sps3b3Preview(request.design, request.command),
      catalogue: () => catalogueRef.current ?? EMPTY_CATALOGUE,
      scaleRefsOf: p => {
        const cat = catalogueRef.current;
        if (!cat) return [];
        const refs = new Set<string>();
        for (const field of (cat.pageFields[p] ?? []).map(name => cat.byName[name])) {
          if (field?.scale_ref) refs.add(field.scale_ref);
        }
        return [...refs];
      },
      allScaleNames: () => [...(catalogueRef.current?.scaleNames ?? [])],
    });
  }

  // The catalogue is a property of the recovered program, read once.
  useEffect(() => {
    let live = true;
    api.sps3b3Catalog()
      .then(raw => {
        if (!live) return;
        const next = readSps3b3Catalog(raw);
        catalogueRef.current = next;
        setCatalogue(next);
        setPage(current => (next.pageOrder.includes(current) ? current : (next.pageOrder[0] ?? 'hull')));
      })
      .catch((cause: unknown) => {
        if (!live) return;
        setCatalogError(w('sps.error.catalog'));
        void cause;
      });
    return () => { live = false; };
    // The catalogue does not depend on the language; only the failure message does.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // The queue's subscription is the one place a confirmed change reaches the draft.
  useEffect(() => {
    const queue = queueRef.current as Sps3b3Queue;
    const unsubscribe = queue.subscribe(next => {
      setState(next);
      pendingRef.current?.(next.pending);
      const current = projectRef.current;
      const display = next.display;
      if (!current || !display || !sps3b3Enabled(current)) return;
      if (sameDesign((current as Record<string, unknown>)[SPS_SECTION] ?? null, display)) return;
      echoRef.current = display;
      onChangeRef.current(withSps3b3Design(current, display));
    });
    return () => {
      unsubscribe();
      pendingRef.current?.(0);
    };
  }, []);

  // Adopt a design the parent replaced out from under us — a reload, an import, a
  // save that returned a normalized section — but never while an edit is in flight.
  useEffect(() => {
    const queue = queueRef.current;
    if (!queue || section === null) return;
    if (echoRef.current === section) return;
    const current = queue.getState();
    if (sameDesign(section, current.display)) { echoRef.current = section; return; }
    queue.start(section as Sps3b3Design);
    echoRef.current = section;
  }, [section]);

  const tabPages = useMemo(() => catalogue?.pageOrder.filter(p => TAB_LABEL[p]) ?? [], [catalogue]);
  const groups = useMemo(
    () => (catalogue && design ? groupsForPage(catalogue, page) : []),
    [catalogue, page, design],
  );

  const run = useCallback(async (action: () => Promise<Sps3b3Design>) => {
    setBusy(true);
    pendingRef.current?.(1);
    setError(null);
    try {
      const next = await action();
      if (!liveRef.current) return;
      onChangeRef.current(withSps3b3Design(projectRef.current, next));
    } catch (cause) {
      if (liveRef.current) setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      if (liveRef.current) {setBusy(false);pendingRef.current?.(0);}
    }
  }, []);

  const enableFresh = useCallback(() => {
    void run(async () => (await api.sps3b3Default()).design);
  }, [run]);

  const enableMigration = useCallback(() => {
    const migration = (projectRef.current as Record<string, unknown>).migration;
    if (migration === undefined) return;
    void run(async () => (await api.sps3b3FromMigration(migration as Record<string, unknown>)).design);
  }, [run]);

  const enableImport = useCallback((file: File) => {
    void run(async () => {
      const base64 = await fileToBase64(file);
      const reply = await api.sps3b3ImportPreview(file.name, base64);
      setSourceName(file.name);
      return reply.design;
    });
  }, [run]);

  const remove = useCallback(() => {
    onChangeRef.current(withSps3b3Design(projectRef.current, null));
  }, []);

  const queue = queueRef.current as Sps3b3Queue;
  const commitField = useCallback((field: Sps3b3Field, value: unknown) => {
    if (!catalogueRef.current) return;
    queue.submit(commandForField(catalogueRef.current, field, value));
  }, [queue]);

  const locked = disabled || busy;
  const hasMigration = (project as Record<string, unknown>).migration !== undefined;
  const pageUnit = catalogue && design ? pageUnitLabel(catalogue, page, design) : null;

  if (!design) {
    return (
      <section className="sps-editor" aria-label={w('sps.title')}>
        <header className="sps-head">
          <p className="sps-kicker">{w('sps.kicker')}</p>
          <h2>{w('sps.enable.title')}</h2>
          <p className="sps-note">{w('sps.enable.hint')}</p>
          <p className="sps-empirical">{w('sps.empiricalNote')}</p>
        </header>
        {catalogError ? <p className="sps-error" role="alert">{catalogError}</p> : null}
        <div className="sps-enable">
          <button type="button" className="sps-button" disabled={disabled || busy}
            onClick={enableFresh}>{w('sps.enable.fresh')}</button>
          <p className="sps-hint">{w('sps.enable.freshHint')}</p>

          <label className="sps-file">
            <span>{w('sps.enable.import')}</span>
            <input type="file" accept=".sship,.dat,.txt,text/plain" disabled={disabled || busy}
              onChange={event => {
                const file = event.target.files?.[0];
                event.target.value = '';
                if (file) enableImport(file);
              }} />
          </label>
          <p className="sps-hint">{w('sps.enable.importHint')}</p>

          <button type="button" className="sps-button" disabled={disabled || busy || !hasMigration}
            onClick={enableMigration}>{w('sps.enable.fromMigration')}</button>
          <p className="sps-hint">{hasMigration ? w('sps.enable.fromMigrationHint') : w('sps.enable.noMigration')}</p>

          {busy ? <p className="sps-pending" role="status">{w('sps.enable.pending')}</p> : null}
          {error ? <p className="sps-error" role="alert">{w('sps.error.generic', { message: error })}</p> : null}
        </div>
      </section>
    );
  }

  return (
    <section className="sps-editor" aria-label={w('sps.title')}>
      <header className="sps-head">
        <p className="sps-kicker">{w('sps.kicker')}</p>
        <h2>{w('sps.title')}</h2>
        <p className="sps-note">{w('sps.intro')}</p>
        <p className="sps-empirical">{w('sps.empiricalNote')}</p>
        <details><summary>{w('sps.readings.origin')}</summary><p className="sps-method">{w('sps.method', {
          method: catalogue ? 'sps-3b3' : '—', schema: design.schema ?? '—',
        })}</p></details>
      </header>

      {catalogError ? <p className="sps-error" role="alert">{catalogError}</p> : null}
      {state.error ? <div className="sps-error" role="alert">{w('sps.queue.failed', { message: state.error })}<button type="button" onClick={()=>queue.retry()}>Retry / 重试</button></div> : null}
      {state.pending > 0 ? (
        <p className="sps-pending" role="status">{w('sps.queue.pending', { count: state.pending })}</p>
      ) : null}

      <div className="sps-drivers" aria-label={w('sps.controls.title')}>
        <DriverGroup label={w('sps.controls.lengthDriver')}>
          <Choice name="length-driver" value={driverValue(design.editing.length_driver, 'waterline')}
            options={[['waterline', w('sps.controls.lengthDriver.waterline')], ['overall', w('sps.controls.lengthDriver.overall')]]}
            disabled={locked}
            onChange={value => queue.submit(lengthDriverCommand(value as 'waterline' | 'overall'))} />
          {design.editing.length_driver==='overall' && <label>{w('sps.controls.overallLength')}<TextControl kind="number" value={design.editing.overall_length} disabled={locked} label={w('sps.controls.overallLength')} onCommit={value=>queue.submit(parameterCommand('length_overall',value))} /></label>}
        </DriverGroup>
        <DriverGroup label={w('sps.controls.displacementDriver')}>
          <Choice name="displacement-driver" value={driverValue(design.editing.displacement_driver, 'block')}
            options={[['block', w('sps.controls.displacementDriver.block')], ['displacement', w('sps.controls.displacementDriver.displacement')]]}
            disabled={locked}
            onChange={value => queue.submit(displacementDriverCommand(value as 'block' | 'displacement'))} />
          {design.editing.displacement_driver==='displacement' && <label>{w('sps.controls.normalDisplacement')}<TextControl kind="number" value={design.editing.normal_displacement_lt} disabled={locked} label={w('sps.controls.normalDisplacement')} onCommit={value=>queue.submit(parameterCommand('normal_displacement_lt',value))} /></label>}
          <label>{w('sps.controls.hullform')}<input type="range" min="0.3" max="1" step="0.001" value={typeof design.parameters.block_coefficient_normal==='number'?design.parameters.block_coefficient_normal:.55} disabled={locked}
            onChange={event=>queue.submit(parameterCommand('block_coefficient_normal',Number(event.target.value)))} /></label>
        </DriverGroup>
        <DriverGroup label={w('sps.controls.freeboardPreset')}>
          <div className="sps-row">
            <button type="button" className="sps-button" disabled={locked}
              onClick={() => queue.submit(freeboardPresetCommand('flush'))}>{w('sps.controls.preset.flush')}</button>
            <button type="button" className="sps-button" disabled={locked}
              onClick={() => queue.submit(freeboardPresetCommand('raised'))}>{w('sps.controls.preset.raised')}</button>
          </div>
        </DriverGroup>
        <DriverGroup label={w('sps.controls.depthLock')}>
          <Toggle checked={design.editing.depth_locked === true} disabled={locked}
            label={w('sps.controls.depthLock')}
            onChange={next => queue.submit(depthLockCommand(next))} />
          {design.editing.depth_locked === true ? <p className="sps-hint">{w('sps.controls.depthLocked')}</p> : null}
        </DriverGroup>
        <DriverGroup label={w('sps.controls.powerLock')}>
          <Toggle checked={design.editing.power_locked === true} disabled={locked}
            label={w('sps.controls.powerLock')}
            onChange={next => queue.submit(powerLockCommand(next))} />
          {design.editing.power_locked===true && <label>{w('sps.controls.powerHp')}<TextControl kind="number" value={design.editing.power_hp} disabled={locked} label={w('sps.controls.powerHp')} onCommit={value=>queue.submit(parameterCommand('power_hp',value))} /></label>}
          <div className="sps-row">
            <button type="button" className="sps-button" disabled={locked}
              onClick={() => queue.submit(recalculatePowerCommand())}>{w('sps.controls.recalculatePower')}</button>
          </div>
        </DriverGroup>
        <DriverGroup label={w('sps.controls.units')}>
          <div className="sps-row">
            <button type="button" className="sps-button" disabled={locked}
              onClick={() => queue.submit(allScalesCommand(1))}>{w('sps.controls.allMetric')}</button>
            <button type="button" className="sps-button" disabled={locked}
              onClick={() => queue.submit(allScalesCommand(0))}>{w('sps.controls.allImperial')}</button>
          </div>
        </DriverGroup>
        <DriverGroup label={w('sps.controls.outfit')}>
          <div className="sps-row">
            <button type="button" className="sps-button" disabled={locked}
              onClick={() => queue.submit(lockShellsCommand())}>{w('sps.controls.lockShells')}</button>
            <button type="button" className="sps-button" disabled={locked}
              onClick={() => queue.submit(unlockShellsCommand())}>{w('sps.controls.unlockShells')}</button>
            <button type="button" className="sps-button" disabled={locked}
              onClick={() => queue.submit(armourDefaultsCommand())}>{w('sps.controls.armourDefaults')}</button>
          </div>
        </DriverGroup>
      </div>

      <div className="sps-meta">
        <label className="sps-text">
          <span>{w('sps.design.source')}</span>
          <SourceField value={design.source ?? ''} disabled={disabled}
            placeholder={w('sps.design.sourcePlaceholder')}
            commit={text => queue.replace(current => ({ ...current, source: text === '' ? null : text }))} />
        </label>
        <p className="sps-hint">{sourceName ? w('sps.enable.imported', { filename: sourceName }) : w('sps.design.sourcePlaceholder')}</p>
        <label className="sps-text">
          <span>{w('sps.design.notes')}</span>
          <NotesField value={design.notes ?? ''} disabled={locked}
            commit={text => queue.submit(notesCommand(text === '' ? null : text))} />
        </label>
        <p className="sps-hint">{w('sps.design.notesHint')}</p>
        <button type="button" className="sps-button sps-remove" disabled={disabled || busy || state.pending>0}
          onClick={remove}>{w('sps.enable.remove')}</button>
        <p className="sps-hint">{w('sps.enable.removeHint')}</p>
      </div>

      <div className="sps-tabs" role="tablist" aria-label={w('sps.tabs')}>
        {tabPages.map(id => (
          <button key={id} type="button" role="tab" aria-selected={id === page}
            className={id === page ? 'sps-tab sps-tab-on' : 'sps-tab'}
            onClick={() => setPage(id)}>{w(TAB_LABEL[id])}</button>
        ))}
      </div>

      <div className="sps-page" role="tabpanel" aria-label={w(TAB_LABEL[page] ?? 'sps.title')}>
        <p className="sps-count">{w('sps.page.fieldCount', { count: groups.reduce((n, g) => n + g.fields.length, 0) })}</p>
        {groups.map(group => (
          <Sps3b3GroupView key={group.id} group={group} design={design} copy={w} disabled={locked}
            onCommand={command => queue.submit(command)} onCommitField={commitField} />
        ))}
      </div>

      {page==='freeboard' && <SpsFreeboardProfile result={state.preview} />}
      <PageReadings result={state.preview} page={page} unit={pageUnit} copy={w} status={state.preview?.status??state.status}
        diagnostics={state.diagnostics} pending={state.pending} busy={state.busy} />
    </section>
  );
}

/**
 * One group of source fields, rendered from the design's own values.
 *
 * Shared by the compatibility editor and the native host: both read the same
 * catalogue and the same recovered source view, so a group looks and behaves
 * the same wherever it is hosted. The host supplies what a commit means — a
 * queued source command in the editor, a native command in the ordinary
 * workbench — so this stays a presentation of the design, not a second editor.
 */
export function Sps3b3GroupView({ group, design, copy, disabled, onCommand, onCommitField }: {
  group: Sps3b3Group; design: Sps3b3Design; disabled: boolean;
  copy: (key: Sps3b3Key, params?: CopyParams) => string;
  onCommand: (command: SpsCommand) => void;
  onCommitField: (field: Sps3b3Field, value: unknown) => void;
}) {
  const [open, setOpen] = useState(group.openByDefault);
  const locked = Array.isArray(design.editing.locked_shell_groups)
    ? design.editing.locked_shell_groups
    : [];
  const shellLocked = group.index !== undefined && locked.includes(group.index);
  return (
    <section className="sps-group">
      {group.collapsible ? (
        <button type="button" className="sps-group-head" aria-expanded={open}
          onClick={() => setOpen(prev => !prev)}>
          {groupLabel(copy, group)}
        </button>
      ) : <h3 className="sps-group-head-static">{groupLabel(copy, group)}</h3>}
      {group.kind==='guns' && group.index !== undefined && (
        <label className="sps-choice"><input type="checkbox" disabled={disabled}
          checked={shellLocked}
          onChange={event=>onCommand({kind:event.target.checked?'lock_shells':'unlock_shells',groups:[group.index as number]})} />
          {copy('sps.controls.lockShells')} · {group.index}</label>
      )}
      {group.kind==='guns' && group.index !== undefined && open && (
        <label>{copy('sps.controls.shellKg')}
          <TextControl kind="number" label={`${copy('sps.controls.shellKg')} ${group.index}`}
            disabled={disabled || shellLocked}
            value={typeof design.parameters[`gun${group.index}_shell_weight`]==='number'
              ? Number(((design.parameters[`gun${group.index}_shell_weight`] as number)*.45359236).toFixed(2))
              : null}
            onCommit={value=>onCommand({kind:'set_shell_weight',group:group.index as number,unit:'kg',value})} />
        </label>
      )}
      {open ? (
        <div className="sps-fields">
          {group.fields.map(field => (
            <FieldRow key={field.key} field={field} copy={copy}
              disabled={disabled || (/_shell_weight$/.test(field.name) && group.index !== undefined
                && locked.includes(Number(field.name[3])))}
              value={design.parameters?.[field.name] ?? null}
              unit={resolvedUnit(field, design)}
              onCommit={next => onCommitField(field, next)} />
          ))}
        </div>
      ) : null}
    </section>
  );
}

/* ------------------------------------------------------------- controls  */

function driverValue(value: unknown, fallback: string): string {
  return typeof value === 'string' ? value : fallback;
}

export function DriverGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="sps-driver">
      <p className="sps-driver-label">{label}</p>
      {children}
    </div>
  );
}

export function Choice({ name, value, options, disabled, onChange }: {
  name: string; value: string; options: Array<[string, string]>;
  disabled: boolean; onChange: (value: string) => void;
}) {
  return (
    <div className="sps-row" role="radiogroup" aria-label={name}>
      {options.map(([id, label]) => (
        <label key={id} className="sps-choice">
          <input type="radio" name={name} checked={value === id} disabled={disabled}
            onChange={() => onChange(id)} />
          <span>{label}</span>
        </label>
      ))}
    </div>
  );
}

export function Toggle({ checked, label, disabled, onChange }: {
  checked: boolean; label: string; disabled: boolean; onChange: (next: boolean) => void;
}) {
  return (
    <label className="sps-choice">
      <input type="checkbox" checked={checked} disabled={disabled} aria-label={label}
        onChange={event => onChange(event.target.checked)} />
      <span>{label}</span>
    </label>
  );
}

export function SourceField({ value, placeholder, disabled, commit }: {
  value: string; placeholder: string; disabled: boolean; commit: (text: string) => void;
}) {
  const [text, setText] = useState(value);
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => { if (document.activeElement !== ref.current) setText(value); }, [value]);
  return (
    <input ref={ref} type="text" className="sps-input" value={text} placeholder={placeholder}
      disabled={disabled} onChange={event => setText(event.target.value)}
      onBlur={() => { if (text !== value) commit(text); }} />
  );
}

export function NotesField({ value, disabled, commit }: {
  value: string; disabled: boolean; commit: (text: string) => void;
}) {
  const [text, setText] = useState(value);
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => { if (document.activeElement !== ref.current) setText(value); }, [value]);
  return (
    <textarea ref={ref} className="sps-textarea" value={text} rows={3} disabled={disabled}
      onChange={event => setText(event.target.value)}
      onBlur={() => { if (text !== value) commit(text); }} />
  );
}

/* --------------------------------------------------------------- fields  */

export function FieldRow({ field, value, unit, disabled, copy, onCommit }: {
  field: Sps3b3Field; value: unknown; unit: string | null; disabled: boolean;
  copy: (key: Sps3b3Key, params?: CopyParams) => string;
  onCommit: (next: unknown) => void;
}) {
  const label = sps3b3FieldLabel(copy, field.name, field.label);
  return (
    <label className="sps-field" data-field={field.name} data-unit={unit ?? ''}>
      <span className="sps-field-label">{label}</span>
      <span className="sps-field-control">
        {field.kind === 'boolean' ? (
          <span className="sps-row">
            <input type="checkbox" checked={value === true} disabled={disabled}
              aria-label={label}
              ref={element => { if (element) element.indeterminate = value === null || value === undefined; }}
              onChange={event => onCommit(event.target.checked)} />
            <button type="button" className="sps-clear" disabled={disabled}
              onClick={() => onCommit(null)}>{copy('sps.field.clear')}</button>
          </span>
        ) : (field.kind === 'enum' || field.kind === 'selector') && field.choices ? (
          <select className="sps-select" value={value === null || value === undefined ? '' : String(value)}
            disabled={disabled} aria-label={label}
            onChange={event => onCommit(event.target.value === '' ? null : Number(event.target.value))}>
            <option value="">{copy('sps.field.unknown')}</option>
            {field.choices.map((choice, index) => (
              <option key={choice + index} value={index}>{choice}</option>
            ))}
          </select>
        ) : (
          <TextControl kind={field.kind} value={value} disabled={disabled} label={label}
            min={field.min_value} max={field.max_value} onCommit={onCommit} />
        )}
      </span>
      <span className="sps-field-unit">{unit ?? ''}</span>
    </label>
  );
}

export function TextControl({ kind, value, disabled, label, min, max, onCommit }: {
  kind: string; value: unknown; disabled: boolean; label: string;
  min?: number | null; max?: number | null; onCommit: (next: unknown) => void;
}) {
  const initial = value === null || value === undefined ? '' : kind==='number' && typeof value==='number' ? String(Number(value.toPrecision(7))) : String(value);
  const [text, setText] = useState(initial);
  const [invalid, setInvalid] = useState(false);
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => { if (document.activeElement !== ref.current) setText(initial); }, [initial]);

  const commit = () => {
    if (text===initial)return;
    if (kind==='text') {setInvalid(false);onCommit(text);return;}
    const trimmed = text.trim();
    if (trimmed === '') { setInvalid(false); onCommit(null); return; }
    const parsed = Number(trimmed);
    if (!Number.isFinite(parsed) || (kind === 'integer' && !Number.isInteger(parsed))) { setInvalid(true); return; }
    setInvalid(false);
    onCommit(parsed);
  };

  const inputType = kind === 'text' ? 'text' : 'number';
  return (
    <input ref={ref} type={inputType} className={invalid ? 'sps-input sps-input-invalid' : 'sps-input'}
      value={text} disabled={disabled} aria-label={label} aria-invalid={invalid}
      step={kind === 'integer' ? 1 : 'any'} min={min ?? undefined} max={max ?? undefined}
      onChange={event => setText(event.target.value)}
      onBlur={commit}
      onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); commit(); } }} />
  );
}

/* -------------------------------------------------------------- readings */

export function PageReadings({ result, page, unit, copy, status, diagnostics, pending, busy }: {
  result: Sps3b3Result | null; page: string; unit: string | null;
  copy: (key: Sps3b3Key, params?: CopyParams) => string;
  status: string | null; diagnostics: Sps3b3Result['diagnostics']; pending: number; busy: boolean;
}) {
  const sectionId = pageSectionId(page);
  const readings = nativeReadingsOf(result, sectionId);
  const review=result?.review as {warnings?:Array<Record<string,unknown>>;design_failures?:Array<Record<string,unknown>>}|undefined;
  const allDiagnostics=[...(diagnostics??[]),...(result?.diagnostics??[]),...(review?.warnings??[]),...(review?.design_failures??[])];
  const { severe,other } = splitDiagnostics(allDiagnostics);
  const findings=[...new Map([...severe,...other].map(item=>[item.message,item])).values()];
  return (
    <section className="sps-preview" aria-label={copy('sps.preview.title')}>
      <header className="sps-preview-head">
        <h3>{copy('sps.preview.title')}</h3>
        <span className="sps-preview-status">{statusLabel(copy, status)}</span>
        {unit ? <span className="sps-preview-unit">{copy('sps.field.nativeUnit')}: {unit}</span> : null}
        {pending > 0 || busy ? <span className="sps-pending-inline" role="status">{copy('sps.preview.pending')}</span> : null}
      </header>
      <p className="sps-hint">{copy('sps.preview.notSaved')}</p>
      <p className="sps-hint">{copy('sps.preview.page')}</p>
      {readings.length === 0 ? <p className="sps-hint">{copy('sps.preview.none')}</p> : (
        <dl className="sps-readings">
          {readings.map(reading => (
            <div key={reading.key} className="sps-reading">
              <dt>{reading.key}</dt>
              <dd>{formatNative(reading.value)}</dd>
            </div>
          ))}
        </dl>
      )}
      {(page==='guns' || page==='weapons') && Array.isArray((result?.[sectionId] as {groups?:unknown[]}|undefined)?.groups) &&
        ((result?.[sectionId] as {groups:Array<Record<string,unknown>>}).groups).map((group,index)=><details key={index}><summary>{String(group.id??index+1)}</summary>
          <dl className="sps-readings">{Object.entries(group).filter(([key,value])=>['gunWeight','mountWeight','totalWeight','magazineWeight','broadsideWeight','armWeight','autoShellWeight','freeGun','super','weaponWeight','area'].includes(key) && (typeof value==='number' || value===null)).map(([key,value])=><div className="sps-reading" key={key}><dt>{key}</dt><dd>{formatNative(value)}</dd></div>)}</dl>
        </details>)}
      {findings.length > 0 ? (
        <div className="sps-warnings">
          <p className="sps-warnings-title">{copy('sps.readings.warnings')}</p>
          <ul>
            {findings.map((diagnostic, index) => (
              <li key={`${diagnostic.code ?? 'diag'}-${index}`}>
                <code>{diagnostic.code ?? '—'}</code>{' '}
                <span>{diagnostic.message ?? ''}</span>
                {diagnostic.field ? <em> · {diagnostic.field}</em> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

export function nativeReadingsOf(result: Sps3b3Result | null, section: string): Array<{ key: string; value: unknown }> {
  if (!result) return [];
  const bag = (result as Record<string, unknown>)[section];
  if (!bag || typeof bag !== 'object' || Array.isArray(bag)) return [];
  return Object.entries(bag as Record<string, unknown>).filter(([,value])=>value===null || typeof value!=='object').map(([key, value]) => ({ key, value }));
}

export function formatNative(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'number') return Number.isFinite(value) ? formatNumber(value) : '—';
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'string') return value;
  return JSON.stringify(value);
}

function statusLabel(copy: (key: Sps3b3Key, params?: CopyParams) => string, status: string | null): string {
  switch (status) {
    case 'available': return copy('sps.preview.status.available');
    case 'partial': return copy('sps.preview.status.partial');
    case 'unavailable': return copy('sps.preview.status.unavailable');
    default: return copy('sps.field.unknown');
  }
}

export function groupLabel(copy: (key: Sps3b3Key, params?: CopyParams) => string, group: Sps3b3Group): string {
  switch (group.kind) {
    case 'guns': return copy('sps.guns.group', { index: group.index ?? 0 });
    case 'torpedo': return copy('sps.weapons.torpedo', { index: group.index ?? 0 });
    case 'mine': return copy('sps.weapons.mine');
    case 'depthCharge': return copy('sps.weapons.depthCharge', { index: group.index ?? 0 });
    case 'misc': return copy('sps.weapons.misc');
    case 'armourThickness': return copy('sps.armour.group.thickness');
    case 'armourExtents': return copy('sps.armour.group.extents');
    default: return copy(TAB_LABEL[group.id] ?? 'sps.title');
  }
}

export function pageUnitLabel(catalogue: Sps3b3Catalogue, page: string, design: Sps3b3Design): string | null {
  for (const name of catalogue.pageFields[page] ?? []) {
    const field = catalogue.byName[name];
    if (field && field.unit) return resolvedUnit(field, design);
  }
  return null;
}

async function fileToBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = '';
  for (let index = 0; index < bytes.length; index += 1) binary += String.fromCharCode(bytes[index]);
  return btoa(binary);
}

export { parameterCommand };
