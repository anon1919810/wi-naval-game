import { useEffect, useState } from 'react';

import * as api from '../api';
import { StageStatus, STAGE_ORDER } from '../components/StageStatus';
import type { RunView } from '../types';

const LABELS: Record<RunView['status'], string> = {
  queued: '排队中', running: '计算中', completed: '计算完成', partial: '部分完成', canceled: '已取消', failed: '计算失败',
};

const TERMINAL = new Set<RunView['status']>(['completed', 'partial', 'canceled', 'failed']);

export function Run({ runId, onBack, onReport }: { runId: string; onBack: (projectId: string) => void; onReport: () => void }) {
  const [run, setRun] = useState<RunView | null>(null);
  const [error, setError] = useState('');
  const [canceling, setCanceling] = useState(false);

  useEffect(() => {
    let active = true;
    let timeout: ReturnType<typeof setTimeout> | null = null;
    async function refresh() {
      try {
        const current = await api.getRun(runId);
        if (!active) return;
        setRun(current);
        setError('');
        if (!TERMINAL.has(current.status)) timeout = setTimeout(refresh, 1500);
      } catch (cause) {
        if (!active) return;
        setError(cause instanceof Error ? cause.message : '无法读取运行');
      }
    }
    void refresh();
    return () => { active = false; if (timeout) clearTimeout(timeout); };
  }, [runId]);

  async function cancel() {
    if (!run || canceling) return;
    setCanceling(true);
    try { setRun(await api.cancelRun(runId)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : '取消失败'); }
    finally { setCanceling(false); }
  }

  return <main className="run-page page-pad"><button className="text-button" onClick={() => run && onBack(run.project_id)}>← 返回舰船</button><span className="section-kicker">RUN / {runId.slice(0, 8).toUpperCase()}</span><h1>计算运行</h1>
    {error && <div className="notice notice--error" role="alert">{error}</div>}
    {!run ? <div className="loading-skeleton" aria-label="正在读取运行" /> : <>
      <div className="run-summary"><div><span className="section-kicker">STATUS / 当前状态</span><h2>{LABELS[run.status]}</h2><p>工况 {run.condition_id} · 项目修订 {run.revision}</p></div><div><span>请求指纹</span><code>{run.request_fingerprint}</code><small>保存的输入快照不会随项目后续编辑变化</small></div></div>
      {(run.status === 'queued' || run.status === 'running') && <div className="run-pending"><span className="run-progress" aria-hidden="true"/><p>{run.status === 'queued' ? '已排队，等待计算工作进程。' : '计算正在后台执行，离开页面后可再打开此运行。'}</p><button className="button button--secondary" disabled={canceling || run.cancel_requested} onClick={cancel}>{run.cancel_requested ? '已请求取消' : '取消计算'}</button></div>}
      {run.error && <div className="notice notice--error" role="alert"><strong>{run.error.code}</strong><p>{run.error.message}</p></div>}
      {run.result && <><div className="run-result-heading"><div><span className="section-kicker">RESULT / 已存结果</span><h2>{run.result.status === 'partial' ? '部分结果可供复核' : run.result.status === 'canceled' ? '已保存取消前的结果' : '计算结果已保存'}</h2><p>计算完成不等于史实验证。逐阶段检查有效性、缺项与诊断。</p></div><button className="button button--primary" onClick={onReport}>查看完整报告 ↗</button></div>
        <div className="run-stage-preview">{Object.entries(run.result.stages).filter(([, stage]) => stage.requested).sort(([a], [b]) => STAGE_ORDER.indexOf(a) - STAGE_ORDER.indexOf(b)).slice(0, 4).map(([name, stage]) => <StageStatus key={name} name={name} stage={stage} />)}</div>
      </>}
    </>}
  </main>;
}
