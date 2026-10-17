import { describe, expect, it } from 'vitest';
import { reportMetrics } from '../components/reportMetrics';
import type { StageEnvelope } from '../types';

const stage = (kernel = 'native-1'): StageEnvelope => ({ requested: true, status: 'completed',
  reason: null, assumptions: [], diagnostics: [], method_versions: { kernel },
  validity: { complete: true, model_applicable: true, converged: true, historical_validated: null },
  data: { method_version: 'native-1', basis_condition_id: 'normal',
    hull: { displacement: 1000 }, performance: { stability: 1.2, metacentre: 8, costDollars: 3 },
    balance: { selected_mass_t: 1016.0469088, difference_t: 0 } },
} as StageEnvelope);

describe('native saved report metrics', () => {
  it('keeps source LT, empirical score and feet distinct from metric ledger mass', () => {
    const rows = reportMetrics('ship_design', stage());
    expect(rows.find(r => r.key === 'hull.displacement')).toMatchObject({ value: 1000, canonicalUnit: 'LT', blocked: false });
    expect(rows.find(r => r.key === 'performance.stability')).toMatchObject({ value: 1.2, canonicalUnit: 'empirical score' });
    expect(rows.find(r => r.key === 'performance.metacentre')).toMatchObject({ value: 8, canonicalUnit: 'ft' });
    expect(rows.find(r => r.key === 'selected_mass_t')).toMatchObject({ dimension: 'mass', storedUnit: 't' });
    expect(rows.find(r => r.key === 'difference_t')?.value).toBe(0);
  });
  it('withholds metrics from an unrequested stage and differences with missing or changed identity', () => {
    expect(reportMetrics('ship_design', { ...stage(), requested: false })).toEqual([]);
    expect(reportMetrics('ship_design', stage('other')).every(r => r.blocked)).toBe(true);
    expect(reportMetrics('ship_design', { ...stage(), method_versions: {} }).every(r => r.blocked)).toBe(true);
  });
});
