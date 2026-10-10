import { useEffect, useRef, useState } from 'react';

import * as api from '../api';
import { outcome } from '../audio/feedback';
import { assertEnvelopeFits, readBackupFile } from './backupFile';
import type { ProjectDiagnostic, ProjectDocument, ProjectImportPreview } from '../types';
import '../styles/projectImport.css';

/**
 * Restoring a project backup, in three explicit steps.
 *
 * A chosen file is read, then sent to the workspace server to validate, and the
 * answer is a description of what the file holds and what the canonical
 * validator still warns about. Only then may the reader confirm a name and ask
 * for it to be saved as a new project. Nothing is written before that button.
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
 */

/** Counts, in the order a reader reads a project: its conditions to its holes. */
const COUNT_ROWS = [
  { key: 'loading_conditions', label: '载荷工况' },
  { key: 'weight_groups', label: '重量分组' },
  { key: 'weight_items', label: '重量条目' },
  { key: 'damage_scenarios', label: '破损场景' },
  { key: 'compartments', label: '舱室' },
  { key: 'openings', label: '开口' },
] as const;

const GEOMETRY_LABEL: Record<string, string> = {
  offsets: '型值表（内嵌）',
  parameters: '参数化几何',
};

/** How many findings are shown before the rest move into a disclosure. */
const SHOWN_FINDINGS = 4;

/** One canonical validator finding, rendered as its own code, path and message. */
function Finding({ diagnostic }: { diagnostic: ProjectDiagnostic }) {
  return <li className="project-import-finding">
    <span className="project-import-finding-severity" data-severity={diagnostic.severity}>
      {diagnostic.severity === 'error' ? '错误' : '提示'}
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
 */
function importFailures(detail: unknown): ImportFailure[] {
  if (!Array.isArray(detail)) return [];
  return detail.map(item => {
    if (typeof item === 'string') return { message: item };
    if (item && typeof item === 'object') {
      const record = item as Record<string, unknown>;
      if (typeof record.path === 'string' && typeof record.message === 'string') {
        return { message: `${record.path}：${record.message}`,
          code: typeof record.code === 'string' ? record.code : undefined,
          severity: typeof record.severity === 'string' ? record.severity : undefined };
      }
      if (typeof record.msg === 'string') {
        const location = Array.isArray(record.loc) ? record.loc.join('.') : '';
        return { message: location ? `${location}：${record.msg}` : record.msg,
          code: typeof record.type === 'string' ? record.type : undefined, severity: 'error' };
      }
    }
    return { message: '工作区拒绝了该备份，请检查项目文档的结构。' };
  });
}

function failureText(cause: unknown): ImportFailure[] {
  const detail = cause instanceof api.ApiError ? cause.detail : null;
  const fromServer = importFailures(detail);
  if (fromServer.length) return fromServer;
  if (typeof detail === 'string' && detail) return [{ message: detail }];
  if (cause instanceof Error && cause.message) return [{ message: cause.message }];
  return [{ message: '导入失败，请检查备份文件后重试。' }];
}

function FailureList({ failures }: { failures: ImportFailure[] }) {
  return <ul className="project-import-failure-list">{failures.map((failure, index) =>
    <li key={index}>{failure.severity && <span className="project-import-finding-severity" data-severity={failure.severity}>
      {failure.severity === 'error' ? '错误' : '提示'}
    </span>}<span>{failure.message}</span>{failure.code && <code>{failure.code}</code>}</li>)}</ul>;
}

type Phase = 'idle' | 'reading' | 'validating' | 'saving';

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
  /** The chosen file, before the workspace server has seen it. */
  const [file, setFile] = useState<{ name: string; size: number } | null>(null);
  const [preview, setPreview] = useState<ProjectImportPreview | null>(null);
  const [name, setName] = useState('');
  const [phase, setPhase] = useState<Phase>('idle');
  const [failures, setFailures] = useState<ImportFailure[]>([]);

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
   * A synchronous lock for the save. The button's `disabled` is decided by a
   * render, so two submissions in one batch would both see it enabled; this
   * ref is set before the first await and is what actually prevents a second
   * project being created.
   */
  const phaseNow = useRef<Phase>('idle');
  const busyReporter = useRef(onBusyChange);
  busyReporter.current = onBusyChange;
  const input = useRef<HTMLInputElement>(null);

  /** Busy because of this section's own work, which is all the parent is told. */
  const localBusy = phase !== 'idle';
  const saving = phase === 'saving';

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
    setFile(null); setPreview(null); setName('');
    work('idle'); setFailures([]);
    if (input.current) input.current.value = '';
  }

  async function choose(selected: File | undefined) {
    if (!selected || outsideBusy || isBlocked?.() || phaseNow.current === 'saving') return;
    const mine = ++ticket.current;
    // The native input is cleared as soon as the file is taken out of it, so
    // choosing the very same file again after a failure still raises `change`.
    if (input.current) input.current.value = '';
    // Everything the previous file had produced is dropped before the new one
    // starts, so a stale answer can never be shown against a new filename.
    document_.current = null;
    setFile({ name: selected.name, size: selected.size });
    setPreview(null); setName(''); setFailures([]);
    work('reading');
    try {
      const backup = await readBackupFile(selected);
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
      setFailures(failureText(cause));
    } finally {
      if (current(mine)) work('idle');
    }
  }

  async function save() {
    const project = document_.current;
    // Every reason to refuse is checked before anything is sent: no preview, a
    // read still running, another creation in flight, a save already started,
    // or a name the reader has not actually filled in. The required name is
    // never quietly replaced by the backup's own.
    if (!project || !preview || phaseNow.current !== 'idle' || outsideBusy || isBlocked?.()) return;
    const confirmed = name.trim();
    if (!confirmed || confirmed.length > 200) return;
    const mine = ++ticket.current;
    work('saving');
    setFailures([]);
    try {
      // Measured as it will be encoded, so an oversized request is refused here
      // rather than by a middleware the reader never sees.
      assertEnvelopeFits({ project, name: confirmed }, '本次导入');
      const view = await api.importProject(project, confirmed);
      if (!current(mine)) return;
      outcome('resolve');
      onOpen(view.project_id);
    } catch (cause) {
      if (!current(mine)) return;
      outcome('hold');
      // The file, the preview and the entered name all survive, so this is a
      // retry rather than a restart.
      setFailures(failureText(cause));
    } finally {
      if (current(mine)) work('idle');
    }
  }

  const findings = preview ? preview.diagnostics : [];
  const shown = findings.slice(0, SHOWN_FINDINGS);
  const hidden = findings.length - shown.length;
  const disabled = localBusy || outsideBusy;

  return <div className="project-import">
    <div className="project-import-pick">
      <label className="project-import-label" htmlFor="project-import-file">选择项目备份 JSON</label>
      <input ref={input} id="project-import-file" className="project-import-file" type="file"
        accept=".json,application/json" disabled={saving || outsideBusy}
        aria-describedby="project-import-file-help"
        onChange={event => { const chosen = event.target.files?.[0]; void choose(chosen); }} />
      <p className="project-import-help" id="project-import-file-help">
        选择从项目页下载的项目 JSON 备份（上限 8 MiB）。文件会发送到工作区进行校验；确认后才保存为新项目。
      </p>
      {file && <p className="project-import-file-name">
        <span className="project-import-file-name-text">{file.name}</span>
        <span className="project-import-file-size">{(file.size / 1024).toFixed(0)} KiB</span>
      </p>}
      {(phase === 'reading' || phase === 'validating') && <p className="project-import-progress" role="status">
        {phase === 'reading' ? '正在读取备份' : '正在校验备份'}：{file?.name}…
      </p>}
      {file && !preview && <button type="button" className="button button--secondary" disabled={saving || outsideBusy}
        data-audio="manual" onClick={() => { reset(); input.current?.focus(); }}>取消</button>}
    </div>

    {failures.length > 0 && <div className="notice notice--error project-import-failure" role="alert">
      <p className="project-import-failure-title">{preview ? '保存失败，请重试' : '这个备份无法导入'}</p>
      <FailureList failures={failures.slice(0, SHOWN_FINDINGS)} />
      {failures.length > SHOWN_FINDINGS && <details className="project-import-findings-more">
        <summary>查看其余 {failures.length - SHOWN_FINDINGS} 条校验信息</summary>
        <FailureList failures={failures.slice(SHOWN_FINDINGS)} />
      </details>}
    </div>}

    {preview && <div className="project-import-preview">
      <dl className="project-import-identity">
        <div><dt>备份内名称</dt><dd>{preview.name}</dd></div>
        <div><dt>备份内 ID</dt><dd><code>{preview.source_id}</code></dd></div>
        <div><dt>备份内修订</dt><dd>修订 {preview.source_revision}</dd></div>
        <div><dt>几何</dt><dd>{preview.geometry_kind
          ? GEOMETRY_LABEL[preview.geometry_kind] ?? preview.geometry_kind
          : '未定义几何'}</dd></div>
      </dl>

      <dl className="project-import-counts">
        {COUNT_ROWS.map(row => <div key={row.key}>
          <dt>{row.label}</dt><dd>{preview.counts[row.key]}</dd>
        </div>)}
      </dl>

      <p className="project-import-note">以上是文件结构校验的结果，不代表计算已就绪或经过历史验证。</p>

      {findings.length > 0 && <div className="project-import-findings">
        <h3 className="project-import-findings-title">校验提示（{findings.length}）</h3>
        <ul className="project-import-finding-list">
          {shown.map((diagnostic, index) => <Finding diagnostic={diagnostic} key={`${diagnostic.path}-${index}`} />)}
        </ul>
        {hidden > 0 && <details className="project-import-findings-more">
          <summary>查看其余 {hidden} 条校验提示</summary>
          <ul className="project-import-finding-list">
            {findings.slice(SHOWN_FINDINGS).map((diagnostic, index) =>
              <Finding diagnostic={diagnostic} key={`more-${diagnostic.path}-${index}`} />)}
          </ul>
        </details>}
      </div>}

      <form className="project-import-confirm" onSubmit={event => { event.preventDefault(); void save(); }}>
        <div className="project-import-name-field">
          <label className="project-import-label" htmlFor="project-import-name">恢复后的项目名称</label>
          <input id="project-import-name" type="text" value={name} maxLength={200} required disabled={saving || outsideBusy}
            aria-describedby="project-import-name-help"
            onChange={event => setName(event.target.value)} />
          <p className="project-import-note" id="project-import-name-help">名称最多 200 个字符。</p>
        </div>
        <p className="project-import-explain">导入只恢复项目输入，不恢复运行记录；不会覆盖已有项目。</p>
        <div className="project-import-actions">
          <button type="submit" className="button button--primary" disabled={disabled || !name.trim() || name.trim().length > 200}>
            {saving ? '保存中…' : '保存为新项目'}
          </button>
          <button type="button" className="button button--secondary" data-audio="manual"
            disabled={saving || outsideBusy} onClick={() => { reset(); input.current?.focus(); }}>取消</button>
        </div>
      </form>
    </div>}
  </div>;
}
