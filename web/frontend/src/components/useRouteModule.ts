import { useEffect, useRef, useState } from 'react';

/**
 * One lazily fetched route module.
 *
 * The workspace is split so the library can be read without downloading the
 * editors, the run reader and the report behind it. `React.lazy` is deliberately
 * not used: it caches the rejected promise of a failed chunk, so nothing behind
 * it can offer a recovery.
 *
 * A second `import()` of the same URL is not a recovery either. Once Chromium has
 * recorded a failed module fetch for that URL, a repeated import of it can be
 * answered straight from that record without touching the network, so a retry
 * button that only calls the loader again would often do nothing at all. The
 * recovery belongs at the document boundary instead: see {@link RouteChunk},
 * which offers an explicit reload that re-requests the chunk and keeps the hash
 * route and the session.
 *
 * Two properties this hook does own:
 *
 * - **A mounted page is not reloaded.** The loader is a module-scope constant, so
 *   a re-render for a language or theme change runs no effect and imports nothing
 *   again: the page that is on screen stays mounted with its draft.
 * - **A late module never lands on the wrong route.** Every attempt carries a
 *   ticket, and only the answer whose ticket is still current is committed, so a
 *   chunk that arrives after the reader has left is discarded.
 */

export type RouteModuleState<T> =
  | { status: 'loading'; module: null; error: null }
  | { status: 'ready'; module: T; error: null }
  | { status: 'error'; module: null; error: unknown };

export function useRouteModule<T>(load: () => Promise<T>): RouteModuleState<T> {
  const [state, setState] = useState<RouteModuleState<T>>({ status: 'loading', module: null, error: null });
  const ticket = useRef(0);

  useEffect(() => {
    const mine = ++ticket.current;
    let live = true;
    setState({ status: 'loading', module: null, error: null });
    load().then(
      module => { if (live && ticket.current === mine) setState({ status: 'ready', module, error: null }); },
      error => { if (live && ticket.current === mine) setState({ status: 'error', module: null, error }); },
    );
    return () => { live = false; ticket.current += 1; };
  }, [load]);

  return state;
}
