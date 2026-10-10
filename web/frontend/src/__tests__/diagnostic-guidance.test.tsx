import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { Report } from '../pages/Report';
import { StageStatus } from '../components/StageStatus';
import {
  diagnosticHref, hullGuidanceId, ledgerGuidanceId, parseDiagnosticPath, PROJECT_JSON,
  readDiagnosticTail, readDiagnosticTarget, REQUEST_DAMAGE, REQUEST_PERFORMANCE, resolveDiagnosticPath,
  type DiagnosticSource,
} from '../components/diagnosticGuidance';
import type { AnalysisResult, ProjectDocument, StageEnvelope } from '../types';

/**
 * Following a real saved diagnostic to its editable location.
 *
 * The resolver is exercised against the shape the coordinator actually writes —
 * `$.weight_groups[0].items[0].mass_t` for a ledger item whose mass was unknown
 * — and against the paths it must refuse to follow. The report is then rendered
 * with those findings to prove the original message, code, source path and
 * severity all survive next to the new navigation.
 */

const snapshot: ProjectDocument = {
  schema: 'plimsoll-project-1', id: 'p1', name: '解析方箱', revision: 1,
  hull: { loa_m: 90, lwl_m: null }, geometry: null,
  weight_groups: [{ id: 'lightship', label: '空船', items: [
    { id: 'steamer-structure', mass_t: null, x_m: 35, source: 'yard plan' },
    { id: 'boilers', mass_t: 0, x_m: -2, source: null },
  ] }],
  loading_conditions: [{ id: 'loaded', label: '满载' }],
};

function source(live: ProjectDocument | null = snapshot): DiagnosticSource {
  return { snapshot, live };
}

function envelope(status: StageEnvelope['status'], requested: boolean, data: StageEnvelope['data'] = null,
  reason: string | null = null, diagnostics: StageEnvelope['diagnostics'] = []): StageEnvelope {
  return {
    status, requested, reason,
    validity: { complete: status === 'completed', converged: null, model_applicable: null, historical_validated: null },
    method_versions: {}, assumptions: [], diagnostics, data,
  };
}

describe('resolving a saved diagnostic path', () => {
  it('reaches the ledger control the source run named, even after the ledger was reordered', () => {
    const location = resolveDiagnosticPath('$.weight_groups[0].items[0].mass_t', source())!;
    expect(location.kind).toBe('control');
    expect(location.chapter).toBe('weights');
    // The target is named by the ids the run saw, never by a live index.
    expect(location.target).toBe(ledgerGuidanceId('lightship', 'steamer-structure', 'mass_t'));
    expect(location.path).toBe('$.weight_groups[0].items[0].mass_t');
    expect(location.note).toContain('保存修订后重新运行');

    // The same ledger, reordered and with a group inserted in front: index 0 is
    // now a different group entirely, and the reader must still be sent to the
    // item the diagnostic is about.
    const edited: ProjectDocument = {
      ...snapshot,
      weight_groups: [
        { id: 'stores', label: '储物品', items: [{ id: 'coal', mass_t: 900, x_m: 10 }] },
        { id: 'lightship', label: '空船', items: [
          { id: 'deck-fittings', mass_t: 40, x_m: 20 },
          { id: 'steamer-structure', mass_t: null, x_m: 35 },
        ] },
      ],
    };
    const remapped = resolveDiagnosticPath('$.weight_groups[0].items[0].mass_t', { snapshot, live: edited })!;
    expect(remapped.target).toBe(ledgerGuidanceId('lightship', 'steamer-structure', 'mass_t'));
  });

  it('refuses to focus a ledger item the current project no longer contains', () => {
    const removed: ProjectDocument = { ...snapshot, weight_groups: [
      { id: 'lightship', label: '空船', items: [{ id: 'deck-fittings', mass_t: 40, x_m: 20 }] },
    ] };
    const location = resolveDiagnosticPath('$.weight_groups[0].items[0].mass_t', { snapshot, live: removed })!;
    // No field, no chapter, and a sentence that says what actually happened.
    expect(location.kind).toBe('evidence');
    expect(location.target).toBeNull();
    expect(location.chapter).toBeNull();
    expect(location.note).toContain('steamer-structure');
    expect(location.path).toBe('$.weight_groups[0].items[0].mass_t');
  });

  it('treats an unknown mass and an exact zero as the same real, focusable field', () => {
    const unknown = resolveDiagnosticPath('$.weight_groups[0].items[0].mass_t', source())!;
    const zero = resolveDiagnosticPath('$.weight_groups[0].items[1].mass_t', source())!;
    expect(unknown.kind).toBe('control');
    expect(zero.kind).toBe('control');
    expect(zero.target).toBe(ledgerGuidanceId('lightship', 'boilers', 'mass_t'));
    // Neither a stored zero nor an unknown mass turns into a fabricated target.
    expect(zero.label).toContain('boilers');
  });

  it('reaches each ledger fact by its own control, and sends other ledger fields to the document', () => {
    expect(resolveDiagnosticPath('$.weight_groups[0].items[0].x_m', source())!.target)
      .toBe(ledgerGuidanceId('lightship', 'steamer-structure', 'x_m'));
    expect(resolveDiagnosticPath('$.weight_groups[0].items[0].source', source())!.target)
      .toBe(ledgerGuidanceId('lightship', 'steamer-structure', 'source'));
    // y_m has no row control: it is a project document field, and the reader is
    // told where the item lives *now* rather than being sent to a stale index.
    const transverse = resolveDiagnosticPath('$.weight_groups[0].items[0].y_m', source())!;
    expect(transverse.kind).toBe('section');
    expect(transverse.chapter).toBe('json');
    expect(transverse.note).toContain('$.weight_groups[0].items[0].y_m');
    expect(transverse.note).toContain('steamer-structure');
    expect(transverse.note).toContain('$.weight_groups[0].items[0]');
  });

  it('gives two different ledger rows two different identities', () => {
    // A separator-joined id would collide here: ('a-b','c') and ('a','b-c').
    expect(ledgerGuidanceId('a-b', 'c', 'mass_t')).not.toBe(ledgerGuidanceId('a', 'b-c', 'mass_t'));
    expect(ledgerGuidanceId('a', 'b', 'mass_t')).not.toBe(ledgerGuidanceId('a', 'b', 'x_m'));
    const first: ProjectDocument = { ...snapshot, weight_groups: [
      { id: 'a-b', label: '组合', items: [{ id: 'c', mass_t: 1, x_m: 1 }] },
    ] };
    const second: ProjectDocument = { ...snapshot, weight_groups: [
      { id: 'a', label: '甲', items: [{ id: 'b-c', mass_t: 2, x_m: 2 }] },
    ] };
    const one = resolveDiagnosticPath('$.weight_groups[0].items[0].mass_t', { snapshot: first, live: first })!;
    const two = resolveDiagnosticPath('$.weight_groups[0].items[0].mass_t', { snapshot: second, live: second })!;
    expect(one.target).toBe(ledgerGuidanceId('a-b', 'c', 'mass_t'));
    expect(two.target).toBe(ledgerGuidanceId('a', 'b-c', 'mass_t'));
    expect(one.target).not.toBe(two.target);
  });

  it('only treats the exact scalar path as a control, never a longer one', () => {
    const longer = resolveDiagnosticPath('$.weight_groups[0].items[0].mass_t.value', source())!;
    expect(longer.kind).toBe('section');
    expect(longer.chapter).toBe('json');
    expect(longer.target).toBe(PROJECT_JSON);
    expect(longer.note).not.toContain('在“重量与载荷”中编辑');
  });

  it('refuses a removed item even when the path has no editor of its own', () => {
    const removed: ProjectDocument = { ...snapshot, weight_groups: [
      { id: 'lightship', label: '空船', items: [{ id: 'deck-fittings', mass_t: 40, x_m: 20 }] },
    ] };
    for (const path of ['$.weight_groups[0].items[0].mass_t', '$.weight_groups[0].items[0].y_m',
      '$.weight_groups[0].items[0]', '$.loading_conditions[0].overrides["boilers"].mass_t']) {
      const location = resolveDiagnosticPath(path, { snapshot, live: removed })!;
      if (path.includes('loading_conditions')) continue;
      expect(location.kind, path).toBe('evidence');
      expect(location.chapter, path).toBeNull();
      expect(location.note, path).toContain('已不在当前项目');
    }
  });

  it('names a condition by its id and its current index, or refuses when it is gone', () => {
    const live: ProjectDocument = { ...snapshot, loading_conditions: [
      { id: 'deep', label: '深载' }, { id: 'loaded', label: '满载' },
    ] as ProjectDocument['loading_conditions'] };
    const moved = resolveDiagnosticPath('$.loading_conditions[0].overrides["boilers"].mass_t', { snapshot, live })!;
    expect(moved.kind).toBe('section');
    expect(moved.chapter).toBe('json');
    expect(moved.note).toContain('loaded');
    expect(moved.note).toContain('$.loading_conditions[1]');
    // The saved index is never repeated as an instruction to edit.
    expect(moved.note).toContain('$.loading_conditions[0].overrides');

    const gone = resolveDiagnosticPath('$.loading_conditions[0].overrides["x"].mass_t',
      { snapshot, live: { ...snapshot, loading_conditions: [{ id: 'deep', label: '深载' }] as ProjectDocument['loading_conditions'] } })!;
    expect(gone.kind).toBe('evidence');
    expect(gone.note).toContain('loaded');
    expect(gone.note).toContain('已不在当前项目');
  });

  it('sends empty and aggregate ledger paths to the document, not to a row form', () => {
    for (const path of ['$.weight_groups', '$.weight_groups[0]', '$.weight_groups[0].items']) {
      const location = resolveDiagnosticPath(path, source())!;
      expect(location.kind, path).toBe('section');
      expect(location.chapter, path).toBe('json');
      expect(location.target, path).toBe(PROJECT_JSON);
      expect(location.note, path).toContain(path);
    }
    // A whole row, which does exist in the ledger form, still points there.
    const row = resolveDiagnosticPath('$.weight_groups[0].items[1]', source())!;
    expect(row.chapter).toBe('weights');
    expect(row.note).toContain('$.weight_groups[0].items[1]');
  });

  it('reaches a hull scalar control, and sends a declared source to the document', () => {
    const loa = resolveDiagnosticPath('$.hull.loa_m', source())!;
    expect(loa.kind).toBe('control');
    expect(loa.chapter).toBe('hull');
    expect(loa.target).toBe(hullGuidanceId('loa_m'));
    expect(loa.label).toBe('船长');
    // One control, one spelling: the legacy names are not second fields.
    expect(resolveDiagnosticPath('$.hull.length_m', source())!.target).toBe(hullGuidanceId('loa_m'));
    expect(resolveDiagnosticPath('$.hull.draft_m', source())!.target).toBe(hullGuidanceId('draught_normal_m'));
    // A declared source has no editor of its own in the workspace, and typing
    // the dimension would not repair missing provenance.
    const provenance = resolveDiagnosticPath('$.hull.sources.lwl_m', source())!;
    expect(provenance.kind).toBe('section');
    expect(provenance.chapter).toBe('json');
    expect(provenance.note).toContain('$.hull.sources.lwl_m');
    expect(resolveDiagnosticPath('$.hull.warnings[0]', source())!.kind).toBe('evidence');
  });

  it('sends request options to the request area that owns them, never to the document', () => {
    const resistance = resolveDiagnosticPath('$.options.resistance.speeds_kn', source())!;
    expect(resistance.kind).toBe('section');
    expect(resistance.chapter).toBe('performance');
    expect(resistance.target).toBe(REQUEST_PERFORMANCE);
    expect(resistance.note).toContain('不会自动重建旧请求');

    const flooding = resolveDiagnosticPath('$.options.flooding.options.max_steps', source())!;
    expect(flooding.chapter).toBe('damage');
    expect(flooding.target).toBe(REQUEST_DAMAGE);
    // The shared environment density belongs to the flooding request.
    expect(resolveDiagnosticPath('$.options.equilibrium.rho_t_m3', source())!.chapter).toBe('damage');
  });

  it('sends a recognized project field to the document with its original path', () => {
    const location = resolveDiagnosticPath('$.compartments[0].x_m', source())!;
    expect(location.kind).toBe('section');
    expect(location.chapter).toBe('json');
    expect(location.target).toBe(PROJECT_JSON);
    expect(location.note).toContain('$.compartments[0].x_m');
    expect(resolveDiagnosticPath('$.loading_conditions[0].overrides["boilers"].mass_t', source())!.chapter).toBe('json');
  });

  it('leaves result, diagnostics and unrecognised paths as plain evidence', () => {
    for (const path of ['$.stages.loading.data', '$.diagnostics[3]', '$.result.stages.gz',
      '$.validity.complete', '$.method_versions.coordinator', '$.totally.unknown', '$.stages.loading.diagnostics[0]']) {
      const location = resolveDiagnosticPath(path, source())!;
      expect(location.kind, path).toBe('evidence');
      expect(location.chapter, path).toBeNull();
      expect(location.target, path).toBeNull();
      expect(location.path).toBe(path);
    }
    // An unreadable path is still returned as evidence with its own wording.
    const malformed = resolveDiagnosticPath('weight_groups[0]', source())!;
    expect(malformed.kind).toBe('evidence');
    expect(malformed.note).toContain('无法解析');
    expect(parseDiagnosticPath('$.weight_groups[0].items')).toEqual([{ key: 'weight_groups' }, { index: 0 }, { key: 'items' }]);
  });

  it('ignores a snapshot path that never named a stable ledger item', () => {
    const anonymous: ProjectDocument = { ...snapshot, weight_groups: [{ id: 'lightship', label: '空船', items: [{ mass_t: 5 }] }] };
    const location = resolveDiagnosticPath('$.weight_groups[0].items[0].mass_t', { snapshot: anonymous, live: anonymous })!;
    expect(location.kind).toBe('evidence');
    expect(location.note).toContain('id');
  });
});

describe('the report-to-project address', () => {
  it('round-trips its own link, explains a malformed tail, and refuses everything else', () => {
    const href = diagnosticHref('p 1', 'run-a', '$.weight_groups[0].items[0].mass_t');
    expect(readDiagnosticTarget(href, 'p 1')).toEqual({ runId: 'run-a', path: '$.weight_groups[0].items[0].mass_t' });
    expect(readDiagnosticTail(href, 'p 1')).toEqual({ kind: 'target', runId: 'run-a', path: '$.weight_groups[0].items[0].mass_t' });
    // Another project, another route and a plain project address are none of
    // them a diagnostic, and none of them is explained as one.
    expect(readDiagnosticTail(href, 'p2').kind).toBe('malformed');
    expect(readDiagnosticTail('#/reports/run-a/diagnostics/run-a/%24.hull.loa_m', 'p 1').kind).toBe('none');
    expect(readDiagnosticTail('#/projects/p%201', 'p 1').kind).toBe('none');
    expect(readDiagnosticTarget('#/reports/run-a/diagnostics/run-a/%24.hull.loa_m', 'p 1')).toBeNull();
    // A diagnostic tail that cannot be trusted says why, and never resolves.
    expect(readDiagnosticTail('#/projects/p%201/diagnostics/run-a', 'p 1').kind).toBe('malformed');
    expect(readDiagnosticTail('#/projects/p%201/diagnostics/run-a/%E0%A4%A', 'p 1').kind).toBe('malformed');
    expect(readDiagnosticTail('#/projects/p%201/diagnostics/run-a/hull.loa_m', 'p 1').kind).toBe('malformed');
    expect(readDiagnosticTail('#/projects/p%201/diagnostics//%24.hull.loa_m', 'p 1').kind).toBe('malformed');
  });
});

function reportWith(diagnostics: AnalysisResult['diagnostics'], stageDiagnostics: StageEnvelope['diagnostics'] = []): AnalysisResult {
  return {
    schema: 'plimsoll-analysis-1', status: 'partial', project_id: 'p1', condition_id: 'loaded',
    project_fingerprint: 'pf', input_fingerprint: 'if', request_fingerprint: 'rf',
    request: { stages: ['loading'], options: { stages: ['loading'] } },
    input_snapshot: snapshot, units: {}, method_versions: {}, sources: {},
    diagnostics,
    validity: { complete: false, converged: null, model_applicable: null, historical_validated: null },
    stages: { loading: envelope('failed', true, null, 'effective mass for item is unknown', stageDiagnostics) },
  } as unknown as AnalysisResult;
}

const MASS_UNKNOWN = {
  code: 'loading.mass_unknown', severity: 'error', blocking: true, stage: 'loading',
  path: '$.weight_groups[0].items[0].mass_t', source_path: '$.weight_groups[0].items[0].mass_t',
  message: 'effective mass for item steamer-structure is unknown',
};

describe('diagnostics a report can act on', () => {
  afterEach(cleanup);

  it('links a serious finding to its ledger control without losing any evidence', () => {
    render(<Report result={reportWith([MASS_UNKNOWN], [MASS_UNKNOWN])} runId="run-a" />);
    const open = document.querySelector('.stage-diagnostics-open') as HTMLElement;
    // Every original part of the finding is still printed.
    expect(within(open).getByText('effective mass for item steamer-structure is unknown')).toBeVisible();
    expect(within(open).getByText('loading.mass_unknown')).toBeVisible();
    expect(within(open).getAllByText('$.weight_groups[0].items[0].mass_t').length).toBeGreaterThan(0);
    // And the reader is offered the field itself, by a real address.
    const link = within(open).getByRole('link');
    expect(link).toHaveAttribute('href', diagnosticHref('p1', 'run-a', '$.weight_groups[0].items[0].mass_t'));
    expect(link.textContent).toContain('steamer-structure');
    expect(link.textContent).toContain('质量');
  });

  it('links root, ordinary and repeated findings, and leaves result paths as evidence', () => {
    const result = reportWith([
      MASS_UNKNOWN,
      { code: 'coordinator.model', severity: 'warning', stage: 'loading', path: '$.stages.loading', message: '模型越界' },
      { code: 'l0.assumption', severity: 'info', path: '$.hull.beam_m', message: '型宽来自示意图' },
    ], [
      MASS_UNKNOWN,
      { code: 'loading.note', severity: 'info', path: '$.stages.loading.data', message: '账本按分组求和' },
      { code: 'loading.repeat', severity: 'warning', path: '$.weight_groups[0].items[1].x_m', message: 'effective mass for item steamer-structure is unknown' },
    ]);
    render(<Report result={result} runId="run-a" />);
    const hrefs = screen.getAllByRole('link').map(link => link.getAttribute('href')!);
    // The root, the ordinary and the repeated copy each reach the same field.
    expect(hrefs).toContain(diagnosticHref('p1', 'run-a', '$.weight_groups[0].items[0].mass_t'));
    expect(hrefs).toContain(diagnosticHref('p1', 'run-a', '$.hull.beam_m'));
    expect(hrefs).toContain(diagnosticHref('p1', 'run-a', '$.weight_groups[0].items[1].x_m'));
    // A generated result path gets no link at all, but keeps its evidence.
    expect(hrefs).not.toContain(diagnosticHref('p1', 'run-a', '$.stages.loading'));
    // The ordinary root finding is folded, so its evidence is asserted on the
    // disclosure itself rather than on what a reader would have to open.
    const fold = document.querySelector('.report-root-diagnostics-fold') as HTMLElement;
    expect(fold.textContent).toContain('模型越界');
    expect(fold.textContent).toContain('$.stages.loading');
  });

  it('renders a stage with no project or run context exactly as before', () => {
    const stage = envelope('failed', true, null, '资料不足', [MASS_UNKNOWN]);
    const { container } = render(<StageStatus name="loading" stage={stage} />);
    expect(container.querySelectorAll('a')).toHaveLength(0);
    expect(container.querySelector('.stage-card--failed')).not.toBeNull();
    expect(screen.getByText('effective mass for item steamer-structure is unknown')).toBeVisible();
    expect(screen.getByText('$.weight_groups[0].items[0].mass_t')).toBeVisible();
  });

  it('keeps the diagnostic controls off paper while the evidence stays on it', () => {
    render(<Report result={reportWith([MASS_UNKNOWN], [MASS_UNKNOWN])} runId="run-a" />);
    const link = screen.getAllByRole('link').find(node => node.getAttribute('href')!.includes('diagnostics'))!;
    expect(link.className).toContain('no-print');
    // The path it points at is still printed, next to the message.
    expect(link.closest('p')!.textContent).toContain('$.weight_groups[0].items[0].mass_t');
  });
});