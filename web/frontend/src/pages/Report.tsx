import { useEffect, useState } from 'react';

import * as api from '../api';
import { ShipProfile } from '../components/ShipProfile';
import { SourceInspector } from '../components/SourceInspector';
import { StageStatus, STAGE_LABELS, STAGE_ORDER } from '../components/StageStatus';
import { StabilityPlot } from '../components/StabilityPlot';
import { UnitProvider, useUnits } from '../components/UnitProvider';
import { CHOICES, classifyKey, DIMENSION_KEYS, type DisplayPreferences } from '../components/units';
import type { AnalysisResult, RunView } from '../types';

const RESULT_LABELS = { completed: '计算完成', partial: '部分完成', canceled: '已取消' } as const;

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
    if (stage.status !== 'completed' || counterpart?.status !== 'completed' || !stage.data || !counterpart.data) continue;
    for (const [key, value] of Object.entries(stage.data)) {
      const other = counterpart.data[key];
      // Only keys that are unambiguous quantities are compared: a force, a time,
      // a density or a rate would otherwise be shown as a length or a speed.
      if (typeof value === 'number' && typeof other === 'number' && classifyKey(key)) {
        rows.push({ name: `${STAGE_LABELS[name] ?? name} / ${key}`, key, left: value, right: other });
      }
      if (rows.length >= 8) return rows;
    }
  }
  return rows;
}

export function Report({ result, runId, compareResult, onBack }: {
  result: AnalysisResult; runId?: string; compareResult?: AnalysisResult; onBack?: () => void;
}) {
  // A report is immutable: this local choice only re-wraps the page content in a
  // display provider. It never edits the stored snapshot, fingerprint or export.
  const [override, setOverride] = useState<Partial<DisplayPreferences>>({});
  return <UnitProvider preferences={{ ...(result.input_snapshot?.display_preferences as object ?? {}), ...override }}>
    <ReportBody result={result} runId={runId} compareResult={compareResult} onBack={onBack}
      override={override} onOverrideChange={setOverride} />
  </UnitProvider>;
}

function ReportBody({ result, runId, compareResult, onBack, override, onOverrideChange }: {
  result: AnalysisResult; runId?: string; compareResult?: AnalysisResult; onBack?: () => void;
  override: Partial<DisplayPreferences>; onOverrideChange: (next: Partial<DisplayPreferences>) => void;
}) {
  const units = useUnits();
  const requested = Object.entries(result.stages).filter(([, stage]) => stage.requested)
    .sort(([a], [b]) => STAGE_ORDER.indexOf(a) - STAGE_ORDER.indexOf(b));
  const compatible = compareResult ? compareCompatible(result, compareResult) : false;
  const compared = compareResult && compatible ? commonNumbers(result, compareResult) : [];
  const name = result.input_snapshot?.name || result.project_id;
  return <div className="report-page page-pad">
    <div className="report-actions no-print">{onBack && <button className="text-button" onClick={onBack}>← 返回运行</button>}<div>
      {runId && <><a className="button button--secondary" href={api.exportUrl(runId, 'json')} download>导出 JSON</a><a className="button button--secondary" href={api.exportUrl(runId, 'csv')} download>导出 CSV</a></>}
      <button className="button button--secondary" onClick={() => window.print()}>打印报告</button>
    </div></div>
    <header className="report-cover"><span className="section-kicker">PLIMSOLL / CALCULATION REPORT</span><span className="report-number">运行 {runId?.slice(0, 8) ?? '预览'}</span><h1>{name}</h1><p>工况 {result.condition_id} · 计算报告</p><div className="report-status-row"><span className={`stage-pill stage-pill--${result.status}`}>{RESULT_LABELS[result.status]}</span><span>所请求阶段 {requested.length} 个</span><span>史实验证：{result.validity.historical_validated === true ? '已声明验证' : '未验证 / 无结论'}</span></div>
      {name.toLowerCase().includes('queen mary') && <div className="report-caveat">HMS Queen Mary 工程代理 · 史实未认证。资料不足的数值继续保持未知。</div>}
      <ReportUnitControls override={override} onChange={onOverrideChange} />
      <ShipProfile />
    </header>
    <div className="report-columns"><main className="report-main"><section className="report-section"><div className="section-heading"><h2>本次计算</h2><span>{requested.length} / {Object.keys(result.stages).length} 阶段已请求</span></div><p className="report-intro">报告直接读取保存的不可变运行结果。灰色或警示状态不是零值，也不是“安全”结论。显示单位只影响本页呈现，导出与指纹仍为规范单位。</p>
      <div className="report-stage-list">{requested.map(([name, stage]) => <StageStatus key={name} name={name} stage={stage} />)}</div>
      {requested.length === 0 && <p>本次结果没有请求阶段。</p>}
    </section>
    {result.stages.gz?.requested && <StabilityPlot stage={result.stages.gz} />}
    {compareResult && <section className="report-section comparison-section"><div className="section-heading"><h2>两次运行对照</h2><span>先对齐口径，再比较值</span></div><div className="comparison-meta"><div><strong>当前运行</strong><span>工况 {result.condition_id}</span><span>单位 {JSON.stringify(result.units)}</span><span>方法 {JSON.stringify(result.method_versions)}</span><code>{result.request_fingerprint}</code></div><div><strong>对照运行</strong><span>工况 {compareResult.condition_id}</span><span>单位 {JSON.stringify(compareResult.units)}</span><span>方法 {JSON.stringify(compareResult.method_versions)}</span><code>{compareResult.request_fingerprint}</code></div></div>
      {!compatible ? <p className="comparison-warning">不可直接比较：工况、单位或方法版本不同。</p> : compared.length === 0 ? <p className="comparison-warning">没有两次均有效的同名数值，可查看各自阶段结果。</p> : <table className="comparison-table"><thead><tr><th>指标</th><th>当前</th><th>对照</th><th>差值</th></tr></thead><tbody>{compared.map(row => <tr key={row.name}><th>{row.name}</th><td>{compareCell(units, row, row.left)}</td><td>{compareCell(units, row, row.right)}</td><td>{compareCell(units, row, row.right - row.left)}</td></tr>)}</tbody></table>}
    </section>}
    <footer className="report-footer">Plimsoll · 计算结果与来源保持同一请求指纹 · 本报告不替代史实或适航认证</footer></main><SourceInspector result={result} /></div>
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
  const [compareResult, setCompareResult] = useState<AnalysisResult | undefined>();
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    api.getRun(runId).then(current => {
      if (!active) return;
      setRun(current);
      void api.listRuns(current.project_id).then(items => { if (active) setHistory(items.filter(item => item.id !== runId && (item.status === 'completed' || item.status === 'partial'))); })
        .catch(() => { /* Comparison list is optional; the stored report remains available. */ });
    }).catch(cause => { if (active) setError(cause instanceof Error ? cause.message : '无法读取报告'); });
    return () => { active = false; };
  }, [runId]);

  async function selectComparison(id: string) {
    setCompareResult(undefined);
    if (!id) return;
    try {
      const other = await api.getRun(id);
      if (!other.result) throw new Error('对照运行尚无已保存结果');
      setCompareResult(other.result);
    } catch (cause) { setError(cause instanceof Error ? cause.message : '无法读取对照运行'); }
  }

  if (error) return <div className="page-pad"><div className="notice notice--error" role="alert">{error}</div><button className="text-button" onClick={onBack}>← 返回运行</button></div>;
  if (!run) return <div className="page-pad"><div className="loading-skeleton" aria-label="正在读取报告" /></div>;
  if (!run.result) return <div className="page-pad"><h1>暂无计算报告</h1><p>此运行尚未保存结果，状态：{run.status}。</p><button className="text-button" onClick={onBack}>← 返回运行</button></div>;
  // A stored report is immutable: display units come from its own input snapshot.
  const preferences = run.result.input_snapshot?.display_preferences;
  return <><div className="report-compare-control no-print"><label htmlFor="compare-run">对照另一运行</label><select id="compare-run" defaultValue="" onChange={event => { void selectComparison(event.target.value); }}><option value="">暂不对照</option>{history.map(item => <option key={item.id} value={item.id}>修订 {item.revision} · {item.condition_id} · {item.id.slice(0, 8)}</option>)}</select></div>
    <UnitProvider preferences={preferences}>
      <Report result={run.result} runId={runId} compareResult={compareResult} onBack={onBack} />
    </UnitProvider></>;
}