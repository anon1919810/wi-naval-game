import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import * as api from '../api';
import { designFingerprint, type DraftSideState } from './designFeedbackModel';
import { shipDesignOf } from './sps3b3Model';
import type { ProjectDocument, ProjectView, ShipDesignResult } from '../types';

/**
 * The saved revision's own native preview, read once per saved identity.
 *
 * The workbench draft is previewed live by the design host; this hook answers
 * the other half of the comparison question — what the saved revision reads —
 * without sending a command or touching the draft. It is a read, so it may be
 * repeated by the reader, and it is keyed to the saved project, revision and the
 * design document's own content, so a save, a reload, a project switch, or a
 * same-revision replacement reads the new document exactly once.
 *
 * Two properties matter to the rest of the workbench:
 *
 * - **A stale answer never lands.** Every request carries a ticket, and only the
 *   answer whose ticket is still current is committed, so a reply for a project
 *   the reader already left is discarded.
 * - **The cache is bounded and never holds a failure.** A settled reading is
 *   reused across chapter switches, up to a handful of identities; a refusal is
 *   not cached, so the reader's retry performs a real second request.
 *
 * A project that declares no ship design needs no read at all: its state is
 * `absent`, and the panel says so in words rather than inventing a baseline.
 */
export interface SavedDesignPreview {
  state: DraftSideState;
  result: ShipDesignResult | null;
  /** The saved identity this reading belongs to, for evidence. */
  identity: string | null;
  /** Re-attempt the read, bypassing the cache. */
  retry: () => void;
}

/** How many settled saved revisions one open draft keeps around. */
const CACHE_LIMIT = 4;

interface Cached { state: 'ready' | 'absent'; result: ShipDesignResult | null }

export function useSavedDesignPreview(view: ProjectView | null | undefined): SavedDesignPreview {
  const project: ProjectDocument | null = view?.project ?? null;
  const identity = useMemo(() => {
    if (!project || !shipDesignOf(project)) return null;
    // A revision number alone is not the document identity: a save that keeps
    // the numeric revision but replaces the design's content is a new baseline,
    // and a reply for the old content must not land on it.
    return `${project.id}|${project.revision}|${designFingerprint(project)}`;
  }, [project]);

  const [attempt, setAttempt] = useState(0);
  const [entry, setEntry] = useState<{ identity: string; state: DraftSideState; result: ShipDesignResult | null } | null>(null);
  const cache = useRef(new Map<string, Cached>());
  const ticket = useRef(0);
  const projectRef = useRef<ProjectDocument | null>(project);
  projectRef.current = project;

  useEffect(() => {
    // Every run retires the one before it, including a cache hit that arrives
    // after a request for a different identity is already in flight.
    const mine = ++ticket.current;
    if (!identity) { setEntry(null); return; }
    const cached = cache.current.get(identity);
    if (cached) { setEntry({ identity, ...cached }); return; }
    const document = projectRef.current;
    if (!document) { setEntry(null); return; }
    setEntry({ identity, state: 'loading', result: null });
    api.designPreview(document).then(reply => {
      if (ticket.current !== mine) return;
      const result = reply.preview ?? null;
      const settled: Cached = { state: result ? 'ready' : 'absent', result };
      cache.current.set(identity, settled);
      while (cache.current.size > CACHE_LIMIT) {
        const oldest = cache.current.keys().next().value;
        if (oldest === undefined) break;
        cache.current.delete(oldest);
      }
      setEntry({ identity, ...settled });
    }).catch(() => {
      // A refusal is not cached: the retry below must reach the server again.
      if (ticket.current !== mine) return;
      setEntry({ identity, state: 'failed', result: null });
    });
    return () => { ticket.current += 1; };
  }, [identity, attempt]);

  const retry = useCallback(() => {
    if (identity) cache.current.delete(identity);
    setAttempt(value => value + 1);
  }, [identity]);

  const current = entry && entry.identity === identity ? entry : null;
  return {
    state: identity === null ? (project ? 'absent' : 'loading') : current ? current.state : 'loading',
    result: current?.result ?? null,
    identity,
    retry,
  };
}
