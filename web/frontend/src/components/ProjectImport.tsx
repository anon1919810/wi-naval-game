import { useEffect, useRef, useState } from 'react';

import * as api from '../api';
import { outcome } from '../audio/feedback';
import { assertEnvelopeFits, readBackupFile, BackupFileError } from './backupFile';
import { readSshipFile, SshipFileError, type SshipSourceFile } from './sshipFile';
import { SshipMigrationPreview } from './SshipMigrationPreview';
import { useWorkspaceCopy, type WorkspaceKey } from '../i18n/workspace';
import type { ProjectDiagnostic, ProjectDocument, ProjectImportPreview, ProjectView, SshipProjectImportPreview } from '../types';
import '../styles/projectImport.css';

/**
 * Restoring a project backup, or migrating a SpringSharp source, in three steps.
 *
 * A chosen file is read, then sent to the workspace server to be read there, and
 * the answer is a description of what the file holds and what the canonical
 * validator still warns about. Only then may the reader confirm a name and ask
 * for it to be saved as a new project. Nothing is written before that button.
 *
 * Two sources, one section. A JSON backup and a SpringSharp 3.0 `.sship`/`.dat`
 * file are different things with different readers, so each has its own chooser,
 * its own progress and its own confirmation, and they never share a preview: a
 * choice in one drops what the other was showing. The SpringSharp flow is
 * deliberately the same three steps and the same locks — a `.sship` file is
 * somebody's ship, and the reader of one deserves exactly the care a backup
 * reader already gets.
 *
 * What this component is careful about:
 *
 * - **Nothing is saved before confirmation.** Choosing and previewing are reads.
 * - **A slow step is cancellable.** Reading and validating show what they are
 *   waiting for and can be abandoned, because a preview that never arrives must
 *   not trap the reader in a section with no way out.
 * - **A late answer belongs to nobody.** Every asynchronous step takes a ticket
 *   when it starts; only the newest ticket, on a still-mounted section, may
 *   write. A read, preview or save that finishes after the reader chose another
 *   file, cancelled, or left the page cannot resurrect an old preview or
 *   navigate to a project.
 * - **A recoverable failure keeps the work.** A failed save leaves the file, the
 *   preview and the entered name exactly as they were, so it is a retry.
 * - **A migration saves the bytes that were previewed.** The SpringSharp file is
 *   held as read and sent unchanged under the digest the preview reported for it,
 *   so the project that is saved is the one the reader was shown — and a file
 *   replaced in the meantime cannot be saved behind their back.
 */

/** Counts, in the order a reader reads a project: its conditions to its holes. */
const COUNT_ROWS = [
  { key: 'loading_conditions', label: 'import.count.loadingConditions' },
  { key: 'weight_groups', label: 'import.count.weightGroups' },
  { key: 'weight_items', label: 'import.count.weightItems' },
  { key: 'damage_scenarios', label: 'import.count.damageScenarios' },
  { key: 'compartments', label: 'import.count.compartments' },
  { key: 'openings', label: 'import.count.openings' },
] as const satisfies ReadonlyArray<{ key: string; label: WorkspaceKey }>;

const GEOMETRY_LABEL: Record<string, WorkspaceKey> = {
  offsets: 'import.geometry.offsets',
  parameters: 'import.geometry.parameters',
};

/** How many findings are shown before the rest move into a disclosure. */
const SHOWN_FINDINGS = 4;

/** One canonical validator finding, rendered as its own code, path and message. */
function Finding({ diagnostic, w }: { diagnostic: ProjectDiagnostic; w: (key: WorkspaceKey, params?: Record<string, string | number>) => string }) {
  return <li className="project-import-finding">
    <span className="project-import-finding-severity" data-severity={diagnostic.severity}>
      {diagnostic.severity === 'error' ? w('import.severity.error') : w('import.severity.notice')}
    </span>
    <code className="project-import-finding-path">{diagnostic.path}</code>
    <span className="project-import-finding-message">{diagnostic.message}</span>
    <code className="project-import-finding-code">{diagnostic.code}</code>
  </li>;
}

type ImportFailure = { message: string; code?: string; severity?: string };

/**
 * The server's own reasons, in the shape it sent them.
 *
 * The canonical validator answers with structured diagnostics that keep their
 * code, path and message, and those are kept: a field path is what tells a
 * reader where to look. A request-shape rejection from the same endpoint is a
 * Pydantic error with a location rather than a field path, so it is rendered as
 * its message beside the location it named. Anything else is shown as text.
 * Only the one sentence this file authors is localized; every path, code and
 * message the server sent is printed exactly as it arrived.
 */
function importFailures(detail: unknown, w: (key: WorkspaceKey, params?: Record<string, string | number>) => string): ImportFailure[] {
  if (!Array.isArray(detail)) return [];
  return detail.map(item => {
    if (typeof item === 'string') return { message: item };
    if (item && typeof item === 'object') {
      const record = item as Record<string, unknown>;
      if (typeof record.path === 'string' && typeof record.message === 'string') {
        return { message: w('workbench.error.validation', { path: record.path, message: record.message }),
          code: typeof record.code === 'string' ? record.code : undefined,
          severity: typeof record.severity === 'string' ? record.severity : undefined };
      }
      if (typeof record.msg === 'string') {
        const location = Array.isArray(record.loc) ? record.loc.join('.') : '';
        return { message: location ? w('workbench.error.validation', { path: location, message: record.msg }) : record.msg,
          code: typeof record.type === 'string' ? record.type : undefined, severity: 'error' };
      }
    }
    return { message: w('import.rejected') };
  });
}

function failureText(cause: unknown, w: (key: WorkspaceKey, params?: Record<string, string | number>) => string): ImportFailure[] {
  if (cause instanceof BackupFileError || cause instanceof SshipFileError) {
    return [{ message: w(cause.key, cause.params) }];
  }
  const detail = cause instanceof api.ApiError ? cause.detail : null;
  const fromServer = importFailures(detail, w);
  if (fromServer.length) return fromServer;
  if (typeof detail === 'string' && detail) return [{ message: detail }];
  if (cause instanceof Error && cause.message) return [{ message: cause.message }];
  return [{ message: w('import.failed') }];
}

function FailureList({ failures, w }: { failures: ImportFailure[]; w: (key: WorkspaceKey, params?: Record<string, string | number>) => string }) {
  return <ul className="project-import-failure-list">{failures.map((failure, index) =>
    <li key={index}>{failure.severity && <span className="project-import-finding-severity" data-severity={failure.severity}>
      {failure.severity === 'error' ? w('import.severity.error') : w('import.severity.notice')}
    </span>}<span>{failure.message}</span>{failure.code && <code>{failure.code}</code>}</li>)}</ul>;
}

type Phase = 'idle' | 'reading' | 'validating' | 'saving';

/**
 * Which chooser is in play.
 *
 * The two are kept apart deliberately. A reader who chooses a SpringSharp file
 * after a backup preview is starting again, not refining the backup, so the two
 * previews are never shown together and one choice always retires the other.
 */
type Source = 'backup' | 'sship';

export function ProjectImport({
  onOpen, busy: outsideBusy = false, isBlocked, onBusyChange,
}: {
  onOpen: (id: string) => void;
  /** Another creation is in flight elsewhere on the page; this one must wait. */
  busy?: boolean;
  /** Read the parent's lock before React has committed its busy state. */
  isBlocked?: () => boolean;
  /** Reports only this section's own work, never what it was told. */
  onBusyChange?: (busy: boolean) => void;
}) {
  const w = useWorkspaceCopy();
  /** Which chooser this section is currently working through, if either. */
  const [source, setSource] = useState<Source | null>(null);
  /** The chosen file, before the workspace server has seen it. */
  const [file, setFile] = useState<{ name: string; size: number } | null>(null);
  const [preview, setPreview] = useState<ProjectImportPreview | null>(null);
  const [migration, setMigration] = useState<SshipProjectImportPreview | null>(null);
  const [name, setName] = useState('');
  const [phase, setPhase] = useState<Phase>('idle');
  const [failure, setFailure] = useState<{cause: unknown} | null>(null);
  const failures = failure ? failureText(failure.cause, w) : [];

  /**
   * This section's lifetime and its current ticket. A file read, a preview and
   * a save each take a ticket when they start; only the holder of the newest
   * ticket, on a still-mounted section, may write to it.
   */
  const alive = useRef(true);
  const ticket = useRef(0);
  /** The parsed document behind the current preview, held for the save. */
  const document_ = useRef<ProjectDocument | null>(null);
  /**
   * The SpringSharp bytes behind the current preview, held for the save exactly
   * as they were read: never decoded, never re-read from disk, never replaced by
   * whatever the chooser holds when Save is finally pressed.
   */
  const source_ = useRef<SshipSourceFile | null>(null);
  /**
   * A synchronous lock for the save. The button's `disabled` is decided by a
   * render, so two submissions in one batch would both see it enabled; this
   * ref is set before the first await and is what actually prevents a second
   * project being created.
   */
  const phaseNow = useRef<Phase>('idle');
  const busyReporter = useRef(onBusyChange);
  busyReporter.current = onBusyChange;
  const input = useRef<HTMLInputElement>(null);
  const sourceInput = useRef<HTMLInputElement>(null);

  /** Busy because of this section's own work, which is all the parent is told. */
  const localBusy = phase !== 'idle';
  const saving = phase === 'saving';
  /**
   * The preview currently on screen, whichever reader produced it.
   *
   * A migration answer without its migration section is not a usable preview:
   * it cannot be confirmed, so it is treated as no answer at all rather than as
   * one with nothing in it.
   */
  const answered = source === 'sship' ? (migration?.migration ? migration : null) : preview;

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      ticket.current += 1;
      busyReporter.current?.(false);
    };
  }, []);

  function work(next: Phase) {
    phaseNow.current = next;
    setPhase(next);
    // Report synchronously so other creation handlers see the lock in this batch.
    busyReporter.current?.(next !== 'idle');
  }

  const current = (mine: number) => alive.current && ticket.current === mine;

  /**
   * Retire every step in flight and return the section to its first state.
   *
   * The ticket moves first, so work already on its way cannot write afterwards;
   * the local busy states are released here because nothing will release them
   * on the way out.
   */
  function reset() {
    if (phaseNow.current === 'saving') return;
    ticket.current += 1;
    document_.current = null;
    source_.current = null;
    setSource(null); setFile(null); setPreview(null); setMigration(null); setName('');
    work('idle'); setFailure(null);
    if (input.current) input.current.value = '';
    if (sourceInput.current) sourceInput.current.value = '';
  }

  /** Whether a chooser may start, checked before any input is taken out of it. */
  function mayChoose() {
    return !(outsideBusy || isBlocked?.() || phaseNow.current === 'saving');
  }

  /**
   * Forget whatever the other chooser had produced, before the new one starts.
   *
   * Dropping the previous preview here — rather than letting the new answer
   * overwrite it — is what stops a stale answer being shown against a new
   * filename, and what makes choosing a second file a replacement rather than
   * an addition.
   */
  function begin(next: Source, chosen: File) {
    const mine = ++ticket.current;
    document_.current = null;
    source_.current = null;
    setSource(next);
    setFile({ name: chosen.name, size: chosen.size });
    setPreview(null); setMigration(null); setName(''); setFailure(null);
    return mine;
  }

  async function choose(selected: File | undefined) {
    if (!selected || !mayChoose()) return;
    // The native input is cleared as soon as the file is taken out of it, so
    // choosing the very same file again after a failure still raises `change`.
    if (input.current) input.current.value = '';
    const mine = begin('backup', selected);
    work('reading');
    try {
      const backup = await readBackupFile(selected, w);
      if (!current(mine)) return;
      document_.current = backup.project as ProjectDocument;
      work('validating');
      const answer = await api.previewProjectImport(backup.project as ProjectDocument);
      if (!current(mine)) return;
      setPreview(answer);
      // The reader may accept the backup's own name or replace it.
      setName(answer.name);
    } catch (cause) {
      if (!current(mine)) return;
      outcome('hold');
      setFailure({cause});
    } finally {
      if (current(mine)) work('idle');
    }
  }

  /**
   * Read a SpringSharp source and ask the server what it holds.
   *
   * The bytes are sent as they were read, so what the server parses is the file
   * the reader chose. The browser learns the version, the digest and the field
   * dispositions and shows them; it decides nothing about the format, and the
   * preview it holds is a description rather than anything it can save on its
   * own.
   */
  async function chooseSship(selected: File | undefined) {
    if (!selected || !mayChoose()) return;
    if (sourceInput.current) sourceInput.current.value = '';
    const mine = begin('sship', selected);
    work('reading');
    try {
      const original = await readSshipFile(selected, w);
      if (!current(mine)) return;
      source_.current = original;
      work('validating');
      const answer = await api.previewSshipImport(original.filename, original.content_base64);
      if (!current(mine)) return;
      setMigration(answer);
      setName(answer.name);
    } catch (cause) {
      if (!current(mine)) return;
      outcome('hold');
      setFailure({cause});
    } finally {
      if (current(mine)) work('idle');
    }
  }

  async function save() {
    // Every reason to refuse is checked before anything is sent: no preview, a
    // read still running, another creation in flight, a save already started,
    // or a name the reader has not actually filled in. The required name is
    // never quietly replaced by the backup's own.
    if (phaseNow.current !== 'idle' || outsideBusy || isBlocked?.()) return;
    const confirmed = name.trim();
    if (!confirmed || confirmed.length > 200) return;
    const migrating = source === 'sship';
    const original = source_.current;
    const digest = migration?.migration?.source.sha256;
    if (migrating ? !(original && digest) : !(document_.current && preview)) return;
    const mine = ++ticket.current;
    work('saving');
    setFailure(null);
    try {
      let view: ProjectView;
      if (migrating && original && digest) {
        // The frozen bytes and the digest the reader was shown for them: the
        // server re-reads the file and refuses anything that no longer matches.
        const { filename, content_base64 } = original;
        assertEnvelopeFits({ filename, content_base64, source_sha256: digest, name: confirmed },
          w('import.envelopeLabel'), w);
        view = await api.importSshipProject(filename, content_base64, digest, confirmed);
      } else {
        const project = document_.current;
        if (!project) return;
        // Measured as it will be encoded, so an oversized request is refused here
        // rather than by a middleware the reader never sees.
        assertEnvelopeFits({ project, name: confirmed }, w('import.envelopeLabel'), w);
        view = await api.importProject(project, confirmed);
      }
      if (!current(mine)) return;
      outcome('resolve');
      onOpen(view.project_id);
    } catch (cause) {
      if (!current(mine)) return;
      outcome('hold');
      // The file, the preview and the entered name all survive, so this is a
      // retry rather than a restart.
      setFailure({cause});
    } finally {
      if (current(mine)) work('idle');
    }
  }

  const findings = preview ? preview.diagnostics : [];
  const shown = findings.slice(0, SHOWN_FINDINGS);
  const hidden = findings.length - shown.length;
  const disabled = localBusy || outsideBusy;
  const isMigration = source === 'sship';
  const busyPhase = phase === 'reading' || phase === 'validating';

  return <div className="project-import">
    <div className="project-import-pick">
      <label className="project-import-label" htmlFor="project-import-file">{w('import.pick.label')}</label>
      <input ref={input} id="project-import-file" className="project-import-file" type="file"
        accept=".json,application/json" disabled={saving || outsideBusy}
        aria-describedby="project-import-file-help"
        onChange={event => { const chosen = event.target.files?.[0]; void choose(chosen); }} />
      <p className="project-import-help" id="project-import-file-help">
        {w('import.pick.help')}
      </p>
      <label className="project-import-label" htmlFor="project-import-sship-file">{w('sship.pick.label')}</label>
      <input ref={sourceInput} id="project-import-sship-file" className="project-import-file" type="file"
        accept=".sship,.dat" disabled={saving || outsideBusy}
        aria-describedby="project-import-sship-file-help"
        onChange={event => { const chosen = event.target.files?.[0]; void chooseSship(chosen); }} />
      <p className="project-import-help" id="project-import-sship-file-help">
        {w('sship.pick.help')}
      </p>
      {file && <p className="project-import-file-name">
        <span className="project-import-file-name-text">{file.name}</span>
        <span className="project-import-file-size">{(file.size / 1024).toFixed(0)} KiB</span>
      </p>}
      {busyPhase && <p className="project-import-progress" role="status">
        {w('import.progress', { phase: w(`${isMigration ? 'sship' : 'import'}.progress.${phase}` as WorkspaceKey), name: file?.name ?? '' })}
      </p>}
      {file && !answered && <button type="button" className="button button--secondary" disabled={saving || outsideBusy}
        data-audio="manual" onClick={() => { reset(); (isMigration ? sourceInput : input).current?.focus(); }}>{w('import.cancel')}</button>}
    </div>

    {failures.length > 0 && <div className="notice notice--error project-import-failure" role="alert">
      <p className="project-import-failure-title">{w(`${isMigration ? 'sship' : 'import'}.failure.${answered ? 'saveTitle' : 'title'}` as WorkspaceKey)}</p>
      <FailureList failures={failures.slice(0, SHOWN_FINDINGS)} w={w} />
      {failures.length > SHOWN_FINDINGS && <details className="project-import-findings-more">
        <summary>{w('import.failure.more', { count: failures.length - SHOWN_FINDINGS })}</summary>
        <FailureList failures={failures.slice(SHOWN_FINDINGS)} w={w} />
      </details>}
    </div>}

    {answered && <div className="project-import-preview">
      {isMigration
        ? <SshipMigrationPreview preview={answered} w={w} />
        : <>
          <dl className="project-import-identity">
            <div><dt>{w('import.identity.name')}</dt><dd>{preview!.name}</dd></div>
            <div><dt>{w('import.identity.id')}</dt><dd><code>{preview!.source_id}</code></dd></div>
            <div><dt>{w('import.identity.revision')}</dt><dd>{w('workbench.chapter.revision', { revision: preview!.source_revision })}</dd></div>
            <div><dt>{w('import.identity.geometry')}</dt><dd>{preview!.geometry_kind && GEOMETRY_LABEL[preview!.geometry_kind]
              ? w(GEOMETRY_LABEL[preview!.geometry_kind])
              : w('import.geometry.undefined')}</dd></div>
          </dl>

          <dl className="project-import-counts">
            {COUNT_ROWS.map(row => <div key={row.key}>
              <dt>{w(row.label)}</dt><dd>{preview!.counts[row.key]}</dd>
            </div>)}
          </dl>

          <p className="project-import-note">{w('import.note')}</p>

          {findings.length > 0 && <div className="project-import-findings">
            <h3 className="project-import-findings-title">{w('import.findings.title', { count: findings.length })}</h3>
            <ul className="project-import-finding-list">
              {shown.map((diagnostic, index) => <Finding diagnostic={diagnostic} w={w} key={`${diagnostic.path}-${index}`} />)}
            </ul>
            {hidden > 0 && <details className="project-import-findings-more">
              <summary>{w('import.findings.more', { count: hidden })}</summary>
              <ul className="project-import-finding-list">
                {findings.slice(SHOWN_FINDINGS).map((diagnostic, index) =>
                  <Finding diagnostic={diagnostic} w={w} key={`more-${diagnostic.path}-${index}`} />)}
              </ul>
            </details>}
          </div>}
        </>}

      <form className="project-import-confirm" onSubmit={event => { event.preventDefault(); void save(); }}>
        <div className="project-import-name-field">
          <label className="project-import-label" htmlFor="project-import-name">{w(isMigration ? 'sship.confirm.label' : 'import.confirm.label')}</label>
          <input id="project-import-name" type="text" value={name} maxLength={200} required disabled={saving || outsideBusy}
            aria-describedby="project-import-name-help"
            onChange={event => setName(event.target.value)} />
          <p className="project-import-note" id="project-import-name-help">{w('import.confirm.nameHelp')}</p>
        </div>
        <p className="project-import-explain">{w(isMigration ? 'sship.confirm.explain' : 'import.confirm.explain')}</p>
        <div className="project-import-actions">
          <button type="submit" className="button button--primary" disabled={disabled || !name.trim() || name.trim().length > 200}>
            {saving ? w('workbench.save.busy') : w('import.confirm.submit')}
          </button>
          <button type="button" className="button button--secondary" data-audio="manual"
            disabled={saving || outsideBusy} onClick={() => { reset(); (isMigration ? sourceInput : input).current?.focus(); }}>{w('import.cancel')}</button>
        </div>
      </form>
    </div>}
  </div>;
}
