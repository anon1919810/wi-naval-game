import { render, cleanup, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { ReportReadings } from '../components/ReportReadings';
import { UnitProvider } from '../components/UnitProvider';
import { inLanguage } from './locale';
import type { AnalysisResult, StageEnvelope } from '../types';

/**
 * The first screen of a native design report, read the way the reader meets it.
 *
 * A native run saved one frozen `ship_design` result; that result is the summary,
 * and the physical cards of stages the run never requested must not stand in for
 * it. Everything asserted here is a saved path of that result — the reconciled
 * balance and the engine and performance sections — printed with the unit the
 * source saved, never a number the browser derived and never a zero standing in
 * for an unbound mass.
 *
 * The panel is the real `ReportReadings`, so these assertions ride the same
 * renderer and the same unit vocabulary the report page uses.
 */

afterEach(cleanup);

function stage(status: StageEnvelope['status'], requested: boolean, data: StageEnvelope['data'],
  reason: string | null = null, methodVersions: Record<string, unknown> = {}): StageEnvelope {
  return {
    status, requested, reason,
    validity: { complete: status === 'completed', converged: null, model_applicable: null, historical_validated: null },
    method_versions: methodVersions, assumptions: [], diagnostics: [], data,
  };
}

function result(stages: Record<string, StageEnvelope>, status: AnalysisResult['status'] = 'completed'): AnalysisResult {
  return { schema: 'plimsoll-analysis-1', status, stages } as unknown as AnalysisResult;
}

const KERNEL = { coordinator: 'analysis-1', kernel: 'ship-design-native-v1' };

const DESIGN: Record<string, unknown> = {
  schema: 'plimsoll-ship-design-result-1',
  method_version: 'ship-design-native-v1',
  status: 'completed',
  condition_id: 'design-normal',
  basis_condition_id: 'design-normal',
  engine: { hpMax: 60000, speedMax: 30, range: 12000 },
  performance: { stability: 1.35 },
  balance: { selected_mass_t: 71934, estimated_mass_t: 70000, target_displacement_t: 72000, difference_t: -66 },
};

/** A native-only result: the one requested stage is the native design. */
const nativeOnly = (overrides: Partial<StageEnvelope> = {}, data: Record<string, unknown> = DESIGN) =>
  result({ ship_design: { ...stage('completed', true, data, null, KERNEL), ...overrides } });

const panel = (saved: AnalysisResult, language: 'zh-CN' | 'en' = 'en') =>
  inLanguage(<UnitProvider preferences={{}}><ReportReadings result={saved} /></UnitProvider>, language);

const panelText = () => document.querySelector('.report-readings')!.textContent ?? '';
const labels = () => Array.from(document.querySelectorAll('.report-reading-label')).map(node => node.textContent);
const card = (label: string) => screen.getByText(label).closest('.report-reading') as HTMLElement;
const value = (label: string) => card(label).querySelector('.report-reading-value')!.textContent;

describe('a native design report leads with its own frozen result', () => {
  it('prints the saved balance, engine and performance readings with their own units', () => {
    render(panel(nativeOnly()));
    expect(labels()).toEqual([
      'Design selected mass', 'Design estimated mass', 'Design target displacement', 'Design mass difference',
      'Maximum design speed', 'Maximum source power', 'Design range', 'Design stability score',
    ]);
    const text = panelText();
    expect(text).toContain('71,934 t');
    expect(text).toContain('-66 t');
    expect(text).toContain('30 kn');
    // The recovered horsepower is a source reading, never a kW conversion.
    expect(text).toContain('60,000 source hp');
    expect(text).not.toContain('kW');
    expect(text).toContain('12,000 nmi');
    expect(text).toContain('1.35 empirical score');
    // The design basis condition is named, so a native mass is never read as the
    // selected physical loading's mass.
    expect(text).toContain('Stage Ship design · design basis design-normal');
  });

  it('shows no card at all for the physical stages the run never requested', () => {
    render(panel(nativeOnly()));
    expect(document.querySelectorAll('.report-reading')).toHaveLength(8);
    // Every native value was saved, so nothing on the panel is unknown, and the
    // physical GM the run never computed is not offered as one.
    expect(panelText()).not.toContain('Unknown');
    expect(panelText()).not.toContain('Upright geometric GM');
    expect(panelText()).not.toContain('This request did not run the stage');
  });

  it('says the same readings in Chinese, with the design basis named', () => {
    render(panel(nativeOnly(), 'zh-CN'));
    const text = panelText();
    expect(text).toContain('设计已选质量');
    expect(text).toContain('71,934 t');
    expect(text).toContain('阶段 舰船设计 · 设计基准 design-normal');
  });
});

describe('a native design that did not fully finish', () => {
  it('shows the fields a partial balance did reconcile and keeps an unbound mass unknown, never zero', () => {
    const partial: Record<string, unknown> = {
      ...DESIGN, status: 'partial',
      balance: { ...(DESIGN.balance as Record<string, unknown>), selected_mass_t: null },
    };
    render(panel(nativeOnly({ status: 'partial', reason: 'the design ledger has unbound roles' }, partial)));
    const selected = card('Design selected mass');
    expect(selected.className).toContain('report-reading--unknown');
    expect(value('Design selected mass')).toBe('Unknown');
    expect(selected.textContent).not.toContain('0 t');
    expect(selected.querySelector('.report-reading-reason')!.textContent)
      .toBe('balance.selected_mass_t is null in the saved result');
    // The other fields the partial balance did reconcile are still shown.
    expect(value('Design estimated mass')).toBe('70,000 t');
    expect(value('Design target displacement')).toBe('72,000 t');
  });

  it('blocks every native number behind a design stage that did not deliver a result', () => {
    render(panel(nativeOnly({ status: 'failed', reason: 'the ledger self-check failed' })));
    expect(document.querySelectorAll('.report-reading')).toHaveLength(8);
    // The frozen payload still carries every residual number; none of it leaks.
    expect(panelText()).not.toMatch(/[0-9]/);
    const selected = card('Design selected mass');
    expect(selected.className).toContain('report-reading--failed');
    expect(value('Design selected mass')).toBe('Unknown');
    expect(selected.querySelector('.report-reading-reason')!.textContent)
      .toBe('Calculation failed: the ledger self-check failed');
  });

  it('names a design stage that carries no native method result instead of quoting it', () => {
    render(panel(nativeOnly({}, { ...DESIGN, method_version: 'sps-3b3-compat-v1' })));
    expect(panelText()).not.toMatch(/[0-9]/);
    expect(panelText()).toContain('carries no native method result');
  });

  it('refuses a payload whose saved version disagrees with the stage kernel identity', () => {
    render(panel(nativeOnly({ method_versions: { kernel: 'ship-design-native-v2' } })));
    expect(panelText()).not.toMatch(/[0-9]/);
    expect(panelText()).toContain('does not match the version this reading declares');
  });
});

describe('the physical readings a native result still owes', () => {
  it('appends only the readings whose own stage this run requested', () => {
    const mixed = result({
      ship_design: stage('completed', true, DESIGN, null, KERNEL),
      loading: stage('completed', true, { values: { total_mass_t: 27200 } }),
      equilibrium: stage('not_requested', false, { waterline_above_keel_m: 9.92, heel_deg: 0 }),
    });
    render(panel(mixed));
    const cards = Array.from(document.querySelectorAll('.report-reading'));
    expect(cards).toHaveLength(9);
    // The native cards lead; the requested physical reading follows them.
    expect(cards[0].querySelector('.report-reading-label')!.textContent).toBe('Design selected mass');
    expect(cards[8].querySelector('.report-reading-label')!.textContent).toBe('Total mass of the chosen condition');
    expect(value('Total mass of the chosen condition')).toBe('27,200 t');
    // The selected physical loading stays separate from the design basis above.
    expect(panelText()).toContain('design-normal');
    // The stage the run did not request contributes no card and no unknown.
    expect(panelText()).not.toContain('Waterline height above keel');
    expect(panelText()).not.toContain('This request did not run the stage');
  });

  it('summarises a design the run never requested exactly as before', () => {
    const unrequested = result({
      ship_design: stage('not_requested', false, DESIGN),
      loading: stage('completed', true, { values: { total_mass_t: 27200 } }),
    });
    render(panel(unrequested));
    expect(labels()).toEqual([
      'Total mass of the chosen condition', 'Waterline height above keel', 'Heel angle',
      'Upright geometric GM', 'Equilibrium equivalent GM', 'Roll period estimate',
      'Power work point', 'Steady endurance',
    ]);
    expect(panelText()).not.toContain('Design selected mass');
  });

  it('leaves a report with no native result exactly as it was', () => {
    const legacy = result({
      loading: stage('completed', true, { values: { total_mass_t: 27200 } }),
      equilibrium: stage('completed', true, { waterline_above_keel_m: 9.92, heel_deg: 0 }),
      hydrostatics: stage('completed', true, { values: { gm_t_m: 1.85 } }),
    });
    render(panel(legacy));
    expect(document.querySelectorAll('.report-reading')).toHaveLength(8);
    expect(labels()).toEqual([
      'Total mass of the chosen condition', 'Waterline height above keel', 'Heel angle',
      'Upright geometric GM', 'Equilibrium equivalent GM', 'Roll period estimate',
      'Power work point', 'Steady endurance',
    ]);
    expect(panelText()).toContain('1.85 m');
  });
});
