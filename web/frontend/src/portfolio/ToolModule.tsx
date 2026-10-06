import { Component, type ReactNode } from 'react';

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
}

interface State { error: Error | null }

export class ToolModuleBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: unknown): State {
    return { error: error instanceof Error ? error : new Error('工作空间模块未能加载') };
  }

  componentDidCatch(): void {
    this.props.onFailure();
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    return <div className="ff-tool-error" role="alert">
      <strong>工作空间未能加载</strong>
      <p className="ff-tool-error-detail">{error.message}</p>
      <p className="ff-tool-error-note">请重新载入页面以恢复工作空间。现有浏览器工作区会保留，也可以先返回公共页面。</p>
      <div className="ff-tool-error-actions">
        <button type="button" className="button button--primary" onClick={() => window.location.reload()}>重新载入页面</button>
        <a className="ff-tool-return" href={this.props.returnHref}>↖ Y’s Formfield</a>
      </div>
    </div>;
  }
}