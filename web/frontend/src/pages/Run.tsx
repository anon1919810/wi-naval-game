import { useEffect, useRef, useState } from 'react';

import * as api from '../api';
import { outcome } from '../audio/feedback';
import { consumeRunRequest } from '../audio/interactionAudio';
import { ReadFailure, ReadPending } from '../components/ReadPending';
import { requestedStages } from '../components/resultReading';
import { StageIndex } from '../components/StageIndex';
import { StageStatus } from '../components/StageStatus';
import { UnitProvider } from '../components/UnitProvider';
import type { RunView } from '../types';

/**
 * The run page: identity, the real run state, and every stage the run asked
 * for.
 *
 * There is no per-stage progress to show. The API answers with the run status
 * only, so a queued or running run gets a plain waiting notice and never a
 * percentage, a bar or a guess about which stage is computing. `cancel_requested`
 * is the server's own word that a cancellation was asked for, and it stays that
 * way until the server actually reports `canceled`: "已请求取消" is never
 * reported as "已取消".
 *
 * Reading the run and cancelling it are separate requests with separate errors:
 * a failing poll keeps the last loaded run on screen, and a failing cancel says
 * so on its own and can be retried, instead of being erased by the next poll.
 * Every response is tied to the run it was asked about, so a slow reply for a
 * previous run, a previous cancel or an unmounted page can never overwrite the
 * run in front of the reader.
 */

const LABELS: Record<RunView['status'], string> = {
  queued: '排队中', running: '计算中', completed: '计算完成', partial: '部分完成', canceled: '已取消', failed: '计算失败',
};

const TERMINAL = new Set<RunView['status']>(['completed', 'partial', 'canceled', 'failed']);
const POLL_MS = 1500;

function moment(value: string | null): string {
  return value ? new Date(value).toLocaleString('zh-CN') : '未记录';
}

export function Run({ runId, onBack, onReport }: { runId: string; onBack: (projectId: string) => void; onReport: () => void }) {
  const [run, setRun] = useState<RunView | null>(null);
  const [error, setError] = useState('');
  const [cancelError, setCancelError] = useState('');
  const [canceling, setCanceling] = useState(false);
  // Every request carries a ticket. A newer request, a new run or an unmount
  // invalidates the older ones, so a late reply is dropped instead of applied.
  const ticket = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const poll = useRef<() => void>(() => {});
  const reportOutcome = useRef<(next: RunView) => void>(() => {});

  useEffect(() => {
    let active = true;
    let observed = false;
    let announced = false;
    const resultCue = (next: RunView) => {
      observed = consumeRunRequest(runId) || observed || !TERMINAL.has(next.status);
      if (!observed || announced || !TERMINAL.has(next.status)) return;
      announced = true;
      outcome(next.status === 'completed' && next.result?.status === 'completed' ? 'resolve'
        : next.status === 'failed' ? 'hold' : 'detent');
    };
    reportOutcome.current = resultCue;
    const current = ++ticket.current;
    if (timer.current) { clearTimeout(timer.current); timer.current = null; }
    setRun(null);
    setError('');
    setCancelError('');
    setCanceling(false);

    async function refresh() {
      // The ticket is read when the request goes out, so the loop can be
      // resumed by a cancel attempt without being rejected as superseded.
      const issued = ticket.current;
      try {
        const next = await api.getRun(runId);
        if (!active || ticket.current !== issued) return;
        resultCue(next);
        setRun(next);
        setError('');
        if (!TERMINAL.has(next.status)) timer.current = setTimeout(refresh, POLL_MS);
      } catch (cause) {
        // The run already on screen stays there: a failed read adds a notice,
        // it does not replace the result the reader came for.
        if (!active || ticket.current !== issued) return;
        setError(cause instanceof Error ? cause.message : '无法读取运行');
      }
    }
    poll.current = () => { void refresh(); };
    void refresh();
    return () => {
      active = false;
      ticket.current += 1;
      if (timer.current) clearTimeout(timer.current);
      timer.current = null;
      poll.current = () => {};
      reportOutcome.current = () => {};
    };
  }, [runId]);

  async function cancel() {
    if (!run || canceling) return;
    setCanceling(true);
    // The cancel supersedes any poll still in flight, and stops the loop until
    // the server has answered.
    const current = ++ticket.current;
    if (timer.current) { clearTimeout(timer.current); timer.current = null; }
    try {
      const next = await api.cancelRun(runId);
      if (ticket.current !== current) return;
      reportOutcome.current(next);
      setRun(next);
      setCancelError('');
      // A terminal answer ends the run; anything else keeps being watched.
      if (!TERMINAL.has(next.status)) poll.current();
    } catch (cause) {
      if (ticket.current !== current) return;
      outcome('hold');
      setCancelError(cause instanceof Error ? cause.message : '取消失败');
      // The cancel took the read loop down with it; a refused cancel must not
      // leave the run unwatched, so the loop goes back to work.
      poll.current();
    } finally {
      if (ticket.current === current) setCanceling(false);
    }
  }

  const stages = run?.result ? requestedStages(run.result) : [];
  const snapshot = run?.result?.input_snapshot;
  const shipName = typeof snapshot?.name === 'string' && snapshot.name ? snapshot.name : '';
  const conditionLabel = snapshot?.loading_conditions?.find(item => item.id === run?.condition_id)?.label
    || run?.condition_id || '';
  const waiting = !!run && (run.status === 'queued' || run.status === 'running');
  // A cancellation that was only requested is still a running run.
  const cancelPending = waiting && run.cancel_requested;
  const statusText = cancelPending ? '已请求取消' : run ? LABELS[run.status] : '';

  const page = <main className="run-page page-pad">
    <button className="text-button" data-audio="manual" onClick={() => run && onBack(run.project_id)}>← 返回舰船</button>
    {/* A read that never succeeded has no run to show, so it says so and offers
        exactly one explicit retry instead of a skeleton that never resolves. */}
    {error && !run
      ? <ReadFailure title={`无法读取运行 ${runId}`} detail={error} onRetry={() => { setError(''); poll.current(); }} />
      : !run ? <ReadPending scope="run" object="运行" /> : <>
      <div className="run-identity">
        <div className="run-identity-lead">
          <span className="section-kicker">RUN / {run.id.slice(0, 8).toUpperCase()}</span>
          <h1>计算运行</h1>
          {shipName && <p className="run-identity-ship">{shipName}</p>}
        </div>
        <dl className="run-identity-facts">
          <div><dt>运行 id</dt><dd><code>{run.id}</code></dd></div>
          <div><dt>保存修订</dt><dd>修订 {run.revision}</dd></div>
          <div><dt>工况</dt><dd>{conditionLabel}</dd></div>
        </dl>
      </div>

      <div className="run-status" role="status">
        <span className="section-kicker">STATUS / 当前状态</span>
        <h2>{statusText}</h2>
        {cancelPending && <p className="run-status-note">已请求取消，等待服务端实际结束；当前服务端状态为 {LABELS[run.status]}。</p>}
        {waiting && <div className="run-pending">
          <span className="run-progress" data-status={run.status} aria-hidden="true" />
          <p>{run.status === 'queued' ? '已排队，等待计算工作进程。' : '计算正在后台执行，离开页面后可再打开此运行。'}</p>
          <button className="button button--secondary" disabled={canceling || (run.cancel_requested && !cancelError)} onClick={cancel}>
            {canceling ? '正在取消' : cancelError ? '重试取消' : run.cancel_requested ? '已请求取消' : '取消计算'}
          </button>
        </div>}
        {run.error && <div className="notice notice--error" role="alert"><strong>{run.error.code}</strong><p>{run.error.message}</p></div>}
        {/* A later read failure is added to the run already on screen, never
            in place of it. */}
        {error && run && <div className="notice notice--error" role="alert">{error}
          <button className="text-button" onClick={() => { setError(''); poll.current(); }}>重新读取</button>
        </div>}
        {cancelError && <div className="notice notice--error" role="alert">取消失败：{cancelError}</div>}
      </div>

      <details className="run-meta">
        <summary>运行元信息 · 指纹与时间</summary>
        <dl>
          <div><dt>请求指纹</dt><dd><code>{run.request_fingerprint}</code></dd></div>
          <div><dt>项目</dt><dd><code>{run.project_id}</code></dd></div>
          <div><dt>创建</dt><dd>{moment(run.created_at)}</dd></div>
          <div><dt>开始</dt><dd>{moment(run.started_at)}</dd></div>
          <div><dt>结束</dt><dd>{moment(run.finished_at)}</dd></div>
          <div><dt>取消请求</dt><dd>{run.cancel_requested ? '已请求' : '未请求'}</dd></div>
          <div><dt>服务端状态</dt><dd>{LABELS[run.status]}</dd></div>
        </dl>
      </details>

      {run.result && <>
        <div className="run-result-heading">
          <div><span className="section-kicker">RESULT / 已存结果</span>
            <h2>{run.result.status === 'partial' ? '部分结果可供复核' : run.result.status === 'canceled' ? '已保存取消前的结果' : '计算结果已保存'}</h2>
            <p>计算完成不等于史实验证。逐阶段检查有效性、缺项与诊断。</p></div>
          <button className="button button--primary" data-audio="manual" onClick={onReport}>查看完整报告 ↗</button>
        </div>
        {/* Every requested stage is reachable: nothing is truncated, and the
            damage evidence lives inside the flooding stage rather than in a
            second copy of it. */}
        {stages.length > 0 && <StageIndex page="runs" runId={runId} stages={stages} />}
        <div className="run-stage-list">{stages.map(({ name, stage }) =>
          <StageStatus key={name} name={name} stage={stage} />)}</div>
      </>}
    </>}
  </main>;
  // Display units come from the run's own stored snapshot, so a saved run always
  // reads the way it was analysed.
  return <UnitProvider preferences={run?.result?.input_snapshot?.display_preferences}>{page}</UnitProvider>;
}
