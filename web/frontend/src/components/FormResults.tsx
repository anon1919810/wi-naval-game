import type { ReactNode } from 'react';
import { FactField } from './FactField';
import { number, object, type Raw } from './formModel';

export function Metric({ label, value, unit = '', estimate, source }: {
  label: string; value: unknown; unit?: string; estimate?: unknown; source?: string | null;
}) {
  const known = number(value) !== null;
  return <FactField label={label} value={number(value)} unit={unit} source={source ?? '当前工况运行结果'}
    status={!known ? 'unknown' : estimate === true ? 'estimate' : 'known'} />;
}

// A declared fact carries its own value/source/estimate; a fact with no value
// stays unknown rather than defaulting to a number or to zero.
export function DeclaredFact({ label, unit, fact: supplied }: { label: string; unit: string; fact: unknown }) {
  const entry = object(supplied);
  return <Metric label={label} value={entry.value} unit={unit} estimate={entry.estimate}
    source={typeof entry.source === 'string' && entry.source ? entry.source : '未声明来源'} />;
}
export function ResultSection({ available, children }: { available: boolean; children: ReactNode }) {
  return <section className="form-results"><div className="section-heading"><h3>当前修订 · 所选工况结果</h3></div>
    {available ? children : <p className="section-intro">保存并运行当前工况后显示结果</p>}</section>;
}
export function Diagnostics({ value }: { value: unknown }) {
  if (!Array.isArray(value) || !value.length) return null;
  return <ul className="diagnostics-list">{value.map((d, i) => <li key={i}>{String(object(d).message ?? object(d).code ?? '未知诊断')}</li>)}</ul>;
}
// A study reports its own applicability, provenance and boundary. Only genuinely
// unavailable or failed studies hide their numbers. `estimated_nonprimary` is a
// valid non-primary result: the value is shown, labelled as an estimate and
// accompanied by the backend's reason and applicability flags.
const PRESENTED = new Set(['completed', 'estimated_nonprimary']);
export function StudyResult({ label, data, metrics }: { label: string; data: unknown; metrics: Array<[string, string, string?]> }) {
  const study = object(data);
  const status = typeof study.status === 'string' ? study.status : null;
  const available = status !== null && PRESENTED.has(status);
  const estimated = status === 'estimated_nonprimary' || study.estimate === true
    || study.model_applicable === false || study.primary_result === false;
  const source = typeof study.source === 'string' && study.source ? study.source
    : typeof study.method === 'string' && study.method ? study.method : null;
  return <div className="study-result"><h4>{label} <span>{status ?? (Object.keys(study).length ? 'declared' : '未请求')}</span></h4>
    {study.reason != null && <p>{String(study.reason)}</p>}
    <div className="metric-grid">{metrics.map(([key, name, unit]) =>
      <Metric key={key} label={name} value={available ? study[key] : null} unit={unit}
        estimate={available ? estimated : undefined}
        source={available ? source : '该研究未完成，结果未知'} />)}</div>
    {available && estimated && <p className="form-hint">该结果为工程估算 / 非主工况结果，仅供比较，不得当作确认值。</p>}
    {study.model_applicable === false && <p className="form-hint">方法适用范围之外：所选几何不属于该模型的主工况。</p>}
    {study.boundary != null && <p className="form-hint">边界：{String(study.boundary)}</p>}
    <Diagnostics value={study.diagnostics} /></div>;
}
export function RowResults({ view }: { view: Raw }) {
  return <><div className="metric-grid">{Object.entries(object(view.groups)).map(([id, row]) => <Metric key={id} label={`${id} 小计`} value={object(row).weight_t} unit="t" />)}</div>
    <Diagnostics value={view.diagnostics} /></>;
}
