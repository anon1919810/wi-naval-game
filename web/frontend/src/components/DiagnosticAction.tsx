import { diagnosticHref, resolveDiagnosticLocation, type Diagnostic, type DiagnosticLocation } from './diagnosticGuidance';
import type { ProjectDocument } from '../types';

/**
 * The one control both surfaces offer on a diagnostic.
 *
 * In a report it is a real address — the project's own hash route plus the run
 * that produced the finding — so it can be copied, reopened and walked back to.
 * In the workspace it is a plain button, because the reader is already there and
 * a jump must never be a navigation. Either way it resolves the same path, and
 * it is simply absent when the path leads nowhere editable: a link to a field
 * that does not exist would be worse than no link.
 *
 * `project` is the project the finding is being resolved against, and it is
 * always named explicitly: the live draft in the workspace, the run's own saved
 * snapshot in a report, which has no other project in play. It is never
 * substituted for the other. A report link is re-resolved against the live
 * draft when it is followed, so a link offered for a saved run can still be
 * refused on arrival for an item that has since been removed.
 *
 * The control never carries the finding itself. The message, the code, the path,
 * the source path and the severity all stay exactly where the saved result put
 * them.
 */
export interface GuidanceContext {
  projectId: string;
  /** The saved run this finding belongs to. */
  runId: string;
  conditionId: string;
  /** The input snapshot that run was computed against. */
  snapshot: ProjectDocument | null;
}

export function DiagnosticAction({ diagnostic, context, project, onNavigate }: {
  diagnostic: Diagnostic;
  /** Absent renders the finding with no navigation at all. */
  context: GuidanceContext | null;
  /** The project this finding is resolved against. */
  project: ProjectDocument | null;
  /** The workspace's own jump: it is given the snapshot to re-resolve against. */
  onNavigate?: (location: DiagnosticLocation, snapshot: ProjectDocument | null) => void;
}) {
  if (!context) return null;
  const location = resolveDiagnosticLocation(diagnostic, { snapshot: context.snapshot, live: project });
  if (!location || location.kind === 'evidence' || !location.target) return null;
  const label = `${location.kind === 'control' ? '编辑' : '打开'}${location.label}`;
  if (onNavigate) {
    return <button type="button" className="diagnostic-action no-print" title={location.note}
      onClick={() => onNavigate(location, context.snapshot)}>{label}</button>;
  }
  return <a className="diagnostic-action no-print" title={location.note}
    href={diagnosticHref(context.projectId, context.runId, location.path)}>{label}</a>;
}