import type { LabCopy } from './comparison';
import type { InspectionTarget } from './narrative';
import type { AnalysisResult } from '../types';
import type { FragmentTrace, LabResult } from './types';

/**
 * Explaining one selected target from the evidence the run actually recorded.
 *
 * This consumes structured records only — the fragment report's traces, hits and
 * boundary responses, the accepted frames, the accepted events and the native
 * flooding observation. It never parses an event's message text, because that
 * text is display prose and may be rewritten; and it never re-simulates, because
 * an explanation of a saved run has to describe *that* run.
 *
 * What it refuses to do matters as much as what it shows:
 *
 * - A frame before the detonation reveals nothing that happened later: no paths,
 *   no boundary responses, no recorded flow.
 * - A quantity the record does not hold stays unknown. Nothing is inferred from
 *   a neighbouring number, and an exposure is never presented as a casualty
 *   count, an armour class or an explosive mass.
 * - Compartment water is reported as the aggregate of the connections that can
 *   contribute, never attributed to one opening.
 * - The estimated opening response (game) and the numerical flooding result
 *   (core) stay separate, each labeled with where it came from.
 * - Without a stable hydraulic endpoint in the record there is no final heel or
 *   trim to show and no survivability judgement to make.
 */

/** How many contributing paths are listed before the rest are summarised. */
const LISTED_PATHS = 5;

export type Provenance = 'game' | 'core' | 'mixed';

export interface ContributingPath {
  /** The trace's own index, so a reader can find it in the fragment evidence. */
  index: number;
  /** The exposure the record attributes to the target along this path. */
  exposure: number | null;
  /** The sequence of rooms and boundary transmissions this path crossed. */
  sequence: string;
  blockedBy: string | null;
  termination: string;
  source: Provenance;
}

export interface BoundaryResponse {
  id: string;
  from: string;
  to: string;
  absorbedExposure: number | null;
  threshold: number | null;
  generatedAreaM2: number | null;
  /** Read off the record's own numbers; never recomputed. */
  state: 'generated' | 'deferred' | 'sealed' | 'unknown';
  source: Provenance;
}

export interface FactorContribution {
  kind: 'mechanical' | 'flooding' | 'staffing';
  /** The value in the selected frame, or null when the record does not hold it. */
  value: number | null;
  /** The frame where this value first changed, and the event it was accepted on. */
  firstFrame: number | null;
  firstEventIndex: number | null;
  firstEventTimeS: number | null;
  source: Provenance;
}

export interface RecordedFlow {
  id?: string;
  from: string;
  to: string;
  flowM3S?: number | null;
  transferM3: number | null;
  massFlowTS: number | null;
  source: 'core';
}

export interface TargetExplanation {
  target: InspectionTarget;
  frame: number;
  /** True when this frame is accepted before the detonation: nothing is revealed. */
  beforeDetonation: boolean;
  /** The target's recorded exposure, aggregated over the paths that reached it. */
  exposure: number | null;
  paths: ContributingPath[];
  /** How many further paths reached this target beyond the listed ones. */
  remainder: number;
  boundaries: BoundaryResponse[];
  factors: FactorContribution[];
  /** Native, aggregate flow the core recorded for this step. */
  flows: RecordedFlow[];
  /** Whether the numbers describe an aggregate over several connections. */
  aggregate: boolean;
  /** The stable hydraulic endpoint, when the record has one. */
  hydraulic: { heelDeg: number | null; trimDeg: number | null };
  notes: string[];
}

const finite = (value: unknown): number | null => typeof value === 'number' && Number.isFinite(value) ? value : null;
const text = (value: unknown): string => value === null || value === undefined ? '—' : String(value);

/** The frames the record accepted, so a frame index is never taken on trust. */
const frameAt = (result: LabResult, frame: number) => {
  const index = Math.max(0, Math.min(result.snapshots.length - 1, Math.trunc(frame)));
  return result.snapshots.length ? { index, state: result.snapshots[index] } : null;
};

export function explainTarget(result: LabResult, frame: number, target: InspectionTarget, t: LabCopy): TargetExplanation {
  const at = frameAt(result, frame);
  const notes: string[] = [];
  const fragmentation = result.fragmentation ?? null;
  const detonationEvent = result.events.find(event => event.kind === 'detonation') ?? null;
  // Before the burst there is nothing recorded *at* this frame to explain, so the
  // later evidence the saved run still holds must not be shown as if it were here.

  const empty: TargetExplanation = {
    target, frame: at?.index ?? Math.trunc(frame),
    beforeDetonation: false, exposure: null, paths: [], remainder: 0, boundaries: [], factors: [],
    flows: [], aggregate: false, hydraulic: { heelDeg: null, trimDeg: null }, notes: [],
  };

  if (!at) return { ...empty, notes: [t('explain.noFrames')] };
  // The record's own flag decides; only when it is absent does the event order
  // stand in for it, so a frame the run itself marked as detonated is never
  // treated as pre-burst.
  const beforeDetonation = at.state.detonation_occurred === false
    || (at.state.detonation_occurred === undefined && Boolean(detonationEvent && at.state.event_index < detonationEvent.index));
  if (beforeDetonation) return { ...empty, beforeDetonation, frame: at.index, notes: [t('explain.beforeDetonation')] };
  if (!fragmentation) return { ...empty, notes: [t('explain.noFragmentation')] };

  // --- Direct exposure: the paths that reached this target, most significant first.
  const hits: Array<{ trace: FragmentTrace; exposure: number | null }> = [];
  for (const trace of fragmentation.traces) {
    if (target.kind === 'compartment' && trace.segments.some(segment => segment.compartment_id === target.id)) { hits.push({trace,exposure:null}); continue; }
    const hit = trace.hits.find(entry => entry.kind === target.kind && entry.id === target.id);
    if (hit) hits.push({ trace, exposure: finite(hit.exposure) });
  }
  hits.sort((left, right) => (right.exposure ?? -1) - (left.exposure ?? -1));
  const listed = hits.slice(0, LISTED_PATHS);
  const paths: ContributingPath[] = listed.map(({ trace, exposure }) => ({
    index: trace.index,
    exposure,
    sequence: trace.segments.map(segment => `${segment.compartment_id} (${text(segment.boundary_transmission ?? segment.transmission)})`).join(' → '),
    blockedBy: trace.blocked_by,
    termination: trace.termination,
    source: 'game',
  }));
  const exposures = hits.map(entry => entry.exposure).filter((value): value is number => value !== null);
  const exposure = target.kind === 'module' ? finite(fragmentation.module_exposure[target.id]) : target.kind === 'crew' ? finite(fragmentation.crew_exposure[target.id]) : null;
  if (hits.length && hits.length > paths.length) notes.push(t('explain.remainder', { count: hits.length - paths.length }));

  // --- The boundary responses those paths crossed, from the recorded load and
  // threshold rather than from a re-derived breach.
  const crossed = new Set<string>();
  for (const { trace } of hits) for (const segment of trace.segments) if (segment.boundary_id) crossed.add(segment.boundary_id);
  const boundaries: BoundaryResponse[] = fragmentation.boundaries
    .filter(boundary => crossed.has(boundary.id))
    .map(boundary => {
      const absorbed = finite(boundary.absorbed_exposure), threshold = finite(boundary.breach_threshold);
      const plannedArea = finite(boundary.generated_area_m2);
      const accepted = at.state.generated_breaches?.find(hole => hole.id === `fragment:${boundary.id}` || (typeof hole.source === 'object' && hole.source.boundary_id === boundary.id));
      const area = accepted ? finite(accepted.area_m2) : plannedArea === null ? null : 0;
      const state: BoundaryResponse['state'] = absorbed === null || threshold === null ? 'unknown'
        : area === null ? 'unknown' : area > 0 ? 'generated'
          : (plannedArea ?? 0) > 0 || absorbed >= threshold ? 'deferred' : 'sealed';
      return { id: boundary.id, from: boundary.from_id, to: boundary.to_id, absorbedExposure: absorbed,
        threshold, generatedAreaM2: area, state, source: 'game' as const };
    });

  // --- Factors, each linked to the first accepted frame that changed it. The
  // frame and its event come from the record; nothing is attributed to a cause.
  const factors: FactorContribution[] = [];
  const firstChange = (read: (state: LabResult['snapshots'][number]) => number | null) => {
    const rows = result.snapshots;
    const value = read(at.state);
    // The earliest accepted frame that already holds this value is where the effect
    // was recorded. A value that has held since the first accepted frame did not
    // change here, so it gets no event rather than the first one.
    let first: number | null = null;
    for (let index = 0; index <= at.index; index += 1) {
      if (read(rows[index]) === value) { first = index; break; }
    }
    if (first === null || first === 0) return { firstFrame: null, firstEventIndex: null, firstEventTimeS: null };
    const state = rows[first];
    return { firstFrame: first, firstEventIndex: state.event_index, firstEventTimeS: finite(state.time_s) };
  };
  if (target.kind === 'module') {
    const moduleAt = (state: LabResult['snapshots'][number]) => state.modules.find(entry => entry.id === target.id);
    const current = moduleAt(at.state);
    if (!current) notes.push(t('explain.noTarget'));
    else {
      // Every reader takes the frame it is asked about. A closure that always read
      // the selected frame would find each value already in place and would then
      // attribute no change to any event at all.
      const kinds: Array<[FactorContribution['kind'], (state: LabResult['snapshots'][number]) => number | null, Provenance]> = [
        ['mechanical', state => finite(moduleAt(state)?.mechanical_integrity), 'game'],
        ['flooding', state => finite(moduleAt(state)?.flooding_availability), 'mixed'],
        ['staffing', state => finite(moduleAt(state)?.staffing_availability), 'game'],
      ];
      for (const [kind, read, source] of kinds) {
        factors.push({ kind, value: read(at.state), ...firstChange(read), source });
      }
    }
  }

  // Hydraulic observations belong to this accepted frame, never to the final core result.
  const native = at.state.ship;
  const targetRoom = target.kind === 'compartment' ? target.id : target.kind === 'module'
    ? at.state.modules.find(module => module.id === target.id)?.compartment_id
    : at.state.crew_groups.find(group => group.id === target.id)?.compartment_id;
  const roomName = (id: string) => id.startsWith('lab-water:') ? id.slice('lab-water:'.length) : id;
  const relevant = (from: string, to: string) => Boolean(targetRoom && (roomName(from) === targetRoom || roomName(to) === targetRoom));
  const flows: RecordedFlow[] = [];
  for (const row of native?.flows ?? []) {
    if (!relevant(row.from, row.to)) continue;
    const mass = finite(row.mass_flow_t_s), volume = finite(row.flow_m3_s), reversed = (mass ?? volume ?? 0) < 0;
    flows.push({ id: row.id, from: roomName(reversed ? row.to : row.from), to: roomName(reversed ? row.from : row.to),
      transferM3: null, massFlowTS: mass === null ? null : Math.abs(mass), flowM3S: volume === null ? null : Math.abs(volume), source: 'core' });
  }
  for (const row of native?.edge_transfers ?? []) {
    if (!relevant(row.from, row.to)) continue;
    const amount = finite(row.transfer_m3), reversed = (amount ?? 0) < 0;
    flows.push({ id: row.connection_id, from: roomName(reversed ? row.to : row.from), to: roomName(reversed ? row.from : row.to),
      transferM3: amount === null ? null : Math.abs(amount), massFlowTS: null, flowM3S: null, source: 'core' });
  }
  const aggregate = new Set(flows.map(flow => flow.id ?? `${flow.from}/${flow.to}`)).size > 1;
  if (aggregate) notes.push(t('explain.aggregate'));
  const heelDeg = finite(native?.equilibrium?.heel_deg), trimDeg = finite(native?.equilibrium?.trim_deg);
  if (heelDeg === null || trimDeg === null) notes.push(t('explain.noEndpoint'));
  if (!paths.length && !result.fragmentation?.module_exposure?.[target.id] && !result.fragmentation?.crew_exposure?.[target.id]) {
    notes.push(t('explain.noEvidence'));
  }

  return {
    target, frame: at.index, beforeDetonation: false, exposure, paths, remainder: Math.max(0, hits.length - paths.length),
    boundaries, factors, flows, aggregate, hydraulic: { heelDeg, trimDeg }, notes,
  };
}
