import { useEffect, useRef, type RefObject } from 'react';

/**
 * Preparing this report for paper, and putting the screen back afterwards.
 *
 * The browser raises `beforeprint` before it lays the page out, whether the
 * reader pressed the report's own button, the browser's print command or Ctrl+P,
 * so the preparation happens on that event and nowhere else. Nothing is printed
 * from a hidden state: the disclosures below are expanded by changing the
 * document's own `open` property, which is what the reader would see, and the
 * screen state each one had is remembered and put back on `afterprint`.
 *
 * Three things are deliberately not touched. The raw stage payload is never
 * opened for printing — a report may carry megabytes of iteration and geometry
 * arrays that belong on screen and in the export, not on paper. When the reader
 * has chosen the compact design scope, the material that scope leaves off the
 * paper is not opened either, so a hidden source appendix is never walked for a
 * sheet that will not show it. And React content that is only mounted for the
 * appendix is mounted by the caller through `deferred`, at the event boundary;
 * `flushSync` is used there and nowhere else.
 */

export type ReportPrintScope = 'design' | 'full';

export interface PrintDeferred {
  /** Mounts content that exists for the print, inside the beforeprint boundary. */
  mount(): void;
}

/** The raw stage payload: reachable on screen, never expanded for paper. */
export const RAW_DATA_CLASS = 'stage-raw-data';

/** Material the compact design scope leaves off the paper. */
export const SECONDARY_CLASS = 'print-secondary';

export function useReportPrint(root: RefObject<HTMLElement | null>, deferred?: PrintDeferred,
  scope: ReportPrintScope = 'full'): void {
  const original = useRef(new Map<HTMLDetailsElement, boolean>());
  const prepared = useRef(false);
  const deferredRef = useRef(deferred);
  deferredRef.current = deferred;
  const scopeRef = useRef(scope);
  scopeRef.current = scope;

  useEffect(() => {
    function excluded(node: HTMLDetailsElement, host: HTMLElement): boolean {
      // Ancestor-aware: a disclosure nested inside a hidden secondary region or
      // the raw payload is hidden with it, even though it carries no marker of
      // its own. Walking only the node itself would open a region the paper will
      // not show.
      let current: HTMLElement | null = node;
      while (current && current !== host) {
        if (current.classList.contains(RAW_DATA_CLASS)) return true;
        if (scopeRef.current === 'design' && current.classList.contains(SECONDARY_CLASS)) return true;
        current = current.parentElement;
      }
      return false;
    }

    function expandable(host: HTMLElement): HTMLDetailsElement[] {
      return Array.from(host.querySelectorAll<HTMLDetailsElement>('details'))
        .filter(node => !excluded(node, host));
    }

    function prepare() {
      const host = root.current;
      if (!host) return;
      // Only the disclosures the current scope will actually show are recorded
      // and opened; a node the scope excludes is never touched, so a later scope
      // switch cannot leave hidden material expanded.
      for (const node of expandable(host)) {
        if (!original.current.has(node)) original.current.set(node, node.open);
      }
      for (const node of expandable(host)) node.open = true;
      deferredRef.current?.mount();
      // Content that only exists because it was mounted for this print is
      // disclosed in the same way as the rest.
      for (const node of expandable(host)) {
        if (!original.current.has(node)) original.current.set(node, node.open);
        node.open = true;
      }
      prepared.current = true;
    }

    function restore() {
      if (!prepared.current) return;
      for (const [node, wasOpen] of original.current) node.open = wasOpen;
      original.current = new Map();
      prepared.current = false;
    }

    window.addEventListener('beforeprint', prepare);
    window.addEventListener('afterprint', restore);
    return () => {
      window.removeEventListener('beforeprint', prepare);
      window.removeEventListener('afterprint', restore);
    };
  }, []);
}
