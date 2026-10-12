import { useCopyMessage } from '../i18n/useCopyMessage';
import { useCallback, useEffect, useRef, useState } from 'react';

import * as api from '../api';
import { ProjectImport } from '../components/ProjectImport';
import { ReadFailure, ReadPending } from '../components/ReadPending';
import type { ProjectSummary } from '../types';
import { SiteGeometry } from '../portfolio/SiteGeometry';
import { outcome } from '../audio/feedback';
import { useDateText } from '../i18n/format';
import { storedTemplateName, useWorkspaceCopy, type WorkspaceKey } from '../i18n/workspace';

/**
 * The templates the library offers, as keys only.
 *
 * A card's name, tag and text are application-authored words on a page this
 * application writes, so they are bilingual dictionary entries. The name a
 * created project is *saved* under is a separate thing and stays the raw stored
 * name in either language — see `storedTemplateName`.
 */
const templates = ['analytic_box', 'generic_steamer', 'queen_mary_1913'] as const;

/**
 * Reading the library and creating a project are two different failures.
 *
 * A failed read ends the skeleton and the reading count together — a page that
 * still claims to be counting something it cannot read is lying — and it leaves
 * every creation entry usable, because nothing about a new project depends on
 * being able to list the old ones. A failed creation says only that the creation
 * failed, next to the entries that can be tried again.
 */
type Read = { status: 'loading' | 'failed' | 'ready'; projects: ProjectSummary[] };

/**
 * How long a creation has been refused for, in words. Nothing here is invented:
 * the answer is either the server's own or the generic fallback.
 */
function creationReason(cause: unknown, w: (key: WorkspaceKey, params?: any) => string): string {
  return cause instanceof Error && cause.message ? cause.message : w('library.creationFailedGeneric');
}

export function Library({ onOpen, onLab, anonymous = false }: { onOpen: (id: string) => void; onLab?: (id: string) => void; anonymous?: boolean }) {
  const w = useWorkspaceCopy();
  const date = useDateText();
  const [read, setRead] = useState<Read>({ status: 'loading', projects: [] });
  const [readError, setReadError] = useCopyMessage();
  const [createError, setCreateError] = useCopyMessage();
  const [creating, setCreating] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [name, setName] = useState('');
  const [query, setQuery] = useState('');
  const [attempt, setAttempt] = useState(0);
  /**
   * One creation at a time across the whole page. Restoring a backup saves a
   * project exactly as a template does, so the two must never overlap: without
   * this a reader could start a template and a restore together and be taken to
   * whichever answered first. Each side reports only its own work to the other —
   * the restore reports its reading and saving, the page reports `creating` —
   * so neither can latch itself busy through the other's state.
   */
  const busy = creating !== null || importing;
  /**
   * The page's own lifetime, and one ticket per request. A creation that is still
   * in flight when the reader leaves must not navigate a page that no longer
   * exists, and a failed one must not speak into an unmounted tree.
   */
  const alive = useRef(true);
  const readTicket = useRef(0);
  const createTicket = useRef(0);
  const creatingNow = useRef(false);
  const importingNow = useRef(false);
  const noteImport = useCallback((value: boolean) => {
    importingNow.current = value;
    if (alive.current) setImporting(value);
  }, []);
  const importBlocked = useCallback(() => creatingNow.current, []);

  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; readTicket.current += 1; createTicket.current += 1; };
  }, []);

  useEffect(() => {
    const ticket = ++readTicket.current;
    setRead(previous => ({ ...previous, status: 'loading' }));
    setReadError('');
    api.listProjects().then(items => {
      if (!alive.current || readTicket.current !== ticket) return;
      setRead({ status: 'ready', projects: items });
    }).catch(cause => {
      if (!alive.current || readTicket.current !== ticket) return;
      setRead({ status: 'failed', projects: [] });
      setReadError(w => cause instanceof Error ? cause.message : w('library.readFailedGeneric'));
    });
  }, [attempt]);

  async function create(template: string | null, initialName: string) {
    if (creatingNow.current || importingNow.current) return;
    creatingNow.current = true;
    const ticket = ++createTicket.current;
    setCreateError('');
    setCreating(template ?? 'blank');
    try {
      const saved = await api.createProject(template, initialName.trim());
      // The answer belongs to the page that asked, and only while it exists.
      if (!alive.current || createTicket.current !== ticket) return;
      outcome('resolve');
      onOpen(saved.project_id);
    } catch (cause) {
      if (!alive.current || createTicket.current !== ticket) return;
      outcome('hold');
      setCreateError(w => creationReason(cause, w));
    } finally {
      if (alive.current && createTicket.current === ticket) {
        creatingNow.current = false;
        setCreating(null);
      }
    }
  }

  const count = read.status === 'loading' ? w('library.count.loading')
    : read.status === 'failed' ? w('library.count.failed')
      : w('library.count.ready', { count: read.projects.length });

  /**
   * The filter is a view of the list already read, never a second request: the
   * reader's own project names are matched as they are stored, so a Chinese name
   * and a Latin one are narrowed by one rule and no row costs a request to keep.
   */
  const needle = query.trim().toLowerCase();
  const matches = needle ? read.projects.filter(project => project.name.toLowerCase().includes(needle)) : read.projects;

  return <main className="library-page page-pad">
    <aside className="library-context" aria-label={w('library.contextLabel')}>
      <header className="library-title"><span className="section-kicker">{w('library.kicker')}</span><h1>{w('library.title')}</h1><p>{w('library.ledeLine1')}<br />{w('library.ledeLine2')}</p></header>
      <div className="library-context-rule" aria-hidden="true"><SiteGeometry variant="rule" /></div>
      {anonymous && <div className="workspace-notice" role="note">
      <strong>{w('library.anonymous.title')}</strong>
      <p className="workspace-summary">{w('library.anonymous.summary')}</p>
      <details><summary>{w('library.anonymous.details')}</summary>
      <p>{w('library.anonymous.body')}</p>
      </details>
      </div>}
      <p className="library-context-foot">{w('library.contextFoot')}<br /><span>{w('library.contextFootNote')}</span></p>
      {onLab && <button className="button button--secondary" onClick={() => onLab('demo')}>{w('library.openLab')}</button>}
    </aside>
    <div className="library-body">
    {createError && <div className="notice notice--error library-create-error" role="alert">{w('library.createFailed', { reason: createError })}</div>}
    {/* First use, as a disclosure rather than a modal: it teaches the order of
        operations and never creates anything. It opens itself only on a
        confirmed, empty, freshly read library — where there is genuinely nothing
        else to read — and it stays a normal closed summary afterwards, so it is
        still findable once projects exist. */}
    <details className="first-use" open={read.status === 'ready' && read.projects.length === 0}>
      <summary>{w('library.firstUse.summary')}</summary>
      <ol className="first-use-steps">
        <li><strong>{w('library.firstUse.1.title')}</strong>{w('library.firstUse.1.text')}</li>
        <li><strong>{w('library.firstUse.2.title')}</strong>{w('library.firstUse.2.text')}</li>
        <li><strong>{w('library.firstUse.3.title')}</strong>{w('library.firstUse.3.text')}</li>
        <li><strong>{w('library.firstUse.4.title')}</strong>{w('library.firstUse.4.text')}</li>
      </ol>
      <button className="button first-use-cta" onClick={() => create('generic_steamer', storedTemplateName('generic_steamer'))} disabled={busy}>
        {creating === 'generic_steamer' ? w('library.firstUse.creating') : w('library.firstUse.cta')}
      </button>
    </details>
    <section className="library-section" aria-labelledby="my-projects-title">
      <div className="section-heading library-section-heading"><div><span className="section-kicker">{w('library.saved.kicker')}</span><h2 id="my-projects-title">{w('library.saved.title')}</h2></div><span data-read-state={read.status}>{count}</span><SiteGeometry /></div>
      {/* Offered only where there is something to sift: over an unread, failed or
          genuinely empty library it would be a control that cannot change
          anything, and its own empty state would be a second way of saying the
          library is empty. */}
      {read.status === 'ready' && read.projects.length > 0 && <div className="library-filter">
        <label className="visually-hidden" htmlFor="library-filter">{w('library.filter.label')}</label>
        <input id="library-filter" type="search" autoComplete="off" value={query} placeholder={w('library.filter.placeholder')} onChange={event => setQuery(event.target.value)} />
        {needle && <span className="library-filter-count" role="status">{w('library.filter.matches', { count: matches.length, total: read.projects.length })}</span>}
        {needle && <button type="button" className="text-button" onClick={() => setQuery('')}>{w('library.filter.clear')}</button>}
      </div>}
      {read.status === 'loading' ? <ReadPending scope="library" object={w('shell.place.library')} className="library-read" />
        : read.status === 'failed' ? <ReadFailure title={w('library.readFailed')} detail={readError} retryLabel={w('library.readFailed.retry')}
            onRetry={() => setAttempt(current => current + 1)} onBack={undefined} />
          : read.projects.length === 0
        ? <div className="empty-state"><span className="empty-glyph" aria-hidden="true">⌁</span><h3>{w('library.empty.title')}</h3><p>{w('library.empty.text')}</p></div>
          : matches.length === 0
        ? <div className="empty-state"><span className="empty-glyph" aria-hidden="true">⌁</span><h3>{w('library.filter.none.title')}</h3><p>{w('library.filter.none.text', { query: query.trim(), total: read.projects.length })}</p><button type="button" className="text-button" onClick={() => setQuery('')}>{w('library.filter.none.clear')}</button></div>
        : <div className="project-list">{matches.map(project => <button key={project.project_id} className="project-row" data-audio="manual" onClick={() => onOpen(project.project_id)}>
            <span className="project-row-mark" aria-hidden="true" /><span className="project-row-main"><strong>{project.name}</strong><small>{w('library.row.meta', { revision: project.revision, date: date(project.updated_at) ?? '' })}</small></span><span aria-hidden="true">↗</span>
          </button>)}</div>}
    </section>
    <section className="library-section" aria-labelledby="template-title">
      <div className="section-heading library-section-heading"><div><span className="section-kicker">{w('library.new.kicker')}</span><h2 id="template-title">{w('library.new.title')}</h2></div><span>{w('library.new.note')}</span><SiteGeometry /></div>
      <div className="template-grid">{templates.map((key, index) => <button className="template-card" key={key} onClick={() => create(key, storedTemplateName(key))} disabled={busy}>
        <span className="template-number">0{index + 1}</span><span className="template-identity"><strong>{w(`library.template.${key}.name` as WorkspaceKey)}</strong><span className="template-tag">{w(`library.template.${key}.tag` as WorkspaceKey)}</span></span><p>{w(`library.template.${key}.text` as WorkspaceKey)}</p><span className="template-action">{creating === key ? w('library.template.creating') : w('library.template.create')}</span>
      </button>)}</div>
      <form className="blank-project" onSubmit={event => { event.preventDefault(); if (name.trim()) void create(null, name); }}>
        <div><strong>{w('library.blank.title')}</strong><p>{w('library.blank.text')}</p></div>
        <label className="visually-hidden" htmlFor="blank-name">{w('library.blank.label')}</label><input id="blank-name" required value={name} onChange={event => setName(event.target.value)} placeholder={w('library.blank.label')} />
        <button className="button button--secondary" disabled={busy || !name.trim()} type="submit">{creating === 'blank' ? w('library.template.creating') : w('library.blank.create')}</button>
      </form>
    </section>
    <section className="library-section" aria-labelledby="restore-title">
      <div className="section-heading library-section-heading"><div><span className="section-kicker">{w('library.restore.kicker')}</span><h2 id="restore-title">{w('library.restore.title')}</h2></div><span>{w('library.restore.note')}</span><SiteGeometry /></div>
      <ProjectImport onOpen={onOpen} busy={creating !== null} isBlocked={importBlocked} onBusyChange={noteImport} />
    </section>
    </div>
  </main>;
}
