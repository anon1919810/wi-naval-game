import { describe, expect, it, vi } from 'vitest';

// Load the actual Python fixtures through the test runner, outside Vite's public
// root, the way the hull tests do: this project carries no `@types/node`, so the
// module is reached through vitest rather than through a plain import.
const { readFileSync } = await vi.importActual<{
  readFileSync(path: string, encoding: 'utf8'): string;
}>('node:fs');

import { buildPreset, PRESET_NAMES, presetProblem } from './presets';
import type { Experiment } from './types';
import type { ProjectDocument } from '../types';

/**
 * The three synthetic presets.
 *
 * The point of these is that a reader can trust the comparison they set up: the
 * shielding pair must differ in exactly one declared input, the sea-opening
 * preset must add exactly one declared response to that same baseline, and the
 * caller's experiment must come back untouched so presets cannot accumulate.
 */

const project: ProjectDocument = JSON.parse(
  readFileSync('../../tools/plimsoll/cases/damage_lab/synthetic-vessel.project.json', 'utf8')) as ProjectDocument;
const baseline: Experiment = JSON.parse(
  readFileSync('../../tools/plimsoll/cases/damage_lab/synthetic-vessel.experiment.json', 'utf8')) as Experiment;

const draft = (name: 'shielded' | 'transmitted' | 'sea-opening') => {
  const built = buildPreset(project, baseline, name);
  if ('problem' in built) throw new Error(`expected a draft for ${name}, got ${built.problem}`);
  return built;
};

/** Digits the fixtures actually need: a comparison of like for like. */
const withDigit = (preset: 'shielded' | 'transmitted' | 'sea-opening') => {
  const experiment = draft(preset).experiment;
  return { walls: experiment.detonation!.boundaries, detonation: experiment.detonation! };
};

describe('synthetic experiment presets', () => {
  it('offers all three presets for the synthetic vessel', () => {
    for (const preset of PRESET_NAMES) expect(presetProblem(project, baseline, preset)).toBeNull();
  });

  it('changes exactly one declared input between the shielding pair', () => {
    const shielded = withDigit('shielded');
    const transmitted = withDigit('transmitted');

    expect(shielded.walls).toHaveLength(1);
    expect(transmitted.walls).toHaveLength(1);
    // Same origin, same sample count, same seed, same wall, same everything else.
    expect(transmitted.detonation.position_m).toEqual(shielded.detonation.position_m);
    expect(transmitted.detonation.fragment_count).toBe(shielded.detonation.fragment_count);
    expect(transmitted.detonation.fragment_count).toBe(128);
    expect(transmitted.detonation.seed).toBe(shielded.detonation.seed);
    expect(transmitted.detonation.seed).toBe(42);
    expect(transmitted.walls[0].id).toBe(shielded.walls[0].id);
    // …and exactly the one input the preset is for.
    expect(shielded.walls[0].transmission).toBe(0);
    expect(transmitted.walls[0].transmission).toBe(0.35);
    const { transmission: _a, ...shieldedWall } = shielded.walls[0];
    const { transmission: _b, ...transmittedWall } = transmitted.walls[0];
    expect(transmittedWall).toEqual(shieldedWall);
  });

  it('declares the wall between the origin compartment and its neighbour, not a guessed one', () => {
    const { walls, detonation } = withDigit('shielded');
    const wall = walls[0];
    // The origin sits in the starboard machinery room; the wall that shields the
    // port machinery room is the one the pair varies.
    expect(wall.to_id).not.toBe('sea');
    expect([wall.from_id, wall.to_id].sort()).toEqual(['port-machinery', 'starboard-machinery']);
    expect(detonation.position_m).toEqual(baseline.impact.position_m);
    // The same declared origin, severity and radius: only the model is switched on.
    expect(draft('shielded').experiment.impact).toMatchObject({position_m:baseline.impact.position_m,severity:0.6,radius_m:8});
  });

  it('adds exactly one exterior response to the same baseline for the sea opening', () => {
    const shielded = withDigit('shielded');
    const opening = withDigit('sea-opening');

    expect(opening.walls).toHaveLength(2);
    // The wall is carried over unchanged: the sea opening isolates one effect.
    expect(opening.walls[0]).toEqual(shielded.walls[0]);
    expect(opening.detonation.position_m).toEqual(shielded.detonation.position_m);
    expect(opening.detonation.fragment_count).toBe(shielded.detonation.fragment_count);
    expect(opening.detonation.seed).toBe(shielded.detonation.seed);
    // The added response is the origin compartment's own exterior face.
    const added = opening.walls[1];
    expect(added.to_id).toBe('sea');
    expect(added.from_id).toBe('starboard-machinery');
    expect(added.id.startsWith('face:starboard-machinery:')).toBe(true);
  });

  it('removes manual holes and initial water so the standard comparison starts clean', () => {
    for(const name of PRESET_NAMES){
      const e=draft(name).experiment;
      expect(e.breaches).toEqual([]);expect(Object.values(e.initial_water_m3).every(v=>v===0)).toBe(true);
      expect(e.impact.radius_m).toBe(8);expect(e.duration_s).toBe(12);
    }
  });

  it('never claims a historical armour class or a real explosive mass', () => {
    for (const preset of PRESET_NAMES) {
      const { detonation, walls } = withDigit(preset);
      expect(detonation.estimate).toBe(true);
      expect(detonation.source).toContain('not surveyed armor or explosive calibration');
      expect(walls.every(wall => wall.estimate === true)).toBe(true);
      expect(walls.every(wall => wall.source === detonation.source)).toBe(true);
    }
  });

  it('returns a draft that shares nothing with the caller’s experiment', () => {
    const before = JSON.stringify(baseline);
    const built = draft('transmitted');
    // The caller's experiment is byte-for-byte what it was…
    expect(JSON.stringify(baseline)).toBe(before);
    // …and the draft is a new object all the way down, so a later edit to the
    // draft cannot reach back into it.
    expect(built.experiment).not.toBe(baseline);
    expect(built.experiment.modules).not.toBe(baseline.modules);
    expect(built.experiment.detonation!.boundaries).not.toBe(baseline.detonation?.boundaries);
    built.experiment.modules[0].required_staff = 999;
    built.experiment.detonation!.boundaries[0].transmission = 1;
    expect(JSON.stringify(baseline)).toBe(before);
  });

  it('explains an unsupported layout instead of guessing connectivity', () => {
    const nowhere = { ...project, compartments: [] } as unknown as ProjectDocument;
    expect(presetProblem(nowhere, baseline, 'shielded')).toBe('unsupported');
    expect('problem' in buildPreset(nowhere, baseline, 'shielded')).toBe(true);

    // One room that holds the origin has exterior faces but no neighbouring wall,
    // so the shielding pair cannot be prepared there.
    const alone = {
      ...project,
      compartments: [{ id: 'starboard-machinery', label: 'Starboard machinery', x_m: -4, y_m: 1.6,
        keel_to_bottom_m: 0.8, length_m: 8, beam_m: 3.2, height_m: 3.2, permeability: 0.8 }],
    } as unknown as ProjectDocument;
    expect(presetProblem(alone, baseline, 'shielded')).toBe('noSharedWall');
    expect(presetProblem(alone, baseline, 'sea-opening')).toBe('noSharedWall');
    expect(buildPreset(alone,baseline,'sea-opening')).toEqual({problem:'noSharedWall'});
  });

  it('prepares nothing at all when the preset cannot be prepared', () => {
    const nowhere = { ...project, compartments: [] } as unknown as ProjectDocument;
    const built = buildPreset(nowhere, baseline, 'transmitted');
    expect('problem' in built && built.problem).toBe('unsupported');
    // No experiment is returned, so nothing can be previewed or run by accident.
    expect('experiment' in built).toBe(false);
  });
});
