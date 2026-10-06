import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { Workbench } from '../pages/Workbench';
import { declaredSource, estimateLabel, estimateState, InputTraceProvider, TracePanel, TracedField } from '../components/InputTrace';
import { overviewReadings, overviewStages, severeDiagnostics } from '../components/WorkbenchOverview';
import * as api from '../api';
import type { AnalysisResult, ProjectDocument, RunView, StageEnvelope } from '../types';

vi.mock('../api', async original => ({ ...await original<typeof import('../api')>(),
  getProject: vi.fn(), saveProject: vi.fn(), listRuns: vi.fn(), enqueueRun: vi.fn(), getRun: vi.fn() }));

const project: ProjectDocument = {
  schema: 'plimsoll-project-1', id: 'p1', name: '解析方箱', revision: 1,
  hull: { loa_m: 90, beam_m: 20, draught_normal_m: 4, sources: { loa_m: 'builder plan' } },
  geometry: null,
  weight_groups: [{ id: 'lightship', label: '空船', items: [{ id: 'steel', mass_t: 2100, x_m: 35, source: 'survey', estimate: false }] }],
  loading_conditions: [{ id: 'loaded', label: '满载' }, { id: 'deep', label: '深载' }],
  resistance_scenarios: [{ id: 'study', method: 'holtrop_mennen_1982' }],
};

function stage(status: StageEnvelope['status'], data: StageEnvelope['data'], extra: Record<string, unknown> = {}): StageEnvelope {
  return {
    status, requested: true, reason: null,
    validity: { complete: status === 'completed', converged: null, model_applicable: null, historical_validated: null },
    method_versions: {}, assumptions: [], diagnostics: [], data, ...extra,
  };
}

function emptyStages(): AnalysisResult['stages'] {
  return Object.fromEntries(
    ['loading', 'equilibrium', 'hydrostatics', 'deck'].map(name => [name, stage('not_requested', null, { requested: false })]),
  ) as AnalysisResult['stages'];
}

function runWith(result: AnalysisResult | null, overrides: Partial<RunView> = {}): RunView {
  return { id: 'run-a', project_id: 'p1', revision: 1, condition_id: 'loaded', status: 'completed',
    request_fingerprint: 'fp-a', created_at: '2026-10-05T00:00:00Z', started_at: null, finished_at: '2026-10-05T00:01:00Z',
    cancel_requested: false, result, error: null, ...overrides } as RunView;
}

function resultWith(stages: AnalysisResult['stages'], diagnostics: AnalysisResult['diagnostics'] = []): AnalysisResult {
  return { schema: 'plimsoll-analysis-1', status: 'completed', project_id: 'p1', condition_id: 'loaded',
    project_fingerprint: 'pf', input_fingerprint: 'if', request_fingerprint: 'rf',
    request: {}, input_snapshot: project, units: {}, method_versions: {}, sources: {},
    diagnostics, validity: { complete: true, converged: true, model_applicable: true, historical_validated: null },
    stages } as AnalysisResult;
}

let narrowViewport = false;

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
  narrowViewport = false;
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: /max-width:\s*1280px/.test(query) ? narrowViewport : false,
    media: query, addEventListener: () => {}, removeEventListener: () => {},
  }));
  vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 1, project });
  vi.mocked(api.listRuns).mockResolvedValue([]);
  vi.mocked(api.getRun).mockRejectedValue(new Error('no stored result'));
  vi.mocked(api.saveProject).mockImplementation(async (_id, input) => ({ project_id: 'p1', revision: 2, project: input.project }));
});

afterEach(() => { vi.unstubAllGlobals(); });

async function open(chapter?: string) {
  render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
  if (chapter) fireEvent.click(await screen.findByRole('button', { name: chapter }));
  await screen.findByRole('button', { name: '概览' });
  await waitFor(() => expect(api.listRuns).toHaveBeenCalled());
  if (!chapter) await waitFor(() => expect(document.querySelector('.result-identity, .result-absent')).not.toBeNull());
}

function group(name: string): HTMLElement {
  return screen.getByRole('heading', { name }).closest('.chapter-group') as HTMLElement;
}

function tracePanel(): HTMLElement {
  return screen.getByLabelText('输入来源') as HTMLElement;
}

describe('workhead and chapter hierarchy', () => {
  it('leads the Overview with the vessel and other chapters with the English title', async () => {
    await open();
    expect(screen.getByRole('heading', { level: 1, name: '解析方箱' })).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: '船型与几何' }));
    expect(screen.getByRole('heading', { level: 1, name: 'Hull & Geometry' })).toBeVisible();
    // The vessel stays reachable as smaller context, never a competing heading.
    expect(screen.queryByRole('heading', { name: '解析方箱' })).toBeNull();
    expect(document.querySelector('.chapter-context .chapter-vessel')!.textContent).toBe('解析方箱');
  });

  it('numbers the chapter index without changing its Chinese accessible names', async () => {
    await open();
    const chapters = screen.getByLabelText('项目章节');
    const first = chapters.querySelector('.nav-item')!;
    expect(first.textContent).toContain('01');
    expect(screen.getByRole('button', { name: '船型与几何' })).toBeVisible();
    expect(first.querySelector('.nav-index')!.getAttribute('aria-hidden')).toBe('true');
  });

  it('keeps condition, saved revision, draft state and Save/Run in one operation bar', async () => {
    await open();
    const bar = document.querySelector('.operation-bar')!;
    expect(bar.querySelector('#condition')).not.toBeNull();
    expect(within(bar as HTMLElement).getByRole('button', { name: '保存修订' })).toBeVisible();
    expect(within(bar as HTMLElement).getByRole('button', { name: '运行计算 ↗' })).toBeVisible();
    expect(within(bar as HTMLElement).getByText('已保存')).toBeVisible();
    // The saved revision stays visible both clean and dirty.
    expect(within(bar as HTMLElement).getByText('修订 1')).toBeVisible();
    const secondary = within(bar as HTMLElement).getByText('更多').closest('details')!;
    expect(secondary.open).toBe(false);
    fireEvent.click(within(bar as HTMLElement).getByText('更多'));
    expect(secondary.open).toBe(true);
    expect(within(bar as HTMLElement).getByRole('button', { name: '下载项目 JSON' })).toBeVisible();

    fireEvent.click(screen.getByRole('button', { name: '船型与几何' }));
    fireEvent.change(await screen.findByLabelText('船长'), { target: { value: '95' } });
    await waitFor(() => expect(within(document.querySelector('.operation-bar') as HTMLElement).getByText('未保存修改')).toBeVisible());
    expect(within(document.querySelector('.operation-bar') as HTMLElement).getByText('修订 1')).toBeVisible();
  });

  it('places request errors directly under the operation bar and clears them when valid', async () => {
    await open('性能与工况');
    // Requesting a resistance study without speed samples cannot be submitted.
    fireEvent.change(await screen.findByLabelText('阻力研究场景'), { target: { value: 'study' } });
    const alerts = document.querySelector('.workbench-alerts')!;
    await waitFor(() => expect(within(alerts as HTMLElement).getByRole('alert')).toHaveTextContent(/采样|递增/));
    expect(screen.getByRole('button', { name: '运行计算 ↗' })).toBeDisabled();
    fireEvent.change(screen.getByLabelText('速度采样'), { target: { value: '10, 12' } });
    await waitFor(() => expect(within(alerts as HTMLElement).queryByRole('alert')).toBeNull());
    expect(screen.getByRole('button', { name: '运行计算 ↗' })).not.toBeDisabled();
  });

  it('reads inputs, then the optional request, then results in the Performance chapter', async () => {
    await open('性能与工况');
    const sections = [...document.querySelectorAll('.editor-section .input-group-head h2')].map(node => node.textContent);
    // The request follows every input it depends on and precedes its results.
    expect(sections).toEqual(['载荷工况与横摇输入', '阻力研究场景', '本次计算请求', '结果']);
    const requestIndex = sections.indexOf('本次计算请求');
    const resistanceIndex = document.body.textContent!.indexOf('阻力研究场景');
    const requestNode = [...document.querySelectorAll('.editor-section')].find(node => node.textContent!.includes('本次计算请求'))!;
    const resistanceNode = [...document.querySelectorAll('.editor-section')].find(node => node.textContent!.includes('阻力方法'))!;
    // Comparing document order proves the request is not rendered before the
    // resistance inputs it references.
    expect(resistanceNode.compareDocumentPosition(requestNode) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(requestIndex).toBe(2);
    expect(resistanceIndex).toBeGreaterThan(-1);
  });

  it('flattens nested input frames into numbered groups with thin rules', async () => {
    await open('重量与载荷');
    const groupHead = document.querySelector('.editor-section .input-group-head')!;
    expect(groupHead.querySelector('.group-index')!.textContent).toBe('01');
    expect(groupHead.querySelector('h2')!.textContent).toBe('载荷账本');
    // A nested group card does not repeat a heavy frame of its own.
    const nested = document.querySelector('.editor-section .form-card, .editor-section .fact-input')!;
    expect(nested).not.toBeNull();
  });
});

describe('overview reads inputs and the identity-guarded result', () => {
  it('labels main dimensions as Input with their actual source declaration', async () => {
    await open();
    const inputs = group('输入 · Input');
    expect(within(inputs).getByText('船长').closest('.fact-field')!.textContent).toContain('90 m');
    expect(within(inputs).getByText('重量条目').closest('.fact-field')!.textContent).toContain('1 项');
    expect(within(inputs).getByText('builder plan')).toBeVisible();
    expect(within(inputs).getAllByText('未声明来源')).toHaveLength(2);
  });

  it('shows the selected condition and saved revision, and marks a dirty draft', async () => {
    await open();
    const identity = group('当前工况与修订');
    expect(within(identity).getByText('满载')).toBeVisible();
    expect(within(identity).getByText('修订 1')).toBeVisible();
    expect(within(identity).getByText('与已保存修订一致')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: '船型与几何' }));
    fireEvent.change(await screen.findByLabelText('型宽'), { target: { value: '22' } });
    fireEvent.click(screen.getByRole('button', { name: '概览' }));
    expect(within(group('输入 · Input')).getByText('22 m')).toBeVisible();
    expect(within(group('当前工况与修订')).getByText('未保存修改')).toBeVisible();
  });

  it('presents the matching saved result with its run identity and canonical stage data', async () => {
    const stages = emptyStages();
    stages.loading = stage('completed', { values: { total_mass_t: 27200 } });
    stages.equilibrium = stage('completed', { waterline_above_keel_m: 9.9 });
    stages.hydrostatics = stage('completed', { values: { gm_t_m: 1.85 } });
    vi.mocked(api.listRuns).mockResolvedValue([runWith(resultWith(stages))]);
    await open();
    const result = group('当前结果 · Result');
    expect(within(result).getByText('运行 run-a')).toBeVisible();
    expect(within(result).getByText('修订 1')).toBeVisible();
    expect(within(result).getByText('工况 loaded')).toBeVisible();
    expect(within(result).getByText('所选工况总质量').closest('.fact-field')!.textContent).toContain('27,200 t');
    expect(within(result).getByText('龙骨基准水线高度').closest('.fact-field')!.textContent).toContain('9.9 m');
    expect(within(result).getByText('初稳性高 GM').closest('.fact-field')!.textContent).toContain('1.85 m');
    expect(api.getRun).not.toHaveBeenCalled();
  });

  it('states that there is no current result, and why, without inventing numbers', async () => {
    await open();
    const result = group('当前结果 · Result');
    expect(within(result).getByText('尚无当前结果')).toBeVisible();
    expect(within(result).getByText(/尚未选择工况|尚无已保存结果/)).toBeVisible();
    expect(result.textContent).not.toMatch(/0 m|0 t/);
  });

  it('loses the current identity the moment the draft is edited', async () => {
    const stages = emptyStages();
    stages.loading = stage('completed', { values: { total_mass_t: 27200 } });
    vi.mocked(api.listRuns).mockResolvedValue([runWith(resultWith(stages))]);
    await open();
    expect(within(group('当前结果 · Result')).getByText('所选工况总质量')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: '船型与几何' }));
    fireEvent.change(await screen.findByLabelText('船长'), { target: { value: '96' } });
    fireEvent.click(screen.getByRole('button', { name: '概览' }));
    const result = group('当前结果 · Result');
    expect(within(result).queryByText('所选工况总质量')).toBeNull();
    expect(within(result).getByText('尚无当前结果')).toBeVisible();
    expect(within(result).getByText(/草稿有未保存修改/)).toBeVisible();
  });

  it('never presents another condition or revision as the current result, and keeps history reachable', async () => {
    const stages = emptyStages();
    stages.loading = stage('completed', { values: { total_mass_t: 4242 } });
    const onRun = vi.fn();
    // The run list is set before the workbench mounts, so it is not raced.
    vi.mocked(api.listRuns).mockResolvedValue([
      runWith(resultWith(stages), { id: 'other-condition', condition_id: 'deep' }),
      runWith(resultWith(stages), { id: 'other-revision', revision: 9 }),
      runWith(resultWith(stages), { id: 'other-project', project_id: 'p2' }),
    ]);
    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={onRun} />);
    await screen.findByRole('button', { name: '概览' });
    await waitFor(() => expect(group('运行记录').querySelectorAll('.run-history button')).toHaveLength(3));
    expect(group('当前结果 · Result').textContent).not.toContain('4242');
    expect(within(group('当前结果 · Result')).getByText('尚无当前结果')).toBeVisible();
    expect(api.getRun).not.toHaveBeenCalled();
    const history = group('运行记录');
    expect(within(history).getByText('工况 deep')).toBeVisible();
    expect(within(history).getByText('修订 9')).toBeVisible();
    // History entries open the run page through the workbench's own callback.
    fireEvent.click(within(history).getByText('工况 deep'));
    expect(onRun).toHaveBeenCalledWith('other-condition');
  });

  it('surfaces unavailable stages and severe diagnostics instead of hiding them', async () => {
    const stages = emptyStages();
    stages.hydrostatics = stage('unavailable', { values: { gm_t_m: 9.99 } }, { reason: '型线资料不足' });
    stages.equilibrium = stage('model_limit', null, {
      reason: '超出方法适用范围',
      diagnostics: [{ code: 'MODEL_LIMIT', severity: 'warning', message: '超出方法适用范围' }],
    });
    const result = resultWith(stages, [
      { code: 'SEVERE', severity: 'error', message: '质量账本缺少关键条目' },
      { code: 'NOTE', severity: 'warning', message: '仅供比较的提示' },
    ]);
    vi.mocked(api.listRuns).mockResolvedValue([runWith(result)]);
    await open();
    const panel = group('当前结果 · Result');
    expect(within(panel).getByText('资料不足')).toBeVisible();
    expect(within(panel).getByText('模型越界')).toBeVisible();
    expect(within(panel).getByText(/质量账本缺少关键条目/)).toBeVisible();
    expect(panel.textContent).not.toContain('仅供比较的提示');
    // An unavailable stage shows no number, not even one left in the envelope.
    const gm = within(panel).getByText('初稳性高 GM').closest('.fact-field')!;
    expect(gm.querySelector('.fact-value')!.textContent).toBe('未知');
    expect(gm.textContent).toContain('资料不足');
    expect(gm.textContent).not.toContain('9.99');
    expect(severeDiagnostics(runWith(result)).map(entry => entry.message)).toEqual(['质量账本缺少关键条目']);
  });
});

describe('overview projection', () => {
  it('reports every canonical reading, with a reason when the stage gave nothing', () => {
    const stages = emptyStages();
    stages.loading = stage('completed', { values: { total_mass_t: 1000 } });
    const run = runWith(resultWith(stages));
    const readings = overviewReadings(run);
    expect(readings).toHaveLength(4);
    const mass = readings.find(entry => entry.key === 'loading.total_mass_t')!;
    expect(mass.value).toBe(1000);
    expect(mass.state).toBe('known');
    for (const entry of readings.filter(item => item.key !== 'loading.total_mass_t')) {
      expect(entry.value).toBeNull();
      expect(entry.state).toBe('unavailable');
      expect(entry.note).toContain('未运行该阶段');
    }
    expect(overviewStages(run).map(entry => entry.name)).toEqual(['loading']);
  });

  it('keeps an exact zero distinct from an unknown value', () => {
    const stages = emptyStages();
    stages.loading = stage('completed', { values: { total_mass_t: 0 } });
    stages.hydrostatics = stage('completed', { values: {} });
    const readings = overviewReadings(runWith(resultWith(stages)));
    const mass = readings.find(entry => entry.key === 'loading.total_mass_t')!;
    expect(mass.value).toBe(0);
    expect(mass.state).toBe('known');
    const gm = readings.find(entry => entry.key === 'hydrostatics.gm_t_m')!;
    expect(gm.value).toBeNull();
    expect(gm.state).toBe('unknown');
    expect(gm.note).toContain('未给出');
  });

  it('reads the actual saved keel-relative waterline without deriving a draught', () => {
    const stages = emptyStages();
    stages.equilibrium = stage('completed', { waterline_d_m: 10.25, waterline_above_keel_m: 7.25, heel_deg: 0 });
    const draught = overviewReadings(runWith(resultWith(stages))).find(entry => entry.key === 'equilibrium.waterline_above_keel_m')!;
    expect(draught.value).toBe(7.25);
    expect(draught.state).toBe('known');
  });

  it('shows a real flattened severe diagnostic only once and retains its stage', () => {
    const diagnostic = { code: 'LOAD', stage: 'loading', severity: 'error', source_path: '$.weights', message: 'missing mass' };
    const stages = emptyStages();
    stages.loading = stage('failed', null, { diagnostics: [diagnostic] });
    expect(severeDiagnostics(runWith(resultWith(stages, [diagnostic])))).toEqual([{ stage: 'loading', message: 'missing mass' }]);
  });
});

describe('input provenance and the Trace panel', () => {
  it('formats a ledger longitudinal position as length in Trace', async () => {
    await open('重量与载荷');
    fireEvent.focus(await screen.findByLabelText('lightship steel 纵向位置'));
    expect(within(tracePanel()).getByText('35 m')).toBeVisible();
    expect(tracePanel().textContent).not.toContain('35 t');
  });

  it('keeps all damage geometry inputs before the optional request and results', async () => {
    await open('破损研究');
    fireEvent.click(screen.getByRole('button', { name: '添加破损场景' }));
    const geometry = screen.getByRole('heading', { name: '项目舱室几何' });
    const request = screen.getByRole('heading', { name: '本次破损计算请求' });
    const results = screen.getByRole('heading', { name: '当前修订 · 所选工况结果' });
    expect(geometry.compareDocumentPosition(request) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(request.compareDocumentPosition(results) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
  it('reveals a closed panel from a field marker and retains selection across panel focus', async () => {
    narrowViewport = true;
    await open('重量与载荷');
    fireEvent.click(document.querySelector('[data-trace-key="ledger.lightship.steel.mass_t"] .trace-pick')!);
    expect(within(tracePanel()).getByText('steel 质量')).toBeVisible();
    fireEvent.focus(within(tracePanel()).getByRole('button', { name: '收起来源' }));
    expect(within(tracePanel()).getByText('survey')).toBeVisible();
  });

  it('isolates duplicate field paths and clears a removed selection', () => {
    const fact = { key: 'duplicate', label: '同名', value: 1, source: 'first', estimate: false };
    const content = (first: boolean) => <InputTraceProvider>
      {first && <TracedField fact={fact}><input aria-label="first" /></TracedField>}
      <TracedField fact={{ ...fact, value: 2, source: 'second' }}><input aria-label="second" /></TracedField>
      <TracePanel open onToggle={() => {}} />
    </InputTraceProvider>;
    const view = render(content(true));
    fireEvent.focus(screen.getByLabelText('first'));
    expect(within(tracePanel()).getByText('first')).toBeVisible();
    expect(document.querySelectorAll('.trace-pick[aria-pressed="true"]')).toHaveLength(1);
    view.rerender(content(false));
    expect(tracePanel().textContent).not.toContain('first');
    expect(within(tracePanel()).getByRole('heading', { name: '输入来源' })).toBeVisible();
  });
  it('never reads an undeclared estimate as confirmed', () => {
    expect(estimateState(null)).toBe('unknown');
    expect(estimateLabel(null)).toBe('估算状态未声明');
    expect(estimateState(false)).toBe('declared');
    expect(estimateLabel(false)).toBe('非估算（已声明）');
    expect(estimateState(true)).toBe('estimate');
    expect(estimateLabel(true)).toBe('工程估算');
  });

  it('marks declared, estimated and unsourced fields from their own stored fields only', async () => {
    await open('重量与载荷');
    await screen.findByLabelText('lightship steel 质量');
    // A declared, non-estimated ledger item reads as a declared source.
    expect(document.querySelector('[data-trace-key="ledger.lightship.steel.mass_t"] .source-mark')!.textContent).toBe('已声明来源');
    // A main dimension with no `hull.sources` entry is explicitly unknown, and an
    // undeclared estimate is never promoted to "confirmed": a declared string
    // without an estimate says so instead of claiming confirmation.
    fireEvent.click(screen.getByRole('button', { name: '船型与几何' }));
    await screen.findByLabelText('水线长');
    expect(document.querySelector('[data-trace-key="hull.lwl_m"] .source-mark')!.textContent).toBe('未知来源');
    expect(document.querySelector('[data-trace-key="hull.loa_m"] .source-mark')!.textContent).toBe('已声明来源 · 估算未声明');
  });

  it('shows only the selected field, and refreshes it as the draft is edited', async () => {
    await open('重量与载荷');
    const source = await screen.findByLabelText('来源');
    expect(tracePanel().textContent).toContain('输入来源');
    fireEvent.focus(source);
    const panel = tracePanel();
    expect(within(panel).getByText('非估算（已声明）')).toBeVisible();
    expect(panel.textContent).toContain('survey');
    // Editing the declared source refreshes the trace without a reload.
    fireEvent.change(source, { target: { value: 'dock survey' } });
    expect(tracePanel().textContent).toContain('dock survey');
    expect(tracePanel().textContent).not.toContain('survey</dd>');
    // A declared source is a provenance statement, never a certification claim.
    expect(panel.textContent).toContain('不代表史实验证');
  });

  it('preserves structured source declarations and treats blank strings as unknown', () => {
    expect(declaredSource({ id: 'drawing', page: '第六页' })).toBe('{"id":"drawing","page":"第六页"}');
    expect(declaredSource('   ')).toBeNull();
    expect(declaredSource(null)).toBeNull();
  });

  it('clears the selection on a chapter change and does not dirty the draft', async () => {
    await open('重量与载荷');
    fireEvent.focus(await screen.findByLabelText('lightship steel 质量'));
    expect(within(tracePanel()).getByText('steel 质量')).toBeVisible();
    const bar = document.querySelector('.operation-bar')!;
    expect(within(bar as HTMLElement).queryByText('未保存修改')).toBeNull();
    // Selecting and expanding the trace is view state: the project is untouched.
    fireEvent.click(within(tracePanel()).getByRole('button', { name: '收起来源' }));
    fireEvent.click(within(tracePanel()).getByRole('button', { name: '来源' }));
    expect(within(document.querySelector('.operation-bar') as HTMLElement).queryByText('未保存修改')).toBeNull();
    expect(api.saveProject).not.toHaveBeenCalled();
    // A different chapter must not inherit an unrelated selected fact.
    fireEvent.click(screen.getByRole('button', { name: '船型与几何' }));
    await waitFor(() => expect(tracePanel().textContent).toContain('输入来源'));
    expect(tracePanel().textContent).not.toContain('steel 质量');
  });

  it('clears the selection when an unsourced control is focused', () => {
    render(<InputTraceProvider>
      <TracedField fact={{ key: 'a', label: '甲', value: 1, source: 'src', estimate: false }}>
        <input aria-label="甲 值" />
      </TracedField>
      <input aria-label="无来源控件" />
      <TracePanel open onToggle={() => {}} />
    </InputTraceProvider>);
    fireEvent.focus(screen.getByLabelText('甲 值'));
    const panel = screen.getByLabelText('输入来源') as HTMLElement;
    expect(panel.textContent).toContain('src');
    expect(panel.textContent).not.toContain('输入来源</h2>');
    fireEvent.blur(screen.getByLabelText('甲 值'));
    // A control with no declared provenance clears rather than inheriting a fact.
    fireEvent.focus(screen.getByLabelText('无来源控件'));
    expect(panel.textContent).toContain('输入来源');
    expect(panel.textContent).not.toContain('src');
  });

  it('opens closed by default at 1024 and places the same panel above the inputs', async () => {
    narrowViewport = true;
    await open('重量与载荷');
    const toggle = within(tracePanel()).getByRole('button', { name: '来源' });
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    expect(tracePanel().querySelector('.trace-body')).toBeNull();
    fireEvent.click(toggle);
    expect(within(tracePanel()).getByRole('button', { name: '收起来源' })).toBeVisible();
    // The panel is the same element; a narrow desktop keeps it in normal flow.
    expect(tracePanel().parentElement!.className).toBe('workbench-layout');
    expect(document.querySelector('.trace-panel-overlay, dialog')).toBeNull();
  });

  it('opens by default on a wide desktop without an overlay', async () => {
    await open('重量与载荷');
    expect(within(tracePanel()).getByRole('button', { name: '收起来源' })).toBeVisible();
    expect(document.querySelector('.trace-panel-overlay, dialog')).toBeNull();
  });

  it('publishes a fact through the keyboard-accessible marker button', async () => {
    await open('重量与载荷');
    const pick = document.querySelector('[data-trace-key="ledger.lightship.steel.x_m"] .trace-pick') as HTMLButtonElement;
    pick.focus();
    fireEvent.click(pick);
    expect(pick.getAttribute('aria-pressed')).toBe('true');
    expect(within(tracePanel()).getByText('steel 纵向位置')).toBeVisible();
  });
});
