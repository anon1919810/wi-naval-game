import { englishCopy, number, numericProblem, numericValue, object, rows, stringList, type NumericDomain, type Raw } from './formModel';
import type { Copy } from './diagnosticGuidance';
import type { Dimension } from './units';
import type { WorkspaceKey } from '../i18n/workspace';

// Saved flooding scenario drafts and the flooding run request.
//
// A saved scenario is research input, not a second weight ledger: it holds tank
// geometry, declared initial liquid, connections and openings for one damage
// case. Nothing here solves anything. The run request only assembles
// `options.flooding = {scenario, options}`; the kernel and the coordinator remain
// the authority for whether a scenario is calculable.
//
// The refusal messages and the field labels are dictionary keys read through the
// `Copy` the caller passes, so this module stays pure; without one it answers in
// English, the workspace's own default.

export const SCENARIO_SCHEMA = 'plimsoll-flooding-scenario-1';

// The equilibrium density the coordinator uses unless a caller overrides it
// (tools/plimsoll/_analysis_request.equilibrium_options default). Scenario sea
// density must match it exactly, otherwise the run is refused.
export const EQUILIBRIUM_RHO_T_M3 = 1.025;

export interface FieldSpec { key: string; label: WorkspaceKey; kind: NumericDomain; dimension?: Dimension; storedUnit?: string }

// Liquid density stays canonical: no dimension is declared for it, so it is
// typed and shown unchanged under every reader preference.
export const TANK_FIELDS: FieldSpec[] = [
  { key: 'length_m', label: 'floodingField.length', kind: 'positive', dimension: 'length' },
  { key: 'beam_m', label: 'floodingField.beam', kind: 'positive', dimension: 'length' },
  { key: 'height_m', label: 'floodingField.height', kind: 'positive', dimension: 'length' },
  { key: 'x_m', label: 'floodingField.x', kind: 'signed', dimension: 'length' },
  { key: 'y_m', label: 'floodingField.y', kind: 'signed', dimension: 'length' },
  { key: 'keel_to_bottom_m', label: 'floodingField.keelToBottom', kind: 'nonnegative', dimension: 'length' },
  { key: 'permeability', label: 'floodingField.permeability', kind: 'nonnegative' },
  { key: 'initial_volume_m3', label: 'floodingField.initialVolume', kind: 'nonnegative', dimension: 'volume' },
];
export const CONNECTION_FIELDS: FieldSpec[] = [
  { key: 'x_m', label: 'floodingField.x', kind: 'signed', dimension: 'length' },
  { key: 'y_m', label: 'floodingField.y', kind: 'signed', dimension: 'length' },
  { key: 'z_m', label: 'floodingField.z', kind: 'signed', dimension: 'length' },
  { key: 'area_m2', label: 'floodingField.area', kind: 'nonnegative', dimension: 'area' },
  { key: 'discharge_coefficient', label: 'floodingField.dischargeCoefficient', kind: 'nonnegative' },
  { key: 'aperture_height_m', label: 'floodingField.apertureHeight', kind: 'positive', dimension: 'length' },
];
export const APERTURE_HEIGHT = CONNECTION_FIELDS.find(field => field.key === 'aperture_height_m') as FieldSpec;

export function tanks(scenario: Raw): Raw[] { return rows(scenario.tanks); }
export function connections(scenario: Raw): Raw[] { return rows(scenario.connections); }
export function sea(scenario: Raw): Raw { return object(scenario.sea); }

export function newScenario(id: string): Raw {
  return {
    schema: SCENARIO_SCHEMA, id, label: '', duration_s: null, time_step_s: null,
    source: null, estimate: null,
    sea: { id: 'sea', fluid_density_t_m3: null, source: null, estimate: null },
    tanks: [], connections: [],
  };
}

export function newTank(id: string): Raw {
  const tank: Raw = { id };
  for (const field of TANK_FIELDS) tank[field.key] = null;
  tank.free_surface = null;
  tank.source = null;
  tank.estimate = null;
  return tank;
}

// `aperture_height_m` is deliberately absent here: the finite-height
// applicability check is optional, and a stored null would be a declared value
// the kernel would then have to reject. The editor adds the key only when the
// user asks for the check.
export function newConnection(id: string): Raw {
  const edge: Raw = { id };
  for (const field of CONNECTION_FIELDS) if (field.key !== 'aperture_height_m') edge[field.key] = null;
  edge.fluid_density_t_m3 = null;
  return edge;
}

export function withApertureHeight(edge: Raw, requested: boolean): Raw {
  const next = { ...edge };
  if (!requested) delete next.aperture_height_m;
  else if (!('aperture_height_m' in next)) next.aperture_height_m = null;
  return next;
}

export function newOpening(id: string): Raw {
  return { id, open: true, x_m: null, y_m: null, z_m: null, source: null, estimate: null };
}

// Scenario compartments are copied from the project on explicit request only.
// The copy keeps declared geometry, source and estimate; the initial liquid is
// left unknown because the project does not declare it.
export function tankFromCompartment(compartment: Raw, seaDensity: number | null): Raw | null {
  const required = ['length_m', 'beam_m', 'height_m', 'x_m', 'y_m', 'keel_to_bottom_m', 'permeability'];
  if (!required.every(field => number(compartment[field]) !== null)) return null;
  const tank: Raw = { id: String(compartment.id) };
  for (const field of TANK_FIELDS) tank[field.key] = number(compartment[field.key]);
  // Project geometry can carry legacy water metadata; a research copy never
  // adopts that water as a new addition to the selected loading ledger.
  tank.initial_volume_m3 = null;
  tank.free_surface = typeof compartment.free_surface === 'boolean' ? compartment.free_surface : null;
  if (seaDensity !== null) tank.fluid_density_t_m3 = seaDensity;
  tank.source = compartment.source ?? null;
  tank.estimate = compartment.estimate ?? null;
  return tank;
}

export interface FloodingRequest {
  scenario: string; rho: string; steps: string; halvings: string; gravity: string;
  /** Canonical remaining-GZ samples in degrees; an empty list requests none. */
  gzAngles: number[]; gzSnapshot: 'final' | 'each_state';
}

export const EMPTY_FLOODING_REQUEST: FloodingRequest = {
  scenario: '', rho: '', steps: '', halvings: '', gravity: '', gzAngles: [], gzSnapshot: 'final',
};

// An explicit environment density is a request choice, not a hidden default: an
// empty field sends nothing and the kernel default (1.025 t/m³ seawater) applies
// to every stage of this run, including the remaining-GZ samples.
export function environmentDensity(request: FloodingRequest): number | null {
  const raw = request.rho.trim();
  if (raw === '') return null;
  return numericProblem('positive', raw) ? null : numericValue(raw);
}

function knownSource(value: unknown): boolean {
  return typeof value === 'string' ? value.trim() !== ''
    : !!value && typeof value === 'object' && Object.keys(value).length > 0;
}
function triState(value: unknown): boolean | null { return typeof value === 'boolean' ? value : null; }

export function requestOptionProblem(request: FloodingRequest, w: Copy = englishCopy): string | null {
  if (request.rho.trim() !== '' && numericProblem('positive', request.rho, w)) return w('flooding.request.rho');
  if (request.steps.trim() !== '') {
    const value = Number(request.steps);
    if (!Number.isInteger(value) || value < 1 || value > 100000) return w('flooding.request.steps');
  }
  if (request.halvings.trim() !== '') {
    const value = Number(request.halvings);
    if (!Number.isInteger(value) || value < 0 || value > 60) return w('flooding.request.halvings');
  }
  if (request.gravity.trim() !== '' && numericProblem('positive', request.gravity, w)) return w('flooding.request.gravity');
  if (request.gzAngles.length > 0) {
    const angles = request.gzAngles;
    if (!angles.length || angles.length > 201 || angles.some(value => !Number.isFinite(value))
      || angles.some((value, index) => index > 0 && value <= angles[index - 1])) {
      return w('flooding.request.gzAngles');
    }
  }
  return null;
}

// Everything a run needs, checked without touching a solver. The messages name
// the offending field so the run is refused for a reason the user can fix.
export function scenarioProblems(scenario: Raw, ledgerIds: string[], environmentRho = EQUILIBRIUM_RHO_T_M3, w: Copy = englishCopy): string[] {
  const problems: string[] = [];
  if (scenario.schema !== SCENARIO_SCHEMA) problems.push(w('flooding.problem.schema'));
  const duration = scenario.duration_s;
  if (number(duration) === null || (number(duration) as number) < 0) problems.push(w('flooding.problem.duration'));
  const step = scenario.time_step_s;
  if (number(step) === null || (number(step) as number) <= 0) problems.push(w('flooding.problem.timeStep'));
  if (!knownSource(scenario.source)) problems.push(w('flooding.problem.scenarioSource'));
  if (triState(scenario.estimate) === null) problems.push(w('flooding.problem.scenarioEstimate'));
  const water = sea(scenario);
  const seaId = typeof water.id === 'string' && water.id.trim() ? water.id : null;
  if (!seaId) problems.push(w('flooding.problem.seaId'));
  const seaDensity = number(water.fluid_density_t_m3);
  if (seaDensity === null || seaDensity <= 0) problems.push(w('flooding.problem.seaDensity'));
  else if (seaDensity !== environmentRho) problems.push(w('flooding.problem.seaMatchesRho', { rho: environmentRho }));
  if (!knownSource(water.source) || triState(water.estimate) === null) problems.push(w('flooding.problem.seaProvenance'));

  const declared = tanks(scenario);
  const ids = new Set<string>();
  if (declared.length === 0) problems.push(w('flooding.problem.needsTank'));
  for (const tank of declared) {
    const label = w('flooding.problem.tankLabel', { id: String(tank.id ?? '?') });
    if (typeof tank.id !== 'string' || !tank.id.trim()) { problems.push(w('flooding.problem.tankId')); continue; }
    if (ids.has(tank.id)) problems.push(w('flooding.problem.tankDuplicate', { id: tank.id }));
    ids.add(tank.id);
    if (seaId && tank.id === seaId) problems.push(w('flooding.problem.tankSeaName', { id: tank.id }));
    if (ledgerIds.includes(tank.id)) problems.push(w('flooding.problem.tankLedgerName', { id: tank.id }));
    for (const field of TANK_FIELDS) {
      if (field.key === 'permeability') continue;
      if (number(tank[field.key]) === null) problems.push(w('flooding.problem.unknown', { label, field: w(field.label) }));
    }
    const permeability = number(tank.permeability);
    if (permeability === null || permeability < 0 || permeability > 1) problems.push(w('flooding.problem.tankPermeability', { label }));
    if (triState(tank.free_surface) === null) problems.push(w('flooding.problem.tankFreeSurface', { label }));
    const density = number(tank.fluid_density_t_m3);
    if (seaDensity !== null && density !== seaDensity) problems.push(w('flooding.problem.tankDensity', { label }));
    if (!knownSource(tank.source) || triState(tank.estimate) === null) problems.push(w('flooding.problem.provenance', { label }));
  }

  const edges = connections(scenario);
  for (const tank of declared) {
    if (tank.free_surface === false && edges.some(edge => edge.open === true &&
      (edge.from === tank.id || edge.to === tank.id))) {
      problems.push(w('flooding.problem.tankOpen', { id: String(tank.id) }));
    }
  }
  if (edges.length === 0) problems.push(w('flooding.problem.needsConnection'));
  const nodes = new Set<string>([...(seaId ? [seaId] : []), ...ids]);
  for (const edge of edges) {
    const label = w('flooding.problem.connectionLabel', { id: String(edge.id ?? '?') });
    if (typeof edge.id !== 'string' || !edge.id.trim()) { problems.push(w('flooding.problem.connectionId')); continue; }
    for (const side of ['from', 'to'] as const) {
      const reference = edge[side];
      if (typeof reference !== 'string' || !nodes.has(reference)) problems.push(w('flooding.problem.connectionSide', { label, side }));
    }
    if (edge.from === edge.to) problems.push(w('flooding.problem.connectionSelfLoop', { label }));
    for (const field of CONNECTION_FIELDS) {
      if (field.key === 'aperture_height_m') continue;
      if (number(edge[field.key]) === null) problems.push(w('flooding.problem.unknown', { label, field: w(field.label) }));
    }
    // An absent or null aperture height simply requests no finite-height check,
    // exactly as the kernel treats a missing key.
    // Requesting the finite-aperture check requires a known positive height; leaving
    // the key out entirely means no applicability check was requested at all.
    const aperture = number(edge.aperture_height_m);
    if ('aperture_height_m' in edge && aperture === null) problems.push(w('flooding.problem.apertureUnknown', { label }));
    else if (aperture !== null && aperture <= 0) problems.push(w('flooding.problem.aperturePositive', { label }));
    const coefficient = number(edge.discharge_coefficient);
    if (coefficient !== null && coefficient > 1) problems.push(w('flooding.problem.coefficientRange', { label }));
    const density = number(edge.fluid_density_t_m3);
    if (seaDensity !== null && density !== seaDensity) problems.push(w('flooding.problem.tankDensity', { label }));
    if (triState(edge.open) === null) problems.push(w('flooding.problem.connectionOpen', { label }));
    if (!knownSource(edge.source) || triState(edge.estimate) === null) problems.push(w('flooding.problem.provenance', { label }));
  }

  if ('openings' in scenario && scenario.openings !== null) {
    if (!Array.isArray(scenario.openings)) problems.push(w('flooding.problem.openingsArray'));
    else for (const opening of scenario.openings) {
      const row = object(opening);
      if (!row.id || triState(row.open) === null) problems.push(w('flooding.problem.openingId'));
      if (['x_m', 'y_m', 'z_m'].some(field => number(row[field]) === null)) problems.push(w('flooding.problem.openingCoords'));
      if (!knownSource(row.source) || triState(row.estimate) === null) problems.push(w('flooding.problem.openingProvenance'));
    }
  }
  return problems;
}

// Assemble the request only when a saved scenario is chosen and complete.
// Nothing is requested when no scenario is selected, so the flooding stage stays
// unrequested exactly like before. An explicit environment density is returned
// separately because the coordinator applies it to the whole request.
export function buildFloodingRequest(project: Raw, request: FloodingRequest, w: Copy = englishCopy): { flooding: Raw | null; rho: number | null; error: string } {
  const rho = environmentDensity(request);
  if (!request.scenario) {
    return { flooding: null, rho: null, error: request.rho.trim() === '' ? '' : w('flooding.request.rhoInactive') };
  }
  const optionProblem = requestOptionProblem(request, w);
  if (optionProblem) return { flooding: null, rho: null, error: optionProblem };
  const scenario = rows(project.flooding_scenarios).find(row => String(row.id) === request.scenario);
  if (!scenario) return { flooding: null, rho: null, error: w('flooding.request.scenarioGone') };
  const problems = scenarioProblems(scenario, ledgerItemIds(project), rho ?? EQUILIBRIUM_RHO_T_M3, w);
  if (problems.length > 0) return { flooding: null, rho: null, error: w('flooding.request.notRunnable', { problems: problems.slice(0, 3).join(w('form.listSeparator')), more: problems.length > 3 ? w('flooding.request.more', { count: problems.length - 3 }) : '' }) };
  const options: Raw = {};
  if (request.steps.trim() !== '') options.max_steps = Number(request.steps);
  if (request.halvings.trim() !== '') options.max_step_halvings = Number(request.halvings);
  if (request.gravity.trim() !== '') options.gravity_m_s2 = numericValue(request.gravity);
  if (request.gzAngles.length > 0) {
    options.remaining_gz_angles_deg = [...request.gzAngles];
    options.remaining_gz_snapshot = request.gzSnapshot;
  }
  return { flooding: { scenario, options }, rho, error: '' };
}

export function ledgerItemIds(project: Raw): string[] {
  return (Array.isArray(project.weight_groups) ? project.weight_groups as Raw[] : [])
    .flatMap(group => rows(group.items).map(item => String(item.id)));
}

export function tankIds(scenario: Raw): string[] { return stringList(tanks(scenario).map(tank => tank.id)); }