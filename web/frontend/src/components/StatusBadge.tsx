import type { RunStatus, StageStatus } from '../types';
import { useWorkspaceCopy } from '../i18n/workspace';

export function StatusBadge({ status }: { status: RunStatus | StageStatus | 'estimate' | 'unknown' }) {
  const w = useWorkspaceCopy();
  return <span className={`status-badge status-badge--${status}`}>{w(`badge.${status}` as Parameters<typeof w>[0])}</span>;
}