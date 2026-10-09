import { useEffect, useState } from 'react';

/**
 * The one reading placeholder the workspace uses, and the one reading failure.
 *
 * Two honest thresholds, both short:
 *
 * - The decorative lines appear after {@link READ_SHIMMER_MS}. A request that
 *   answers faster than that renders no lines at all, so a cached project, a
 *   saved run or an already-loaded chunk never flashes a shimmer.
 * - After {@link READ_WAIT_MS} the notice adds what it is still waiting for, so
 *   a slow read is distinguishable from a stuck one. It names the same object it
 *   named from the start; it never invents progress, an estimate or a stage.
 *
 * The component never holds data and never delays it: a page renders it only
 * while it has nothing yet, and it disappears the moment the answer arrives.
 * Both timers are cleared on unmount, so a read that finishes at 80 ms leaves no
 * pending state behind.
 */

/** Which page is loading, so the placeholder echoes the real shape. */
export type ReadScope = 'library' | 'workbench' | 'run' | 'report' | 'workspace';

/** Decorative lines only: below this, a fast answer shows no shimmer at all. */
export const READ_SHIMMER_MS = 150;
/** Past this the notice adds the object it is still waiting for. */
export const READ_WAIT_MS = 2000;



export function ReadPending({ scope, object, className }: { scope: ReadScope; object: string; className?: string }) {
  const [decorated, setDecorated] = useState(false);
  const [waiting, setWaiting] = useState(false);
  useEffect(() => {
    const quick = window.setTimeout(() => setDecorated(true), READ_SHIMMER_MS);
    const slow = window.setTimeout(() => setWaiting(true), READ_WAIT_MS);
    return () => { window.clearTimeout(quick); window.clearTimeout(slow); };
  }, []);
  return <div className={`read-pending read-pending--${scope}${className ? ` ${className}` : ''}`}
    role="status" aria-busy="true" aria-label={`正在读取${object}`}>
    {decorated && <span className="read-pending-lines" aria-hidden="true">
      <ReadShape scope={scope} />
    </span>}
    <p className="read-pending-object">正在读取{object}</p>
    {waiting && <p className="read-pending-wait">仍在等待{object}的读取结果，已超过 2 秒。</p>}
  </div>;
}

/**
 * The placeholder is the page's own shape, not a grey slab: a list of ruled rows,
 * a chapter heading with input rows beneath it, a cover with its readings, an
 * index beside a body. Someone arriving at a slow page should recognise where
 * they are from the layout alone.
 *
 * Nothing here says anything about the data — no counts, no labels, no invented
 * values. It is purely the frame the real content will fill.
 */
function ReadShape({ scope }: { scope: ReadScope }) {
  switch (scope) {
    case 'library':
      return <span className="read-shape read-shape--rows">
        {[0, 1, 2].map(index => <span className="read-row" key={index}>
          <i className="read-row-mark" /><span className="read-row-body"><i className="read-line read-line--title" /><i className="read-line read-line--meta" /></span>
        </span>)}
      </span>;
    case 'workbench':
      return <span className="read-shape read-shape--editor">
        <span className="read-rail">{[0, 1, 2, 3].map(index => <i className="read-line read-line--nav" key={index} />)}</span>
        <span className="read-editor">
          <i className="read-line read-line--head" />
          <span className="read-toolbar"><i className="read-line read-line--bar" /><i className="read-line read-line--pill" /></span>
          <span className="read-fields">{[0, 1, 2].map(index => <i className="read-field" key={index} />)}</span>
        </span>
      </span>;
    case 'run':
      return <span className="read-shape read-shape--run">
        <span className="read-ident"><i className="read-line read-line--head" /><span className="read-facts"><i className="read-line read-line--fact" /><i className="read-line read-line--fact" /><i className="read-line read-line--fact" /></span></span>
        <i className="read-line read-line--section" />
        <span className="read-stages">{[0, 1].map(index => <i className="read-stage" key={index} />)}</span>
      </span>;
    case 'report':
      return <span className="read-shape read-shape--report">
        <span className="read-cover"><i className="read-line read-line--kicker" /><i className="read-line read-line--cover" /><i className="read-line read-line--meta" /></span>
        <span className="read-metrics">{[0, 1, 2, 3, 4, 5].map(index => <i className="read-metric" key={index} />)}</span>
        <span className="read-body"><span className="read-index">{[0, 1, 2, 3].map(index => <i className="read-line read-line--nav" key={index} />)}</span><span className="read-prose"><i className="read-line read-line--section" /><i className="read-line read-line--wide" /><i className="read-line read-line--wide" /></span></span>
      </span>;
    default:
      return <span className="read-shape read-shape--workspace">
        <i className="read-line read-line--wordmark" />
        <i className="read-line read-line--bar" />
        <i className="read-line read-line--meta" />
      </span>;
  }
}

export interface ReadFailureProps {
  /** What could not be read, named the way the address names it. */
  title: string;
  /** The server's own reason, already reduced to a sentence. */
  detail: string;
  /** One explicit retry. Reads may be repeated; a write may not be repeated silently. */
  onRetry: () => void;
  retryLabel?: string;
  /** In-place return, or a real address when this page has no parent to call back into. */
  onBack?: () => void;
  backHref?: string;
  backLabel?: string;
}

/**
 * A read that failed is the content, not a notice above it. There is no skeleton
 * behind this: a placeholder that cannot resolve is exactly what the reader must
 * not be left looking at. Retry stays on the page, and so does the way out.
 */
export function ReadFailure({ title, detail, onRetry, retryLabel = '重新读取', onBack, backHref, backLabel = '返回' }: ReadFailureProps) {
  return <div className="read-failed" role="alert">
    <strong>{title}</strong>
    <p className="read-failed-detail">{detail}</p>
    <div className="read-failed-actions">
      <button type="button" className="button button--primary" onClick={onRetry}>{retryLabel}</button>
      {onBack && <button type="button" className="button button--secondary" data-audio="manual" onClick={onBack}>{backLabel}</button>}
      {!onBack && backHref && <a className="button button--secondary" href={backHref}>{backLabel}</a>}
    </div>
  </div>;
}
