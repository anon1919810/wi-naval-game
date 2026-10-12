import { useMemo } from 'react';

import { provenanceGroups } from './sourceAudit';
import { useWorkspaceCopy, type WorkspaceKey } from '../i18n/workspace';
import type { AnalysisResult } from '../types';

/**
 * The audit trail at the end of the report.
 *
 * It sits inside the report body rather than in a third rail: at 1440 and 1024
 * a permanent side column would cost the reading column more than it gives. The
 * applicability flags stay in view because they decide how the numbers above may
 * be read; the long material — fingerprints, the saved sources, the method
 * versions and the provenance of every declared field — folds, and printing
 * opens it.
 *
 * The provenance appendix is walked from the saved payload rather than described,
 * and only when it is needed: a result can carry a very large payload, so it is
 * mounted when the reader opens it or when the report is printed. It says what
 * the payload declares and nothing more; it is not a claim of historical
 * confirmation.
 */
function triState(w: (key: WorkspaceKey, params?: any) => string, value: boolean | null | undefined): string {
  return value === true ? w('report.tri.yes') : value === false ? w('report.tri.no') : w('report.tri.unknown');
}

/**
 * The estimate state a declaration carries, in the reader's language.
 *
 * Three states stay three facts: an engineering estimate, a declared
 * non-estimate, and a state the payload never declared at all. The declaration
 * text beside it is the saved payload's own and is never rewritten.
 */
function estimateState(w: (key: WorkspaceKey, params?: any) => string, estimate: boolean | null): string {
  return estimate === true ? w('trace.estimate.estimate') : estimate === false ? w('trace.estimate.declared') : w('trace.estimate.unknown');
}

export function SourceInspector({ result, deferred = false, onOpen }: {
  result: AnalysisResult; deferred?: boolean; onOpen?: () => void;
}) {
  const w = useWorkspaceCopy();
  const groups = useMemo(() => (deferred ? provenanceGroups(result) : []), [deferred, result]);
  const paths = groups.reduce((total, group) => total + group.paths.length, 0);
  const requested = Object.values(result.stages ?? {}).filter(stage => stage?.requested === true).length;
  return <section className="report-sources report-audit" aria-label={w('audit.label')}>
    <div className="section-heading"><h2>{w('audit.title')}</h2><span>{w('audit.note')}</span></div>
    <dl className="report-audit-facts">
      <dt>{w('audit.complete')}</dt><dd>{result.validity.complete ? w('report.complete.all') : w('report.complete.some')}</dd>
      <dt>{w('audit.converged')}</dt><dd>{triState(w, result.validity.converged)}</dd>
      <dt>{w('audit.applicable')}</dt><dd>{triState(w, result.validity.model_applicable)}</dd>
      <dt>{w('audit.historical')}</dt><dd>{triState(w, result.validity.historical_validated)}</dd>
      <dt>{w('audit.requested')}</dt><dd>{w('audit.requestedCount', { count: requested })}</dd>
      {/* The request fingerprint identifies this report and stays in view; the
          two long input fingerprints fold. */}
      <dt>{w('audit.fingerprint')}</dt><dd><code>{result.request_fingerprint}</code></dd>
    </dl>
    <details className="report-audit-fold"><summary>{w('audit.fold.identities')}</summary>
      <dl className="report-audit-facts">
        <dt>{w('audit.projectFingerprint')}</dt><dd><code>{result.project_fingerprint}</code></dd>
        <dt>{w('audit.conditionFingerprint')}</dt><dd><code>{result.input_fingerprint}</code></dd>
        <dt>{w('audit.project')}</dt><dd><code>{result.project_id}</code></dd>
        <dt>{w('audit.condition')}</dt><dd><code>{result.condition_id}</code></dd>
      </dl>
    </details>
    <details className="report-audit-fold"><summary>{w('audit.fold.sources')}</summary>
      <pre>{JSON.stringify(result.sources, null, 2)}</pre>
    </details>
    <details className="report-audit-fold"><summary>{w('audit.fold.methods')}</summary>
      <pre>{JSON.stringify(result.method_versions, null, 2)}</pre>
    </details>
    {/* The walk is deferred on purpose: it reads the saved payload, which is
        large. The summary is always there so a reader can ask for it, and the
        content is mounted when they open it or when the report is printed. */}
    <details className="report-audit-fold report-provenance"
      onToggle={event => { if (event.currentTarget.open) onOpen?.(); }}>
      <summary>{deferred ? w('audit.fold.provenance', { groups: groups.length, paths }) : w('audit.fold.provenanceLazy')}</summary>
      {deferred && (groups.length === 0
        ? <p className="report-audit-empty">{w('audit.empty')}</p>
        : groups.map(group => <details className="report-audit-group" key={group.key}>
          <summary><span className="report-audit-declaration">{group.text}</span>
            <span className="report-audit-estimate">{estimateState(w, group.estimate)}</span>
            <span className="report-audit-count">{w('audit.count', { count: group.paths.length })}</span></summary>
          <ul className="report-audit-paths">{group.paths.map(path => <li key={path}><code>{path}</code></li>)}</ul>
        </details>))}
    </details>
    <p className="source-footnote">{w('audit.footnote')}</p>
  </section>;
}