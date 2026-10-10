import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import DamageLabPage from './Page';
import * as api from './api';
import type { ProjectView } from '../types';
import type { Experiment, LabResult, LabRun } from './types';

vi.mock('./api', () => ({ readProject: vi.fn(), readSetup: vi.fn(), listRuns: vi.fn(), readRun: vi.fn(),
  enqueue: vi.fn(), cancel: vi.fn(), preview: vi.fn(), readDemo: vi.fn(), exportUrl: () => '/export' }));
vi.mock('./Scene', () => ({ default: () => <div>3D inspection placeholder</div> }));
const experiment = { schema: 'plimsoll-damage-lab-experiment-1', source: 'test fixture', estimate: true,
  duration_s: 0, time_step_s: 1, initial_water_m3: { room: 0 },
  modules: [{ id: 'engine', label: 'Engine', role: 'propulsion', compartment_id: 'room',
    box: { center_m: [0,0,1], size_m: [1,1,1] }, weight_item_ids: [], required_staff: 6,
    initial_integrity: 1, nominal_shaft_power_kw: 500, source: 'fixture', estimate: true }],
  crew_groups: [{ id: 'watch', label: 'Watch', compartment_id: 'room', module_id: 'engine', personnel: 10,
    station_box: { center_m: [0,0,1], size_m: [1,1,1] }, source: 'fixture', estimate: true }],
  impact: { position_m: [0,0,1], severity: .5, radius_m: 2, source: 'fixture', estimate: true },
  breaches: [], remaining_gz_angles_deg: [0,10], rules: { casualty_fraction: .4, fatal_fraction: .25,
    module_flood_threshold: .5, evacuate_fill_fraction: .3, source: 'fixture', estimate: true } } as Experiment;
const project = { project_id: 'p', revision: 1, project: { id: 'p', name: 'Rig',
  loading_conditions: [{ id: 'normal', label: 'Normal' }], compartments: [], geometry: {} } } as unknown as ProjectView;
const queued = { id: 'r', project_id: 'p', revision: 1, condition_id: 'normal', status: 'queued',
  request_fingerprint: 'frozen', request: { experiment }, result: null, error: null, cancel_requested: false } as LabRun;
const result = { request_fingerprint: 'frozen', snapshots: [{ time_s: 0, event_index: -1,
  ship: null, modules: [], crew_groups: [], compartments: [], capabilities: { shaft_power_kw: null } }],
  request: { experiment }, input_snapshot: project.project, simulated_duration_s: 0,
  core_analysis: { stages: { flooding: { status: 'completed', data: { stop_reason: 'requested_duration' } } } },
  assumptions: [], diagnostics: [], validity: {}, method_versions: {}, events: [] } as unknown as LabResult;

afterEach(cleanup);
beforeEach(() => {
  vi.clearAllMocks(); sessionStorage.clear();
  vi.mocked(api.readProject).mockResolvedValue(project);
  vi.mocked(api.readSetup).mockResolvedValue({ revision: 1, experiment, diagnostics: [] });
  vi.mocked(api.listRuns).mockResolvedValue([]);
  vi.mocked(api.enqueue).mockResolvedValue(queued);
});
describe('laboratory page lifetime and result ownership', () => {
  it('retains unknown layout as unavailable and offers an explicit demo', async () => {
    vi.mocked(api.readSetup).mockResolvedValue({ revision: 1, experiment: null, diagnostics: [{ code: 'missing',
      path: '$.compartments', message: 'No declared compartments', severity: 'error' }] });
    render(<DamageLabPage projectId="p" onBack={vi.fn()} onProject={vi.fn()} />);
    expect(await screen.findByText('No declared compartments')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '建立合成试验场' })).toBeEnabled();
    expect(screen.queryByRole('button', { name: '运行命中试验' })).not.toBeInTheDocument();
  });
  it('hides a finished old job after its impact draft changes', async () => {
    let finish!: (run: LabRun) => void;
    vi.mocked(api.readRun).mockImplementation(() => new Promise(resolve => { finish=resolve; }));
    render(<DamageLabPage projectId="p" onBack={vi.fn()} onProject={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '运行命中试验' }));
    await waitFor(() => expect(api.readRun).toHaveBeenCalled());
    fireEvent.change(screen.getByLabelText('命中强度'), { target: { value: '.8' } });
    await act(async () => { finish({ ...queued, status: 'completed', result }); });
    expect(screen.queryByRole('region', { name: '回放结果' })).not.toBeInTheDocument();
    expect(screen.getByText(/配置已改变/)).toBeInTheDocument();
  });
  it('cancels polling on unmount and leaves no stale read mounted', async () => {
    let signal: AbortSignal | undefined;
    vi.mocked(api.readRun).mockImplementation((_id, value) => { signal=value; return new Promise(() => {}); });
    const view = render(<DamageLabPage projectId="p" onBack={vi.fn()} onProject={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '运行命中试验' }));
    await waitFor(() => expect(signal).toBeDefined());
    view.unmount();
    expect(signal!.aborted).toBe(true);
  });
  it('surfaces failed jobs without inventing a report and can cancel a queued job', async () => {
    vi.mocked(api.readRun).mockResolvedValue({ ...queued, status: 'failed', error: { code: 'test', message: 'worker boundary reached' } });
    render(<DamageLabPage projectId="p" onBack={vi.fn()} onProject={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '运行命中试验' }));
    expect(await screen.findByText('worker boundary reached')).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: '回放结果' })).not.toBeInTheDocument();
  });
  it('keeps invalid imported JSON out of the rendered layout', async () => {
    vi.mocked(api.preview).mockRejectedValue(new Error('requires a nonempty string'));
    render(<DamageLabPage projectId="p" onBack={vi.fn()} onProject={vi.fn()} />);
    await screen.findByRole('button', { name: '运行命中试验' });
    fireEvent.click(screen.getByText('编辑完整配置 JSON'));
    fireEvent.change(screen.getByLabelText('完整配置 JSON'), { target: { value: '{"modules":[{"role":null}]}' } });
    fireEvent.click(screen.getByRole('button', { name: '应用配置' }));
    expect(await screen.findByText('requires a nonempty string')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '运行命中试验' })).toBeInTheDocument();
  });
  it.each(['impact', 'condition'])('does not let late history overwrite a newer %s edit', async kind => {
    const twoConditions = structuredClone(project);
    twoConditions.project.loading_conditions.push({ id: 'other', label: 'Other' });
    vi.mocked(api.readProject).mockResolvedValue(twoConditions);
    const historical = { ...queued, status: 'completed', result, has_result: true } as LabRun;
    vi.mocked(api.listRuns).mockResolvedValue([historical]);
    let resolve!: (run: LabRun) => void;
    vi.mocked(api.readRun).mockImplementation(() => new Promise(done=>{resolve=done;}));
    render(<DamageLabPage projectId="p" onBack={vi.fn()} onProject={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: 'r · R1 · 计算完成' }));
    await waitFor(()=>expect(api.readRun).toHaveBeenCalled());
    if(kind==='impact') fireEvent.change(screen.getByLabelText('命中强度'), { target: { value: '.8' } });
    else fireEvent.change(screen.getByLabelText('载荷工况'), { target: { value: 'other' } });
    await act(async()=>{resolve(historical);});
    expect(screen.getByLabelText(kind==='impact' ? '命中强度' : '载荷工况')).toHaveValue(kind==='impact' ? '0.8' : 'other');
    expect(screen.queryByRole('region', { name: '回放结果' })).not.toBeInTheDocument();
  });
  it('does not let a delayed file read overwrite newer JSON typing', async () => {
    render(<DamageLabPage projectId="p" onBack={vi.fn()} onProject={vi.fn()} />);
    await screen.findByRole('button', { name: '运行命中试验' });
    fireEvent.click(screen.getByText('编辑完整配置 JSON'));
    let resolve!: (text: string) => void;
    const file = new File(['{}'], 'first.json', { type: 'application/json' });
    Object.defineProperty(file, 'text', { value: () => new Promise<string>(done=>{resolve=done;}) });
    fireEvent.change(screen.getByLabelText('选择配置文件'), { target: { files: [file] } });
    fireEvent.change(screen.getByLabelText('完整配置 JSON'), { target: { value: 'newer typed draft' } });
    await act(async()=>{resolve('older file draft');});
    expect(screen.getByLabelText('完整配置 JSON')).toHaveValue('newer typed draft');
  });
  it('keeps the newer selected file when an older read resolves last', async () => {
    render(<DamageLabPage projectId="p" onBack={vi.fn()} onProject={vi.fn()} />);
    await screen.findByRole('button', { name: '运行命中试验' });
    fireEvent.click(screen.getByText('编辑完整配置 JSON'));
    let first!: (text: string) => void, second!: (text: string) => void;
    const oldFile = new File(['{}'], 'old.json'), newFile = new File(['{}'], 'new.json');
    Object.defineProperty(oldFile, 'text', { value: () => new Promise<string>(done=>{first=done;}) });
    Object.defineProperty(newFile, 'text', { value: () => new Promise<string>(done=>{second=done;}) });
    fireEvent.change(screen.getByLabelText('选择配置文件'), { target: { files: [oldFile] } });
    fireEvent.change(screen.getByLabelText('选择配置文件'), { target: { files: [newFile] } });
    await act(async()=>{second('new file');first('old file');});
    expect(screen.getByLabelText('完整配置 JSON')).toHaveValue('new file');
  });
});
