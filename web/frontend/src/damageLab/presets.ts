import { boundaryCandidates, bounds, META } from './Detonation';
import type { Boundary, Experiment, Room, Vec3 } from './types';
import type { ProjectDocument } from '../types';

/**
 * The three synthetic experiment presets.
 *
 * They exist so one comparison can be run without assembling it by hand. What
 * changes between the shielding pair is exactly one declared wall's fragment
 * transmission; the sea-opening preset adds exactly one declared exterior
 * response to that same baseline. Everything else — the declared origin, the
 * severity, the radius, the sample count and the seed — is carried over, so a
 * difference in the result is read against a *stated* difference in the input.
 *
 * Nothing here is a historical claim. The provenance is the same normalized game
 * provenance the boundary editor writes (`META`), never a surveyed armour class
 * or a real explosive mass, and preparing a preset runs nothing: it returns a
 * draft that the existing preview and run actions still have to accept.
 */

export type PresetName = 'shielded' | 'transmitted' | 'sea-opening';
export const PRESET_NAMES: readonly PresetName[] = ['shielded', 'transmitted', 'sea-opening'] as const;

/** Why a preset cannot be prepared for this vessel, or null when it can. */
export type PresetProblem = 'unsupported' | 'noSharedWall' | 'noExteriorFace';

export interface PresetAssumption {
  /** A lab copy key, resolved by the page in the reader's language. */
  key: string;
  params?: Readonly<Record<string, string | number>>;
}

export interface PreparedPreset {
  experiment: Experiment;
  /** What this preset declares, shown before anything runs. */
  assumptions: PresetAssumption[];
}

/** The sample count and seed the shielding pair shares: the app's own accepted pair. */
const SAMPLES = 128;
const SEED = 42;
/** The one input the shielding pair changes. */
const TRANSMITTED = 0.35;

const roomsOf = (project: ProjectDocument): Room[] => (project.compartments ?? []) as unknown as Room[];

/** The room the declared origin sits in, by the same boxes the scene draws. */
function originRoom(rooms: Room[], origin: Vec3): Room | null {
  return rooms.find(room => {
    const { c, s } = bounds(room);
    return origin.every((value, axis) => value >= c[axis] - s[axis] / 2 - 1e-9 && value <= c[axis] + s[axis] / 2 + 1e-9);
  }) ?? null;
}

/** The interior wall that borders the origin's room. */
function sharedWall(rooms: Room[], origin: Room): Boundary | null {
  return boundaryCandidates(rooms).find(candidate => candidate.to_id !== 'sea'
    && (candidate.from_id === origin.id || candidate.to_id === origin.id)) ?? null;
}

/** The origin room's own exterior face: the accepted proxy for an opening to sea. */
function exteriorFace(rooms: Room[], origin: Room): Boundary | null {
  return boundaryCandidates(rooms).find(candidate => candidate.id === `face:${origin.id}:2:-1`) ?? null;
}

/**
 * Whether this vessel can carry the preset at all.
 *
 * A layout where the declared origin is outside every room, or where the origin
 * room has no neighbouring wall or no exterior face, gets an explanation rather
 * than a guessed connectivity: the laboratory's flooding model is only as honest
 * as the boundaries it is given.
 */
export function presetProblem(project: ProjectDocument, baseline: Experiment, preset: PresetName): PresetProblem | null {
  const rooms = roomsOf(project);
  const origin = originRoom(rooms, baseline.impact.position_m);
  if (!origin) return 'unsupported';
  if (!sharedWall(rooms, origin)) return 'noSharedWall';
  if (preset === 'sea-opening') return exteriorFace(rooms, origin) ? null : 'noExteriorFace';
  return sharedWall(rooms, origin) ? null : 'noSharedWall';
}

/**
 * A draft for one preset. The caller's baseline is never modified, and the draft
 * shares nothing with it, so applying a preset twice or applying two presets in
 * a row cannot accumulate changes.
 */
export function buildPreset(project: ProjectDocument, baseline: Experiment, preset: PresetName): PreparedPreset | { problem: PresetProblem } {
  const problem = presetProblem(project, baseline, preset);
  if (problem) return { problem };

  const rooms = roomsOf(project);
  const origin = originRoom(rooms, baseline.impact.position_m)!;
  const wall = sharedWall(rooms, origin)!;
  const boundaries: Boundary[] = [{
    ...wall,
    position_m: [...wall.position_m],
    transmission: preset === 'transmitted' ? TRANSMITTED : wall.transmission,
  }];
  const assumptions: PresetAssumption[] = [{ key: 'preset.assumption.shared' }];
  if (preset === 'transmitted') assumptions.push({ key: 'preset.assumption.transmission', params: { value: TRANSMITTED } });
  if (preset === 'sea-opening') {
    const face = exteriorFace(rooms, origin)!;
    boundaries.push({ ...face, position_m: [...face.position_m] });
    assumptions.push({ key: 'preset.assumption.seaOpening' });
  }

  return {
    experiment: {
      ...structuredClone(baseline),
      duration_s: 12, time_step_s: 1,
      impact: { ...structuredClone(baseline.impact), severity: 0.6, radius_m: 8 },
      initial_water_m3: Object.fromEntries(rooms.map(room => [room.id, 0])),
      breaches: [],
      detonation: { position_m: [...baseline.impact.position_m], fragment_count: SAMPLES, seed: SEED, boundaries, ...META },
    },
    assumptions,
  };
}
