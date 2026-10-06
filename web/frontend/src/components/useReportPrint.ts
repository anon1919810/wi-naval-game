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
 * Two things are deliberately not touched. The raw stage payload is never opened
 * for printing — a report may carry megabytes of iteration and geometry arrays
 * that belong on screen and in the export, not on paper. And React content that
 * is only mounted for the appendix is mounted by the caller through
 * `deferred`, at the event boundary; `flushSync` is used there and nowhere else.
 */
export interface PrintDeferred {
  /** Mounts content that exists for the print, inside the beforeprint boundary. */
  mount(): void;
}

/** The raw stage payload: reachable on screen, never expanded for paper. */
export const RAW_DATA_CLASS = 'stage-raw-data';

function expandable(root: ParentNode): HTMLDetailsElement[] {
  return Array.from(root.querySelectorAll<HTMLDetailsElement>('details'))
    .filter(node => !node.classList.contains(RAW_DATA_CLASS));
}

export function useReportPrint(root: RefObject<HTMLElement | null>, deferred?: PrintDeferred): void {
  const original = useRef(new Map<HTMLDetailsElement, boolean>());
  const prepared = useRef(false);
  const deferredRef = useRef(deferred);
  deferredRef.current = deferred;

  useEffect(() => {
    function capture(host: HTMLElement): void {
      // A disclosure is recorded the first time it is seen, so preparing twice
      // cannot record the open state the first preparation created.
      for (const node of expandable(host)) if (!original.current.has(node)) original.current.set(node, node.open);
    }

    function prepare() {
      const host = root.current;
      if (!host) return;
      capture(host);
      for (const node of original.current.keys()) node.open = true;
      deferredRef.current?.mount();
      // Content that only exists because it was mounted for this print is
      // disclosed in the same way as the rest.
      capture(host);
      for (const node of original.current.keys()) node.open = true;
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