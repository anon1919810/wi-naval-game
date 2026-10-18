import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { DesignFeedback, FrozenDesignSummary } from '../components/DesignFeedback';
import type { Sps3b3Catalogue } from '../components/sps3b3Model';
import type { Sps3b3Field } from '../types';
import { designFeedbackCopy } from '../i18n/designFeedback';
import { inLanguage } from './locale';
import type { AnalysisResult, ProjectDocument, ShipDesignResult, StageEnvelope } from '../types';

/**
 * The draft feedback panel and the frozen summary, read the way a reader meets
 * them: a stated direction, the nine readings with their own units, the changed
 * inputs behind a disclosure, and a recoverable saved read.
 */

afterEach(cleanup);

const en = (key: Parameters<typeof designFeedbackCopy>[1], params?: Record<string, string | number>) =>
  designFeedbackCopy('en', key, params);

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

const project = (parameters: Record<string, unknown> = {}): ProjectDocument => ({
  schema: 'plimsoll-project-1', id: 'p', name: 'P', revision: 1, hull: {}, geometry: null,
  loading_conditions: [{ id: 'normal', label: 'Normal' }],
  weight_groups: [{ id: 'g', label: 'G', items: [] }],
  ship_design: {
    schema: 'plimsoll-ship-design-1', source: null, parameters, editing: {}, notes: null,
    condition_id: 'normal', mass_bindings: {},
  },
} as unknown as ProjectDocument);

const stage = (data: unknown, over: Partial<StageEnvelope> = {}): StageEnvelope => ({
  status: 'completed', requested: true, reason: null, assumptions: [], diagnostics: [],
  method_versions: { kernel: 'ship-design-native-v1' },
  validity: { complete: true, converged: true, model_applicable: true, historical_validated: null },
  data: data as Record<string, unknown>, ...over,
});

const analysis = (data: ShipDesignResult | null, snapshot: ProjectDocument = project()): AnalysisResult => ({
  schema: 'plimsoll-analysis-1', status: 'completed', project_id: 'p', condition_id: 'normal',
  project_fingerprint: 'p', input_fingerprint: 'i', request_fingerprint: 'r', request: {},
  input_snapshot: snapshot, units: {}, method_versions: {}, sources: {}, diagnostics: [],
  validity: { complete: true, converged: true, model_applicable: true, historical_validated: null },
  stages: data ? { ship_design: stage(data) } : {},
} as AnalysisResult);

const beamField = (over: Partial<Sps3b3Field> = {}): Sps3b3Field => ({
  key: 'beam', name: 'beam', source_index: 0, page: 'hull', label: 'Beam', kind: 'number',
  unit: 'ft', unit_resolved: 'ft', unit_choices: null, choices: null, scale_ref: null,
  allows_unselected: false, min_value: null, ...over,
} as unknown as Sps3b3Field);

const catalogue = (...fields: Sps3b3Field[]): Sps3b3Catalogue => ({
  entries: fields,
  byName: Object.fromEntries(fields.map(entry => [entry.name, entry])),
  pageOrder: ['hull'],
  pageLabels: { hull: 'Hull' },
  pageFields: { hull: fields.map(entry => entry.name) },
  controls: {}, fieldCount: fields.length, scaleNames: new Set(),
} as unknown as Sps3b3Catalogue);

describe('the draft feedback panel', () => {
  it('states its direction and prints both sides with the draft − saved difference', () => {
    const saved = native();
    const draft = structuredClone(saved);
    draft.balance!.selected_mass_t = 1120;
    render(<DesignFeedback
      before={{ result: saved, project: project(), state: 'ready' }}
      after={{ result: draft, project: project(), state: 'ready' }} />);

    expect(screen.getByText(en('feedback.direction.draft'))).toBeVisible();
    const table = screen.getByRole('table', { name: en('feedback.direction.draft') });
    expect(within(table).getByRole('columnheader', { name: en('feedback.reading.before') })).toBeVisible();
    expect(within(table).getByRole('columnheader', { name: en('feedback.reading.after') })).toBeVisible();

    const row = within(table).getByRole('rowheader', { name: /Selected mass/ }).closest('tr')!;
    expect(within(row).getByText('1,000 t')).toBeVisible();
    expect(within(row).getByText('1,120 t')).toBeVisible();
    expect(within(row).getByText('+120 t')).toBeVisible();
  });

  it('withholds the readings while an edit is pending but keeps the declared changes', () => {
    render(<DesignFeedback
      before={{ result: native(), project: project({ beam: 20 }), state: 'ready' }}
      after={{ result: native(), project: project({ beam: 22 }), state: 'pending' }}
      catalogue={catalogue(beamField())} />);
    expect(screen.getByText(en('feedback.current.pending'))).toBeVisible();
    expect(screen.queryByRole('table')).toBeNull();
    expect(screen.getByText(en('feedback.inputs.count', { count: 1 }))).toBeVisible();
    expect(screen.getByText('Beam')).toBeVisible();
    expect(screen.getByText(/20 ft/)).toBeVisible();
  });

  it('prints each side in its own resolved unit and names the scale change', () => {
    const scaled = beamField({ unit: 'ft', unit_choices: ['ft', 'm'], scale_ref: 'units', unit_resolved: null });
    render(<DesignFeedback
      before={{ result: native(), project: project({ beam: 20, units: 0 }), state: 'ready' }}
      after={{ result: native(), project: project({ beam: 6.1, units: 1 }), state: 'ready' }}
      catalogue={catalogue(scaled)} />);
    expect(screen.getByText(/20 ft/)).toBeVisible();
    expect(screen.getByText(/6\.1 m/)).toBeVisible();
    expect(screen.getByText(en('feedback.inputs.unitChanged', { before: 'ft', after: 'm' }))).toBeVisible();
  });

  it('offers one saved-read retry when the saved revision could not be read', () => {
    const retry = vi.fn();
    render(<DesignFeedback
      before={{ result: null, project: project(), state: 'failed' }}
      after={{ result: native(), project: project(), state: 'ready' }} onRetry={retry} />);
    expect(screen.getByText(en('feedback.baseline.failed'))).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: en('feedback.baseline.retry') }));
    expect(retry).toHaveBeenCalledTimes(1);
  });

  it('links a changed input to the chapter its source page names', () => {
    const open = vi.fn();
    render(<DesignFeedback
      before={{ result: native(), project: project({ beam: 20 }), state: 'ready' }}
      after={{ result: native(), project: project({ beam: 22 }), state: 'ready' }}
      catalogue={catalogue(beamField())} onOpenChapter={open} />);
    fireEvent.click(screen.getByRole('button', { name: /^Open / }));
    expect(open).toHaveBeenCalledWith('hull');
  });

  it('localizes the ledger policy and prints role masses in the active mass unit', () => {
    const ledger = (roles: Record<string, unknown>) => native({ ledger: { schema: 'plimsoll-ship-design-1', roles } as ShipDesignResult['ledger'] });
    render(<DesignFeedback
      before={{ result: ledger({ machinery: { selected_mass_t: 100, estimate_t: 95, mode: 'estimated' } }), project: project(), state: 'ready' }}
      after={{ result: ledger({ machinery: { selected_mass_t: 110, estimate_t: 95, mode: 'declared' } }), project: project(), state: 'ready' }} />);
    expect(screen.getByText(`${en('feedback.policy.estimated')} → ${en('feedback.policy.declared')}`)).toBeVisible();
    expect(screen.getByText(/100 t/)).toBeVisible();
    expect(screen.getByText(/\+10 t/)).toBeVisible();
  });

  it('prints the Chinese direction and reading labels under a Chinese reader', () => {
    render(inLanguage(<DesignFeedback
      before={{ result: native(), project: project(), state: 'ready' }}
      after={{ result: native(), project: project(), state: 'ready' }} />, 'zh-CN'));
    expect(screen.getByText(designFeedbackCopy('zh-CN', 'feedback.direction.draft'))).toBeVisible();
    expect(screen.getByText(designFeedbackCopy('zh-CN', 'feedback.reading.selectedMass'))).toBeVisible();
  });
});

describe('the frozen native summary', () => {
  it('labels the comparison − current direction and prints nothing without a native stage', () => {
    render(<FrozenDesignSummary
      current={analysis(native(), project({ beam: 20 }))}
      comparison={analysis(native({ balance: { selected_mass_t: 1050, estimated_mass_t: 990, target_displacement_t: 1060, difference_t: -4 } }), project({ beam: 24 }))}
      currentLabel="Current · revision 1" comparisonLabel="Comparison · revision 2"
      catalogue={catalogue(beamField())} />);
    expect(screen.getByText(en('feedback.direction.frozen'))).toBeVisible();
    const table = screen.getByRole('table', { name: en('feedback.direction.frozen') });
    expect(within(table).getByRole('columnheader', { name: 'Current · revision 1' })).toBeVisible();
    const row = within(table).getByRole('rowheader', { name: /Selected mass/ }).closest('tr')!;
    expect(within(row).getByText('+50 t')).toBeVisible();
    // The frozen summary gets the same catalogue-driven names and per-side units
    // as the workbench panel; it prints no raw register key.
    const changedBeam = screen.getByText('Beam', { selector: '.design-feedback-input-name' }).closest('li')!;
    expect(within(changedBeam).getByText(/20 ft/)).toBeVisible();

    cleanup();
    const empty = render(<FrozenDesignSummary current={analysis(null)} comparison={analysis(null)}
      currentLabel="Current" comparisonLabel="Comparison" />);
    expect(empty.container).toBeEmptyDOMElement();
  });
});
