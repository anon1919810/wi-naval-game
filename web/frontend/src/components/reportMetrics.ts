import { DATA_LABEL_ORDER } from '../i18n/workspace';
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

/** Only output values and explicitly indexed work points; never metadata or a first-row estimate. */
export function reportMetrics(name: string, stage?: StageEnvelope): ReportMetric[] {
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
