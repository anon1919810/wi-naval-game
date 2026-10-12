import { stageLabel } from './StageStatus';
import { reportMetrics, type ReportMetric } from './reportMetrics';
import type { Copy } from './diagnosticGuidance';
import type { AnalysisResult, RunView, StageEnvelope } from '../types';

export type ComparisonCellState = 'known' | 'unknown' | 'unrequested' | 'incompatible';
export interface ComparisonCell extends Omit<ReportMetric, 'value' | 'id' | 'blocked'> {
  state: ComparisonCellState;
  comparisonPath?: string;
  current: number | null;
  comparison: number | null;
  delta: number | null;
}
export interface ComparisonGroup { stage: string; label: string; cells: ComparisonCell[] }
export interface ComparisonIdentity { project: string; runId?: string; condition: string; revision: number | null; fingerprint: string }
export interface Comparison {
  current: ComparisonIdentity; comparison: ComparisonIdentity; compatible: boolean;
  inputChanges: string[]; groups: ComparisonGroup[]; warnings: string[];
}
export interface ComparisonSide { result: AnalysisResult; revision?: number; run?: RunView }
const finite = (value: unknown): number | null => typeof value === 'number' && Number.isFinite(value) ? value : null;
const record = (value: unknown): Record<string, unknown> | null => value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
const canonical = (value: unknown): unknown => Array.isArray(value) ? value.map(canonical)
  : record(value) ? Object.fromEntries(Object.entries(value as Record<string, unknown>).sort(([a], [b]) => a.localeCompare(b)).map(([k, v]) => [k, canonical(v)])) : value;
const same = (a: unknown, b: unknown) => JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));
const ran = (stage?: StageEnvelope) => stage?.requested === true && stage.status === 'completed';
function identity(side: ComparisonSide): ComparisonIdentity {
  return { project: side.result.project_id, runId: side.run?.id, condition: side.result.condition_id,
    revision: side.run?.revision ?? side.revision ?? (typeof side.result.input_snapshot?.revision === 'number' ? side.result.input_snapshot.revision : null),
    fingerprint: side.result.request_fingerprint };
}
export function validReportIdentity(side: ComparisonSide): boolean {
  const r = side.run, s = side.result.input_snapshot;
  if (s?.id && s.id !== side.result.project_id) return false;
  if (!r) return true;
  return r.project_id === side.result.project_id && r.condition_id === side.result.condition_id
    && r.request_fingerprint === side.result.request_fingerprint
    && s?.id === r.project_id && s.revision === r.revision && r.status === side.result.status
    && (r.status === 'completed' || r.status === 'partial' || r.status === 'canceled');
}
function changes(w: Copy, a: unknown, b: unknown, path: string, found: string[]) {
  if (same(a, b)) return;
  const left = record(a), right = record(b);
  if (Array.isArray(a) && Array.isArray(b)) {
    for (let index = 0; index < Math.max(a.length, b.length); index++) changes(w, a[index], b[index], `${path}[${index}]`, found);
  } else if (left && right) {
    for (const key of [...new Set([...Object.keys(left), ...Object.keys(right)])].sort()) changes(w, left[key], right[key], `${path}.${key}`, found);
  } else {
    const text = (value: unknown) => value === undefined ? w('report.compare.absent') : JSON.stringify(value).slice(0, 180);
    found.push(w('report.compare.changedInput', { path, current: text(a), comparison: text(b) }));
  }
}
export function compareReports(a: ComparisonSide, b: ComparisonSide, w: Copy): Comparison {
  const left = a.result, right = b.result, reasons: string[] = [], inputChanges: string[] = [];
  if (!validReportIdentity(a) || !validReportIdentity(b)) reasons.push(w('report.compare.identityMismatch'));
  if (left.project_id !== right.project_id) reasons.push(w('report.compare.changeProject', { current: left.project_id, comparison: right.project_id }));
  if (left.condition_id !== right.condition_id) reasons.push(w('report.compare.changeCondition', { current: left.condition_id, comparison: right.condition_id }));
  if (!same(left.units, right.units)) reasons.push(w('report.compare.changeUnits'));
  if (!left.method_versions || !right.method_versions || !same(left.method_versions, right.method_versions)) reasons.push(w('report.compare.changeMethods'));
  for (const [name, x] of Object.entries(left.stages)) {
    const y = right.stages[name];
    if (ran(x) && ran(y) && (!x.method_versions || !y.method_versions || !same(x.method_versions, y.method_versions))) reasons.push(w('report.compare.changeKernel', { stage: stageLabel(w, name) }));
  }
  const compatible = reasons.length === 0;
  const warnings = [...reasons];
  if (!record(left.input_snapshot) || !record(right.input_snapshot) || !Object.keys(left.input_snapshot).length || !Object.keys(right.input_snapshot).length) warnings.push(w('report.compare.snapshotMissing'));
  else changes(w, left.input_snapshot, right.input_snapshot, 'input', inputChanges);
  changes(w, left.request, right.request, 'request', inputChanges);
  if (inputChanges.length) warnings.push(w('report.compare.changedInputsWarning'));
  const groups: ComparisonGroup[] = [];
  for (const name of [...new Set([...Object.keys(left.stages), ...Object.keys(right.stages)])]) {
    const x = left.stages[name], y = right.stages[name];
    if (!ran(x) && !ran(y)) continue;
    const xs = reportMetrics(name, x), ys = reportMetrics(name, y), cells: ComparisonCell[] = [];
    const methodSame = x?.method_versions && y?.method_versions && same(x.method_versions, y.method_versions);
    if (ran(x) && ran(y) && !methodSame) warnings.push(w('report.compare.changeKernel', { stage: stageLabel(w, name) }));
    for (const id of [...new Set([...xs.map(m => m.id), ...ys.map(m => m.id)])]) {
      const xm = xs.find(m => m.id === id), ym = ys.find(m => m.id === id), metric = xm ?? ym!;
      const av = finite(xm?.value), bv = finite(ym?.value);
      const state: ComparisonCellState = !ran(x) || !ran(y) ? 'unrequested'
        : !compatible || !methodSame || xm?.blocked || ym?.blocked || x?.validity?.converged === false || y?.validity?.converged === false || x?.validity?.model_applicable === false || y?.validity?.model_applicable === false ? 'incompatible'
          : av === null || bv === null ? 'unknown' : metric.dimension || metric.canonicalUnit ? 'known' : 'incompatible';
      cells.push({ key: metric.key, path: metric.path, comparisonPath: ym?.path, point: metric.point,
        dimension: metric.dimension, storedUnit: metric.storedUnit, canonicalUnit: metric.canonicalUnit,
        state, current: ran(x) ? av : null, comparison: ran(y) ? bv : null,
        delta: state === 'known' ? bv! - av! : null });
    }
    if (cells.length) groups.push({ stage: name, label: stageLabel(w, name), cells });
  }
  if (!compatible || warnings.some(s => s === w('report.compare.changeMethods') || s === w('report.compare.identityMismatch'))) warnings.push(w('report.compare.incompatible'));
  if (!groups.some(g => g.cells.some(c => c.delta !== null))) warnings.push(w('report.compare.none'));
  return { current: identity(a), comparison: identity(b), compatible, inputChanges, groups, warnings };
}
