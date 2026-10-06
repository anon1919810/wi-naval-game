import { useCallback, useEffect, useRef } from 'react';

import { readStageTarget, stageHref } from './resultReading';
import { STAGE_LABELS } from './StageStatus';
import type { StageEnvelope } from '../types';

/**
 * Stage navigation, shared by the run and report pages.
 *
 * The index only locates: it never loads data, never watches a run and never
 * changes the reading order. With a run id every entry is a real link whose
 * address is the page's own hash route plus a `/stages/{name}` tail, so it can
 * be copied, reopened and bookmarked and still resolves to the same run. A
 * standalone report preview with no run id has no address to offer, so it uses
 * buttons instead of inventing one.
 *
 * A click scrolls to the section and moves the keyboard focus onto its heading,
 * because the reader asked for that section, and the browser then records the
 * address. A deep link only positions: it never takes focus away from wherever
 * the reader already is, and it never writes the address on its own. The hash is
 * read on mount and on `hashchange` only.
 */

/** A section is the positioning target the pages render; its heading takes focus. */
function sectionId(name: string): string {
  return `stage-${name}`;
}

/** Bounded wait: the target section may still be mounting, but not forever. */
const TARGET_ATTEMPTS = 30;

export interface StageIndexProps {
  page: 'runs' | 'reports';
  /** Absent only for a standalone preview that has no run address to offer. */
  runId?: string;
  stages: Array<{ name: string; stage: StageEnvelope }>;
}

function focusHeading(section: Element): boolean {
  const heading = section.querySelector('h1, h2, h3, h4') as HTMLElement | null;
  if (!heading) return false;
  // The pages render their headings with tabIndex={-1}; this only covers a
  // section whose heading does not declare one yet, so focus always lands.
  if (!heading.hasAttribute('tabindex')) heading.setAttribute('tabindex', '-1');
  heading.focus();
  return true;
}

function positionStage(name: string, takeFocus: boolean): boolean {
  const section = document.getElementById(sectionId(name));
  if (!section) return false;
  section.scrollIntoView();
  if (takeFocus) focusHeading(section);
  return true;
}

/**
 * Scrolls to a section as soon as it exists, retrying only while it may still
 * be mounting, and returns a cancel function for the pending frame.
 */
function positionWhenMounted(name: string, takeFocus: boolean, onDone: () => void): () => void {
  const frame: (task: () => void) => number = typeof requestAnimationFrame === 'function'
    ? task => requestAnimationFrame(() => { task(); })
    : task => setTimeout(task, 16) as unknown as number;
  const cancel: (handle: number) => void = typeof cancelAnimationFrame === 'function' ? cancelAnimationFrame : clearTimeout;
  let attempts = 0;
  let pending = 0;
  const attempt = () => {
    if (positionStage(name, takeFocus) || attempts++ >= TARGET_ATTEMPTS) { onDone(); return; }
    pending = frame(attempt);
  };
  pending = frame(attempt);
  return () => { cancel(pending); };
}

export function StageIndex({ page, runId, stages }: StageIndexProps) {
  const names = stages.map(item => item.name);
  // Only a stage this index lists can be positioned; an unknown or unrequested
  // target in the address leaves the reader exactly where they are.
  const known = new Set(names);
  const listed = names.join(' ');
  const pending = useRef<{ name: string; cancel: () => void } | null>(null);

  const go = useCallback((name: string) => {
    pending.current?.cancel();
    pending.current = null;
    if (!known.has(name)) return;
    if (positionStage(name, true)) return;
    pending.current = { name, cancel: positionWhenMounted(name, true, () => { pending.current = null; }) };
  }, [listed]);

  const follow = useCallback((hash: string) => {
    const target = runId ? readStageTarget(hash, page, runId) : null;
    // The click's own hashchange must retain its focus-taking retry. A newer
    // destination (including an invalid tail) cancels any older positioning.
    if (target && known.has(target) && pending.current?.name === target) return;
    pending.current?.cancel();
    pending.current = null;
    if (!target || !known.has(target)) return;
    if (positionStage(target, false)) return;
    pending.current = { name: target, cancel: positionWhenMounted(target, false, () => { pending.current = null; }) };
  }, [page, runId, listed]);

  useEffect(() => {
    follow(window.location.hash);
    const update = () => follow(window.location.hash);
    window.addEventListener('hashchange', update);
    return () => {
      window.removeEventListener('hashchange', update);
      pending.current?.cancel();
      pending.current = null;
    };
  }, [follow]);

  if (names.length === 0) return null;
  return <nav className="stage-index" aria-label="阶段索引">
    <ol>{names.map(name => {
      const label = STAGE_LABELS[name] ?? name;
      // A real address only where one exists: without a run id there is no run
      // page to link to, so the entry stays a button and still positions.
      return <li key={name}>{runId
        ? <a href={stageHref(page, runId, name)} onClick={() => go(name)}>{label}</a>
        : <button type="button" className="text-button" onClick={() => go(name)}>{label}</button>}
      </li>;
    })}</ol>
  </nav>;
}
