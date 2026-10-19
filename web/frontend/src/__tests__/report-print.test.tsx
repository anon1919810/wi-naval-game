import { act, cleanup, fireEvent, screen, within } from '@testing-library/react';
import { renderZh as render, zhCopy } from './locale';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { Report } from '../pages/Report';
import { Sps3b3Readings } from '../components/Sps3b3Readings';
import { UnitProvider } from '../components/UnitProvider';
import { estimateLabel, provenanceGroups } from '../components/sourceAudit';
import { CANONICAL_PREFERENCES } from '../components/units';
import { weightBreakdownCopy } from '../i18n/weightBreakdown';
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

const designCopy = (key: Parameters<typeof weightBreakdownCopy>[1]) => weightBreakdownCopy('zh-CN', key);

/** The saved native design a readable report carries: ledger, balance and text. */
const NATIVE_DESIGN = {
  schema: 'plimsoll-ship-design-result-1',
  method_version: 'ship-design-native-v1',
  status: 'available',
  basis_condition_id: 'normal',
  ledger: {
    complete: true,
    selected_mass_t: 8012,
    estimated_mass_t: 8000,
    target_displacement_t: 9000,
    difference_t: -988,
    roles: {
      structure: { estimate_t: 2000, selected_mass_t: 2000, mode: 'estimated', item_ids: ['hull.structure'] },
      machinery: { estimate_t: 6000, selected_mass_t: 6000, mode: 'estimated', item_ids: ['engine.machinery'] },
      other: {},
    },
  },
  balance: { selected_mass_t: 8012, estimated_mass_t: 8000, target_displacement_t: 9000, difference_t: -988 },
  report: {
    sections: [{ id: 'saved', title: 'Saved native report', lines: ['the original saved native text'] }],
    text: 'the original saved native text',
  },
  provenance: { source: 'saved native run' },
  hull: { loa_m: 213.4 },
  engine: { power_kw: 12000 },
  performance: { speed_kn: 18 },
};

function nativePrintableResult(): AnalysisResult {
  const result = printableResult();
  const stage = envelope('completed', true, NATIVE_DESIGN as unknown as StageEnvelope['data']);
  stage.method_versions = { kernel: 'ship-design-native-v1' };
  result.stages.ship_design = stage;
  return result;
}

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
    expect(box.textContent).toContain(estimateLabel(true, zhCopy));
    expect(box.textContent).toContain(estimateLabel(false, zhCopy));
    expect(box.textContent).toContain(estimateLabel(null, zhCopy));

    // The reordered pair is one declaration that lists both of its paths.
    const drawingGroup = Array.from(box.querySelectorAll('.report-audit-group'))
      .find(node => node.querySelector('.report-audit-estimate')?.textContent === estimateLabel(true, zhCopy)
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

    fireEvent.change(screen.getByLabelText('报告质量显示单位'), { target: { value: 'kg' } });
    expect(within(document.querySelector('.report-readings') as HTMLElement).getByText('27,200,000 kg')).toBeVisible();
    print();
    done();

    // The reader's page choice survives the print, and so does the saved result.
    expect(within(document.querySelector('.report-readings') as HTMLElement).getByText('27,200,000 kg')).toBeVisible();
    expect(screen.getByLabelText('报告质量显示单位')).toHaveValue('kg');
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

describe('the report print scope', () => {
  it('defaults a readable native report to the design scope and leaves the duplicate paper material off', () => {
    render(<Report result={nativePrintableResult()} runId="run-9" />);
    const page = document.querySelector('.report-page') as HTMLElement;
    expect(page.dataset.printScope).toBe('design');
    expect(screen.getByRole('radio', { name: designCopy('print.scope.design') })).toBeChecked();
    expect(screen.getByRole('radio', { name: designCopy('print.scope.full') })).not.toBeChecked();

    // The screen stays complete: the original text, the native audit and the
    // appendix are all still mounted and readable.
    expect(document.querySelector('.sps-report')!.textContent).toContain('the original saved native text');
    expect(document.querySelector('.sps-native')).not.toBeNull();
    expect(appendix()).not.toBeNull();
    // The design paper still carries its own identity, including the request
    // fingerprint in the always-visible audit facts.
    const identity = document.querySelector('[data-report-identity]') as HTMLElement;
    expect(document.querySelector('.report-audit-facts')!.textContent).toContain('request-fingerprint-0123456789');
    expect(identity.textContent).toContain('ship-design-native-v1');
    // The duplicate material is explicitly marked for the design sheet.
    for (const selector of ['.sps-report', '.sps-native', '.report-provenance']) {
      expect(document.querySelector(selector)!.classList.contains('print-secondary')).toBe(true);
    }

    print();
    // A design sheet never walks or mounts the source appendix or the native key
    // audit, and the original text is not expanded for it.
    expect(document.querySelectorAll('.report-audit-group')).toHaveLength(0);
    expect(appendix().hasAttribute('open')).toBe(false);
    expect(document.querySelector('.sps-native')!.hasAttribute('open')).toBe(false);
    // Not even a nested section of the hidden native audit is opened: the walk is
    // ancestor-aware, so the whole hidden region stays shut.
    expect(document.querySelectorAll('.sps-native details[open]')).toHaveLength(0);
    done();
    expect(document.querySelectorAll('details[open]')).toHaveLength(0);
  });

  it('prints the source appendix and the original text only in the full scope', () => {
    render(<Report result={nativePrintableResult()} runId="run-9" />);
    fireEvent.click(screen.getByRole('radio', { name: designCopy('print.scope.full') }));
    expect((document.querySelector('.report-page') as HTMLElement).dataset.printScope).toBe('full');
    expect(screen.getByText(designCopy('print.scope.fullHint'))).toBeVisible();

    print();
    expect(appendix().hasAttribute('open')).toBe(true);
    expect(document.querySelectorAll('.report-audit-group').length).toBeGreaterThan(0);
    expect(document.querySelector('.sps-native')!.hasAttribute('open')).toBe(true);
    // In the full scope the saved native audit really opens, including its nested
    // per-section disclosures the Sps3b3 stylesheet would otherwise hide.
    expect(document.querySelectorAll('.sps-native details[open]').length).toBeGreaterThan(0);
    done();

    // The same screen states return, exactly as the full scope always promised.
    expect(appendix().hasAttribute('open')).toBe(false);
    expect(document.querySelector('.sps-native')!.hasAttribute('open')).toBe(false);
    expect(document.querySelectorAll('.sps-native details[open]')).toHaveLength(0);
  });

  it('defaults a kernel-mismatched native stage to the full scope and keeps its source material', () => {
    const mismatched = nativePrintableResult();
    mismatched.stages.ship_design.method_versions = { kernel: 'other-kernel' };
    render(<Report result={mismatched} runId="run-9" />);
    expect((document.querySelector('.report-page') as HTMLElement).dataset.printScope).toBe('full');
    // No readable native replacement, so the source text and native audit are not
    // marked as duplicates and stay on the sheet.
    for (const selector of ['.sps-report', '.sps-native']) {
      expect(document.querySelector(selector)!.classList.contains('print-secondary')).toBe(false);
    }
  });

  it('keeps a compatibility stage main report on the sheet, unmarked', () => {
    const compat = {
      schema: 'plimsoll-sps3b3-result-1', status: 'available',
      report: { sections: [{ id: 's', title: 'Compat', lines: ['compat text'] }], text: 'compat text' },
      provenance: { source: 'compat' },
    };
    render(<UnitProvider preferences={CANONICAL_PREFERENCES}>
      <Sps3b3Readings data={compat} />
    </UnitProvider>);
    expect(document.querySelector('.sps-report')!.textContent).toContain('compat text');
    for (const selector of ['.sps-report', '.sps-native']) {
      expect(document.querySelector(selector)!.classList.contains('print-secondary')).toBe(false);
    }
  });

  it('defaults a report without a readable native design to the full scope', () => {
    render(<Report result={printableResult()} runId="run-9" />);
    expect((document.querySelector('.report-page') as HTMLElement).dataset.printScope).toBe('full');
    expect(screen.getByRole('radio', { name: designCopy('print.scope.full') })).toBeChecked();
  });

  it('keeps the reader s disclosure across scope switches and repeated prints', () => {
    render(<Report result={nativePrintableResult()} runId="run-9" />);
    const readerOpened = detailsBySummary('假设与适用性');
    act(() => { readerOpened.open = true; });
    fireEvent(readerOpened, new Event('toggle'));

    print(); done();
    expect(readerOpened.hasAttribute('open')).toBe(true);

    fireEvent.click(screen.getByRole('radio', { name: designCopy('print.scope.full') }));
    print(); done();
    expect(readerOpened.hasAttribute('open')).toBe(true);

    fireEvent.click(screen.getByRole('radio', { name: designCopy('print.scope.design') }));
    print(); done();
    expect(readerOpened.hasAttribute('open')).toBe(true);
    // The design print never opened the appendix behind the reader's back.
    expect(appendix().hasAttribute('open')).toBe(false);
  });
});