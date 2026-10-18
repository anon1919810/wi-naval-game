import { describe, expect, it } from 'vitest';

import {
  FEEDBACK_READING_KEYS, chapterForSourcePage, compareDraft, compareFrozen, designFingerprint,
  type DraftSide, type FeedbackLabels,
} from '../components/designFeedbackModel';
import type { AnalysisResult, ProjectDocument, ShipDesign, ShipDesignResult, StageEnvelope } from '../types';

/**
 * The draft feedback readers, before any of them are put on screen.
 *
 * These tests pin the four rules the panel depends on: the nine readings are the
 * saved paths read on both sides with a draft − saved difference; absent stays
 * absent rather than becoming a zero; a schema, method or basis mismatch withholds
 * every number; and the frozen report summary reads only the two saved results and
 * keeps the comparison − current sign its neighbour already uses.
 */

/* --------------------------------------------------------------- fixtures */

const native = (over: Partial<ShipDesignResult> = {}): ShipDesignResult => ({
  schema: 'plimsoll-ship-design-result-1',
  method_version: 'ship-design-native-v1',
  status: 'available',
  basis_condition_id: 'normal',
  balance: { selected_mass_t: 1000, estimated_mass_t: 980, target_displacement_t: 1050, difference_t: -5 },
  engine: { speedMax: 30, hpMax: 60000, range: 5000 },
  performance: { stability: 1.2, strengthComp: 0.98 },
  ...over,
} as ShipDesignResult);

const project = (parameters: Record<string, unknown> = {}, revision = 1): ProjectDocument => ({
  schema: 'plimsoll-project-1', id: 'p', name: 'P', revision, hull: {}, geometry: null,
  loading_conditions: [{ id: 'normal', label: 'Normal' }],
  weight_groups: [{ id: 'g', label: 'G', items: [] }],
  ship_design: {
    schema: 'plimsoll-ship-design-1', source: null, parameters, editing: {}, notes: null,
    condition_id: 'normal', mass_bindings: {},
  },
} as unknown as ProjectDocument);

const bare = (): ProjectDocument => {
  const value = project();
  delete (value as { ship_design?: unknown }).ship_design;
  return value;
};

const side = (over: Partial<DraftSide> = {}): DraftSide => ({ result: native(), project: project(), state: 'ready', ...over });

const reading = (feedback: ReturnType<typeof compareDraft>, key: string) => feedback.readings.find(item => item.key === key)!;

/* --------------------------------------------------------------- readings */

describe('draft readings', () => {
  it('reads the nine saved paths and subtracts the saved revision from the draft', () => {
    const saved = native();
    const draft = structuredClone(saved);
    draft.balance!.selected_mass_t = 1120;
    draft.engine!.speedMax = 31.5;
    draft.engine!.hpMax = 62000;
    draft.engine!.range = 5200;
    draft.performance!.stability = 1.15;
    draft.performance!.strengthComp = 0.9;

    const feedback = compareDraft(side({ result: saved }), side({ result: draft }), 'en', {});

    expect(FEEDBACK_READING_KEYS).toEqual([
      'balance.selected_mass_t', 'balance.estimated_mass_t', 'balance.target_displacement_t', 'balance.difference_t',
      'engine.speedMax', 'engine.hpMax', 'engine.range', 'performance.stability', 'performance.strength',
    ]);
    expect(feedback.comparable).toBe(true);
    expect(reading(feedback, 'balance.selected_mass_t')).toMatchObject({
      before: 1000, after: 1120, delta: 120, dimension: 'mass', storedUnit: 't', state: 'known',
    });
    expect(reading(feedback, 'balance.selected_mass_t').percent).toBeCloseTo(12);
    expect(reading(feedback, 'engine.speedMax')).toMatchObject({ delta: 1.5, dimension: 'speed', storedUnit: 'kn' });
    expect(reading(feedback, 'engine.hpMax')).toMatchObject({ delta: 2000, canonicalUnit: 'source hp', dimension: undefined });
    expect(reading(feedback, 'performance.stability').delta).toBeCloseTo(-0.05);
    expect(reading(feedback, 'performance.stability').canonicalUnit).toBe('empirical score');
    expect(reading(feedback, 'performance.strength').delta).toBeCloseTo(-0.08);
    expect(reading(feedback, 'performance.strength').canonicalUnit).toBe('empirical score');
  });

  it('keeps a genuine zero, an explicit null and a non-finite value three different facts', () => {
    const saved = native({ balance: { selected_mass_t: 0, estimated_mass_t: null, target_displacement_t: 1000, difference_t: Infinity } });
    const draft = structuredClone(saved);
    draft.balance!.selected_mass_t = 50;
    draft.balance!.estimated_mass_t = 40;

    const feedback = compareDraft(side({ result: saved }), side({ result: draft }), 'en', {});
    // A zero baseline is a real baseline: the change is shown absolutely, with no
    // percentage invented from it.
    expect(reading(feedback, 'balance.selected_mass_t')).toMatchObject({ before: 0, after: 50, delta: 50, percent: null, state: 'known' });
    expect(reading(feedback, 'balance.estimated_mass_t')).toMatchObject({ before: null, delta: null, state: 'unknown' });
    expect(reading(feedback, 'balance.difference_t')).toMatchObject({ before: null, delta: null, state: 'unknown' });
  });

  it('reflects the direction it is given: the same numbers compare the other way', () => {
    const saved = native();
    const draft = structuredClone(saved);
    draft.balance!.selected_mass_t = 900;
    const savedFirst = compareDraft(side({ result: saved }), side({ result: draft }), 'en', {});
    const draftFirst = compareDraft(side({ result: draft }), side({ result: saved }), 'en', {});
    expect(reading(savedFirst, 'balance.selected_mass_t').delta).toBe(-100);
    expect(reading(draftFirst, 'balance.selected_mass_t').delta).toBe(100);
  });

  it('reads only the composite hull strength — a missing composite is unknown, never another strength', () => {
    // Longitudinal and cross-sectional strength are different quantities; a
    // comparison must never subtract one of them from the other.
    const saved = native({ performance: { stability: 1, strengthLong: 0.8 } });
    const draft = native({ performance: { stability: 1, strengthLong: 0.9 } });
    const feedback = compareDraft(side({ result: saved }), side({ result: draft }), 'en', {});
    expect(reading(feedback, 'performance.strength')).toMatchObject({ before: null, after: null, state: 'unknown' });

    const composite = native({ performance: { stability: 1, strengthComp: 0.8 } });
    const next = native({ performance: { stability: 1, strengthComp: 0.9 } });
    const strength = reading(compareDraft(side({ result: composite }), side({ result: next }), 'en', {}),
      'performance.strength');
    expect(strength).toMatchObject({ before: 0.8, after: 0.9, beforeField: 'strengthComp' });
    expect(strength.delta).toBeCloseTo(0.1);
  });

  it('withholds every numeric difference when the schema, method or basis disagrees', () => {
    const saved = native();
    const otherMethod = structuredClone(saved);
    otherMethod.method_version = 'ship-design-native-v2';
    const method = compareDraft(side({ result: saved }), side({ result: otherMethod }), 'en', {});
    expect(method.comparable).toBe(false);
    expect(method.readings).toEqual([]);
    expect(method.warnings.join(' ')).toContain('do not both declare the supported native design method');

    const otherBasis = structuredClone(saved);
    otherBasis.basis_condition_id = 'ballast';
    const basis = compareDraft(side({ result: saved }), side({ result: otherBasis }), 'en', {});
    expect(basis.comparable).toBe(false);
    expect(basis.warnings.join(' ')).toContain('same known basis condition');

    const otherSchema = structuredClone(saved);
    otherSchema.schema = 'plimsoll-ship-design-result-2';
    const schema = compareDraft(side({ result: saved }), side({ result: otherSchema }), 'en', {});
    expect(schema.comparable).toBe(false);
    expect(schema.warnings.join(' ')).toContain('result shape');
  });

  it('treats an unestablished method, basis or project identity as no match at all', () => {
    const saved = native();
    // Both sides omitting the method is not agreement on a method.
    const noMethod = structuredClone(saved);
    delete (noMethod as { method_version?: unknown }).method_version;
    const method = compareDraft(side({ result: saved }), side({ result: noMethod }), 'en', {});
    expect(method.comparable).toBe(false);
    expect(method.warnings.join(' ')).toContain('supported native design method');

    // Both sides omitting the basis is not agreement on a basis.
    const noBasis = structuredClone(saved);
    delete (noBasis as { basis_condition_id?: unknown }).basis_condition_id;
    const basis = compareDraft(side({ result: noBasis }), side({ result: noBasis }), 'en', {});
    expect(basis.comparable).toBe(false);
    expect(basis.warnings.join(' ')).toContain('same known basis condition');

    // The declared condition and the result's own basis are one fact.
    const disagreeing = project();
    (disagreeing.ship_design as ShipDesign).condition_id = 'ballast';
    const condition = compareDraft(side({ result: saved }), side({ result: saved, project: disagreeing }), 'en', {});
    expect(condition.comparable).toBe(false);
    expect(condition.warnings.join(' ')).toContain('same known basis condition');

    // Two sides of different projects are not two revisions of one design.
    const otherProject = { ...project(), id: 'q' } as ProjectDocument;
    const projects = compareDraft(side({ result: saved }), side({ result: saved, project: otherProject }), 'en', {});
    expect(projects.comparable).toBe(false);
    expect(projects.warnings.join(' ')).toContain('same project');
  });
});

/* ------------------------------------------------------------- draft state */

describe('draft availability', () => {
  it('keeps the declared inputs but withholds the readings while an edit is pending', () => {
    const saved = side({ project: project({ beam: 20 }) });
    const draft = side({ project: project({ beam: 22 }), state: 'pending' });
    const feedback = compareDraft(saved, draft, 'en', {});
    expect(feedback.comparable).toBe(false);
    expect(feedback.readings).toEqual([]);
    expect(feedback.roles).toEqual([]);
    expect(feedback.warnings.join(' ')).toContain('still being confirmed');
    expect(feedback.inputs.map(input => input.key)).toEqual(['beam']);
  });

  it('names a failed saved read and offers no invented baseline for a revision with no design', () => {
    const failed = compareDraft(side({ state: 'failed', result: null }), side(), 'en', {});
    expect(failed.comparable).toBe(false);
    expect(failed.warnings.join(' ')).toContain('could not be read');

    const absent = compareDraft(side({ state: 'absent', result: null, project: bare() }), side({ project: project({ beam: 22 }) }), 'en', {});
    expect(absent.comparable).toBe(false);
    expect(absent.inputs).toEqual([]);
    expect(absent.warnings.join(' ')).toContain('declares no ship design');
  });
});

/* ------------------------------------------------------------ changed rows */

describe('changed inputs and roles', () => {
  it('lists only the declared inputs that changed, with each side\'s own unit and source page', () => {
    const labels: FeedbackLabels = {
      field: (key, side) => key === 'beam' ? { label: 'Beam', unit: side === 'before' ? 'ft' : 'm', page: 'hull' }
        : key === 'shaft_power' ? { label: 'Shaft power', unit: 'shp', page: 'engine' }
          : null,
    };
    const saved = side({ project: project({ beam: 20, shaft_power: 100, draught: 5 }) });
    const draft = side({ project: project({ beam: 6.1, shaft_power: 100, draught: 6 }) });
    const feedback = compareDraft(saved, draft, 'en', labels);
    expect(feedback.inputs.map(input => input.key).sort()).toEqual(['beam', 'draught']);
    const beam = feedback.inputs.find(input => input.key === 'beam')!;
    expect(beam).toMatchObject({
      label: 'Beam', before: 20, after: 6.1, beforeUnit: 'ft', afterUnit: 'm', unitChanged: true, chapter: 'hull',
    });
    const draught = feedback.inputs.find(input => input.key === 'draught')!;
    // An unlabelled recovered name stays its own register name.
    expect(draught).toMatchObject({ label: 'draught', beforeUnit: null, afterUnit: null, unitChanged: false, chapter: null });
  });

  it('ranks changed role masses by size and records a changed policy', () => {
    const ledger = (roles: Record<string, unknown>) => native({ ledger: { schema: 'plimsoll-ship-design-1', roles } as ShipDesignResult['ledger'] });
    const saved = side({ result: ledger({
      machinery: { selected_mass_t: 100, estimate_t: 95, mode: 'estimated' },
      armour: { selected_mass_t: 300, estimate_t: 300, mode: 'estimated' },
      guns: { selected_mass_t: 50, estimate_t: 50, mode: 'declared' },
    }) });
    const draft = side({ result: ledger({
      machinery: { selected_mass_t: 110, estimate_t: 95, mode: 'estimated' },
      armour: { selected_mass_t: 400, estimate_t: 300, mode: 'declared' },
      guns: { selected_mass_t: 50, estimate_t: 50, mode: 'declared' },
    }) });
    const feedback = compareDraft(saved, draft, 'en', { role: role => role.toUpperCase() });
    expect(feedback.roles.map(role => role.role)).toEqual(['armour', 'machinery']);
    expect(feedback.roles[0]).toMatchObject({ label: 'ARMOUR', beforeMode: 'estimated', afterMode: 'declared', delta: 100 });
    expect(feedback.roles[1]).toMatchObject({ label: 'MACHINERY', delta: 10 });
    expect(feedback.roles.some(role => role.role === 'guns')).toBe(false);
  });

  it('does not call two identical unknown role masses a change', () => {
    const ledger = (roles: Record<string, unknown>) => native({ ledger: { schema: 'plimsoll-ship-design-1', roles } as ShipDesignResult['ledger'] });
    const unknown = { selected_mass_t: null, estimate_t: null, mode: null, target_mass_t: null, difference_t: null };
    const feedback = compareDraft(
      side({ result: ledger({ other: unknown }) }), side({ result: ledger({ other: unknown }) }), 'en', {});
    expect(feedback.roles).toEqual([]);
  });

  it('fingerprints the saved design content, not only its project and revision number', () => {
    const first = project({ beam: 20 });
    const second = project({ beam: 24 });
    // A same-revision replacement is a different saved document, so its cached
    // preview must not be reused for the old content.
    expect(first.revision).toBe(second.revision);
    expect(designFingerprint(first)).not.toBe(designFingerprint(second));
    expect(designFingerprint(first)).toBe(designFingerprint(project({ beam: 20 })));
  });

  it('maps only the chapters the one source-page table names', () => {
    expect(chapterForSourcePage('engine')).toBe('propulsion');
    expect(chapterForSourcePage('hull')).toBe('hull');
    expect(chapterForSourcePage('nonsense')).toBeNull();
    expect(chapterForSourcePage(null)).toBeNull();
  });
});

/* ------------------------------------------------------------- frozen runs */

const stage = (data: unknown, over: Partial<StageEnvelope> = {}): StageEnvelope => ({
  status: 'completed', requested: true, reason: null, assumptions: [], diagnostics: [],
  method_versions: { kernel: 'ship-design-native-v1' },
  validity: { complete: true, converged: true, model_applicable: true, historical_validated: null },
  data: data as Record<string, unknown>, ...over,
});

const analysis = (data: ShipDesignResult | null, over: Partial<AnalysisResult> = {}, snapshot: ProjectDocument = project()): AnalysisResult => ({
  schema: 'plimsoll-analysis-1', status: 'completed', project_id: 'p', condition_id: 'normal',
  project_fingerprint: 'p', input_fingerprint: 'i', request_fingerprint: 'r', request: {},
  input_snapshot: snapshot, units: {}, method_versions: {}, sources: {}, diagnostics: [],
  validity: { complete: true, converged: true, model_applicable: true, historical_validated: null },
  stages: data ? { ship_design: stage(data) } : {}, ...over,
} as AnalysisResult);

describe('frozen report summary', () => {
  it('compares comparison − current using only the two saved results', () => {
    const current = analysis(native());
    const comparison = analysis(native({ balance: { selected_mass_t: 1050, estimated_mass_t: 990, target_displacement_t: 1060, difference_t: -4 } }));
    const feedback = compareFrozen(current, comparison, 'en', {})!;
    expect(feedback.comparable).toBe(true);
    expect(reading(feedback, 'balance.selected_mass_t')).toMatchObject({ before: 1000, after: 1050, delta: 50 });
    expect(feedback.scopeNote).toBeNull();
  });

  it('returns nothing when neither run carries a native stage', () => {
    expect(compareFrozen(analysis(null), analysis(null), 'en', {})).toBeNull();
  });

  it('names an unreadable or unrequested stage and withholds the numbers', () => {
    const current = analysis(native());
    const unrequested = analysis(null);
    (unrequested as unknown as { stages: AnalysisResult['stages'] }).stages = { ship_design: stage(native(), { requested: false, status: 'not_requested' }) };
    const feedback = compareFrozen(current, unrequested, 'en', {})!;
    expect(feedback.comparable).toBe(false);
    expect(feedback.warnings.join(' ')).toContain('comparison run has no readable native design stage');

    const failed = analysis(null);
    (failed as unknown as { stages: AnalysisResult['stages'] }).stages = { ship_design: stage(native(), { status: 'failed' }) };
    expect(compareFrozen(analysis(native()), failed, 'en', {})!.comparable).toBe(false);
  });

  it('withholds the numbers across a changed native basis, and warns about optional scope', () => {
    const current = analysis(native({ basis_condition_id: 'normal' }));
    const other = analysis(native({ basis_condition_id: 'ballast' }));
    expect(compareFrozen(current, other, 'en', {})!.comparable).toBe(false);

    const withPhysical = analysis(native({ basis_condition_id: 'normal' }), { stages: {
      ship_design: stage(native({ basis_condition_id: 'normal' })),
      loading: stage({ values: { total_mass_t: 900 } }),
    } });
    const feedback = compareFrozen(current, withPhysical, 'en', {})!;
    expect(feedback.comparable).toBe(true);
    expect(feedback.scopeNote).toContain('optional physical stages');
  });

  it('refuses a stage whose declared kernel disagrees with its payload', () => {
    const current = analysis(native());
    const mismatched = analysis(null);
    (mismatched as unknown as { stages: AnalysisResult['stages'] }).stages = {
      ship_design: stage(native(), { method_versions: { kernel: 'unrelated-kernel' } }),
    };
    const feedback = compareFrozen(current, mismatched, 'en', {})!;
    expect(feedback.comparable).toBe(false);
    expect(feedback.warnings.join(' ')).toContain('kernel identity');
  });

  it('refuses a run whose snapshot or project identity disagrees', () => {
    const current = analysis(native());
    const foreignSnapshot = analysis(native(), {}, { ...project(), id: 'q' } as ProjectDocument);
    const snapshot = compareFrozen(current, foreignSnapshot, 'en', {})!;
    expect(snapshot.comparable).toBe(false);
    expect(snapshot.warnings.join(' ')).toContain('input snapshot');

    const foreignProject = analysis(native(), { project_id: 'q' },
      { ...project(), id: 'q' } as ProjectDocument);
    const projects = compareFrozen(current, foreignProject, 'en', {})!;
    expect(projects.comparable).toBe(false);
    expect(projects.warnings.join(' ')).toContain('same project');
  });

  it('honours the report identity verdict without rejecting a different optional scope', () => {
    const current = analysis(native());
    const other = analysis(native());
    const invalid = compareFrozen(current, other, 'en', {}, { currentValid: false })!;
    expect(invalid.comparable).toBe(false);
    expect(invalid.warnings.join(' ')).toContain('saved envelope does not agree');

    const withPhysical = analysis(native(), { stages: {
      ship_design: stage(native()),
      loading: stage({ values: { total_mass_t: 900 } }),
    } });
    const scoped = compareFrozen(current, withPhysical, 'en', {}, { currentValid: true, comparisonValid: true })!;
    expect(scoped.comparable).toBe(true);
  });

  it('reads changed inputs from the two immutable snapshots', () => {
    const current = analysis(native(), {}, project({ beam: 20 }));
    const comparison = analysis(native(), {}, project({ beam: 24 }));
    const feedback = compareFrozen(current, comparison, 'en', {})!;
    expect(feedback.inputs.map(input => input.key)).toEqual(['beam']);
    expect(feedback.inputs[0]).toMatchObject({ before: 20, after: 24 });
  });
});


describe('saved document identity includes declared ledger mass', () => {
  it('invalidates the same revision when only a declared mass changes', () => {
    const first = project();
    first.weight_groups[0].items = [{ id: 'manual', name: 'Manual', mass_t: 10 }] as any;
    const next = structuredClone(first);
    next.weight_groups[0].items[0].mass_t = 20;
    expect(designFingerprint(first)).not.toBe(designFingerprint(next));
  });
});
