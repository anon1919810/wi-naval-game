import type { ReactNode } from 'react';
import { FactField } from './FactField';
import { number, object, type Raw } from './formModel';
import { useWorkspaceCopy } from '../i18n/workspace';
import type { Dimension } from './units';

export function Metric({ label, value, unit = '', dimension, storedUnit, estimate, source }: {
  label: string; value: unknown; unit?: string; dimension?: Dimension; storedUnit?: string;
  estimate?: unknown; source?: string | null;
}) {
  const w = useWorkspaceCopy();
  const known = number(value) !== null;
  return <FactField label={label} value={number(value)} unit={unit} dimension={dimension} storedUnit={storedUnit}
    source={source ?? w('formResults.sourceRun')}
    status={!known ? 'unknown' : estimate === true ? 'estimate' : 'known'} />;
}

// A declared fact carries its own value/source/estimate; a fact with no value
// stays unknown rather than defaulting to a number or to zero.
export function DeclaredFact({ label, unit, fact: supplied, dimension, storedUnit }: {
  label: string; unit: string; fact: unknown; dimension?: Dimension; storedUnit?: string;
}) {
  const w = useWorkspaceCopy();
  const entry = object(supplied);
  return <Metric label={label} value={entry.value} unit={unit} dimension={dimension} storedUnit={storedUnit}
    estimate={entry.estimate}
    source={typeof entry.source === 'string' && entry.source ? entry.source : w('formResults.sourceUndeclared')} />;
}
export function ResultSection({ available, children }: { available: boolean; children: ReactNode }) {
  const w = useWorkspaceCopy();
  return <section className="form-results"><div className="section-heading"><h3>{w('formResults.section')}</h3></div>
    {available ? children : <p className="section-intro">{w('formResults.empty')}</p>}</section>;
}
export function Diagnostics({ value }: { value: unknown }) {
  const w = useWorkspaceCopy();
  if (!Array.isArray(value) || !value.length) return null;
  return <ul className="diagnostics-list">{value.map((d, i) => <li key={i}>{String(object(d).message ?? object(d).code ?? w('formResults.diagnosticFallback'))}</li>)}</ul>;
}
// A study reports its own applicability, provenance and boundary. Only genuinely
// unavailable or failed studies hide their numbers. `estimated_nonprimary` is a
// valid non-primary result: the value is shown, labelled as an estimate and
// accompanied by the backend's reason and applicability flags.
const PRESENTED = new Set(['completed', 'estimated_nonprimary']);
export function StudyResult({ label, data, metrics }: {
  label: string; data: unknown; metrics: Array<[string, string, string?, Dimension?, string?]>;
}) {
  const w = useWorkspaceCopy();
  const study = object(data);
  const status = typeof study.status === 'string' ? study.status : null;
  const available = status !== null && PRESENTED.has(status);
  const estimated = status === 'estimated_nonprimary' || study.estimate === true
    || study.model_applicable === false || study.primary_result === false;
  const source = typeof study.source === 'string' && study.source ? study.source
    : typeof study.method === 'string' && study.method ? study.method : null;
  return <div className="study-result"><h4>{label} <span>{status ?? (Object.keys(study).length ? w('formResults.declared') : w('formResults.notRequested'))}</span></h4>
    {study.reason != null && <p>{String(study.reason)}</p>}
    <div className="metric-grid">{metrics.map(([key, name, unit, dimension, storedUnit]) =>
      <Metric key={key} label={name} value={available ? study[key] : null} unit={unit} dimension={dimension} storedUnit={storedUnit}
        estimate={available ? estimated : undefined}
        source={available ? source : w('formResults.studyIncomplete')} />)}</div>
    {available && estimated && <p className="form-hint">{w('formResults.estimateNote')}</p>}
    {study.model_applicable === false && <p className="form-hint">{w('formResults.outOfRange')}</p>}
    {study.boundary != null && <p className="form-hint">{w('formResults.boundary', { value: String(study.boundary) })}</p>}
    <Diagnostics value={study.diagnostics} /></div>;
}
export function RowResults({ view }: { view: Raw }) {
  const w = useWorkspaceCopy();
  return <><div className="metric-grid">{Object.entries(object(view.groups)).map(([id, row]) =>
    <Metric key={id} label={w('formResults.subtotal', { id })} value={object(row).weight_t} unit="t" dimension="mass" />)}</div>
    <Diagnostics value={view.diagnostics} /></>;
}