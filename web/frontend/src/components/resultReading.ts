import { declaredSource } from './InputTrace';
import { number, object, rows, type Raw } from './formModel';
import { STAGE_LABELS, STAGE_ORDER } from './StageStatus';
import type { AnalysisResult, StageEnvelope } from '../types';
import type { Dimension } from './units';

/**
 * Saved-result readings, shared by the run and report pages.
 *
 * Every number here is projected from one saved path of `result.stages` — the
 * same paths the coordinator writes — and from nothing else. Nothing is derived
 * in the browser: no draught inferred from the waterline, no first resistance
 * row picked out of a list, no average or interpolation, no fallback to the input
 * snapshot or to a historical propulsion figure. A stage that did not deliver a
 * result reports why instead of a number, even when its envelope still carries
 * residual values, and a genuine zero is a value like any other.
 *
 * The overall result status is deliberately not consulted: a `partial` or
 * `canceled` run still shows the stages that did finish, because those stages
 * are saved facts. Units follow the existing `Dimension` vocabulary so the
 * reader's display preference can convert a stored number without changing what
 * was saved; a range stays in nmi because it has no convertible reader unit. A
 * structured `source` is carried through as declared; it is a statement about
 * where a number came from, never historical confirmation.
 */

export type ReadingState = 'known' | 'unknown' | 'not_requested' | 'unavailable' | 'model_limit' | 'failed' | 'canceled' | 'multiple';

export interface ReportReading {
  key: string;
  stage: string;
  label: string;
  value: number | null;
  dimension?: Dimension;
  storedUnit?: string;
  canonicalUnit?: string;
  state: ReadingState;
  reason: string | null;
  context: string | null;
  source: string | null;
  estimate: boolean | null;
}

/**
 * Either the stage that may be read, or the reason it may not. The stage is
 * only ever reachable through the `ok` branch, so no reader can touch a stage
 * it has not been cleared for.
 */
type StageAccess = { ok: true; stage: StageEnvelope } | { ok: false; state: ReadingState; reason: string };

const STATUS_STATE: Record<string, ReadingState> = {
  not_requested: 'not_requested', unavailable: 'unavailable', model_limit: 'model_limit',
  failed: 'failed', canceled: 'canceled',
};

const STATUS_REASON: Record<string, string> = {
  not_requested: '本次请求未运行该阶段', unavailable: '资料不足', model_limit: '模型越界',
  failed: '计算失败', canceled: '该阶段已取消',
};

/** The only saved paths the first-screen readings are allowed to read. */
const SCALARS: Array<{ key: string; stage: string; label: string; dimension: Dimension; storedUnit: string; path: string }> = [
  { key: 'loading.total_mass_t', stage: 'loading', label: '所选工况总质量', dimension: 'mass', storedUnit: 't', path: 'values.total_mass_t' },
  { key: 'equilibrium.waterline_above_keel_m', stage: 'equilibrium', label: '龙骨基准水线高度', dimension: 'length', storedUnit: 'm', path: 'waterline_above_keel_m' },
  { key: 'equilibrium.heel_deg', stage: 'equilibrium', label: '横倾角', dimension: 'angle', storedUnit: 'deg', path: 'heel_deg' },
  { key: 'hydrostatics.gm_t_m', stage: 'hydrostatics', label: '初稳性高 GM', dimension: 'length', storedUnit: 'm', path: 'values.gm_t_m' },
];

function stageOf(result: AnalysisResult | null | undefined, name: string): StageEnvelope | null {
  const stage = object(object(result?.stages)[name]);
  return Object.keys(stage).length ? stage as StageEnvelope : null;
}

function stageContext(name: string): string {
  return `阶段 ${STAGE_LABELS[name] ?? name}`;
}

function flag(value: unknown): boolean | null {
  return typeof value === 'boolean' ? value : null;
}

function readPath(data: Raw, path: string): unknown {
  return path.split('.').reduce<unknown>((node, key) => object(node)[key], data);
}

/**
 * A reading is possible only for a stage that was requested and finished.
 * Anything else is blocked before a single field is touched, so a residual
 * value inside a failed, unavailable, model-limited or canceled envelope can
 * never reach the reader.
 */
function stageAccess(stage: StageEnvelope | null): StageAccess {
  if (!stage) return { ok: false, state: 'not_requested', reason: '该运行没有保存此阶段' };
  if (!stage.requested) return { ok: false, state: 'not_requested', reason: '本次请求未运行该阶段' };
  if (stage.status === 'completed') return { ok: true, stage };
  const state = STATUS_STATE[stage.status] ?? 'failed';
  const label = STATUS_REASON[stage.status] ?? STATUS_REASON.failed;
  return { ok: false, state, reason: stage.reason ? `${label}：${stage.reason}` : label };
}

/** A missing field, an explicit null and a non-finite value stay three facts. */
function scalarReason(field: string, raw: unknown): string {
  if (raw === undefined) return '本次结果未给出此字段';
  if (raw === null) return `保存结果中 ${field} 为 null`;
  return `保存结果中 ${field} 不是有限数字`;
}

function scalarReading(spec: typeof SCALARS[number], stage: StageEnvelope | null): ReportReading {
  const base: ReportReading = {
    key: spec.key, stage: spec.stage, label: spec.label, value: null,
    dimension: spec.dimension, storedUnit: spec.storedUnit, canonicalUnit: spec.storedUnit,
    state: 'unknown', reason: null, context: stageContext(spec.stage), source: null, estimate: null,
  };
  const access = stageAccess(stage);
  if (!access.ok) return { ...base, state: access.state, reason: access.reason };
  const data = object(access.stage.data);
  const source = declaredSource(data.source);
  const estimate = flag(data.estimate);
  const raw = readPath(data, spec.path);
  const value = number(raw);
  if (value === null) return { ...base, reason: scalarReason(spec.path, raw), source, estimate };
  return { ...base, state: 'known', value, reason: null, source, estimate };
}

/**
 * The power work point. Only a single complete, primary and in-scope row may
 * speak for the stage; several rows stay several work points and the first one
 * is never chosen on the reader's behalf.
 */
function powerReading(stage: StageEnvelope | null): ReportReading {
  const base: ReportReading = {
    key: 'resistance.shaft_power_kw', stage: 'resistance', label: '功率工作点', value: null,
    dimension: 'power', storedUnit: 'kW', canonicalUnit: 'kW',
    state: 'unknown', reason: null, context: stageContext('resistance'), source: null, estimate: null,
  };
  const access = stageAccess(stage);
  if (!access.ok) return { ...base, state: access.state, reason: access.reason };
  const data = object(access.stage.data);
  const power = rows(data.power_rows);
  if (power.length === 0) return { ...base, reason: '本次结果未给出此字段' };
  if (power.length > 1) {
    return { ...base, state: 'multiple', reason: '多个工作点，见阻力与功率', context: `${stageContext('resistance')} · ${power.length} 个工作点` };
  }
  const row = power[0];
  const source = declaredSource(object(row.qpc).source) ?? declaredSource(row.source);
  const estimate = flag(row.estimate);
  const speed = number(row.speed_kn);
  const shaft = number(row.shaft_power_kw);
  if (speed === null || shaft === null) {
    return { ...base, reason: '该工作点未给出有限航速或轴功率，见阻力与功率', source, estimate };
  }
  const context = `${stageContext('resistance')} · 工作点 ${speed} kn`;
  // The envelope's own validity speaks for the row it carries, so an
  // out-of-scope stage cannot be quoted through an in-scope looking row.
  const outOfScope = access.stage.validity?.model_applicable === false
    || object(data.validity).model_applicable === false
    || row.model_applicable === false;
  if (row.complete !== true) return { ...base, reason: '该工作点未完整求得，见阻力与功率', context, source, estimate };
  if (outOfScope) return { ...base, reason: '该工作点不在经验适用范围，见阻力与功率', context, source, estimate };
  if (row.primary_result === false || data.primary_result === false) {
    return { ...base, reason: '该工作点为非主试算，见阻力与功率', context, source, estimate };
  }
  const primary = row.primary_result === true || data.primary_result === true;
  const applicable = row.model_applicable === true || object(data.validity).model_applicable === true
    || access.stage.validity?.model_applicable === true;
  if (!primary || !applicable) {
    return { ...base, reason: '该工作点未声明主结果或模型适用性，见阻力与功率', context, source, estimate };
  }
  return { ...base, state: 'known', value: shaft, reason: null, context, source, estimate };
}

/** Steady endurance stays in nautical miles: a range has no reader unit to convert. */
function enduranceReading(stage: StageEnvelope | null): ReportReading {
  const base: ReportReading = {
    key: 'endurance.range_nm', stage: 'endurance', label: '稳态续航', value: null, canonicalUnit: 'nmi',
    state: 'unknown', reason: null, context: stageContext('endurance'), source: null, estimate: null,
  };
  const access = stageAccess(stage);
  if (!access.ok) return { ...base, state: access.state, reason: access.reason };
  const values = object(object(access.stage.data).values);
  const source = declaredSource(values.source);
  const estimate = flag(values.estimate);
  const speed = number(values.speed_kn);
  const context = speed === null ? base.context ?? null : `${stageContext('endurance')} · 工作点 ${speed} kn`;
  const raw = values.range_nm;
  const value = number(raw);
  if (value === null) return { ...base, reason: scalarReason('range_nm', raw), context, source, estimate };
  return { ...base, state: 'known', value, reason: null, context, source, estimate };
}

/**
 * The stages this result actually asked for, in the canonical order. A stage
 * name the interface does not know yet keeps its saved position after the known
 * ones instead of being dropped by the sort.
 */
export function requestedStages(result: AnalysisResult | null | undefined): Array<{ name: string; stage: StageEnvelope }> {
  const entries = Object.entries(object(result?.stages))
    .filter(([, stage]) => stage && typeof stage === 'object' && (stage as StageEnvelope).requested === true)
    .map(([name, stage], index) => ({ name, stage: stage as StageEnvelope, index }));
  const rank = (name: string): number => {
    const known = STAGE_ORDER.indexOf(name);
    return known === -1 ? STAGE_ORDER.length : known;
  };
  return entries
    .sort((a, b) => rank(a.name) - rank(b.name) || a.index - b.index)
    .map(entry => ({ name: entry.name, stage: entry.stage }));
}

/** The six first-screen readings, in a fixed reading order. */
export function reportReadings(result: AnalysisResult | null | undefined): ReportReading[] {
  const readings: ReportReading[] = [];
  for (const spec of SCALARS) readings.push(scalarReading(spec, stageOf(result, spec.stage)));
  readings.push(powerReading(stageOf(result, 'resistance')));
  readings.push(enduranceReading(stageOf(result, 'endurance')));
  return readings;
}

/**
 * A stage address that keeps the tool route intact: `#/runs/{runId}` and
 * `#/reports/{runId}` still resolve to the same page, because the run id stays
 * the second segment and only a `/stages/{name}` tail is added.
 */
export function stageHref(page: 'runs' | 'reports', runId: string, stageName: string): string {
  return `#/${page}/${encodeURIComponent(runId)}/stages/${encodeURIComponent(stageName)}`;
}

function safeDecode(segment: string): string | null {
  try { return decodeURIComponent(segment); } catch { return null; }
}

/**
 * The stage named by `hash`, or null when the hash is not this page's stage
 * address. An old `#/reports/{id}` link, another page, another id, a missing
 * `stages` segment, a broken percent-escape or an unknown tail is ignored
 * rather than guessed at, and the reader stays where they are.
 */
export function readStageTarget(hash: string, page: 'runs' | 'reports', runId: string): string | null {
  const path = String(hash ?? '').replace(/^#/, '').replace(/^\/+/, '').split('/');
  if (path.length !== 4 || path[0] !== page || path[2] !== 'stages') return null;
  const id = safeDecode(path[1]);
  const stage = safeDecode(path[3]);
  if (id === null || stage === null || id !== runId || stage === '') return null;
  return stage;
}
