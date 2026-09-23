import type { AnalysisResult, StageEnvelope } from '../types';

export const stageNames = [
  'loading', 'systems', 'l0', 'geometry', 'equilibrium', 'hydrostatics', 'gz', 'deck',
  'hydrostatic_curve', 'bonjean', 'resistance', 'propulsion', 'endurance', 'historical', 'flooding',
] as const;

function envelope(status: StageEnvelope['status'] = 'not_requested', requested = false, data: StageEnvelope['data'] = null): StageEnvelope {
  return {
    status, requested, reason: status === 'not_requested' ? '未请求' : null,
    validity: { complete: status === 'completed', converged: status === 'completed' ? true : null, model_applicable: status === 'completed' ? true : null, historical_validated: null },
    method_versions: {}, assumptions: [], diagnostics: [], data,
  };
}

const base: AnalysisResult = {
  schema: 'plimsoll-analysis-1', status: 'completed', project_id: 'queen-mary', condition_id: 'normal-engineering',
  project_fingerprint: 'project-123', input_fingerprint: 'input-123', request_fingerprint: 'request-123',
  request: { stages: ['loading', 'equilibrium'] },
  input_snapshot: { schema: 'plimsoll-project-1', id: 'queen-mary', name: 'HMS Queen Mary', revision: 2, hull: { loa_m: 213.4, beam_m: 27.2 }, geometry: null, weight_groups: [], loading_conditions: [{ id: 'normal-engineering', label: '正常载荷' }] },
  units: { length: 'm', mass: 't' }, method_versions: { coordinator: 'selected-loading-analysis-1' },
  sources: {}, diagnostics: [],
  validity: { complete: true, converged: true, model_applicable: true, historical_validated: null },
  stages: Object.fromEntries(stageNames.map(name => [name, envelope()])),
};

export const completedFixture: AnalysisResult = structuredClone(base);
completedFixture.stages.loading = envelope('completed', true, { total_mass_t: 27200, lcg_m: 0 });
completedFixture.stages.equilibrium = envelope('completed', true, { draught_m: 9.9, heel_deg: 0 });

export const partialFixture: AnalysisResult = structuredClone(completedFixture);
partialFixture.status = 'partial';
partialFixture.validity.complete = false;
partialFixture.stages.deck = envelope('unavailable', true);
partialFixture.stages.deck.reason = '甲板端点资料不足';
partialFixture.stages.equilibrium = envelope('model_limit', true);
partialFixture.stages.equilibrium.reason = '超出方法适用范围';
partialFixture.stages.equilibrium.diagnostics = [{ code: 'MODEL_LIMIT', severity: 'warning', path: '$.stages.equilibrium', message: '超出方法适用范围' }];
