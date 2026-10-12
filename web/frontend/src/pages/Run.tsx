import { useCopyMessage } from '../i18n/useCopyMessage';
import { useEffect, useRef, useState } from 'react';

import * as api from '../api';
import { outcome } from '../audio/feedback';
import { consumeRunRequest } from '../audio/interactionAudio';
import { ReadFailure, ReadPending } from '../components/ReadPending';
import { requestedStages } from '../components/resultReading';
import { StageIndex } from '../components/StageIndex';
import { StageStatus } from '../components/StageStatus';
import { UnitProvider } from '../components/UnitProvider';
import { useMomentText } from '../i18n/format';
import { useWorkspaceCopy, type WorkspaceKey } from '../i18n/workspace';
import type { RunView } from '../types';

/**
 * The run page: identity, the real run state, and every stage the run asked
 * for.
 *
 * There is no per-stage progress to show. The API answers with the run status
 * only, so a queued or running run gets a plain waiting notice and never a
 * percentage, a bar or a guess about which stage is computing. `cancel_requested`
 * is the server's own word that a cancellation was asked for, and it stays that
 * way until the server actually reports `canceled`: a requested cancellation is
 * never reported as a completed one.
 *
 * Reading the run and cancelling it are separate requests with separate errors:
 * a failing poll keeps the last loaded run on screen, and a failing cancel says
 * so on its own and can be retried, instead of being erased by the next poll.
 * Every response is tied to the run it was asked about, so a slow reply for a
 * previous run, a previous cancel or an unmounted page can never overwrite the
 * run in front of the reader.
 */

const STATUS_KEY: Record<RunView['status'], WorkspaceKey> = {
  queued: 'run.status.queued', running: 'run.status.running', completed: 'run.status.completed',
  partial: 'run.status.partial', canceled: 'run.status.canceled', failed: 'run.status.failed',
};

const TERMINAL = new Set<RunView['status']>(['completed', 'partial', 'canceled', 'failed']);
const POLL_MS = 1500;

export function Run({ runId, onBack, onReport }: { runId: string; onBack: (projectId: string) => void; onReport: () => void }) {
  const w = useWorkspaceCopy();
  const moment = useMomentText();
  const [run, setRun] = useState<RunView | null>(null);
  const [error, setError] = useCopyMessage();
  const [cancelError, setCancelError] = useCopyMessage();
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
        setError(w => cause instanceof Error ? cause.message : w('run.readFailedGeneric'));
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
      setCancelError(w => cause instanceof Error ? cause.message : w('run.cancel.failedGeneric'));
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
  const statusText = cancelPending ? w('run.status.cancelRequested') : run ? w(STATUS_KEY[run.status]) : '';

  const page = <main className="run-page page-pad">
    <button className="text-button" data-audio="manual" onClick={() => run && onBack(run.project_id)}>{w('run.back')}</button>
    {/* A read that never succeeded has no run to show, so it says so and offers
        exactly one explicit retry instead of a skeleton that never resolves. */}
    {error && !run
      ? <ReadFailure title={w('run.readFailed', { id: runId })} detail={error} onRetry={() => { setError(''); poll.current(); }} />
      : !run ? <ReadPending scope="run" object={w('run.pending.object')} /> : <>
      <div className="run-identity">
        <div className="run-identity-lead">
          <span className="section-kicker">RUN / {run.id.slice(0, 8).toUpperCase()}</span>
          <h1>{w('run.title')}</h1>
          {shipName && <p className="run-identity-ship">{shipName}</p>}
        </div>
        <dl className="run-identity-facts">
          <div><dt>{w('run.identity.id')}</dt><dd><code>{run.id}</code></dd></div>
          <div><dt>{w('run.identity.revision')}</dt><dd>{w('workbench.save.revision', { revision: run.revision })}</dd></div>
          <div><dt>{w('run.identity.condition')}</dt><dd>{conditionLabel}</dd></div>
        </dl>
      </div>

      <div className="run-status" role="status">
        <span className="section-kicker">{w('run.status.kicker')}</span>
        <h2>{statusText}</h2>
        {cancelPending && <p className="run-status-note">{w('run.status.cancelPending', { status: w(STATUS_KEY[run.status]) })}</p>}
        {waiting && <div className="run-pending">
          <span className="run-progress" data-status={run.status} aria-hidden="true" />
          <p>{run.status === 'queued' ? w('run.pending.queued') : w('run.pending.running')}</p>
          <button className="button button--secondary" disabled={canceling || (run.cancel_requested && !cancelError)} onClick={cancel}>
            {canceling ? w('run.cancel.busy') : cancelError ? w('run.cancel.retry') : run.cancel_requested ? w('run.cancel.requested') : w('run.cancel.action')}
          </button>
        </div>}
        {/* The server's own failure is evidence and is shown exactly as saved. */}
        {run.error && <div className="notice notice--error" role="alert"><strong>{run.error.code}</strong><p>{run.error.message}</p></div>}
        {/* A later read failure is added to the run already on screen, never
            in place of it. */}
        {error && run && <div className="notice notice--error" role="alert">{error}
          <button className="text-button" onClick={() => { setError(''); poll.current(); }}>{w('run.readAgain')}</button>
        </div>}
        {cancelError && <div className="notice notice--error" role="alert">{w('run.cancel.failed', { reason: cancelError })}</div>}
      </div>

      <details className="run-meta">
        <summary>{w('run.meta.summary')}</summary>
        <dl>
          <div><dt>{w('run.meta.fingerprint')}</dt><dd><code>{run.request_fingerprint}</code></dd></div>
          <div><dt>{w('run.meta.project')}</dt><dd><code>{run.project_id}</code></dd></div>
          <div><dt>{w('run.meta.created')}</dt><dd>{moment(run.created_at) ?? w('run.moment.missing')}</dd></div>
          <div><dt>{w('run.meta.started')}</dt><dd>{moment(run.started_at) ?? w('run.moment.missing')}</dd></div>
          <div><dt>{w('run.meta.finished')}</dt><dd>{moment(run.finished_at) ?? w('run.moment.missing')}</dd></div>
          <div><dt>{w('run.meta.cancelRequested')}</dt><dd>{run.cancel_requested ? w('run.meta.cancelYes') : w('run.meta.cancelNo')}</dd></div>
          <div><dt>{w('run.meta.serverStatus')}</dt><dd>{w(STATUS_KEY[run.status])}</dd></div>
        </dl>
      </details>

      {run.result && <>
        <div className="run-result-heading">
          <div><span className="section-kicker">{w('run.result.kicker')}</span>
            <h2>{run.result.status === 'partial' ? w('run.result.partial') : run.result.status === 'canceled' ? w('run.result.canceled') : w('run.result.saved')}</h2>
            <p>{w('run.result.note')}</p></div>
          <button className="button button--primary" data-audio="manual" onClick={onReport}>{w('run.result.report')}</button>
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
