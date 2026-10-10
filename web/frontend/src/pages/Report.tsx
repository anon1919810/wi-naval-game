import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { flushSync } from 'react-dom';

import * as api from '../api';
import { outcome } from '../audio/feedback';
import { DiagnosticAction, type GuidanceContext } from '../components/DiagnosticAction';
import { ReadFailure, ReadPending } from '../components/ReadPending';
import { ReportReadings } from '../components/ReportReadings';
import { requestedStages } from '../components/resultReading';
import { SourceInspector } from '../components/SourceInspector';
import { StageIndex } from '../components/StageIndex';
import { StageStatus, STAGE_LABELS } from '../components/StageStatus';
import { UnitProvider, useUnits } from '../components/UnitProvider';
import { useReportPrint } from '../components/useReportPrint';
import { CHOICES, classifyKey, DIMENSION_KEYS, type DisplayPreferences } from '../components/units';
import type { AnalysisResult, RunView, StageEnvelope } from '../types';

const RESULT_LABELS = { completed: '计算完成', partial: '部分完成', canceled: '已取消' } as const;

type Diagnostic = StageEnvelope['diagnostics'][number];

/** A finding that decides whether a number may be shown at all. */
const SEVERE = new Set(['error', 'critical', 'severe', 'fatal']);

/** How much a finding insists, so a stronger restatement is never folded away. */
const SEVERITY_RANK: Record<string, number> = { info: 0, note: 1, warning: 2, severe: 3, critical: 4, error: 5, fatal: 6 };

function blockingOf(item: Diagnostic): boolean {
  return (item as { blocking?: unknown }).blocking === true;
}

function isSerious(item: Diagnostic): boolean {
  return SEVERE.has(String(item.severity ?? '')) || blockingOf(item);
}

function severityRank(item: Diagnostic): number {
  return SEVERITY_RANK[String(item.severity ?? '').toLowerCase()] ?? 0;
}

/**
 * Evidence on two axes, never as one score: a blocking finding and a fatal
 * finding are different facts, so neither can cancel the other out.
 */
function strongerThan(candidate: Diagnostic, current: Diagnostic): boolean {
  if (blockingOf(candidate) !== blockingOf(current)) return blockingOf(candidate);
  return severityRank(candidate) > severityRank(current);
}

/** True when `child` carries this finding at least as firmly as the root copy. */
function dominated(child: Diagnostic, root: Diagnostic): boolean {
  return severityRank(child) >= severityRank(root) && (blockingOf(child) || !blockingOf(root));
}

/** What a finding says and where it belongs, by name, never by property order. */
function findingKey(item: Diagnostic, stage: string | null): string {
  return [stage ?? '', item.code ?? '', item.message ?? '', item.path ?? '', item.source_path ?? ''].join('|');
}

/**
 * The root findings that add something this report does not already show.
 *
 * A finding is matched by what it says and by the stage it belongs to, so a
 * stage's own copy of the same finding is not repeated above it — including when
 * the stage's copy carries no stage field of its own, and only when that copy is
 * at least as firm. Everything else stays: a root finding about a requested
 * stage that the stage never recorded, a restatement stronger than the stage's,
 * and of repeated root copies of one finding only the firmest is shown.
 */
function rootFindings(result: AnalysisResult, stages: Array<{ name: string; stage: StageEnvelope }>): Diagnostic[] {
  const found = new Map<string, Diagnostic>();
  for (const item of result.diagnostics ?? []) {
    const owner = item.stage ? stages.find(candidate => candidate.name === item.stage) : undefined;
    const children = owner?.stage.diagnostics ?? [];
    const key = findingKey(item, item.stage ?? null);
    if (children.some(child => findingKey(child, item.stage ?? null) === key && dominated(child, item))) continue;
    const current = found.get(key);
    // The same finding twice is one line, and it is the firmest reading of it.
    if (!current || strongerThan(item, current)) found.set(key, item);
  }
  return [...found.values()];
}

/** A diagnostic line: the message reads once, and its evidence stays beside it. */
function Finding({ item, fallback, guidance }: { item: Diagnostic; fallback: string; guidance: GuidanceContext | null }) {
  const message = item.message ?? item.code ?? fallback;
  // A code is evidence too, so it is kept rather than dropped whenever a message
  // happens to exist. Identical text is printed once, not twice.
  const code = item.code && item.code !== item.message ? item.code : null;
  return <p><strong>{message}</strong>
    {code && <code className="report-diagnostic-code">{code}</code>}
    {item.stage && <span className="report-diagnostic-stage">阶段 {STAGE_LABELS[item.stage] ?? item.stage}</span>}
    {item.path && <code>{item.path}</code>}
    {item.source_path && item.source_path !== item.path && <small>来源 {item.source_path}</small>}
    <DiagnosticAction diagnostic={item} context={guidance} project={guidance?.snapshot ?? null} />
  </p>;
}

function triState(value: boolean | null | undefined): string {
  return value === true ? '是 · 已声明' : value === false ? '否' : '未知 · 无结论';
}

function compareCompatible(left: AnalysisResult, right: AnalysisResult): boolean {
  return left.condition_id === right.condition_id
    && JSON.stringify(left.units) === JSON.stringify(right.units)
    && JSON.stringify(left.method_versions) === JSON.stringify(right.method_versions)
    && Object.entries(left.stages).every(([name, stage]) => {
      const other = right.stages[name];
      return !other || stage.status !== 'completed' || other.status !== 'completed'
        || JSON.stringify(stage.method_versions) === JSON.stringify(other.method_versions);
    });
}

function commonNumbers(left: AnalysisResult, right: AnalysisResult) {
  // Each row keeps its original key: the displayed name alone would lose whether
  // a value is an area, a volume, a mass or something that must stay canonical.
  const rows: Array<{ name: string; key: string; left: number; right: number }> = [];
  for (const [name, stage] of Object.entries(left.stages)) {
    const counterpart = right.stages[name];
    // Only a stage that was asked for and finished is a result. An unrequested
    // stage may still hold numbers, and those are not comparable values.
    if (stage.requested !== true || counterpart?.requested !== true) continue;
    if (stage.status !== 'completed' || counterpart?.status !== 'completed' || !stage.data || !counterpart.data) continue;
    for (const [key, value] of Object.entries(stage.data)) {
      const other = counterpart.data[key];
      // Only keys that are unambiguous quantities are compared: a force, a time,
      // a density or a rate would otherwise be shown as a length or a speed. A
      // number that is not finite on both sides is not a value to subtract.
      if (typeof value === 'number' && typeof other === 'number'
        && Number.isFinite(value) && Number.isFinite(other) && classifyKey(key)) {
        rows.push({ name: `${STAGE_LABELS[name] ?? name} / ${key}`, key, left: value, right: other });
      }
      if (rows.length >= 8) return rows;
    }
  }
  return rows;
}

export function Report({ result, runId, revision, compareResult, compareError, onBack }: {
  result: AnalysisResult; runId?: string; revision?: number; compareResult?: AnalysisResult;
  compareError?: string; onBack?: () => void;
}) {
  // A report is immutable: this local choice only re-wraps the page content in a
  // display provider. It never edits the stored snapshot, fingerprint or export.
  const [override, setOverride] = useState<Partial<DisplayPreferences>>({});
  return <UnitProvider preferences={{ ...(result.input_snapshot?.display_preferences as object ?? {}), ...override }}>
    <ReportBody result={result} runId={runId} revision={revision} compareResult={compareResult}
      compareError={compareError} onBack={onBack} override={override} onOverrideChange={setOverride} />
  </UnitProvider>;
}

function ReportBody({ result, runId, revision, compareResult, compareError, onBack, override, onOverrideChange }: {
  result: AnalysisResult; runId?: string; revision?: number; compareResult?: AnalysisResult; compareError?: string;
  onBack?: () => void; override: Partial<DisplayPreferences>; onOverrideChange: (next: Partial<DisplayPreferences>) => void;
}) {
  const units = useUnits();
  const host = useRef<HTMLDivElement>(null);
  // The provenance appendix is mounted when the reader opens it, or here for a
  // print. Once mounted it stays: it is read from one saved result, and the
  // disclosure it sits in returns to the state the reader left it in.
  const [auditMounted, setAuditMounted] = useState(false);
  const mountAudit = useCallback(() => setAuditMounted(true), []);
  useReportPrint(host, { mount: () => flushSync(() => setAuditMounted(true)) });
  const stages = useMemo(() => requestedStages(result), [result]);
  const compatible = !!compareResult && compareCompatible(result, compareResult);
  const compared = compareResult && compatible ? commonNumbers(result, compareResult) : [];
  const snapshot = result.input_snapshot;
  const shipName = snapshot?.name || result.project_id;
  const condition = snapshot?.loading_conditions?.find(item => item.id === result.condition_id);
  const savedRevision = revision ?? snapshot?.revision;
  // Root diagnostics only. A stage's own findings are already shown inside that
  // stage, so repeating them here would double both the count and the reading.
  const root = rootFindings(result, stages);
  const rootSevere = root.filter(isSerious);
  const rootOrdinary = root.filter(item => !isSerious(item));
  // A diagnostic only becomes a link where this page can name the project it
  // belongs to and the run that produced it. A standalone preview has neither,
  // and renders every finding exactly as it always has.
  const guidance: GuidanceContext | null = runId && result.project_id
    ? { projectId: result.project_id, runId, conditionId: result.condition_id, snapshot }
    : null;

  return <div className="report-page page-pad" ref={host}>
    <div className="report-actions no-print">
      {onBack && <button className="text-button" data-audio="manual" onClick={onBack}>← 返回运行</button>}
      <div className="report-action-group">
        {runId && <><a className="button button--secondary" href={api.exportUrl(runId, 'json')} download>导出 JSON</a><a className="button button--secondary" href={api.exportUrl(runId, 'csv')} download>导出 CSV</a></>}
        <button className="button button--secondary" onClick={() => window.print()}>打印报告</button>
      </div>
    </div>

    <header className="report-cover report-identity">
      <span className="section-kicker">REPORT / {runId ? `运行 ${runId.slice(0, 8).toUpperCase()}` : '独立预览'}</span>
      <h1>{shipName}</h1>
      <p>工况 {condition?.label || result.condition_id}{condition?.label && condition.label !== result.condition_id ? ` · ${result.condition_id}` : ''}
        {savedRevision ? ` · 保存修订 ${savedRevision}` : ''} · 运行 {runId ?? '预览'}</p>
      <div className="report-status-row">
        <span className={`stage-pill stage-pill--${result.status}`}>{RESULT_LABELS[result.status]}</span>
        <span>所请求阶段 {stages.length} 个</span>
        <span>完整性：{result.validity.complete ? '所请求阶段已完成' : '存在未完成阶段'}</span>
        <span>收敛：{triState(result.validity.converged)}</span>
        <span>模型适用性：{triState(result.validity.model_applicable)}</span>
        <span>史实验证：{triState(result.validity.historical_validated)}</span>
      </div>
      <p className="report-caveat">计算完成只表示模型执行情况，不代表史实、设计或适航认证。</p>
      <ReportUnitControls override={override} onChange={onOverrideChange} />
    </header>

    <ReportReadings result={result} />

    {(rootSevere.length > 0 || rootOrdinary.length > 0) && <section className="report-root-diagnostics" aria-label="整体诊断">
      {rootSevere.length > 0 && <div className="stage-diagnostics-open" role="alert">
        <strong>整体严重诊断 · {rootSevere.length} 条</strong>
        {rootSevere.map((item, index) => <Finding key={`${item.code ?? ''}-${index}`} item={item} fallback="严重诊断" guidance={guidance} />)}
      </div>}
      {rootOrdinary.length > 0 && <details className="report-root-diagnostics-fold"><summary>整体诊断与缺项 · {rootOrdinary.length} 条</summary>
        {rootOrdinary.map((item, index) => <Finding key={`${item.code ?? ''}-${index}`} item={item} fallback="诊断" guidance={guidance} />)}
      </details>}
    </section>}

    <div className="report-columns">
      {/* Locating only: the stages below stay one continuous body. */}
      <StageIndex page="reports" runId={runId} stages={stages} />
      <main className="report-main">
        <section className="report-section">
          <div className="section-heading"><h2>本次计算</h2><span>{stages.length} 个已请求阶段</span></div>
          <p className="report-intro">报告直接读取保存的不可变运行结果。灰色或警示状态不是零值，也不是“安全”结论。显示单位只影响本页呈现，导出与指纹仍为规范单位。</p>
          <div className="report-stage-list">{stages.map(({ name, stage }) =>
            <StageStatus key={name} name={name} stage={stage} guidance={guidance} />)}</div>
          {stages.length === 0 && <p>本次结果没有请求阶段。</p>}
        </section>

        {(compareResult || compareError) && <section className="report-section comparison-section">
          <div className="section-heading"><h2>两次运行对照</h2><span>先对齐口径，再比较值</span></div>
          {compareError
            ? <div className="notice notice--error" role="alert">{compareError}</div>
            : <>
              <div className="comparison-meta">
                <div><strong>当前运行</strong><span>工况 {result.condition_id}</span><span>单位 {JSON.stringify(result.units)}</span><span>方法 {JSON.stringify(result.method_versions)}</span><code>{result.request_fingerprint}</code></div>
                <div><strong>对照运行</strong><span>工况 {compareResult!.condition_id}</span><span>单位 {JSON.stringify(compareResult!.units)}</span><span>方法 {JSON.stringify(compareResult!.method_versions)}</span><code>{compareResult!.request_fingerprint}</code></div>
              </div>
              {!compatible ? <p className="comparison-warning">不可直接比较：工况、单位或方法版本不同。</p>
                : compared.length === 0 ? <p className="comparison-warning">没有两次均有效的同名数值，可查看各自阶段结果。</p>
                  : <table className="comparison-table"><thead><tr><th>指标</th><th>当前</th><th>对照</th><th>差值</th></tr></thead><tbody>{compared.map(row => <tr key={row.name}>
                    <th>{row.name}</th><td>{compareCell(units, row, row.left)}</td><td>{compareCell(units, row, row.right)}</td><td>{compareCell(units, row, row.right - row.left)}</td></tr>)}</tbody></table>}
            </>}
        </section>}

        <SourceInspector result={result} deferred={auditMounted} onOpen={mountAudit} />
        <footer className="report-footer">Plimsoll · 计算结果与来源保持同一请求指纹 · 本报告不替代史实或适航认证</footer>
      </main>
    </div>
  </div>;
}

// Both sides and the difference use the row's own key: an area stays an area, a
// volume stays a volume, and a stored kilogram mass is not read as tonnes.
function compareCell(units: ReturnType<typeof useUnits>, row: { key: string }, value: number): string {
  const kind = classifyKey(row.key);
  return kind ? units.text(value, kind.dimension, kind.storedUnit) : `${value}`;
}

// Report-local display controls. They change only what this page prints: the
// stored snapshot, its fingerprints and the exports stay exactly as saved.
function ReportUnitControls({ override, onChange }: {
  override: Partial<DisplayPreferences>; onChange: (next: Partial<DisplayPreferences>) => void;
}) {
  const units = useUnits();
  return <div className="report-units no-print">
    <span className="section-kicker">DISPLAY / 本页显示单位</span>
    {DIMENSION_KEYS.map(key => <label className="field-label" key={key}>
      {{ length: '长度', mass: '质量', power: '功率', speed: '航速', angle: '角度' }[key]}
      <select aria-label={`报告${key}显示单位`} value={String(override[key] ?? units.prefs[key])}
        onChange={event => {
          const value = event.target.value as DisplayPreferences[typeof key];
          const next: Record<string, string> = { ...override };
          if (value === units.prefs[key]) delete next[key]; else next[key] = value;
          onChange(next as Partial<DisplayPreferences>);
        }}>
        {CHOICES[key].map(choice => <option key={choice.value} value={choice.value}>{choice.label}</option>)}
      </select>
    </label>)}
    <small>规范单位（m / t / kW / kn / deg）与导出内容不变；本选择只影响本页显示。</small>
  </div>;
}

export function ReportPage({ runId, onBack }: { runId: string; onBack: () => void }) {
  const [run, setRun] = useState<RunView | null>(null);
  const [history, setHistory] = useState<RunView[]>([]);
  const [compareId, setCompareId] = useState('');
  const [compareResult, setCompareResult] = useState<AnalysisResult | undefined>();
  const [compareError, setCompareError] = useState('');
  const [compareBusy, setCompareBusy] = useState(false);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  // Late answers are rejected by ticket: a comparison that arrives after the
  // reader changed or cleared the selection is not the one they asked for.
  const comparison = useRef(0);
  const loading = useRef(0);

  useEffect(() => {
    let active = true;
    const ticket = ++loading.current;
    comparison.current += 1;
    // A different run starts from nothing: its own result, its own history and
    // its own comparison, with no error or unit choice carried over.
    setRun(null);
    setHistory([]);
    setCompareId('');
    setCompareResult(undefined);
    setCompareError('');
    setCompareBusy(false);
    setError('');
    api.getRun(runId).then(current => {
      if (!active || loading.current !== ticket) return;
      setRun(current);
      void api.listRuns(current.project_id).then(items => {
        if (!active || loading.current !== ticket) return;
        setHistory(items.filter(item => item.id !== runId && (item.status === 'completed' || item.status === 'partial')));
      }).catch(() => { /* Comparison list is optional; the stored report remains available. */ });
    }).catch(cause => { if (active && loading.current === ticket) setError(cause instanceof Error ? cause.message : '无法读取报告'); });
    return () => { active = false; loading.current += 1; comparison.current += 1; };
  }, [runId, attempt]);

  async function selectComparison(id: string) {
    const ticket = ++comparison.current;
    setCompareId(id);
    setCompareResult(undefined);
    setCompareError('');
    if (!id) { setCompareBusy(false); return; }
    setCompareBusy(true);
    try {
      const other = await api.getRun(id);
      if (comparison.current !== ticket) return;
      if (!other.result) throw new Error('对照运行尚无已保存结果');
      setCompareResult(other.result);
    } catch (cause) {
      if (comparison.current !== ticket) return;
      outcome('hold');
      setCompareError(cause instanceof Error ? cause.message : '无法读取对照运行');
    } finally {
      if (comparison.current === ticket) setCompareBusy(false);
    }
  }

  if (error) return <div className="page-pad">
    <ReadFailure title={`无法读取报告 ${runId}`} detail={error} retryLabel="重新读取报告"
      onRetry={() => { setError(''); setAttempt(current => current + 1); }} onBack={onBack} backLabel="← 返回运行" /></div>;
  if (!run) return <div className="page-pad"><ReadPending scope="report" object="计算报告" /></div>;
  if (!run.result) return <div className="page-pad"><h1>暂无计算报告</h1><p>此运行尚未保存结果，状态：{run.status}。</p><button className="text-button" data-audio="manual" onClick={onBack}>← 返回运行</button></div>;
  // A stored report is immutable: display units come from its own input snapshot.
  const preferences = run.result.input_snapshot?.display_preferences;
  return <>
    <div className="report-compare-control no-print">
      <label htmlFor="compare-run">对照另一运行</label>
      <select id="compare-run" value={compareId} onChange={event => { void selectComparison(event.target.value); }}>
        <option value="">暂不对照</option>
        {history.map(item => <option key={item.id} value={item.id}>修订 {item.revision} · {item.condition_id} · {item.id.slice(0, 8)}</option>)}
      </select>
      {compareBusy && <small className="report-compare-busy">正在读取对照运行…</small>}
    </div>
    <UnitProvider preferences={preferences}>
      {/* The page's own unit choice belongs to one saved result. Keying by its
          identity resets it for a different run, even when the next run loads so
          quickly that nothing ever unmounts. */}
      <Report key={`${runId}:${run.result.request_fingerprint}`} result={run.result} revision={run.revision} runId={runId}
        compareResult={compareResult} compareError={compareError} onBack={onBack} />
    </UnitProvider></>;
}
