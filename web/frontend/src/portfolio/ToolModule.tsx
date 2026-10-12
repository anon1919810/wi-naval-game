import { Component, type ReactNode } from 'react';

import type { ShellKey } from '../i18n/shell';

/**
 * Recovery for the workspace chunk.
 *
 * The application is fetched, so a dropped connection or a stale cached chunk can
 * fail the import itself. Retrying is offered exactly once and it is a real page
 * reload, because that is the only thing that can help: a failed dynamic import
 * is remembered by the browser's module map for the lifetime of the document, so
 * a second `import()` of the same URL — behind a new `React.lazy` or not — resolves
 * the very same rejection. Only a fresh document gets a fresh module map, and
 * only a fresh document can fetch the chunk again. Offering "retry the import"
 * here would be offering a button that cannot succeed.
 *
 * The boundary is scoped to the workspace subtree and nothing else. The public
 * shell is a sibling, so a failed chunk can never lock the home page, Work or
 * About, and the real public address is offered as the way out — that surface
 * never needed the chunk.
 *
 * Reloading also cannot mint a new identity: the module's own bootstrap asks
 * `/me` before it would create a workspace, so a reload re-enters through the
 * same path as the first load and adopts the existing browser session.
 */

interface Props {
  children: ReactNode;
  returnHref: string;
  /** Report that the module failed, so a later entry does not reuse it. */
  onFailure: () => void;
  /**
   * The four sentences this boundary prints, looked up by its caller.
   *
   * A class component cannot read a hook, so the copy arrives as a prop rather
   * than being hard-coded here. That keeps this panel in the visitor's chosen
   * language without teaching the module boundary about dictionaries.
   */
  copy: Readonly<Record<'title' | 'note' | 'reload' | 'returnLabel', string>>;
}

interface State { error: Error | null }

export class ToolModuleBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: unknown): State {
    return { error: error instanceof Error ? error : new Error('The workspace module could not be loaded') };
  }

  componentDidCatch(): void {
    this.props.onFailure();
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    const { title, note, reload, returnLabel } = this.props.copy;
    return <div className="ff-tool-error" role="alert">
      <strong>{title}</strong>
      <p className="ff-tool-error-detail">{error.message}</p>
      <p className="ff-tool-error-note">{note}</p>
      <div className="ff-tool-error-actions">
        <button type="button" className="button button--primary" onClick={() => window.location.reload()}>{reload}</button>
        <a className="ff-tool-return" href={this.props.returnHref}>{returnLabel}</a>
      </div>
    </div>;
  }
}

/** The keys a caller resolves to build {@link ToolModuleBoundary}'s `copy`. */
export const TOOL_MODULE_KEYS = {
  title: 'shell.module.title',
  note: 'shell.module.note',
  reload: 'shell.module.reload',
  returnLabel: 'shell.toolReturn',
} as const satisfies Record<string, ShellKey>;