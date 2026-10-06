import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { Report } from '../pages/Report';
import { estimateLabel, provenanceGroups } from '../components/sourceAudit';
import type { AnalysisResult, StageEnvelope } from '../types';

/**
 * Printing this report: what has to be open on paper, what must never open, and
 * what the screen looks like afterwards.
 *
 * The lifecycle is driven the way a browser drives it, through `beforeprint` and
 * `afterprint`, because that is the same path the report's own print button, the
 * browser's print command and Ctrl+P all take.
 */
function envelope(status: StageEnvelope['status'], requested: boolean, data: StageEnvelope['data'] = null,
  reason: string | null = null, diagnostics: StageEnvelope['diagnostics'] = []): StageEnvelope {
  return {
    status, requested, reason,
    validity: { complete: status === 'completed', converged: status === 'completed' ? true : null, model_applicable: status === 'completed' ? true : null, historical_validated: null },
    method_versions: { kernel: 'saved-kernel-1' }, assumptions: ['固定工作点假设', '线性插值假设'],
    diagnostics, data,
  };
}

const DRAWING = { id: 'drawing', page: '第四十二页' };

function printableResult(): AnalysisResult {
  return {
    schema: 'plimsoll-analysis-1', status: 'partial', project_id: 'p1', condition_id: 'normal',
    project_fingerprint: 'project-fingerprint-0123456789', input_fingerprint: 'input-fingerprint-0123456789',
    request_fingerprint: 'request-fingerprint-0123456789', request: { stages: ['loading', 'geometry', 'deck'] },
    input_snapshot: {
      schema: 'plimsoll-project-1', id: 'p1', name: 'HMS Fixture', revision: 3, hull: { loa_m: 213.4 },
      geometry: { frame: 'station-plan', source: 'yard drawing 1913' },
      // The same declaration twice under different key order, and once with a
      // different estimate state: one declaration, three statements.
      weight_groups: [
        { id: 'armour', label: '装甲', source: { page: '第四十二页', id: 'drawing' }, estimate: true, items: [] },
        { id: 'guns', label: '火炮', source: { id: 'drawing', page: '第四十二页' }, estimate: false, items: [] },
        { id: 'stores', label: '储物品', source: DRAWING, items: [] },
      ],
      loading_conditions: [{ id: 'normal', label: '正常载荷', source: '   ' }],
      // Deep nesting and arrays are searched, and an array index is a real path.
      compartments: [{ id: 'room', label: '舱室',
        iterations: [{ time_s: 0, cells: [{ source: 'tank survey', estimate: null }] }],
        notes: { nested: { deeper: [{ source: 'dockyard memo' }] } } }],
      // An input scenario this run never used still counts as a declaration.
      scenarios: [{ id: 'deep', source: 'deep condition study' }],
    },
    units: { length: 'm', mass: 't' },
    method_versions: { coordinator: 'selected-loading-analysis-1', geometry: 'frame-1' },
    sources: {
      limitations: ['未认证的史实', '几何来自示意图'],
      validation: { reviewed_by: null, source: 'review note 1913' },
    },
    diagnostics: [
      { code: 'coordinator.note', severity: 'info', message: '已记录请求与快照指纹' },
      { code: 'coordinator.limit', severity: 'warning', blocking: true, path: '$.stages.geometry', message: '几何为示意图' },
    ],
    validity: { complete: false, converged: true, model_applicable: true, historical_validated: null },
    stages: {
      loading: envelope('completed', true, { values: { total_mass_t: 27200, source: 'weight ledger', estimate: false } },
        null, [{ code: 'loading.note', severity: 'info', path: '$.stages.loading.data.values', message: '账本按分组求和' },
          { code: 'loading.short', severity: 'error', path: '$.stages.loading.data', message: '一项重量没有来源' }]),
      geometry: envelope('completed', true, { source: DRAWING, estimate: true,
        mesh: { cells: [{ source: 'tank survey' }] }, notes: { nested: { deeper: [{ source: 'dockyard memo' }] } } }),
      deck: envelope('not_requested', false, { source: 'unrequested deck survey' }, '未请求'),
    },
  } as unknown as AnalysisResult;
}

const detailsBySummary = (label: string | RegExp) => screen.getAllByText(label)[0].closest('details') as HTMLDetailsElement;
const appendix = () => document.querySelector('.report-provenance') as HTMLDetailsElement;
const rawData = () => document.querySelector('.stage-raw-data') as HTMLDetailsElement;
const print = () => act(() => { window.dispatchEvent(new Event('beforeprint')); });
const done = () => act(() => { window.dispatchEvent(new Event('afterprint')); });

beforeEach(() => {
  vi.spyOn(window, 'addEventListener');
  vi.spyOn(window, 'removeEventListener');
});

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('preparing a report for paper', () => {
  it('opens the folded evidence and never the raw stage payload', () => {
    render(<Report result={printableResult()} runId="run-9" />);

    // The screen starts folded, and the provenance walk has not been done yet:
    // the summary is there to ask for it, its content is not.
    const raw = rawData();
    expect(raw.hasAttribute('open')).toBe(false);
    expect(raw.classList.contains('no-print')).toBe(true);
    expect(raw.querySelector('pre')).toBeNull();
    expect(within(appendix()).getByText(/来源声明附录/)).toBeVisible();
    expect(document.querySelectorAll('.report-audit-group')).toHaveLength(0);
    for (const node of document.querySelectorAll('details')) expect(node.hasAttribute('open')).toBe(false);

    print();

    // Ordinary diagnostics, assumptions, methods, fingerprints and the audit
    // appendix are all on the page now.
    for (const label of ['诊断与缺项 · 1 条', '整体诊断与缺项 · 1 条', '假设与适用性',
      '完整指纹与请求身份', '保存的来源声明与限制', '方法版本']) {
      expect(detailsBySummary(label).hasAttribute('open')).toBe(true);
    }
    expect(appendix().hasAttribute('open')).toBe(true);
    expect(appendix().textContent).toMatch(/来源声明附录 · \d+ 组 \/ \d+ 处声明/);
    for (const node of document.querySelectorAll('.report-audit-group')) expect(node.hasAttribute('open')).toBe(true);

    // The raw payload is still closed and still unmounted: a report may carry
    // megabytes of saved arrays, and paper is not where they belong. The same
    // text is readable as an audit declaration, which is a different thing.
    expect(raw.hasAttribute('open')).toBe(false);
    expect(raw.querySelector('pre')).toBeNull();
    expect(appendix().textContent).toContain('weight ledger');

    done();
    expect(document.querySelectorAll('details[open]')).toHaveLength(0);
  });

  it('mounts the provenance of the saved payload with every path and estimate state', () => {
    render(<Report result={printableResult()} runId="run-9" />);
    print();

    const box = appendix();
    const paths = Array.from(box.querySelectorAll('.report-audit-paths code')).map(node => node.textContent ?? '');
    // Same declaration, three statements: true, false and unsaid are not merged,
    // and the unknown one is not turned into a false.
    expect(box.textContent).toContain(estimateLabel(true));
    expect(box.textContent).toContain(estimateLabel(false));
    expect(box.textContent).toContain(estimateLabel(null));

    // The reordered pair is one declaration that lists both of its paths.
    const drawingGroup = Array.from(box.querySelectorAll('.report-audit-group'))
      .find(node => node.querySelector('.report-audit-estimate')?.textContent === estimateLabel(true)
        && node.querySelector('.report-audit-declaration')?.textContent?.includes('第四十二页'));
    expect(drawingGroup).toBeDefined();
    expect(Array.from(drawingGroup!.querySelectorAll('.report-audit-paths code')).map(node => node.textContent))
      .toEqual(['result.input_snapshot.weight_groups[0].source', 'result.stages.geometry.data.source']);

    // Deep arrays and objects are searched, and their paths are real paths.
    expect(paths).toContain('result.input_snapshot.compartments[0].iterations[0].cells[0].source');
    expect(paths).toContain('result.input_snapshot.compartments[0].notes.nested.deeper[0].source');
    expect(paths).toContain('result.sources.validation.source');
    expect(paths).toContain('result.input_snapshot.scenarios[0].source');
    // A stage this run never requested contributes no stage path.
    expect(paths.some(path => path.startsWith('result.stages.deck'))).toBe(false);
    // The saved sources keep their own full context, separately.
    expect(within(appendix().closest('.report-audit') as HTMLElement).getByText(/未认证的史实/)).toBeVisible();
  });

  it('lets the reader open the appendix, and keeps it open through a print', () => {
    render(<Report result={printableResult()} runId="run-9" />);
    expect(document.querySelectorAll('.report-audit-group')).toHaveLength(0);

    act(() => { appendix().open = true; });
    fireEvent(appendix(), new Event('toggle'));
    expect(document.querySelectorAll('.report-audit-group').length).toBeGreaterThan(0);
    expect(appendix().textContent).toContain('result.sources.validation.source');

    print();
    done();
    // The reader opened it, so the screen still has it open afterwards.
    expect(appendix().hasAttribute('open')).toBe(true);
  });

  it('puts back exactly the screen states the reader left, and prepares twice', () => {
    render(<Report result={printableResult()} runId="run-9" />);
    // The reader had opened one of them, and had a stage raw payload open too.
    const readerOpened = detailsBySummary('假设与适用性');
    const raw = rawData();
    act(() => {
      readerOpened.open = true;
      raw.open = true;
    });
    fireEvent(raw, new Event('toggle'));

    print();
    expect(raw.hasAttribute('open')).toBe(true);
    // Preparing again must not record the state the first preparation made.
    print();
    done();

    expect(readerOpened.hasAttribute('open')).toBe(true);
    expect(detailsBySummary('诊断与缺项 · 1 条').hasAttribute('open')).toBe(false);
    expect(detailsBySummary('方法版本').hasAttribute('open')).toBe(false);
    expect(appendix().hasAttribute('open')).toBe(false);
    // A raw payload the reader opened stays open, and a queued toggle after the
    // restore must not close or reopen it behind their back.
    expect(raw.hasAttribute('open')).toBe(true);
    expect(raw.querySelector('pre')).not.toBeNull();
    act(() => { fireEvent(raw, new Event('toggle')); });
    expect(raw.hasAttribute('open')).toBe(true);

    // A second print cycle restores the same screen again.
    print();
    done();
    expect(readerOpened.hasAttribute('open')).toBe(true);
    expect(detailsBySummary('完整指纹与请求身份').hasAttribute('open')).toBe(false);
  });

  it('stops listening once the report is gone', () => {
    const { unmount } = render(<Report result={printableResult()} runId="run-9" />);
    expect(vi.mocked(window.addEventListener).mock.calls.some(call => call[0] === 'beforeprint')).toBe(true);
    unmount();
    const removed = vi.mocked(window.removeEventListener).mock.calls.map(call => call[0]);
    expect(removed).toContain('beforeprint');
    expect(removed).toContain('afterprint');
    // Nothing is left to prepare, and saying so is not an error.
    expect(() => print()).not.toThrow();
  });

  it('prints the report it was given, and changes neither the units nor the snapshot', () => {
    const result = printableResult();
    const snapshot = result.input_snapshot;
    const before = JSON.stringify(result);
    render(<Report result={result} runId="run-9" />);

    fireEvent.change(screen.getByLabelText('报告mass显示单位'), { target: { value: 'kg' } });
    expect(within(document.querySelector('.report-readings') as HTMLElement).getByText('27,200,000 kg')).toBeVisible();
    print();
    done();

    // The reader's page choice survives the print, and so does the saved result.
    expect(within(document.querySelector('.report-readings') as HTMLElement).getByText('27,200,000 kg')).toBeVisible();
    expect(screen.getByLabelText('报告mass显示单位')).toHaveValue('kg');
    expect(result.input_snapshot).toBe(snapshot);
    expect(JSON.stringify(result)).toBe(before);
  });
});

describe('provenance of one saved result', () => {
  it('groups by declaration and estimate without dropping any path', () => {
    const result = printableResult();
    const groups = provenanceGroups(result);
    expect(groups.length).toBeGreaterThan(0);
    expect(groups.every(group => group.paths.length > 0)).toBe(true);
    expect(new Set(groups.flatMap(group => group.paths)).size)
      .toBe(groups.reduce((sum, group) => sum + group.paths.length, 0));
    // The same result is walked once: the second call returns the same groups.
    expect(provenanceGroups(result)).toBe(groups);
    // A different saved result is a different set of statements.
    const other = printableResult();
    other.input_snapshot.hull.loa_m = 214;
    expect(provenanceGroups(other).length).toBe(groups.length);
  });
});