import type { LabKey } from '../i18n/lab';
import type { Breach, CrewState, Experiment, LabRun, LabState, ModuleState } from './types';

/**
 * Comparing two completed laboratory trials.
 *
 * A difference is only a result about the ship when the two runs share their
 * basis and their accepted endpoint. So this module answers three questions in
 * order — may these two be compared, what did the *inputs* change, and where did
 * the accepted states differ — and it refuses to smooth over the rest:
 *
 * - A run whose revision, condition, method versions or status differs is
 *   reported with the reason, not with a delta.
 * - Every changed experiment input is listed. A changed seed or sample count, a
 *   changed duration, or more than one changed input at all, makes the pair an
 *   uncontrolled comparison: the difference is real, its cause is not attributed.
 * - Both endpoint times are printed as recorded. Runs that stopped at different
 *   accepted times are flagged, never interpolated onto a common time.
 * - The three availability factors are kept in their multiplicative
 *   relationship — each is reported separately and their product is checked
 *   against the recorded effective value instead of being added to it.
 * - An unknown operand yields an unknown difference (`null`), never zero.
 */

export type LabCopy = (key: LabKey, params?: Readonly<Record<string, string | number>>) => string;

/** A difference that is `null` whenever either side is unknown. */
export type Delta = number | null;

export interface TrialSide {
  /** The run this side came from. */
  id: string;
  revision: number;
  condition: string;
  /** The saved endpoint, as recorded. */
  endpointTimeS: number | null;
  simulatedDurationS: number | null;
  status: string;
}

export interface ChangedInput {
  /** The experiment field that differs, in dotted form. */
  path: string;
  from: string;
  to: string;
}

export interface FactorDelta {
  /** The module's own id and label, so a reader can find the row it came from. */
  id: string;
  label: string;
  mechanical: Delta;
  flooding: Delta;
  staffing: Delta;
  effective: Delta;
  shaftPowerKw: Delta;
  /**
   * Whether the recorded effective availability equals the product of the three
   * recorded factors. Reported, never repaired: this module does not add losses.
   */
  multiplicative: boolean | null;
}

export interface CrewDelta {
  id: string;
  label: string;
  available: Delta;
  incapacitated: Delta;
  dead: Delta;
  evacuated: Delta;
}

export interface BreachDelta {
  id: string;
  /** Areas are reported in m² exactly as recorded; nothing is summed per opening. */
  areaM2: Delta;
}

export interface ShipDelta {
  volumeM3: Delta;
  massT: Delta;
  heelDeg: Delta;
  trimDeg: Delta;
}

export interface TrialComparison {
  a: TrialSide;
  b: TrialSide;
  compatible: boolean;
  /** Why the two runs may not be compared quantitatively, in the reader's words. */
  reasons: string[];
  /** Every changed experiment input. */
  changes: ChangedInput[];
  /** Changes that stop a difference from being attributed to one setting. */
  uncontrolled: string[];
  /** True only when both runs stopped at the same accepted time. */
  sameEndpoint: boolean;
  modules: FactorDelta[];
  crew: CrewDelta[];
  breaches: BreachDelta[];
  ship: ShipDelta;
}

const number = (value: unknown): number | null => typeof value === 'number' && Number.isFinite(value) ? value : null;
const text = (value: unknown): string => value === null || value === undefined ? '—' : String(value);
const canonical = (value: unknown): unknown => Array.isArray(value) ? value.map(canonical)
  : value && typeof value === 'object' ? Object.fromEntries(Object.entries(value).sort(([a],[b])=>a.localeCompare(b)).map(([key,v])=>[key,canonical(v)])) : value;
const same = (left: unknown, right: unknown): boolean => JSON.stringify(canonical(left)) === JSON.stringify(canonical(right));

/** The difference between two recorded numbers, unknown when either side is. */
export const delta = (current: unknown, comparison: unknown): Delta => {
  const a = number(current), b = number(comparison);
  return a === null || b === null ? null : b - a;
};

const side = (run: LabRun): TrialSide => ({
  id: run.id,
  revision: run.revision,
  condition: run.condition_id,
  endpointTimeS: number(run.result?.final_state.time_s),
  simulatedDurationS: number(run.result?.simulated_duration_s),
  status: run.status,
});

/** Compare every frozen experiment field, matching identified records independently of array order. */
function inputChanges(a: Experiment, b: Experiment): ChangedInput[] {
  const changes: ChangedInput[] = [];
  const object = (value: unknown): value is Record<string, unknown> => Boolean(value && typeof value === 'object' && !Array.isArray(value));
  const show = (value: unknown) => value === undefined ? '(absent)' : JSON.stringify(value);
  function visit(left: unknown, right: unknown, path: string) {
    if (same(left,right))return;
    if (Array.isArray(left) && Array.isArray(right) && [...left,...right].every(v=>object(v)&&typeof v.id==='string')) {
      const ids=[...new Set([...left,...right].map(v=>(v as Record<string,unknown>).id as string))].sort();
      for(const id of ids)visit(left.find(v=>v.id===id),right.find(v=>v.id===id),`${path}[${id}]`);
    } else if(object(left)||object(right)) {
      const a=object(left)?left:{},b=object(right)?right:{};
      for(const key of [...new Set([...Object.keys(a),...Object.keys(b)])].sort())visit(a[key],b[key],path ? `${path}.${key}` : key);
    } else changes.push({path,from:show(left),to:show(right)});
  }
  visit(a,b,'');return changes;
}
export function validTrialIdentity(run: LabRun): boolean {
  const result=run.result;
  return Boolean(result && result.input_snapshot?.id===run.project_id && result.input_snapshot.revision===run.revision
    && result.condition_id===run.condition_id && result.request_fingerprint===run.request_fingerprint
    && result.status===run.status && run.request.condition_id===run.condition_id
    && result.request.condition_id===run.condition_id && same(run.request,result.request)
    && same(result.method_versions,result.request.method_versions));
}

/**
 * Why these two runs may not be compared quantitatively.
 *
 * Identity is checked against what the frozen request recorded — the project and
 * revision the snapshot names, the condition and the method versions — so two
 * runs that merely look similar are still refused.
 */
function incompatibilities(l: LabCopy, a: LabRun, b: LabRun): string[] {
  const reasons: string[] = [];
  if (a.id === b.id) reasons.push(l('compare.reason.sameRun'));
  if (a.project_id !== b.project_id) reasons.push(l('compare.reason.project'));
  if (a.revision !== b.revision) reasons.push(l('compare.reason.revision', { a: a.revision, b: b.revision }));
  if (a.condition_id !== b.condition_id) reasons.push(l('compare.reason.condition', { a: a.condition_id, b: b.condition_id }));
  const left = a.result, right = b.result;
  if (!left || !right) { reasons.push(l('compare.reason.noResult')); return reasons; }
  if (!validTrialIdentity(a) || !validTrialIdentity(b)) reasons.push(l('compare.reason.identity'));
  if (left.schema !== right.schema) reasons.push(l('compare.reason.schema'));
  if (left.input_snapshot?.id !== right.input_snapshot?.id) reasons.push(l('compare.reason.snapshot'));
  if (left.input_snapshot?.revision !== right.input_snapshot?.revision) reasons.push(l('compare.reason.snapshotRevision'));
  if (!same(left.method_versions, right.method_versions)) reasons.push(l('compare.reason.methods'));
  // An accepted endpoint is what makes the final state comparable at all.
  if (left.status !== 'completed' || right.status !== 'completed') {
    reasons.push(l('compare.reason.unfinished', { a: left.status, b: right.status }));
  }
  return reasons;
}

function factorFor(current: ModuleState | undefined, comparison: ModuleState | undefined): FactorDelta | null {
  if (!current && !comparison) return null;
  const mechanical = number(current?.mechanical_integrity), otherMechanical = number(comparison?.mechanical_integrity);
  const flooding = number(current?.flooding_availability), otherFlooding = number(comparison?.flooding_availability);
  const staffing = number(current?.staffing_availability), otherStaffing = number(comparison?.staffing_availability);
  const effective = number(current?.effective_availability), otherEffective = number(comparison?.effective_availability);
  /** Whether one recorded state's effective availability is its factors' product. */
  const consistent = (state: ModuleState | undefined): boolean | null => {
    if (!state) return null;
    const m = number(state.mechanical_integrity), f = number(state.flooding_availability);
    const s = number(state.staffing_availability), e = number(state.effective_availability);
    return m === null || f === null || s === null || e === null ? null : Math.abs(m * f * s - e) < 1e-9;
  };
  const leftConsistent = consistent(current), rightConsistent = consistent(comparison);
  return {
    id: (current ?? comparison)!.id, label: (current ?? comparison)!.label,
    mechanical: delta(mechanical, otherMechanical),
    flooding: delta(flooding, otherFlooding),
    staffing: delta(staffing, otherStaffing),
    effective: delta(effective, otherEffective),
    shaftPowerKw: delta(number(current?.available_shaft_power_kw), number(comparison?.available_shaft_power_kw)),
    // Reported as recorded for both runs: a run whose own numbers disagree is shown
    // disagreeing rather than repaired, and one that cannot be checked is unknown.
    multiplicative: leftConsistent === null || rightConsistent === null ? null : leftConsistent && rightConsistent,
  };
}

function crewFor(current: CrewState | undefined, comparison: CrewState | undefined): CrewDelta | null {
  if (!current && !comparison) return null;
  return {
    id: (current ?? comparison)!.id, label: (current ?? comparison)!.label,
    available: delta(current?.available, comparison?.available),
    incapacitated: delta(current?.incapacitated, comparison?.incapacitated),
    dead: delta(current?.dead, comparison?.dead),
    evacuated: delta(current?.evacuated, comparison?.evacuated),
  };
}

const breached = (result: LabRun['result']): Breach[] => {
  const applied = result?.applied_breaches ?? [];
  const generated = (result?.final_state as LabState | undefined)?.generated_breaches ?? [];
  const merged = [...applied, ...generated];
  return merged.filter((entry, index) => merged.findIndex(other => other.id === entry.id) === index);
};

export function compareTrials(a: LabRun, b: LabRun, l: LabCopy): TrialComparison {
  const reasons = incompatibilities(l, a, b);
  const changes = a.result && b.result ? inputChanges(a.request.experiment, b.request.experiment) : [];

  // A changed sample count or seed is not an input like any other: it changes the
  // draw itself, so the pair cannot attribute the difference to one setting.
  const draw = changes.filter(change => change.path === 'detonation.seed' || change.path === 'detonation.fragment_count');
  const uncontrolled = draw
    .map(change => l('compare.uncontrolled.draw', { path: change.path, from: change.from, to: change.to }));
  // The draw flag already says the sample itself moved, so the "several inputs"
  // flag exists for the case it does not cover: more than one ordinary input.
  const material = changes.filter(change => change.path !== 'detonation.position_m' && !draw.includes(change));
  if (draw.length === 0 && material.length > 1) uncontrolled.push(l('compare.uncontrolled.multiple', { count: material.length }));
  if (changes.some(change => change.path === 'duration_s')) uncontrolled.push(l('compare.uncontrolled.duration'));

  const left = a.result?.final_state, right = b.result?.final_state;
  const endA = number(left?.time_s), endB = number(right?.time_s);
  const sameEndpoint = endA !== null && endB !== null && Math.abs(endA - endB) < 1e-9;

  const modules: FactorDelta[] = [];
  const crew: CrewDelta[] = [];
  const breaches: BreachDelta[] = [];
  if (left && right) {
    for (const id of [...new Set([...left.modules,...right.modules].map(row=>row.id))]) {
      const factor = factorFor(left.modules.find(row=>row.id===id),right.modules.find(row=>row.id===id));
      if(factor)modules.push(factor);
    }
    for (const id of [...new Set([...left.crew_groups,...right.crew_groups].map(row=>row.id))]) {
      const entry = crewFor(left.crew_groups.find(row=>row.id===id),right.crew_groups.find(row=>row.id===id));
      if(entry)crew.push(entry);
    }
    const leftBreaches = breached(a.result), rightBreaches = breached(b.result);
    const ids = [...new Set([...leftBreaches.map(entry => entry.id), ...rightBreaches.map(entry => entry.id)])];
    for (const id of ids) {
      breaches.push({ id, areaM2: delta(leftBreaches.find(entry => entry.id === id)?.area_m2 ?? null,
        rightBreaches.find(entry => entry.id === id)?.area_m2 ?? null) });
    }
  }

  return {
    a: side(a), b: side(b),
    compatible: reasons.length === 0,
    reasons, changes, uncontrolled, sameEndpoint,
    modules, crew, breaches,
    ship: {
      volumeM3: delta(left?.ship?.total_onboard_water_volume_m3, right?.ship?.total_onboard_water_volume_m3),
      massT: delta(left?.ship?.total_onboard_water_mass_t, right?.ship?.total_onboard_water_mass_t),
      heelDeg: delta(left?.ship?.equilibrium?.heel_deg, right?.ship?.equilibrium?.heel_deg),
      trimDeg: delta(left?.ship?.equilibrium?.trim_deg, right?.ship?.equilibrium?.trim_deg),
    },
  };
}
