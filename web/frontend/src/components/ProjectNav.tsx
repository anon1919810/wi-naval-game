import { useMemo, useState } from 'react';
import { useWorkspaceCopy, workspaceCopy, type WorkspaceKey } from '../i18n/workspace';

// The chapter index.
//
// Numbers are static page furniture; the two titles are application-owned
// words, so each is looked up from the workspace dictionary rather than being a
// literal in this file. The chapter id is a contract: it is what `onSelect`
// takes, what the JSON section keys are built from and what a followed
// diagnostic addresses, so it never changes with the language.
const CHAPTERS = [
  ['overview', undefined, 'chapter.overview'],
  ['hull', undefined, 'chapter.hull'],
  ['weights', undefined, 'chapter.weights'],
  ['armour', 'systems', 'chapter.armour'],
  ['guns', 'systems', 'chapter.guns'],
  ['weapons', 'systems', 'chapter.weapons'],
  ['stability', 'deck', 'chapter.stability'],
  ['propulsion', 'systems', 'chapter.propulsion'],
  ['performance', undefined, 'chapter.performance'],
  ['damage', 'flooding_scenarios', 'chapter.damage'],
  ['json', undefined, 'chapter.json'],
] as const;

export type Chapter = typeof CHAPTERS[number][0];

export interface ChapterDefinition {
  id: Chapter;
  /** The dictionary namespace whose `label` and `purpose` name this chapter. */
  namespace: string;
  /** Section key of the chapter JSON view, where the contract has one. */
  jsonKey?: string;
}

/**
 * One chapter in the reader's language.
 *
 * Both names come from the same dictionary namespace, so the index and the
 * chapter heading can never disagree: the `label` is the short name in the rail
 * and the `purpose` is the one sentence printed directly under the heading. A
 * chapter rendered alone, with no provider, gets the English pair it has always
 * printed.
 */
export interface LocalisedChapter extends ChapterDefinition {
  /** Accessible name of the chapter entry and the chapter heading. */
  label: string;
  /** One-sentence purpose, shown directly under the heading. */
  purpose: string;
}

const DEFINITIONS: readonly ChapterDefinition[] = CHAPTERS.map(([id, jsonKey, namespace]) => (
  { id, namespace, ...(jsonKey ? { jsonKey } : {}) }
));

/** Every chapter, in the canonical order, resolved in one language. */
export function chaptersIn(w: (key: WorkspaceKey) => string): LocalisedChapter[] {
  return DEFINITIONS.map(entry => ({
    ...entry,
    label: w(`${entry.namespace}.label` as WorkspaceKey),
    purpose: w(`${entry.namespace}.purpose` as WorkspaceKey),
  }));
}

/** One chapter in one language. `overview` is the fallback, as it always was. */
export function chapterOf(chapter: Chapter, w: (key: WorkspaceKey) => string): LocalisedChapter {
  const chapters = chaptersIn(w);
  return chapters.find(entry => entry.id === chapter) ?? chapters[0];
}

/** The chapters that own a raw-JSON view, and the project section each edits. */
export function chapterJsonKeys(): Partial<Record<Chapter, string>> {
  return Object.fromEntries(DEFINITIONS.filter(entry => entry.jsonKey).map(entry => [entry.id, entry.jsonKey!]));
}

/** Static two-digit index of a chapter; decorative, never part of the name. */
export function chapterNumber(chapter: Chapter): string {
  return String(DEFINITIONS.findIndex(entry => entry.id === chapter) + 1).padStart(2, '0');
}

export function ProjectNav({ name, active, onSelect, onBack }: {
  name: string; active: Chapter; onSelect: (chapter: Chapter) => void; onBack: () => void;
}) {
  const w = useWorkspaceCopy();
  // Resolved once per language rather than once per chapter: a language switch
  // changes this array and nothing else, so the selected chapter, the scroll
  // position and the unsaved draft all stay exactly where they were.
  const chapters = useMemo(() => chaptersIn(w), [w]);
  /**
   * The index filter, and why the word lives here rather than beside the chapter:
   * moving between chapters — including through a followed diagnostic — is a
   * change of `active`, not a remount, so a narrowed index stays narrowed and the
   * reader's word is still in the field when they come back to it.
   *
   * Escape gives the whole index back and Enter opens the first chapter still
   * standing. A chapter is view state, so neither can cost a draft or a prompt.
   */
  const [query, setQuery] = useState('');
  const needle = query.trim().toLowerCase();
  // The resolved name *and* its one-line purpose are both matched, so a reader who
  // remembers the sentence finds the chapter it belongs to. Both are already in
  // the current language, so one rule serves a Chinese word and a Latin one.
  const matches = needle
    ? chapters.filter(entry => `${entry.id} ${entry.label} ${entry.purpose} ${workspaceCopy('en', `${entry.namespace}.label` as WorkspaceKey)} ${workspaceCopy('en', `${entry.namespace}.purpose` as WorkspaceKey)} ${workspaceCopy('zh-CN', `${entry.namespace}.label` as WorkspaceKey)} ${workspaceCopy('zh-CN', `${entry.namespace}.purpose` as WorkspaceKey)}`.toLowerCase().includes(needle))
    : chapters;
  return <aside className="project-nav" aria-label={w('nav.label')}>
    <button className="nav-return" data-audio="manual" onClick={onBack}>← {w('nav.back').replace(/^←\s*/, '')}</button>
    <div className="nav-section-label">{w('nav.vessel')}</div>
    <div className="nav-project-name" title={name}>{name}</div>
    <div className="nav-section-label nav-section-label--chapters">{w('nav.chapters')}</div>
    <div className="nav-filter">
      <label className="visually-hidden" htmlFor="chapter-filter">{w('nav.filter.label')}</label>
      <input id="chapter-filter" type="search" autoComplete="off" value={query} placeholder={w('nav.filter.placeholder')}
        onChange={event => setQuery(event.target.value)}
        onKeyDown={event => {
          if (event.key === 'Escape') { setQuery(''); return; }
          if (event.key === 'Enter' && matches.length > 0) { event.preventDefault(); onSelect(matches[0].id); }
        }} />
      {needle && <span className="nav-filter-count" role="status">{w('nav.filter.matches', { count: matches.length, total: chapters.length })}</span>}
      {needle && <button type="button" className="text-button" data-audio="manual" onClick={() => setQuery('')}>{w('nav.filter.clear')}</button>}
    </div>
    {needle && matches.length === 0 && <p className="nav-filter-none">{w('nav.filter.none')}</p>}
    <nav>{matches.map(entry => <button key={entry.id}
      className={`nav-item ${active === entry.id ? 'nav-item--active' : ''}`}
      aria-current={active === entry.id ? 'page' : undefined}
      onClick={() => onSelect(entry.id)}>
      {/* The number is page furniture; the localized name is the name. */}
      <span className="nav-index" aria-hidden="true">{chapterNumber(entry.id)}</span>
      <span className="nav-label">{entry.label}</span>
    </button>)}</nav>
    <div className="nav-bottom"><span className="datum-icon" aria-hidden="true" />{w('nav.footer')}</div>
  </aside>;
}