import { DATA_LABEL_ORDER } from '../i18n/workspace';
import { ARMOUR_DEFAULT_VALUE_KEYS } from './armourDefaults';
import { classifyKey, type Dimension } from './units';
import type { StageEnvelope } from '../types';

export interface ReportMetric {
  id: string;
  key: string;
  path: string;
  value: unknown;
  dimension?: Dimension;
  storedUnit?: string;
  canonicalUnit?: string;
  blocked?: boolean;
  point?: number;
}

const object = (value: unknown): Record<string, unknown> => value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
const LENGTH_OUTPUTS = new Set(['lcb_m','tcb_m','kb_m','bm_t_m','bm_l_m','km_t_m','reference_draft_midships_m','waterplane_centroid_x_m','waterplane_centroid_y_m','waterline_length_body_x_m','waterline_beam_body_y_m','waterline_d_m']);
const quantity = (key: string) => classifyKey(key) ?? (LENGTH_OUTPUTS.has(key) ? {dimension:'length' as const,storedUnit:'m'} : key === 'total_resistance_kn' ? { canonicalUnit: 'kN' }
  : key === 'hours' ? { canonicalUnit: 'h' } : key.endsWith('_nm') ? { canonicalUnit: 'nmi' } : {});

// The recovered screen's own recovered units. A long ton is not a converted
// quantity here: the recovered expressions are written in long tons, so their
// readings keep that unit whatever the reader's display preference is. The cost
// keeps the source's own historical million-dollar and million-pound labels and is
// never turned into a modern currency.
const LT = 'LT';
const USD_MILLION = 'million USD';
const GBP_MILLION = 'million GBP';

/** A reading whose unit is fixed by the source rather than by a dimension. */
const exact = (unit: string): Partial<ReportMetric> =>
  ({ dimension: undefined, storedUnit: undefined, canonicalUnit: unit });

/**
 * The version the *stage* declares for one component family, when it declares one.
 *
 * The core copies `data.methods` into the stage's `method_versions`, so a stage
 * that declared fixed armour, auxiliary weapons or cost states which method
 * produced each of them.
 */
function declaredMethod(stage: StageEnvelope | undefined, family: string): string | null {
  const value = object(object(stage?.method_versions).methods)[family];
  return typeof value === 'string' && value !== '' ? value : null;
}

/**
 * Whether this record's component identity is unavailable.
 *
 * A difference may only be attributed to a component when *both* halves of its
 * identity are present and agree: the version the record reports for itself, and
 * the version its own stage declares for that family. Anything else — the stage
 * declaring no family version, the record reporting none, both missing, or the two
 * disagreeing — means the identity is not established, and an unestablished
 * identity is not the same thing as a matching one. It therefore blocks exactly
 * like an explicit conflict does.
 *
 * This is deliberately the same rule for the layout readings. An older result may
 * carry layout readings with no `methods` map at all, and showing a layout delta
 * from such a result would attribute a difference to a method nothing recorded;
 * the readings themselves stay visible either way, which is what a reader of the
 * report actually needs. The current core emits both halves for every declared
 * family, so this withholds nothing it could legitimately show.
 */
function identityUnavailable(stage: StageEnvelope | undefined, family: string,
  record: Record<string, unknown>): boolean {
  const declared = declaredMethod(stage, family);
  if (declared === null) return true;
  const own = record.method_version;
  if (typeof own !== 'string' || own === '') return true;
  return own !== declared;
}

/**
 * Rows that carry a unique identifier, matched by that identifier and never by
 * array position.
 *
 * Two runs that declare the same regions in a different order are the same
 * declaration, and matching them by position would report a difference that does
 * not exist. A missing or repeated identifier cannot be matched at all, and an
 * unavailable or method-mismatched record has no number to attribute, so all
 * three are blocked: they stay visible as the reason there is no delta, and they
 * never become one.
 *
 * `valuesKey` names the nested object holding the numbers, or is `''` when the
 * row publishes them at its own top level.
 */
function keyedRows(data: Record<string, unknown>, stage: StageEnvelope | undefined, family: string,
  methodFamily: string, valuesKey: string, keys: ReadonlyArray<readonly [string, string]>): ReportMetric[] {
  const list = Array.isArray(data[family]) ? data[family] as unknown[] : [];
  const records = list.map((entry, index) => ({ record: object(entry), index }));
  const counts = new Map<string, number>();
  for (const { record } of records) {
    const id = typeof record.id === 'string' && record.id !== '' ? record.id : null;
    if (id !== null) counts.set(id, (counts.get(id) ?? 0) + 1);
  }
  const seen = new Set<string>();
  const found: ReportMetric[] = [];
  for (const { record, index } of records) {
    const id = typeof record.id === 'string' && record.id !== '' ? record.id : null;
    // A record with no identifier is addressed by its position and marked, so it
    // can never be silently matched against a different record next run.
    const token = id ?? `?${index}`;
    if (seen.has(token)) continue;
    seen.add(token);
    const blocked = id === null || (counts.get(id) ?? 0) > 1
      || (record.status !== undefined && record.status !== 'available')
      || identityUnavailable(stage, methodFamily, record);
    const values = valuesKey === '' ? record : object(record[valuesKey]);
    const base = valuesKey === '' ? '' : `${valuesKey}.`;
    for (const [key, unit] of keys) {
      const value = values[key];
      if (typeof value !== 'number' && value !== null) continue;
      found.push({ id: `${family}:${token}:${key}`, key, value,
        path: `stages.design_balance.data.${family}[${token}].${base}${key}`,
        ...exact(unit), blocked });
    }
  }
  return found;
}

/**
 * The whole-battery and armour mass summaries, as keyed metrics.
 *
 * The whole battery is one row per declared layout, matched by that layout's own
 * stable id and never by array position; its declared estimate and its current
 * condition are two separate value objects, so a delta is always attributed to
 * the right side of the reader's own two-column reading. The armour total is the
 * one `ship_armour` reading, whose identity is its own stable id.
 *
 * Blocking follows the same rule as every other component row: a missing or
 * repeated id, a record that declares itself unavailable, and a record whose own
 * method does not match the family version its stage declares, all withhold the
 * numeric delta. A record that declares itself partial keeps whatever figures it
 * did derive — a null beside a number is unknown, not a delta — because a partial
 * reading is not a refused one. The canonical value is metric tonnes and its
 * display follows the reader's mass preference; no formula is evaluated here.
 */
function massSummaryMetrics(stage: StageEnvelope | undefined): ReportMetric[] {
  const data = object(stage?.data);
  const found: ReportMetric[] = [];
  const batteryKeys: ReadonlyArray<readonly [string, string]> = [
    ['guns_t', 'guns_t'], ['mounts_t', 'mounts_t'], ['armour_t', 'armour_t'], ['total_t', 'total_t'],
  ];
  const selectedKeys: ReadonlyArray<readonly [string, string]> = [
    ['guns_t', 'selected_guns_t'], ['mounts_t', 'selected_mounts_t'],
    ['armour_t', 'selected_armour_t'], ['total_t', 'selected_total_t'],
  ];
  const list = Array.isArray(data.battery_totals) ? data.battery_totals as unknown[] : [];
  const counts = new Map<string, number>();
  for (const entry of list) {
    const id = object(entry).id;
    if (typeof id === 'string' && id !== '') counts.set(id, (counts.get(id) ?? 0) + 1);
  }
  const seen = new Set<string>();
  list.forEach((entry, index) => {
    const record = object(entry);
    const id = typeof record.id === 'string' && record.id !== '' ? record.id : null;
    const token = id ?? `?${index}`;
    if (seen.has(token)) return;
    seen.add(token);
    const blocked = id === null || (counts.get(id) ?? 0) > 1 || record.status === 'unavailable'
      || identityUnavailable(stage, 'battery_totals', record);
    const groups: ReadonlyArray<readonly [string, ReadonlyArray<readonly [string, string]>]> = [
      ['values', batteryKeys], ['selected_values', selectedKeys],
    ];
    for (const [valuesKey, keys] of groups) {
      const values = object(record[valuesKey]);
      for (const [field, key] of keys) {
        const value = values[field];
        if (typeof value !== 'number' && value !== null) continue;
        found.push({ id: `battery_totals:${token}:${valuesKey}.${field}`, key, value,
          path: `stages.design_balance.data.battery_totals[${token}].${valuesKey}.${field}`,
          dimension: 'mass', storedUnit: 't', blocked });
      }
    }
  });
  const armour = data.armour_totals;
  if (armour && typeof armour === 'object' && !Array.isArray(armour)) {
    const record = object(armour);
    const id = typeof record.id === 'string' && record.id !== '' ? record.id : null;
    const blocked = id === null || record.status === 'unavailable'
      || identityUnavailable(stage, 'armour_totals', record);
    const values = object(record.values);
    // The label key is namespaced because the report comparison table is one
    // flat key space: the armour family's own `selected_total_t` would otherwise
    // share a label with the whole-battery selected total. The `path` still names
    // the payload field so the reading stays traceable to its source.
    for (const [field, key] of [
      ['estimated_belts_t', 'armour_estimated_belts_t'],
      ['estimated_total_t', 'armour_estimated_total_t'],
      ['known_estimate_subtotal_t', 'armour_known_estimate_subtotal_t'],
      ['selected_belts_t', 'armour_selected_belts_t'],
      ['selected_total_t', 'armour_selected_total_t'],
    ] as ReadonlyArray<readonly [string, string]>) {
      const value = values[field];
      if (typeof value !== 'number' && value !== null) continue;
      found.push({ id: `armour_totals:${id ?? '?'}:${field}`, key, value,
        path: `stages.design_balance.data.armour_totals.values.${field}`,
        dimension: 'mass', storedUnit: 't', blocked });
    }
  }
  return found;
}

/**
 * The recovered default armour sizes, as keyed length metrics.
 *
 * One declaration with one stable id, matched by that id and never by position;
 * its identity is established only when the record's own method and the version
 * its stage declares for `armour_defaults` agree. A missing id, an unavailable
 * record or a mismatched method withholds every delta at once, and each dimension
 * is withheld on its own when the record's own availability says it could not be
 * derived — a partial reading keeps the figures it did derive, because a valid
 * partial number is still a number. The canonical value is metres and its display
 * follows the reader's length preference; no formula is evaluated here.
 */
function armourDefaultMetrics(stage: StageEnvelope | undefined): ReportMetric[] {
  const data = object(stage?.data);
  const value = data.armour_defaults;
  if (!value || typeof value !== 'object' || Array.isArray(value)) return [];
  const record = object(value);
  const id = typeof record.id === 'string' && record.id !== '' ? record.id : null;
  const recordBlocked = id === null || record.status === 'unavailable'
    || identityUnavailable(stage, 'armour_defaults', record);
  const values = object(record.values);
  const availability = object(record.availability);
  const found: ReportMetric[] = [];
  for (const [, , key] of ARMOUR_DEFAULT_VALUE_KEYS) {
    const metric = values[key];
    if (typeof metric !== 'number' && metric !== null) continue;
    const entry = object(availability[key]);
    const state = entry.state ?? entry.status;
    found.push({ id: `armour_defaults:${id ?? '?'}:${key}`, key, value: metric,
      path: `stages.design_balance.data.armour_defaults.values.${key}`,
      dimension: 'length', storedUnit: 'm', blocked: recordBlocked || state !== 'available' });
  }
  return found;
}

/**
 * The concept screen's own optional component readings, as explicit output paths.
 *
 * These are named one by one rather than found by walking the payload: metadata,
 * provenance and the declared `inputs` of a nested result are not outputs, and
 * treating them as metrics would put a source string and a declared input into a
 * comparison table. A stage that declares no fixed armour, no auxiliary weapons
 * and no cost adds no row here at all, which is what keeps an absent optional
 * feature absent.
 */
function auxiliarySpaceMetrics(stage: StageEnvelope | undefined): ReportMetric[] {
  const reading=object(object(stage?.data).auxiliary_space);
  if (!Object.keys(reading).length) return [];
  const records=Array.isArray(reading.records)?reading.records.map(object):[];
  const counts=new Map<string,number>();
  for(const row of records)if(typeof row.id==='string'&&row.id)counts.set(row.id,(counts.get(row.id)??0)+1);
  const result:ReportMetric[]=[];const seen=new Set<string>();
  const parentBlocked=reading.id!=='selected_torpedoes'||identityUnavailable(stage,'auxiliary_space',reading);
  for(const {row,group,index} of [{row:reading,group:'summary',index:0},...records.map((row,index)=>({row,group:'record',index}))]) {
    const id=typeof row.id==='string'&&row.id?row.id:null;const token=`${group}:${id??'?'+index}`;
    if(seen.has(token))continue;seen.add(token);
    const values=object(row.values),availability=object(row.availability);
    const blocked=parentBlocked||id===null||(group==='record'&&(counts.get(id)??0)>1)
      ||row.status==='unavailable'||identityUnavailable(stage,'auxiliary_space',row);
    for(const [key,unit] of [['deck_area_m2','m²'],['hull_volume_m3','m³'],['deck_ratio','ratio'],['hull_ratio','ratio']]) {
      const value=values[key];if(typeof value!=='number'&&value!==null)continue;
      result.push({id:`auxiliary_space:${token}:${key}`,key:`auxiliary_space_${key}`,value,
        path:`stages.design_balance.data.auxiliary_space.${group==='summary'?'':`records[${id??'?'+index}].`}values.${key}`,
        ...exact(unit),blocked:blocked||object(availability[key]).state!=='available'});
    }
  }
  return result;
}

/**
 * The whole-battery mount allocation, as keyed metrics.
 *
 * One row per selected layout, matched by its own stable id and never by array
 * position; the source SPS total, the old per-row subtotal, the product's
 * allocated total and the selected ledger total are four separate facts on two
 * sides of the reader's own reading. Each per-battery member is keyed by its own
 * battery id and carries its own method version. Because the layout is the
 * allocation unit whose totals are the sum of its members, a member that cannot be
 * identified — a missing or repeated id, an unavailable member, or a member whose
 * own method disagrees with the family version — withholds the whole layout, and
 * not only that member. Blocking follows the same rule as every other component
 * row, and
 * a partial reading keeps whatever figures it did derive — a null beside a
 * number is unknown, not a refused one. Masses are metric tonnes and the share
 * is dimensionless; no share or allocation is evaluated here.
 */
function batteryAllocationMetrics(stage: StageEnvelope | undefined): ReportMetric[] {
  const data = object(stage?.data);
  const list = Array.isArray(data.battery_mass_allocation) ? data.battery_mass_allocation as unknown[] : [];
  const found: ReportMetric[] = [];
  const counts = new Map<string, number>();
  for (const entry of list) {
    const id = object(entry).id;
    if (typeof id === 'string' && id !== '') counts.set(id, (counts.get(id) ?? 0) + 1);
  }
  const seen = new Set<string>();
  list.forEach((entry, index) => {
    const record = object(entry);
    const id = typeof record.id === 'string' && record.id !== '' ? record.id : null;
    const token = id ?? `?${index}`;
    if (seen.has(token)) return;
    seen.add(token);
    const members = Array.isArray(record.records) ? record.records as unknown[] : [];
    const memberCounts = new Map<string, number>();
    for (const raw of members) {
      const memberId = object(raw).id;
      if (typeof memberId === 'string' && memberId !== '') {
        memberCounts.set(memberId, (memberCounts.get(memberId) ?? 0) + 1);
      }
    }
    // The layout is the allocation unit: its totals are the sum of its members, so
    // a member that cannot be identified attributes nothing to the layout either.
    const memberUnavailable = members.some(raw => {
      const member = object(raw);
      const memberId = typeof member.id === 'string' && member.id !== '' ? member.id : null;
      return memberId === null || (memberCounts.get(memberId) ?? 0) > 1
        || member.status === 'unavailable'
        || identityUnavailable(stage, 'battery_mass_allocation', member);
    });
    const blocked = id === null || (counts.get(id) ?? 0) > 1 || record.status === 'unavailable'
      || identityUnavailable(stage, 'battery_mass_allocation', record) || memberUnavailable;
    const values = object(record.values);
    for (const field of ['source_mounts_t', 'legacy_mounts_t', 'allocated_total_t',
      'selected_mounts_t'] as ReadonlyArray<string>) {
      const value = values[field];
      if (typeof value !== 'number' && value !== null) continue;
      found.push({ id: `battery_mass_allocation:${token}:values.${field}`,
        key: `allocation_${field}`, value,
        path: `stages.design_balance.data.battery_mass_allocation[${token}].values.${field}`,
        dimension: 'mass', storedUnit: 't', blocked });
    }
    const memberSeen = new Set<string>();
    members.forEach((raw, memberIndex) => {
      const member = object(raw);
      const memberId = typeof member.id === 'string' && member.id !== '' ? member.id : null;
      const memberToken = memberId ?? `?${memberIndex}`;
      if (memberSeen.has(memberToken)) return;
      memberSeen.add(memberToken);
      const memberBlocked = blocked || memberId === null || (memberCounts.get(memberId) ?? 0) > 1
        || member.status === 'unavailable' || identityUnavailable(stage, 'battery_mass_allocation', member);
      const prefixPath = `stages.design_balance.data.battery_mass_allocation[${token}].records[${memberToken}]`;
      for (const [field, key] of [
        ['weight_t', 'allocation_weight_t'], ['allocated_mass_t', 'allocation_allocated_mass_t'],
        ['selected_mass_t', 'allocation_selected_mass_t'],
      ] as ReadonlyArray<readonly [string, string]>) {
        const value = member[field];
        if (typeof value !== 'number' && value !== null) continue;
        found.push({ id: `battery_mass_allocation:${token}:${memberToken}:${field}`, key, value,
          path: `${prefixPath}.${field}`, dimension: 'mass', storedUnit: 't', blocked: memberBlocked });
      }
      const share = member.share;
      if (typeof share === 'number' || share === null) {
        found.push({ id: `battery_mass_allocation:${token}:${memberToken}:share`, key: 'allocation_share',
          value: share, path: `${prefixPath}.share`, ...exact('share'), blocked: memberBlocked });
      }
    });
  });
  return found;
}

/**
 * The geometric armour panels, as keyed metrics.
 *
 * One row per selected region, matched by its own stable id and never by array
 * position, with each plate keyed by its own stable plate id. Area is square
 * metres, volume cubic metres and mass metric tonnes whatever the reader's length
 * preference is; the units are stated on the metric, not derived from a generic
 * key. The saved-report parent gate here is strict: a region contributes only from
 * a stage that was requested and completed. A repeated, missing or
 * method-mismatched region or plate withholds the delta exactly as every other
 * component row's does.
 */
function armourGeometryMetrics(stage: StageEnvelope | undefined): ReportMetric[] {
  if (stage?.requested !== true || stage.status !== 'completed') return [];
  const data = object(stage?.data);
  const list = Array.isArray(data.armour_geometry) ? data.armour_geometry as unknown[] : [];
  const found: ReportMetric[] = [];
  const counts = new Map<string, number>();
  for (const entry of list) {
    const id = object(entry).id;
    if (typeof id === 'string' && id !== '') counts.set(id, (counts.get(id) ?? 0) + 1);
  }
  const seen = new Set<string>();
  list.forEach((entry, index) => {
    const record = object(entry);
    const id = typeof record.id === 'string' && record.id !== '' ? record.id : null;
    const token = id ?? `?${index}`;
    if (seen.has(token)) return;
    seen.add(token);
    const plates = Array.isArray(record.records) ? record.records as unknown[] : [];
    const plateCounts = new Map<string, number>();
    for (const raw of plates) {
      const plateId = object(raw).id;
      if (typeof plateId === 'string' && plateId !== '') plateCounts.set(plateId, (plateCounts.get(plateId) ?? 0) + 1);
    }
    // A plate that cannot be identified attributes nothing to the region either:
    // the region's own area, volume and mass are the sum of its plates.
    const plateUnavailable = plates.some(raw => {
      const plate = object(raw);
      const plateId = typeof plate.id === 'string' && plate.id !== '' ? plate.id : null;
      return plateId === null || (plateCounts.get(plateId) ?? 0) > 1 || plate.status === 'unavailable'
        || identityUnavailable(stage, 'armour_geometry', plate);
    });
    const blocked = id === null || (counts.get(id) ?? 0) > 1 || record.status === 'unavailable'
      || identityUnavailable(stage, 'armour_geometry', record) || plateUnavailable;
    const values = object(record.values);
    for (const [field, key, dimension, unit] of [
      ['area_m2', 'armour_geometry_area_m2', 'area', undefined],
      ['volume_m3', 'armour_geometry_volume_m3', 'volume', undefined],
      ['mass_t', 'armour_geometry_mass_t', 'mass', 't'],
      ['known_mass_subtotal_t', 'armour_geometry_known_mass_subtotal_t', 'mass', 't'],
    ] as ReadonlyArray<readonly [string, string, Dimension, string | undefined]>) {
      const value = values[field];
      if (typeof value !== 'number' && value !== null) continue;
      found.push({ id: `armour_geometry:${token}:values.${field}`, key, value,
        path: `stages.design_balance.data.armour_geometry[${token}].values.${field}`,
        dimension, ...(unit === undefined ? {} : { storedUnit: unit }), blocked });
    }
    const plateSeen = new Set<string>();
    plates.forEach((raw, plateIndex) => {
      const plate = object(raw);
      const plateId = typeof plate.id === 'string' && plate.id !== '' ? plate.id : null;
      const plateToken = plateId ?? `?${plateIndex}`;
      if (plateSeen.has(plateToken)) return;
      plateSeen.add(plateToken);
      const plateValues = object(plate.values);
      for (const [field, key, dimension, unit] of [
        ['area_m2', 'armour_geometry_plate_area_m2', 'area', undefined],
        ['volume_m3', 'armour_geometry_plate_volume_m3', 'volume', undefined],
        ['mass_t', 'armour_geometry_plate_mass_t', 'mass', 't'],
      ] as ReadonlyArray<readonly [string, string, Dimension, string | undefined]>) {
        const value = plateValues[field];
        if (typeof value !== 'number' && value !== null) continue;
        found.push({ id: `armour_geometry:${token}:${plateToken}:${field}`, key, value,
          path: `stages.design_balance.data.armour_geometry[${token}].records[${plateToken}].${field}`,
          dimension, ...(unit === undefined ? {} : { storedUnit: unit }), blocked });
      }
    });
  });
  return found;
}

function conceptComponentMetrics(stage: StageEnvelope | undefined): ReportMetric[] {
  const data = object(stage?.data);
  const found: ReportMetric[] = [
    ...keyedRows(data, stage, 'fixed_armour', 'fixed_armour', 'values', [
      ['total_long_tons', LT], ['mass_t', 't'], ['plate_long_tons', LT],
      ['central_long_tons', LT], ['fore_long_tons', LT], ['quarter_long_tons', LT],
      ['aft_long_tons', LT],
    ]),
    ...keyedRows(data, stage, 'battery_layouts', 'layout', '', [
      ['freeboard_m', 'm'], ['super_factor', 'factor'], ['mounts', 'mounts'], ['barrels', 'barrels'],
    ]),
    ...keyedRows(data, stage, 'auxiliary_weapons', 'auxiliary_weapons', 'values', [
      ['weapon_long_tons', LT], ['mount_long_tons', LT], ['total_long_tons', LT],
      ['mass_t', 't'], ['mount_factor', 'factor'],
    ]),
    ...massSummaryMetrics(stage),
    ...batteryAllocationMetrics(stage),
    ...armourGeometryMetrics(stage),
    ...armourDefaultMetrics(stage),
    ...auxiliarySpaceMetrics(stage),
  ];
  const cost = data.cost;
  if (data.armour_review && typeof data.armour_review === 'object') {
    const review = object(data.armour_review);
    const value = object(review.values).minimum_main_belt_length_m;
    if (typeof value === 'number' || value === null) found.push({
      id: 'armour_review:minimum_main_belt_length_m', key: 'minimum_main_belt_length_m',
      path: 'stages.design_balance.data.armour_review.values.minimum_main_belt_length_m',
      value, dimension: 'length', storedUnit: 'm',
      blocked: review.status !== 'available' || identityUnavailable(stage, 'armour_review', review),
    });
  }
  if (cost && typeof cost === 'object' && !Array.isArray(cost)) {
    const record = object(cost);
    const blocked = record.status !== 'available' || identityUnavailable(stage, 'cost', record);
    const values = object(record.values);
    for (const [key, unit] of [
      ['usd_million', USD_MILLION], ['gbp_million', GBP_MILLION], ['base_usd_million', USD_MILLION],
      ['light_usd_million', USD_MILLION], ['machinery_usd_million', USD_MILLION],
      ['borne_usd_million', USD_MILLION], ['load_long_tons', LT], ['light_basis_long_tons', LT],
      ['year_factor', 'factor'],
    ] as ReadonlyArray<readonly [string, string]>) {
      const value = values[key];
      if (typeof value !== 'number' && value !== null) continue;
      found.push({ id: `cost:${key}`, key, value,
        path: `stages.design_balance.data.cost.values.${key}`, ...exact(unit), blocked });
    }
  }
  return found;
}

/** Native source readings keep their actual empirical units and identity. */
function shipDesignMetrics(stage: StageEnvelope | undefined): ReportMetric[] {
  if (stage?.requested !== true || stage.status !== 'completed') return [];
  const data = object(stage.data);
  const method = data.method_version;
  const blocked = typeof method !== 'string' || method === ''
    || object(stage.method_versions).kernel !== method;
  const found: ReportMetric[] = [];
  for (const [section, fields] of [
    ['hull', [['length', 'ft'], ['lengthOA', 'ft'], ['beam', 'ft'], ['draught', 'ft'],
      ['displacement', LT], ['block', 'coefficient']]],
    ['guns', [['gunWeight', LT], ['mountWeight', LT], ['armWeight', LT], ['magazine', LT]]],
    ['armour', [['weight', LT], ['weightBeltMain', LT], ['weightDeck', LT]]],
    ['engine', [['engineWeight', LT], ['hullWeightDisplayed', LT], ['bunker', LT],
      ['hpMax', 'source hp'], ['speedMax', 'kn'], ['range', 'nmi']]],
    ['performance', [['dispLight', LT], ['dispStandard', LT], ['dispMaxLoad', LT],
      ['stability', 'empirical score'], ['metacentre', 'ft'], ['rollPeriod', 's'],
      ['strengthCross', 'empirical score'], ['strengthLong', 'empirical score'],
      ['strengthComp', 'empirical score'], ['costDollars', USD_MILLION], ['costPounds', GBP_MILLION]]],
  ] as ReadonlyArray<readonly [string, ReadonlyArray<readonly [string, string]>]>) {
    const values = object(data[section]);
    for (const [field, unit] of fields) {
      const value = values[field];
      if (typeof value !== 'number' && value !== null) continue;
      found.push({ id: `ship_design:${section}.${field}`, key: `${section}.${field}`, value,
        path: `stages.ship_design.data.${section}.${field}`, ...exact(unit), blocked });
    }
  }
  const balance = object(data.balance);
  for (const field of ['selected_mass_t', 'estimated_mass_t', 'target_displacement_t', 'difference_t']) {
    const value = balance[field];
    if (typeof value !== 'number' && value !== null) continue;
    found.push({ id: `ship_design:${data.basis_condition_id}:balance.${field}`, key: field, value,
      path: `stages.ship_design.data.balance.${field}`, dimension: 'mass', storedUnit: 't',
      blocked: blocked || typeof data.basis_condition_id !== 'string' });
  }
  return found;
}

/** Only output values and explicitly indexed work points; never metadata or a first-row estimate. */
export function reportMetrics(name: string, stage?: StageEnvelope): ReportMetric[] {
  if (name === 'ship_design') return shipDesignMetrics(stage);
  const data = object(stage?.data), found: ReportMetric[] = [];
  const add = (key: string, value: unknown, path: string, extra: Partial<ReportMetric> = {}) => {
    if (typeof value !== 'number' && value !== null) return;
    found.push({ id: path, key, value, path: `stages.${name}.data.${path}`, ...quantity(key), ...extra });
  };
  // These stages publish their scalar outputs under the canonical values object.
  const nested = new Set(['loading', 'hydrostatics', 'propulsion', 'endurance', 'systems']);
  if (nested.has(name)) {
    for (const [key, value] of Object.entries(object(data.values))) {
      if (key === 'power_design_shp' || key === 'power_trial_shp') continue; // same power already in kW
      add(key, value, `values.${key}`);
    }
  } else {
    for (const [key, value] of Object.entries(data)) add(key, value, key);
  }
  if (name === 'design_balance') found.push(...conceptComponentMetrics(stage));
  if (name === 'gz' || name === 'resistance') {
    const axis = name === 'gz' ? 'angle_deg' : 'speed_kn';
    for (const table of name === 'gz' ? ['rows'] : ['rows', 'power_rows']) {
      const rows = Array.isArray(data[table]) ? data[table] as unknown[] : [];
      const counts = new Map<number, number>();
      for (const raw of rows) { const n = object(raw)[axis]; if (typeof n === 'number' && Number.isFinite(n)) counts.set(n, (counts.get(n) ?? 0) + 1); }
      rows.forEach((raw, index) => {
        const row = object(raw), point = row[axis];
        if (typeof point !== 'number' || !Number.isFinite(point)) return;
        const blocked = counts.get(point)! > 1 || row.complete === false || row.converged === false
          || (name === 'resistance' && (row.complete !== true || row.model_applicable === false || stage?.validity.model_applicable === false
            || object(data.validity).model_applicable === false || row.primary_result === false || data.primary_result === false
            || !(row.primary_result === true || data.primary_result === true)
            || !(row.model_applicable === true || object(data.validity).model_applicable === true || stage?.validity.model_applicable === true)));
        for (const key of name === 'gz' ? ['gz_m'] : table === 'rows' ? ['total_resistance_kn', 'effective_power_kw'] : ['shaft_power_kw']) {
          add(key, row[key], `${table}[${index}].${key}`, { id: `${table}:${point}:${key}`, point, blocked });
        }
      });
    }
  }
  const rank=(key:string)=>{const index=DATA_LABEL_ORDER.indexOf(key);return index<0 ? DATA_LABEL_ORDER.length : index;};
  return found.sort((a,b)=>rank(a.key)-rank(b.key) || (a.point ?? -Infinity)-(b.point ?? -Infinity) || a.id.localeCompare(b.id));
}
