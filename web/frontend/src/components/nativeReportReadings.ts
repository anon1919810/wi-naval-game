import { number, object, type Raw } from './formModel';
import { stageLabel } from './StageStatus';
import { shipDesignCopy, type ShipDesignKey } from '../i18n/shipDesign';
import { reportReadings, requestedStages, type ReadingState, type ReportReading } from './resultReading';
import {
  SHIP_DESIGN_METHOD_VERSION, SHIP_DESIGN_RESULT_SCHEMA, SHIP_DESIGN_STAGE,
} from './sps3b3Model';
import { workspaceCopy, type WorkspaceKey } from '../i18n/workspace';
import type { Dimension } from './units';
import type { SiteLanguage } from '../portfolio/LanguageProvider';
import type { AnalysisResult, StageEnvelope } from '../types';

/**
 * The native design readings, and the physical ones a native result still owes.
 *
 * A native run is summarised by the frozen `ship_design` result it saved, not by
 * the physical projections that happen to sit in the same payload: that result
 * already answers the question the first screen asks, and the eight physical
 * cards were printing "unknown" for stages the run never requested. So when —
 * and only when — this result *requested* the native stage, the native readings
 * lead and an unrequested physical stage contributes no card at all.
 *
 * Every number below is one saved path of that frozen result: the balance the
 * ledger reconciled, and the engine and performance sections the source adapter
 * lifted. Nothing is derived: no physical GM stands in for the empirical
 * stability screen, no input snapshot is consulted, and a `partial` design that
 * could not bind a role shows the field as unknown rather than as a zero.
 *
 * The gate is the one the physical readings already use, applied to the native
 * stage. A design that did not deliver a result names why, and a number left
 * behind in a failed, cancelled or unavailable envelope is never read. The
 * native result schema and the native method version are required as well, so a
 * design stage that carries neither is named instead of quoted, and a stage
 * whose own declared kernel identity disagrees with its payload is refused too.
 *
 * A native result still shows the physical readings of the stages it actually
 * asked for, behind their own existing gates and in their own existing order:
 * the native balance is the design's own basis condition, and a selected
 * physical loading stays a separate reading beside it.
 */

/** One saved native field, with the label and the unit identity it is read in. */
interface NativeSpec {
  key: string;
  label: ShipDesignKey;
  /** The native section the field sits in; `''` reads the balance at its root. */
  section: string;
  field: string;
  dimension?: Dimension;
  storedUnit?: string;
  canonicalUnit?: string;
}

/**
 * The native readings, in one fixed order, all lifted from the frozen result.
 *
 * The recovered horsepower is a *source* reading rather than shaft power: it has
 * no convertible reader unit and is never shown as, or converted to, kW. A range
 * and the empirical stability screen have no convertible reader unit either, so
 * they keep the units the source saved. The stability score states its own name:
 * it is the source method's empirical screen, not a physical metacentric height.
 */
const NATIVE_SPECS: ReadonlyArray<NativeSpec> = [
  { key: 'ship_design.balance.selected_mass_t', label: 'shipDesign.reading.selectedMass',
    section: 'balance', field: 'selected_mass_t', dimension: 'mass', storedUnit: 't' },
  { key: 'ship_design.balance.estimated_mass_t', label: 'shipDesign.reading.estimatedMass',
    section: 'balance', field: 'estimated_mass_t', dimension: 'mass', storedUnit: 't' },
  { key: 'ship_design.balance.target_displacement_t', label: 'shipDesign.reading.targetDisplacement',
    section: 'balance', field: 'target_displacement_t', dimension: 'mass', storedUnit: 't' },
  { key: 'ship_design.balance.difference_t', label: 'shipDesign.reading.difference',
    section: 'balance', field: 'difference_t', dimension: 'mass', storedUnit: 't' },
  { key: 'ship_design.engine.speedMax', label: 'shipDesign.reading.speedMax',
    section: 'engine', field: 'speedMax', dimension: 'speed', storedUnit: 'kn' },
  { key: 'ship_design.engine.hpMax', label: 'shipDesign.reading.powerMax',
    section: 'engine', field: 'hpMax', canonicalUnit: 'source hp' },
  { key: 'ship_design.engine.range', label: 'shipDesign.reading.range',
    section: 'engine', field: 'range', canonicalUnit: 'nmi' },
  { key: 'ship_design.performance.stability', label: 'shipDesign.reading.stability',
    section: 'performance', field: 'stability', canonicalUnit: 'empirical score' },
];

/** Either the stage that may be read, or the reason it may not. */
type NativeAccess = { ok: true; data: Raw } | { ok: false; state: ReadingState; reason: string };

const STATUS_STATE: Record<string, ReadingState> = {
  not_requested: 'not_requested', unavailable: 'unavailable', model_limit: 'model_limit',
  failed: 'failed', canceled: 'canceled',
};

const STATUS_REASON: Record<string, WorkspaceKey> = {
  not_requested: 'reading.reason.notRequested', unavailable: 'reading.reason.unavailable',
  model_limit: 'reading.reason.modelLimit', failed: 'reading.reason.failed', canceled: 'reading.reason.canceled',
};

function stageOf(result: AnalysisResult | null | undefined, name: string): StageEnvelope | null {
  const stage = object(object(result?.stages)[name]);
  return Object.keys(stage).length ? stage as StageEnvelope : null;
}

/**
 * The requested native stage and its saved payload, or `null` when this result is
 * not a native design summary. An unrequested stage is not summarised, exactly as
 * the physical projections already treat it.
 */
function nativeDesign(result: AnalysisResult | null | undefined): { stage: StageEnvelope; data: Raw } | null {
  const stage = stageOf(result, SHIP_DESIGN_STAGE);
  if (!stage || stage.requested !== true) return null;
  return { stage, data: object(stage.data) };
}

/**
 * A short, reader-facing statement of a stop in the native stage's own terms.
 *
 * The stage's saved stop reason is the core's own text and is passed through
 * verbatim; only the sentence around it is localized.
 */
function stopReason(language: SiteLanguage, stage: StageEnvelope, status: string):
  { state: ReadingState; reason: string } {
  const state = STATUS_STATE[status] ?? 'failed';
  const label = workspaceCopy(language, STATUS_REASON[status] ?? STATUS_REASON.failed);
  const saved = stage.reason == null ? '' : String(stage.reason);
  return { state, reason: saved ? workspaceCopy(language, 'reading.reason.withReason', { label, reason: saved }) : label };
}

/**
 * Whether the native fields may be read, or why they may not.
 *
 * A `completed` or `partial` design is readable field by field; anything else
 * names its own stop before a single field is touched, so a residual number in a
 * failed, unavailable or cancelled envelope never reaches the reader. The saved
 * result must declare the native schema and method version, and when the stage
 * declares its own kernel identity that identity has to agree with the payload:
 * an unestablished identity is not a matching one, so it blocks exactly as a
 * mismatch does.
 */
function nativeAccess(language: SiteLanguage, stage: StageEnvelope, data: Raw): NativeAccess {
  const status = String(stage.status);
  if (status !== 'completed' && status !== 'partial') return { ok: false, ...stopReason(language, stage, status) };
  if (data.schema !== SHIP_DESIGN_RESULT_SCHEMA || data.method_version !== SHIP_DESIGN_METHOD_VERSION) {
    return { ok: false, state: 'unknown', reason: shipDesignCopy(language, 'shipDesign.reading.reason.notNative') };
  }
  const kernel = object(stage.method_versions).kernel;
  if (typeof kernel === 'string' && kernel !== data.method_version) {
    return { ok: false, state: 'unknown', reason: shipDesignCopy(language, 'shipDesign.reading.reason.identity') };
  }
  return { ok: true, data };
}

/**
 * The stage and the design's own basis condition, so a native mass is never read
 * as the selected physical loading's mass.
 */
function nativeContext(language: SiteLanguage, basis: string | null): string {
  const context = workspaceCopy(language, 'reading.stageContext', {
    name: stageLabel(key => workspaceCopy(language, key), SHIP_DESIGN_STAGE),
  });
  if (!basis) return context;
  return workspaceCopy(language, 'reading.context.note', {
    context, note: shipDesignCopy(language, 'shipDesign.reading.basisNote', { condition: basis }),
  });
}

/** A missing field, an explicit null and a non-finite value stay three facts. */
function scalarReason(language: SiteLanguage, field: string, raw: unknown): string {
  if (raw === undefined) return workspaceCopy(language, 'reading.reason.noField');
  if (raw === null) return workspaceCopy(language, 'reading.reason.nullField', { field });
  return workspaceCopy(language, 'reading.reason.notFiniteField', { field });
}

/** One saved native scalar, projected only through the native gate. */
function nativeReading(language: SiteLanguage, access: NativeAccess, spec: NativeSpec, context: string): ReportReading {
  const base: ReportReading = {
    key: spec.key, stage: SHIP_DESIGN_STAGE, label: shipDesignCopy(language, spec.label), value: null,
    dimension: spec.dimension, storedUnit: spec.storedUnit, canonicalUnit: spec.canonicalUnit ?? spec.storedUnit,
    state: 'unknown', reason: null, context, source: null, estimate: null,
  };
  if (!access.ok) return { ...base, state: access.state, reason: access.reason };
  const scope = spec.section === '' ? access.data : object(access.data[spec.section]);
  const path = spec.section === '' ? spec.field : `${spec.section}.${spec.field}`;
  const raw = scope[spec.field];
  const value = number(raw);
  // A finite negative and a genuine zero are results like any other; an unbound
  // balance is a null and stays unknown rather than becoming a zero.
  if (value === null) return { ...base, reason: scalarReason(language, path, raw) };
  return { ...base, state: 'known', value, reason: null };
}

/**
 * The first-screen readings of a native design result, native cards first.
 *
 * Returns `null` when the result requested no native stage, so a report with no
 * native design keeps exactly the physical projection it always had. Otherwise
 * the eight native readings lead, and only the physical readings whose own stage
 * this run actually requested are appended, behind their existing gates.
 */
export function nativePrimaryReadings(result: AnalysisResult | null | undefined, language: SiteLanguage): ReportReading[] | null {
  const native = nativeDesign(result);
  if (!native) return null;
  const access = nativeAccess(language, native.stage, native.data);
  const declared = native.data.basis_condition_id;
  const basis = typeof declared === 'string' && declared !== '' ? declared : null;
  const context = nativeContext(language, basis);
  const readings = NATIVE_SPECS.map(spec => nativeReading(language, access, spec, context));
  const requested = new Set(requestedStages(result).map(entry => entry.name));
  return [...readings, ...reportReadings(result, language).filter(reading => requested.has(reading.stage))];
}
