import type { RunStatus, StageStatus } from '../types';

const LABELS: Record<RunStatus | StageStatus | 'estimate' | 'unknown', string> = {
  queued: '排队中', running: '计算中', completed: '已完成', partial: '部分完成',
  canceled: '已取消', failed: '失败', not_requested: '未请求',
  unavailable: '不可用', model_limit: '方法不适用', estimate: '估算', unknown: '未知',
};

export function StatusBadge({ status }: { status: keyof typeof LABELS }) {
  return <span className={`status-badge status-badge--${status}`}>{LABELS[status]}</span>;
}
