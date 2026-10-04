import { object } from './formModel';

// Display-unit conversion for reading and typing.
//
// FACTOR[unit] is how many units of the dimension's canonical base one `unit`
// represents — the exact values of tools/plimsoll/units.py:
//   ft = 0.3048 m, kg = 0.001 t, long_ton = 1.0160469088 t,
//   1 m_s = 3600/1852 kn, 1 shp = 0.7456998715822702 kW, 1 rad = 180/pi deg.
//
// A field is stored in its own canonical unit (`thickness_mm` in mm,
// `projectile_mass_kg` in kg, `shaft_power_shp` in shp). Reading converts
// stored → dimension base → the reader's chosen display unit; typing converts
// back through the same chain, so the stored number never changes units.
// Stored project values, run payloads, exports and fingerprints stay canonical:
// this module is only ever used for presentation and for typed input.

export type DisplayUnit = 'm' | 'ft' | 't' | 'kg' | 'long_ton' | 'kW' | 'shp' | 'kn' | 'm_s' | 'deg' | 'rad';

export interface DisplayPreferences {
  length: 'm' | 'ft';
  mass: 't' | 'kg' | 'long_ton';
  power: 'kW' | 'shp';
  speed: 'kn' | 'm_s';
  angle: 'deg' | 'rad';
}

// Only the values project_io accepts in `display_preferences` are offered, so a
// preference can never store an unsupported unit. Millimetres and centimetres
// exist only as field storage units (plate thickness, torpedo diameter), never
// as a reader preference.
export const CHOICES: Record<keyof DisplayPreferences, { value: DisplayUnit; label: string }[]> = {
  length: [{ value: 'm', label: 'm' }, { value: 'ft', label: 'ft' }],
  mass: [{ value: 't', label: 't' }, { value: 'kg', label: 'kg' }, { value: 'long_ton', label: 'long ton' }],
  power: [{ value: 'kW', label: 'kW' }, { value: 'shp', label: 'shp' }],
  speed: [{ value: 'kn', label: 'kn' }, { value: 'm_s', label: 'm/s' }],
  angle: [{ value: 'deg', label: '°' }, { value: 'rad', label: 'rad' }],
};

export const CANONICAL_PREFERENCES: DisplayPreferences = { length: 'm', mass: 't', power: 'kW', speed: 'kn', angle: 'deg' };
export const DIMENSION_KEYS: Array<keyof DisplayPreferences> = ['length', 'mass', 'power', 'speed', 'angle'];

/** Unit → canonical base. */
const FACTOR: Record<string, number> = {
  m: 1, ft: 0.3048, cm: 0.01, mm: 0.001,
  t: 1, kg: 0.001, long_ton: 1.0160469088,
  kW: 1, shp: 0.7456998715822702,
  kn: 1, m_s: 3600 / 1852,
  deg: 1, rad: 180 / Math.PI,
  't/day': 1, 'kg/day': 0.001, 'long ton/day': 1.0160469088,
};

// Reader-facing labels: the stored identifiers never leak into the interface.
const LABEL: Record<string, string> = {
  long_ton: 'long ton', m_s: 'm/s', deg: '°',
  'kg/day': 'kg/day', 'long ton/day': 'long ton/day', 't/day': 't/day',
};

function factor(unit: string, exponent = 1): number {
  const base = FACTOR[unit];
  if (base === undefined) return 1;
  return exponent === 1 ? base : base ** exponent;
}

/** A quantity that may be shown and typed in the reader's units. */
export type Dimension = 'length' | 'mass' | 'power' | 'speed' | 'angle' | 'area' | 'volume' | 'moment4';

const EXPONENT: Record<Dimension, number> = { length: 1, mass: 1, power: 1, speed: 1, angle: 1, area: 2, volume: 3, moment4: 4 };
const BASE_UNIT: Record<Dimension, string> = { length: 'm', mass: 't', power: 'kW', speed: 'kn', angle: 'deg', area: 'm', volume: 'm', moment4: 'm' };
const PREFERRED: Record<Dimension, keyof DisplayPreferences> = {
  length: 'length', mass: 'mass', power: 'power', speed: 'speed', angle: 'angle',
  area: 'length', volume: 'length', moment4: 'length',
};

/** The canonical base unit of a dimension, e.g. m² / m³ / m⁴. */
export function unitLabel(dimension: Dimension, unit?: string): string {
  const base = BASE_UNIT[dimension];
  const chosen = unit ?? base;
  const text = LABEL[chosen] ?? chosen;
  if (chosen === base) return dimension === 'area' ? 'm²' : dimension === 'volume' ? 'm³' : dimension === 'moment4' ? 'm⁴' : text;
  return `${text}${dimension === 'area' ? '²' : dimension === 'volume' ? '³' : dimension === 'moment4' ? '⁴' : ''}`;
}

export function displayUnit(dimension: Dimension, prefs: DisplayPreferences): DisplayUnit {
  return prefs[PREFERRED[dimension]] as DisplayUnit;
}

function finite(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

/**
 * stored value → displayed value.
 * `storedUnit` is the unit the field is stored in; it defaults to the canonical
 * base of the dimension.
 */
export function toDisplay(dimension: Dimension, storedValue: unknown, prefs: DisplayPreferences, storedUnit?: string): number | null {
  const value = finite(storedValue);
  if (value === null) return null;
  const exponent = EXPONENT[dimension];
  const base = value * factor(storedUnit ?? BASE_UNIT[dimension], exponent);
  return base / factor(displayUnit(dimension, prefs), exponent);
}

/** Typed displayed value → stored value, exactly inverting toDisplay. */
export function fromDisplay(dimension: Dimension, typedValue: unknown, prefs: DisplayPreferences, storedUnit?: string): number | null {
  const value = finite(typedValue);
  if (value === null) return null;
  const exponent = EXPONENT[dimension];
  const base = value * factor(displayUnit(dimension, prefs), exponent);
  return base / factor(storedUnit ?? BASE_UNIT[dimension], exponent);
}

const formatter = new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 6 });

export function formatNumber(value: number): string {
  return Object.is(value, -0) ? '0' : formatter.format(value);
}

export function formatQuantity(dimension: Dimension, storedValue: unknown, prefs: DisplayPreferences, storedUnit?: string): string {
  const displayed = toDisplay(dimension, storedValue, prefs, storedUnit);
  if (displayed === null) return '未知';
  return `${formatNumber(displayed)} ${unitLabel(dimension, displayUnit(dimension, prefs))}`;
}

export function displayNumber(dimension: Dimension, storedValue: unknown, prefs: DisplayPreferences, storedUnit?: string): string {
  const displayed = toDisplay(dimension, storedValue, prefs, storedUnit);
  return displayed === null ? '未知' : formatNumber(displayed);
}

/** Displayed number without a unit, for dense table cells. */
export function displayValue(dimension: Dimension, storedValue: unknown, prefs: DisplayPreferences, storedUnit?: string): number | null {
  return toDisplay(dimension, storedValue, prefs, storedUnit);
}

/** Controlled-input text for a stored value; never stored itself. */
export function inputText(dimension: Dimension, storedValue: unknown, prefs: DisplayPreferences, storedUnit?: string): string {
  const displayed = toDisplay(dimension, storedValue, prefs, storedUnit);
  return displayed === null ? '' : String(displayed);
}

// Fuel burn is a defined compound: the mass component follows the reader's mass
// preference while the day is fixed, so t/day becomes kg/day and never anything
// else. Flow rates (m³/s) and every other compound stay canonical.
export function burnRateText(tPerDay: unknown, prefs: DisplayPreferences): string {
  const value = finite(tPerDay);
  if (value === null) return '未知';
  const unit = prefs.mass === 'kg' ? 'kg/day' : prefs.mass === 'long_ton' ? 'long ton/day' : 't/day';
  return `${formatNumber(value / factor(unit))} ${unit}`;
}

export function isDisplayUnit(value: unknown): value is DisplayUnit {
  return typeof value === 'string' && DIMENSION_KEYS.some(key => CHOICES[key].some(choice => choice.value === value));
}

export function readPreferences(value: unknown): DisplayPreferences {
  const stored = object(value);
  const result: Record<string, DisplayUnit> = { ...CANONICAL_PREFERENCES };
  for (const key of DIMENSION_KEYS) {
    const candidate = stored[key];
    // Only a unit this dimension actually offers is accepted, so a saved
    // preference can never hold an unsupported value such as cm or mm.
    if (isDisplayUnit(candidate) && CHOICES[key].some(choice => choice.value === candidate)) result[key] = candidate;
  }
  return result as unknown as DisplayPreferences;
}

/**
 * A data key becomes a quantity only when its name is unambiguous. The optional
 * `unit` is the unit the value is *stored* in, not a display override: a stored
 * kilogram mass converts through tonnes into whatever the reader prefers.
 *
 * Deliberately unconverted: densities, viscosities, times, forces, flow rates,
 * ratios, percentages and counts keep their canonical label and value. `_kn` is
 * never inferred because a speed in kn and a force in kN share the suffix.
 */
export interface QuantityKey { dimension: Dimension; storedUnit?: string }

const EXPLICIT: Record<string, QuantityKey> = {
  loa_m: { dimension: 'length' }, lwl_m: { dimension: 'length' }, length_m: { dimension: 'length' },
  beam_m: { dimension: 'length' }, draught_m: { dimension: 'length' }, draught: { dimension: 'length' },
  draught_normal_m: { dimension: 'length' }, draught_deep_m: { dimension: 'length' }, draft_m: { dimension: 'length' },
  depth_m: { dimension: 'length' }, x_m: { dimension: 'length' }, y_m: { dimension: 'length' },
  z_m: { dimension: 'length' }, height_m: { dimension: 'length' }, keel_to_bottom_m: { dimension: 'length' },
  fore_m: { dimension: 'length' }, aft_m: { dimension: 'length' }, thickness_m: { dimension: 'length' },
  bulb_height_m: { dimension: 'length' }, aperture_height_m: { dimension: 'length' }, diameter_m: { dimension: 'length' },
  beam_between_m: { dimension: 'length' }, reference_length_m: { dimension: 'length' },
  freeboard_m: { dimension: 'length' }, freeboard_aft_m: { dimension: 'length' }, freeboard_fore_m: { dimension: 'length' },
  weighted_mean_freeboard_m: { dimension: 'length' }, minimum_clearance_m: { dimension: 'length' },
  minimum_clearance: { dimension: 'length' }, x_fore_perpendicular_m: { dimension: 'length' },
  x_aft_perpendicular_m: { dimension: 'length' }, lcg_m: { dimension: 'length' }, tcg_m: { dimension: 'length' },
  gm_m: { dimension: 'length' }, kb_m: { dimension: 'length' }, km_m: { dimension: 'length' },
  gz_m: { dimension: 'length' }, waterline_above_keel_m: { dimension: 'length' }, waterline_d_m: { dimension: 'length' },
  terminal_max_head_difference_m: { dimension: 'length' }, terminal_head_tolerance_m: { dimension: 'length' },
  mass_t: { dimension: 'mass' }, unit_mass_t: { dimension: 'mass' }, displacement_t: { dimension: 'mass' },
  reference_displacement_normal_t: { dimension: 'mass' }, reference_displacement_deep_t: { dimension: 'mass' },
  reserve_t: { dimension: 'mass' }, absolute_t: { dimension: 'mass' }, other_mount_mass_t: { dimension: 'mass' },
  // Aggregate masses reported by the loading and systems stages.
  total_mass_t: { dimension: 'mass' }, known_mass_t: { dimension: 'mass' },
  linked_total_mass_t: { dimension: 'mass' }, linked_known_mass_t: { dimension: 'mass' },
  machinery_mass_t: { dimension: 'mass' }, variable_load_t: { dimension: 'mass' },
  coal_t: { dimension: 'mass' }, oil_t: { dimension: 'mass' },
  ledger_mass_t: { dimension: 'mass' }, weight_t: { dimension: 'mass' },
  ship_wide_ammunition_t: { dimension: 'mass' },
  kg_m: { dimension: 'length' }, gm_t_m: { dimension: 'length' },
  thickness_mm: { dimension: 'length', storedUnit: 'mm' },
  rotating_armour_mass_t: { dimension: 'mass' },
  projectile_mass_kg: { dimension: 'mass', storedUnit: 'kg' }, charge_mass_kg: { dimension: 'mass', storedUnit: 'kg' },
  unit_weight_kg: { dimension: 'mass', storedUnit: 'kg' }, shell_mass_kg: { dimension: 'mass', storedUnit: 'kg' },
  broadside_mass_kg: { dimension: 'mass', storedUnit: 'kg' }, per_gun_shell_kg: { dimension: 'mass', storedUnit: 'kg' },
  speed_kn: { dimension: 'speed' }, max_speed_kn: { dimension: 'speed' }, cruise_speed_kn: { dimension: 'speed' },
  heel_deg: { dimension: 'angle' }, trim_deg: { dimension: 'angle' }, angle_deg: { dimension: 'angle' },
  target_trim_deg: { dimension: 'angle' }, inclination_deg: { dimension: 'angle' }, stem_angle_deg: { dimension: 'angle' },
  avs_deg: { dimension: 'angle' }, heel_bounds_deg: { dimension: 'angle' }, trim_bounds_deg: { dimension: 'angle' },
  design_power_kw: { dimension: 'power' }, trial_power_kw: { dimension: 'power' },
  effective_power_kw: { dimension: 'power' }, shaft_power_kw: { dimension: 'power' },
  shaft_power_shp: { dimension: 'power', storedUnit: 'shp' },
  area_m2: { dimension: 'area' }, covered_plan_area_m2: { dimension: 'area' }, reference_plan_area_m2: { dimension: 'area' },
  wetted_area_m2: { dimension: 'area' }, bulb_area_m2: { dimension: 'area' }, transom_area_m2: { dimension: 'area' },
  awp_m2: { dimension: 'area' }, waterplane_area_m2: { dimension: 'area' }, volume_m3: { dimension: 'volume' },
  initial_volume_m3: { dimension: 'volume' }, capacity_m3: { dimension: 'volume' },
  total_onboard_water_volume_m3: { dimension: 'volume' }, total_onboard_water_mass_t: { dimension: 'mass' },
  volume_conservation_error_m3: { dimension: 'volume' }, mass_conservation_error_t: { dimension: 'mass' },
  cumulative_sea_exchange_m3: { dimension: 'volume' }, cumulative_sea_exchange_t: { dimension: 'mass' },
  initial_total_water_volume_m3: { dimension: 'volume' }, initial_total_water_mass_t: { dimension: 'mass' },
};

// Compound names that merely end in a convertible-looking suffix. A density is
// not a volume, a kinematic viscosity is not an area and a burn rate is not a
// mass: these keep their canonical label and value.
const COMPOUND_UNITS = /(_kg_m3|_t_m3|_g_m3|_m2_s|_t_per_day|_kg_per_day|_m3_s|_m3_per_s|_per_s)$/;

/** True when a key names a density, viscosity or rate that must stay canonical. */
export function isCompoundUnitKey(key: string): boolean {
  return COMPOUND_UNITS.test(key);
}

export function classifyKey(key: string): QuantityKey | null {
  const explicit = EXPLICIT[key];
  if (explicit) return explicit;
  if (isCompoundUnitKey(key)) return null;
  if (key.endsWith('_m2')) return { dimension: 'area' };
  if (key.endsWith('_m3')) return { dimension: 'volume' };
  if (key.endsWith('_m4')) return { dimension: 'moment4' };
  if (key.endsWith('_deg')) return { dimension: 'angle' };
  if (key.endsWith('_kw')) return { dimension: 'power' };
  // `_kn` is deliberately absent: a speed in kn and a force in kN share the
  // suffix, so only the explicit speed names above are ever converted.
  // Bare `_t`, `_kg` and `_m` suffixes are ambiguous enough in mixed payloads
  // that only the names listed above are converted.
  return null;
}
