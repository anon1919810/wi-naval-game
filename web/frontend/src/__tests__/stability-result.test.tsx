import { cleanup, screen, within } from '@testing-library/react';
import { renderZh as render, inLanguage, zhCopy } from './locale';
import { afterEach, describe, expect, it } from 'vitest';

import { PerformanceResults } from '../components/PerformanceEditor';
import { ReportReadings } from '../components/ReportReadings';
import { StageStatus } from '../components/StageStatus';
import { UnitProvider } from '../components/UnitProvider';
import { overviewReadings as overviewInLanguage } from '../components/WorkbenchOverview';
import { Report } from '../pages/Report';
import {
  EQUILIBRIUM_GM_KEY, equilibriumGmReading, reportReadings as readingsInLanguage,
  ROLL_PERIOD_KEY, rollPeriodReading, uprightGmReading,
} from '../components/resultReading';
import { formatNumber, readPreferences } from '../components/units';
import type { AnalysisResult, RunView, StageEnvelope } from '../types';

/**
 * The pinned F06 physical-result contract, read the way the reader meets it.
 *
 * The upright geometric GM (`values.gm_t_m`) and the equilibrium equivalent GM
 * (`small_angle_stability.equilibrium_gm_m`) are two different facts from two
 * different saved paths, and the loaded-roll period (`loaded_roll.period_s`) is
 * a third. This file pins them separately on every surface that shows a saved
 * result: the overview, the shared run/report readings, and the performance
 * results, in both languages and in both length units.
 *
 * Everything here is a saved value or a saved reason. No number is derived in
 * the browser, nothing falls back to the old GM, to the request or to another
 * run, and a residual scalar inside a nested result that did not complete is
 * never shown.
 */

afterEach(cleanup);

function stage(status: StageEnvelope['status'], requested: boolean, data: StageEnvelope['data'] = null,
  reason: string | null = null): StageEnvelope {
  return {
    status, requested, reason,
    validity: { complete: status === 'completed', converged: status === 'completed' ? true : null,
      model_applicable: status === 'completed' ? true : null, historical_validated: null },
    method_versions: {}, assumptions: [], diagnostics: [], data,
  };
}

function result(stages: Record<string, StageEnvelope>): AnalysisResult {
  // A minimally complete envelope, so the same fixture can be projected, rendered
  // as a stage card, and rendered as the whole report page.
  return { schema: 'plimsoll-analysis-1', status: 'completed', project_id: 'p1', condition_id: 'trimmed',
    project_fingerprint: 'pf', input_fingerprint: 'if', request_fingerprint: 'rf',
    request: { stages: [] }, input_snapshot: null, units: {}, method_versions: {}, sources: {},
    diagnostics: [],
    validity: { complete: true, converged: true, model_applicable: true, historical_validated: null },
    stages } as unknown as AnalysisResult;
}

const HYDRO = 'hydrostatics';

function savedResult(data: StageEnvelope['data'], overrides: Partial<StageEnvelope> = {}): AnalysisResult {
  return result({
    loading: stage('completed', true, { values: { total_mass_t: 27200 } }),
    equilibrium: stage('completed', true, { waterline_above_keel_m: 9.92, heel_deg: 0 }),
    hydrostatics: { ...stage('completed', true, data), ...overrides },
  });
}

function savedRun(data: StageEnvelope['data'], overrides: Partial<StageEnvelope> = {}): RunView {
  return { id: 'run-f06', project_id: 'p1', revision: 1, condition_id: 'trimmed', status: 'completed',
    request_fingerprint: 'fp-f06', created_at: '2026-10-15T00:00:00Z', started_at: null, finished_at: null,
    cancel_requested: false, error: null, result: savedResult(data, overrides) } as unknown as RunView;
}

/** A trimmed, non-upright condition that finished: upright GM null, new GM saved. */
const TRIMMED = {
  values: { gm_t_m: null, equilibrium_gm_t_m: 0.86185, waterline_beam_body_y_m: 8 },
  small_angle_stability: {
    status: 'completed', reason: null, equilibrium_gm_m: 0.86185,
    method_version: 'free_trim_equilibrium_roll_stiffness_v1',
    definition: 'dR/dphi at the free-trim equilibrium heel',
    restoring_sign: 'positive', refinement_delta_m: 4.2e-4,
  },
  loaded_roll: { status: 'unavailable', period_s: null, reason: '有纵倾时缺少与基态横倾轴兼容的惯性轴资料',
    method: 'selected_loading_equilibrium_roll_v2', selected_gm_m: 0.86185, source: 'roll inertia study' },
} as Record<string, unknown>;

const GM_NOTE = zhCopy('reading.equilibriumGmNote');
const PERIOD_NOTE = zhCopy('reading.rollPeriodNote');
const HYDRO_LABEL = zhCopy('stage.hydrostatics');
const KNOWN_NOTE = zhCopy('overview.reading.known', { stage: HYDRO_LABEL });

function byKey(data: Record<string, unknown>, key: string, overrides: Partial<StageEnvelope> = {}) {
  const reading = readingsInLanguage(savedResult(data, overrides), 'zh-CN').find(item => item.key === key);
  if (!reading) throw new Error(`reading ${key} was not projected`);
  return reading;
}
const upright = (data: Record<string, unknown>, overrides?: Partial<StageEnvelope>) =>
  byKey(data, 'hydrostatics.gm_t_m', overrides);
const equilibrium = (data: Record<string, unknown>, overrides?: Partial<StageEnvelope>) =>
  byKey(data, EQUILIBRIUM_GM_KEY, overrides);
const roll = (data: Record<string, unknown>, overrides?: Partial<StageEnvelope>) =>
  byKey(data, ROLL_PERIOD_KEY, overrides);
const nested = (patch: Record<string, unknown>): Record<string, unknown> => ({
  ...TRIMMED, small_angle_stability: { ...(TRIMMED.small_angle_stability as Record<string, unknown>), ...patch },
});

describe('the two metacentric heights stay two readings', () => {
  it('reads the saved restoring slope beside the upright GM, never instead of it', () => {
    // A trimmed condition has no upright geometric GM at all, and that stays
    // unknown rather than borrowing the restoring slope or an input value.
    expect(upright(TRIMMED)).toMatchObject({ state: 'unknown', value: null, dimension: 'length', storedUnit: 'm' });
    expect(upright(TRIMMED).reason).toBe('保存结果中 values.gm_t_m 为 null');
    expect(upright(TRIMMED).label).toBe('直立几何 GM');

    const saved = equilibrium(TRIMMED);
    expect(saved).toMatchObject({ state: 'known', value: 0.86185, dimension: 'length', storedUnit: 'm', reason: null });
    expect(saved.label).toBe('平衡态等效 GM');
    // The saved explanation says what the new number is, and what it is not.
    expect(saved.context).toBe(`阶段 静水力 · ${GM_NOTE}`);

    // Two heights and one period, in one fixed order.
    expect(readingsInLanguage(savedResult(TRIMMED), 'zh-CN').map(item => item.key)).toEqual([
      'loading.total_mass_t', 'equilibrium.waterline_above_keel_m', 'equilibrium.heel_deg',
      'hydrostatics.gm_t_m', EQUILIBRIUM_GM_KEY, ROLL_PERIOD_KEY,
      'resistance.shaft_power_kw', 'endurance.range_nm',
    ]);
  });

  it('keeps an upright run\'s own GM and offers no restoring slope it never saved', () => {
    const uprightOnly = { values: { gm_t_m: 1.85 },
      loaded_roll: { status: 'unavailable', period_s: null, reason: '缺少有来源的回转系数' } };
    expect(upright(uprightOnly)).toMatchObject({ state: 'known', value: 1.85 });
    // An old saved result that predates the nested result stays unknown with a
    // missing-result reason: no fallback to the old GM, the input or a later run.
    expect(equilibrium(uprightOnly)).toMatchObject({ state: 'unknown', value: null, reason: '本次结果未保存小角度稳性结果' });
  });

  it('reaches the reader when the nested result is unavailable although its parent completed', () => {
    const reading = equilibrium(nested({
      status: 'unavailable', reason: '基态横倾未收敛', equilibrium_gm_m: 0.4, restoring_sign: 'unresolved',
    }));
    expect([reading.state, reading.value]).toEqual(['unavailable', null]);
    // The core's own reason text is passed through verbatim inside a local frame.
    expect(reading.reason).toBe('暂不可计算：基态横倾未收敛');
    // A residual scalar left inside a nested result that did not complete never
    // reaches the reader, not even beside the same number saved in `values`.
    expect(reading.reason).not.toContain('0.4');
    expect(reading.label).toBe('平衡态等效 GM');
  });

  it('never shows a nested number behind a stage that did not deliver a result', () => {
    const blocked: Array<Partial<StageEnvelope>> = [
      { status: 'unavailable', reason: '型线资料不足' },
      { status: 'canceled' },
      { status: 'not_requested', requested: false },
      { status: 'failed', reason: '权重账本自检未通过' },
    ];
    for (const overrides of blocked) {
      const gm = equilibrium(TRIMMED, overrides);
      const period = roll(TRIMMED, overrides);
      expect([gm.value, period.value], String(overrides.status)).toEqual([null, null]);
      expect([gm.state, period.state], String(overrides.status)).not.toContain('known');
      expect(gm.context).toContain('静水力');
    }
    // The parent stage's own stop reason names the stop; an unrequested stage is
    // named as such rather than read.
    expect(equilibrium(TRIMMED, { status: 'unavailable', reason: '型线资料不足' }).reason).toBe('暂不可计算：型线资料不足');
    expect(equilibrium(TRIMMED, { status: 'not_requested', requested: false }).reason).toBe('本次请求未运行该阶段');
  });

  it('keeps a finite negative and a genuine zero as the values they are', () => {
    // An unresolved or destabilising restoring slope is a computed answer: it is
    // never folded into zero, into a positive number or into "safe".
    expect(equilibrium(nested({ equilibrium_gm_m: -0.0135, restoring_sign: 'negative' })))
      .toMatchObject({ state: 'known', value: -0.0135, reason: null });
    expect(equilibrium(nested({ equilibrium_gm_m: 0, restoring_sign: 'unresolved' })))
      .toMatchObject({ state: 'known', value: 0, reason: null });

    // Missing, null and non-finite stay three different facts.
    expect(equilibrium(nested({ equilibrium_gm_m: undefined })).reason).toBe('本次结果未给出此字段');
    expect(equilibrium(nested({ equilibrium_gm_m: null })).reason).toBe('保存结果中 equilibrium_gm_m 为 null');
    expect(equilibrium(nested({ equilibrium_gm_m: '0.86' })).reason).toBe('保存结果中 equilibrium_gm_m 不是有限数字');
    // A nested block with no status of its own is not a result.
    expect(equilibrium({ ...TRIMMED, small_angle_stability: {} })).toMatchObject({
      state: 'unknown', value: null, reason: '本次结果未保存小角度稳性结果' });
  });
});

describe('the saved roll period', () => {
  const WITH_PERIOD = { ...TRIMMED, loaded_roll: { status: 'completed', period_s: 12.5, reason: null,
    method: 'selected_loading_equilibrium_roll_v2', selected_gm_m: 0.86185, source: 'roll inertia study', estimate: true } };

  it('shows a saved positive period in seconds and never converts it', () => {
    const reading = roll(WITH_PERIOD);
    expect(reading).toMatchObject({ state: 'known', value: 12.5, canonicalUnit: 's', reason: null });
    // A period has no convertible reader unit, exactly like the nmi of a range.
    expect(reading.dimension).toBeUndefined();
    expect(reading.source).toBe('roll inertia study');
    expect(reading.estimate).toBe(true);
    expect(reading.label).toBe('横摇周期估算');
    expect(reading.context).toBe(`阶段 静水力 · ${PERIOD_NOTE}`);
  });

  it('names the saved unavailable reason instead of a period it never had', () => {
    const reading = roll(TRIMMED);
    expect([reading.state, reading.value]).toEqual(['unavailable', null]);
    expect(reading.reason).toBe('暂不可计算：有纵倾时缺少与基态横倾轴兼容的惯性轴资料');
    expect(reading.label).toBe('横摇周期估算');
  });

  it('keeps a completed study without a finite period unknown with a field reason', () => {
    expect(roll({ ...TRIMMED, loaded_roll: { status: 'completed', period_s: null } }).reason).toBe('保存结果中 period_s 为 null');
    expect(roll({ ...TRIMMED, loaded_roll: { status: 'completed', period_s: Number.POSITIVE_INFINITY } }).reason)
      .toBe('保存结果中 period_s 不是有限数字');
    // A stray number beside an unavailable study is never read.
    const stray = { ...TRIMMED, loaded_roll: { status: 'unavailable', period_s: 9.9, reason: '缺少有来源的回转系数' } };
    expect(roll(stray)).toMatchObject({ state: 'unavailable', value: null, reason: '暂不可计算：缺少有来源的回转系数' });
  });

  it('keeps a saved result with no roll study unknown instead of guessing a period', () => {
    expect(roll({ values: { gm_t_m: 1.85 } })).toMatchObject({ state: 'unknown', value: null, reason: '本次结果未保存装载横摇结果' });
  });

  it('never reads the restoring height as a period, or the period as a restoring height', () => {
    // Both saved identities live in one stage and are not interchangeable.
    const mixed = { ...TRIMMED, loaded_roll: { status: 'completed', period_s: 12.5, method: 'selected_loading_small_angle_roll_v1' } };
    expect(equilibrium(mixed)).toMatchObject({ state: 'known', value: 0.86185 });
    expect(roll(mixed)).toMatchObject({ state: 'known', value: 12.5 });
    expect(equilibrium({ values: { gm_t_m: null }, loaded_roll: mixed.loaded_roll }))
      .toMatchObject({ state: 'unknown', value: null });
  });
});

describe('the overview projection', () => {
  const overview = (data: Record<string, unknown>, overrides: Partial<StageEnvelope> = {}) =>
    overviewInLanguage(savedRun(data, overrides), 'zh-CN');

  it('adds the equilibrium GM as its own reading, after the upright one', () => {
    const entries = overview(TRIMMED);
    expect(entries.map(entry => entry.key)).toEqual([
      'loading.total_mass_t', 'equilibrium.waterline_above_keel_m', 'equilibrium.heel_deg',
      'hydrostatics.gm_t_m', EQUILIBRIUM_GM_KEY,
    ]);
    const saved = entries[4];
    expect(saved).toMatchObject({ state: 'known', value: 0.86185, dimension: 'length', storedUnit: 'm' });
    expect(saved.label).toBe('平衡态等效 GM');
    expect(saved.note).toBe(`${KNOWN_NOTE} · ${GM_NOTE}`);
    // The upright GM of the same run stays unknown and shows no number.
    expect(entries[3]).toMatchObject({ state: 'unknown', value: null });
    expect(entries[4].note).not.toContain('null');
  });

  it('keeps a nested reason on the overview reading and never its residual number', () => {
    const saved = overview(nested({ status: 'unavailable', reason: '几何接触', equilibrium_gm_m: 1.5 }))[4];
    expect(saved).toMatchObject({ state: 'unavailable', value: null, note: '暂不可计算：几何接触 · 阶段 静水力' });
    expect(saved.note).not.toContain('1.5');
  });

  it('gives a run without the nested result a missing-result note of its own', () => {
    expect(overview({ values: { gm_t_m: 1.85 } })[4]).toMatchObject({
      state: 'unknown', value: null, note: `阶段 静水力 · ${zhCopy('reading.reason.noSmallAngle')}`,
    });
  });

  it('follows the parent stage when that stage is not usable', () => {
    expect(overview(TRIMMED, { status: 'unavailable', reason: '型线资料不足' })[4])
      .toMatchObject({ state: 'unavailable', value: null, note: '暂不可计算：型线资料不足 · 阶段 静水力' });
  });
});

describe('the shared report readings, rendered', () => {
  const readingsPanel = (data: Record<string, unknown>, preferences: unknown = {}, language: 'zh-CN' | 'en' = 'zh-CN') =>
    inLanguage(<UnitProvider preferences={preferences}><ReportReadings result={savedResult(data)} /></UnitProvider>, language);

  it('prints both heights, the period and their reasons in Chinese', () => {
    render(readingsPanel(TRIMMED));
    expect(document.querySelectorAll('.report-reading')).toHaveLength(8);
    const panel = within(document.querySelector('.report-readings') as HTMLElement);
    expect(panel.getByText('直立几何 GM')).toBeVisible();
    expect(panel.getByText('平衡态等效 GM')).toBeVisible();
    expect(panel.getByText('0.86185 m')).toBeVisible();
    expect(panel.getByText(`阶段 静水力 · ${GM_NOTE}`)).toBeVisible();
    // The upright GM of a trimmed condition is unknown: the field-level projection
    // wording is said for the reader and the field name is not printed.
    const uprightCard = panel.getByText('直立几何 GM').closest('.report-reading') as HTMLElement;
    expect(within(uprightCard).getByText('未知')).toBeVisible();
    expect(within(uprightCard).getByText(zhCopy('reading.reason.null'))).toBeVisible();
    expect(within(uprightCard).queryByText(/values\.gm_t_m/)).toBeNull();
    // The period is unavailable, so its saved reason is what the reader gets, and
    // the stray scalar that sat beside it in the payload is never shown.
    const periodCard = panel.getByText('横摇周期估算').closest('.report-reading') as HTMLElement;
    expect(within(periodCard).getByText('未知')).toBeVisible();
    expect(within(periodCard).getByText('暂不可计算：有纵倾时缺少与基态横倾轴兼容的惯性轴资料')).toBeVisible();
    expect(periodCard.querySelector('.report-reading-value')!.textContent).toBe('未知');
  });

  it('converts both stored metres through the reader length preference', () => {
    render(readingsPanel(TRIMMED, readPreferences({ length: 'ft' })));
    const panel = within(document.querySelector('.report-readings') as HTMLElement);
    // 0.86185 m is 2.827592 ft; the stored metre value is not rewritten.
    expect(panel.getByText('2.827592 ft')).toBeVisible();
    expect(panel.queryByText('0.86185 m')).toBeNull();
  });

  it('prints the same values, states and order in English', () => {
    render(readingsPanel(TRIMMED, {}, 'en'));
    const panel = within(document.querySelector('.report-readings') as HTMLElement);
    expect(document.querySelectorAll('.report-reading')).toHaveLength(8);
    expect(panel.getByText('Upright geometric GM')).toBeVisible();
    expect(panel.getByText('Equilibrium equivalent GM')).toBeVisible();
    expect(panel.getByText('Roll period estimate')).toBeVisible();
    expect(panel.getByText('0.86185 m')).toBeVisible();
    // The reason is the core's saved text; only the frame around it is localized.
    expect(panel.getByText(`Not computable now: 有纵倾时缺少与基态横倾轴兼容的惯性轴资料`)).toBeVisible();
    expect(panel.getByText(/^Stage Hydrostatics · Local restoring slope/)).toBeVisible();
    expect(panel.getByText(/^Stage Hydrostatics · Saved scalar period estimate/)).toBeVisible();
    // One language change re-words the panel without touching a single number.
    const english = readingsInLanguage(savedResult(TRIMMED), 'en');
    const chinese = readingsInLanguage(savedResult(TRIMMED), 'zh-CN');
    expect(english.map(item => [item.key, item.state, item.value])).toEqual(chinese.map(item => [item.key, item.state, item.value]));
  });
});

describe('the performance results', () => {
  const field = (label: string) => screen.getByText(label).closest('.fact-field') as HTMLElement;
  const value = (label: string) => field(label).querySelector('.fact-value')!.textContent;
  /** The provenance line of a card: what the run says about where it came from. */
  const meta = (label: string) => field(label).querySelector('.fact-meta')!.textContent ?? '';
  const study = (label: string) => screen.getByText(label).closest('.study-result') as HTMLElement;
  /** The separate note lines: an explanation or a reason, never a source. */
  const hints = () => Array.from(document.querySelectorAll('.form-hint')).map(node => node.textContent ?? '');
  const section = () => document.querySelector('.form-results') as HTMLElement;

  it('show the two heights separately, with the saved note on the new one', () => {
    render(inLanguage(<PerformanceResults run={savedRun(TRIMMED)} />, 'zh-CN'));
    expect(value('所选工况总质量')).toContain('27,200 t');
    expect(value('直立几何 GM')).toBe('未知');
    expect(value('平衡态等效 GM')).toBe('0.86185 m');
    // The explanation is its own note, not the card's provenance.
    expect(hints()).toContain(`平衡态等效 GM · ${GM_NOTE}`);
    expect(meta('平衡态等效 GM')).not.toContain(GM_NOTE);
    // No number is borrowed across the two labels.
    expect(field('直立几何 GM').textContent).not.toContain('0.86185');
  });

  it('show the saved period in seconds, with its own note and saved method', () => {
    render(inLanguage(<PerformanceResults run={savedRun({ ...TRIMMED, loaded_roll: { status: 'completed', period_s: 12.5,
      reason: null, method: 'selected_loading_equilibrium_roll_v2', selected_gm_m: 0.86185, estimate: true } })} />, 'zh-CN'));
    expect(value('横摇周期估算')).toBe('12.5 s');
    expect(hints()).toContain(`横摇周期估算 · ${PERIOD_NOTE}`);
    expect(meta('横摇周期估算')).toContain('估算');
    expect(meta('横摇周期估算')).not.toContain(PERIOD_NOTE);
    // The saved method identity is still shown as saved.
    expect(within(study('所选工况横摇')).getByText('selected_loading_equilibrium_roll_v2')).toBeVisible();
  });

  it('name the unavailable reason in its own note, never as the card provenance', () => {
    render(inLanguage(<PerformanceResults run={savedRun(TRIMMED)} />, 'zh-CN'));
    expect(value('横摇周期估算')).toBe('未知');
    expect(hints()).toContain(`横摇周期估算：暂不可计算：有纵倾时缺少与基态横倾轴兼容的惯性轴资料`);
    expect(meta('横摇周期估算')).not.toContain('有纵倾时缺少与基态横倾轴兼容的惯性轴资料');
  });

  it('keep the saved roll status visible beside its own study', () => {
    render(inLanguage(<PerformanceResults run={savedRun({ ...TRIMMED,
      loaded_roll: { status: 'completed', period_s: 12.5, method: 'selected_loading_small_angle_roll_v1' } })} />, 'zh-CN'));
    expect(study('所选工况横摇').querySelector('h4')!.textContent).toContain('completed');
    expect(study('所选工况横摇').textContent).toContain('12.5 s');
    // The old and the new roll methods are separate saved identities.
    expect(within(study('所选工况横摇')).getByText('selected_loading_small_angle_roll_v1')).toBeVisible();
  });

  it('still read the mass and the studies the section already showed', () => {
    render(inLanguage(<PerformanceResults run={savedRun(TRIMMED)} />, 'zh-CN'));
    expect(value('所选工况总质量')).toContain('27,200 t');
    expect(screen.getByText('目标纵倾约束研究')).toBeVisible();
    expect(screen.getByText('所选工况横摇')).toBeVisible();
  });

  it('say nothing at all without a saved run', () => {
    render(inLanguage(<PerformanceResults run={null} />, 'zh-CN'));
    expect(document.querySelectorAll('.fact-field')).toHaveLength(0);
  });
});

describe('the saved provenance of a stability reading', () => {
  const field = (label: string) => screen.getByText(label).closest('.fact-field') as HTMLElement;
  const meta = (label: string) => field(label).querySelector('.fact-meta')!.textContent ?? '';
  const hints = () => Array.from(document.querySelectorAll('.form-hint')).map(node => node.textContent ?? '');

  it('shows the declared string source as saved, and keeps the note elsewhere', () => {
    render(inLanguage(<PerformanceResults run={savedRun({ ...TRIMMED, loaded_roll: { status: 'completed', period_s: 12.5,
      reason: null, method: 'selected_loading_equilibrium_roll_v2', source: 'explicit coefficient from inclining record', estimate: true } })} />, 'zh-CN'));
    expect(meta('横摇周期估算')).toContain('explicit coefficient from inclining record');
    expect(meta('横摇周期估算')).not.toContain(PERIOD_NOTE);
    expect(hints()).toContain(`横摇周期估算 · ${PERIOD_NOTE}`);
  });

  it('shows a structured saved source as saved, through the shared source helper', () => {
    const source = { id: 'inclining-record', page: '第 12 页' };
    // The projection carries it; the card must show the same text, not a summary.
    expect(rollPeriodReading('zh-CN', savedResult({ ...TRIMMED, loaded_roll: { status: 'completed', period_s: 12.5,
      reason: null, method: 'selected_loading_equilibrium_roll_v2', source } }).stages[HYDRO]).source)
      .toBe(JSON.stringify(source));
    render(inLanguage(<PerformanceResults run={savedRun({ ...TRIMMED,
      loaded_roll: { status: 'completed', period_s: 12.5, reason: null, method: 'selected_loading_equilibrium_roll_v2', source } })} />, 'zh-CN'));
    expect(meta('横摇周期估算')).toContain(JSON.stringify(source));
  });

  it('says the run was the source when the core declared none, never the note', () => {
    render(inLanguage(<PerformanceResults run={savedRun({ ...TRIMMED, loaded_roll: { status: 'completed', period_s: 12.5,
      reason: null, method: 'selected_loading_equilibrium_roll_v2' } })} />, 'zh-CN'));
    expect(meta('横摇周期估算')).toContain(zhCopy('formResults.sourceRun'));
    expect(meta('横摇周期估算')).not.toContain(PERIOD_NOTE);
  });

  it('keeps the equilibrium GM provenance apart from its definition as well', () => {
    render(inLanguage(<PerformanceResults run={savedRun(TRIMMED)} />, 'zh-CN'));
    expect(meta('平衡态等效 GM')).toContain(zhCopy('formResults.sourceRun'));
    expect(meta('平衡态等效 GM')).not.toContain(GM_NOTE);
    expect(hints()).toContain(`平衡态等效 GM · ${GM_NOTE}`);
  });
});

describe('the performance results read every stability reading through the saved gate', () => {
  const RESIDUAL = {
    values: { gm_t_m: 9.99, equilibrium_gm_t_m: 7.77 },
    small_angle_stability: { status: 'completed', reason: null, equilibrium_gm_m: 7.77,
      method_version: 'free_trim_equilibrium_roll_stiffness_v1', restoring_sign: 'positive', refinement_delta_m: 1e-4 },
    loaded_roll: { status: 'completed', period_s: 99.9, reason: null, method: 'selected_loading_equilibrium_roll_v2' },
  };
  const blocked: Array<[string, Partial<StageEnvelope>]> = [
    ['failed', { status: 'failed', reason: '权重账本自检未通过' }],
    ['unavailable', { status: 'unavailable', reason: '型线资料不足' }],
    ['canceled', { status: 'canceled' }],
    ['not requested', { status: 'not_requested', requested: false }],
  ];

  const shown = (label: string) =>
    screen.getByText(label).closest('.fact-field')!.querySelector('.fact-value')!.textContent;

  it('suppresses a residual old GM, new GM and period behind a stage that failed', () => {
    for (const [name, overrides] of blocked) {
      cleanup();
      render(inLanguage(<PerformanceResults run={savedRun(RESIDUAL, overrides)} />, 'zh-CN'));
      // The old GM is a plain saved scalar, so it is the one most likely to leak;
      // it must be gated exactly like the two nested results beside it.
      expect(shown('直立几何 GM'), name).toBe('未知');
      expect(shown('平衡态等效 GM'), name).toBe('未知');
      expect(shown('横摇周期估算'), name).toBe('未知');
      const text = document.body.textContent ?? '';
      for (const residual of ['9.99', '7.77', '99.9']) expect(text, `${name} leaks ${residual}`).not.toContain(residual);
    }
  });

  it('agrees with the shared report readings, reading for reading', () => {
    const cases: Array<[string, Record<string, unknown>, Partial<StageEnvelope>?]> = [
      ['both saved', TRIMMED],
      ['period unavailable', TRIMMED],
      ['gm unavailable', nested({ status: 'unavailable', reason: '基态横倾未收敛', equilibrium_gm_m: 0.4 })],
      ['nothing nested', { values: { gm_t_m: 1.85 } }],
      ['negative gm', nested({ equilibrium_gm_m: -0.0135, restoring_sign: 'negative' })],
      ['zero gm', nested({ equilibrium_gm_m: 0, restoring_sign: 'unresolved' })],
      ['period saved', { ...TRIMMED, loaded_roll: { status: 'completed', period_s: 12.5, reason: null, method: 'selected_loading_equilibrium_roll_v2' } }],
      ['failed parent', RESIDUAL, { status: 'failed', reason: '权重账本自检未通过' }],
      ['unrequested parent', RESIDUAL, { status: 'not_requested', requested: false }],
    ];
    const pairs: Array<[string, string]> = [
      ['hydrostatics.gm_t_m', '直立几何 GM'],
      [EQUILIBRIUM_GM_KEY, '平衡态等效 GM'],
      [ROLL_PERIOD_KEY, '横摇周期估算'],
    ];
    for (const [name, data, overrides] of cases) {
      cleanup();
      const readings = readingsInLanguage(savedResult(data, overrides), 'zh-CN');
      render(inLanguage(<PerformanceResults run={savedRun(data, overrides)} />, 'zh-CN'));
      for (const [key, label] of pairs) {
        const reading = readings.find(item => item.key === key)!;
        const printed = shown(label);
        if (reading.state !== 'known' || reading.value === null) {
          expect(printed, `${name} / ${key}`).toBe(zhCopy('reading.unknown'));
        } else {
          // Canonical display units: metres for a height, unconverted seconds.
          const unit = reading.canonicalUnit === 's' ? ' s' : ' m';
          expect(printed, `${name} / ${key}`).toBe(`${formatNumber(reading.value)}${unit}`);
        }
      }
    }
  });

  it('reads the upright GM through the same exported projection', () => {
    const saved = savedResult(TRIMMED).stages[HYDRO];
    expect(uprightGmReading('zh-CN', saved)).toMatchObject({
      key: 'hydrostatics.gm_t_m', state: 'unknown', value: null, label: '直立几何 GM',
    });
    // An upright run's own GM reads through exactly the same gate as the report.
    expect(uprightGmReading('zh-CN', savedResult({ values: { gm_t_m: 1.85 } }).stages[HYDRO]))
      .toMatchObject({ state: 'known', value: 1.85 });
    expect(uprightGmReading('zh-CN', savedResult(RESIDUAL, { status: 'failed', reason: '权重账本自检未通过' }).stages[HYDRO]))
      .toMatchObject({ state: 'failed', value: null, reason: '计算失败：权重账本自检未通过' });
  });
});

/**
 * The saved alias on the stage card itself.
 *
 * `values.equilibrium_gm_t_m` repeats `small_angle_stability.equilibrium_gm_m`,
 * so the generic stage card must apply the nested result's own completed status
 * before quoting it. The parent stage's gate was already applied there; this is
 * the second half of the same rule, on the real Run and Report surfaces.
 */
describe('the hydrostatics stage card quotes the alias only when the nested result completed', () => {
  const ALIAS_LABEL = zhCopy('data.equilibrium_gm_t_m');
  const RESIDUAL_ALIAS: Record<string, unknown> = {
    values: { gm_t_m: null, equilibrium_gm_t_m: 0.4, waterline_d_m: 4.0 },
    small_angle_stability: { status: 'unavailable', reason: 'contact', equilibrium_gm_m: 0.4,
      method_version: 'free_trim_equilibrium_roll_stiffness_v1', restoring_sign: 'unresolved' },
  };

  it('drops a residual alias beside an unavailable nested result', () => {
    const hydrostatics = stage('completed', true, RESIDUAL_ALIAS);
    render(inLanguage(<StageStatus name="hydrostatics" stage={hydrostatics} />, 'zh-CN'));
    const card = document.getElementById('stage-hydrostatics')!;
    // The shared reading blocks it, and so must the card.
    expect(equilibriumGmReading('zh-CN', hydrostatics)).toMatchObject({ state: 'unavailable', value: null });
    expect(card.querySelector('.stage-values')!.textContent).not.toContain(ALIAS_LABEL);
    expect(card.querySelector('.stage-values')!.textContent).not.toContain('0.4');
    // Nothing else in the payload is collateral: the upright GM and the rest stay.
    expect(card.textContent).toContain('4 m');
    // The raw payload is still reachable, so nothing is lost by not showing it.
    expect(card.textContent).toContain('完整阶段数据与来源');
  });

  it('drops the alias when an older result has no nested result at all', () => {
    const hydrostatics = stage('completed', true, { values: { gm_t_m: 1.85, equilibrium_gm_t_m: 0.4 } });
    render(inLanguage(<StageStatus name="hydrostatics" stage={hydrostatics} />, 'zh-CN'));
    const card = document.getElementById('stage-hydrostatics')!;
    expect(card.querySelector('.stage-values')!.textContent).not.toContain(ALIAS_LABEL);
    // The upright GM of the same run is still quoted: it needs no nested status.
    expect(card.querySelector('.stage-values')!.textContent).toContain('1.85 m');
  });

  it('still quotes the alias when the nested result completed', () => {
    const hydrostatics = stage('completed', true, {
      values: { gm_t_m: null, equilibrium_gm_t_m: 0.86185 },
      small_angle_stability: { status: 'completed', reason: null, equilibrium_gm_m: 0.86185 },
    });
    render(inLanguage(<StageStatus name="hydrostatics" stage={hydrostatics} />, 'zh-CN'));
    const values = document.getElementById('stage-hydrostatics')!.querySelector('.stage-values')!;
    expect(values.textContent).toContain(ALIAS_LABEL);
    expect(values.textContent).toContain('0.86185 m');
  });

  it.each([undefined, null, Infinity])('drops the alias when the completed nested GM is %s', value => {
    const hydrostatics = stage('completed', true, {
      values: { gm_t_m: 1.85, equilibrium_gm_t_m: 0.4 },
      small_angle_stability: { status: 'completed', equilibrium_gm_m: value },
    });
    expect(equilibriumGmReading('zh-CN', hydrostatics)).toMatchObject({ state: 'unknown', value: null });
    render(inLanguage(<StageStatus name="hydrostatics" stage={hydrostatics} />, 'zh-CN'));
    const values = document.getElementById('stage-hydrostatics')!.querySelector('.stage-values')!;
    expect(values.textContent).not.toContain(ALIAS_LABEL);
    expect(values.textContent).not.toContain('0.4 m');
    expect(values.textContent).toContain('1.85 m');
  });

  it('keeps the alias out of the report page for the same reason', () => {
    render(inLanguage(<Report result={savedResult(RESIDUAL_ALIAS)} runId="run-7" />, 'zh-CN'));
    const card = document.getElementById('stage-hydrostatics')!;
    expect(card.querySelector('.stage-values')!.textContent).not.toContain(ALIAS_LABEL);
    expect(card.querySelector('.stage-values')!.textContent).not.toContain('0.4');
    // The readings panel states the same refusal with its saved reason.
    const readings = within(document.querySelector('.report-readings') as HTMLElement);
    expect(readings.getByText('暂不可计算：contact')).toBeVisible();
    expect(readings.queryByText('0.4 m')).toBeNull();
  });
});

describe('the exported reading projections', () => {
  const saved = savedResult(TRIMMED).stages[HYDRO];

  it('are the numbers the rendered panels print, in either language', () => {
    expect(equilibriumGmReading('en', saved)).toMatchObject({
      key: EQUILIBRIUM_GM_KEY, state: 'known', value: 0.86185,
      dimension: 'length', storedUnit: 'm', label: 'Equilibrium equivalent GM',
    });
    expect(equilibriumGmReading('zh-CN', saved).label).toBe('平衡态等效 GM');
    expect(rollPeriodReading('en', saved)).toMatchObject({
      key: ROLL_PERIOD_KEY, state: 'unavailable', value: null, canonicalUnit: 's',
    });
  });

  it('name a stage that is absent instead of reading it', () => {
    for (const project of [equilibriumGmReading, rollPeriodReading]) {
      expect(project('zh-CN', null)).toMatchObject({ state: 'not_requested', value: null, reason: '该运行没有保存此阶段' });
    }
  });
});
