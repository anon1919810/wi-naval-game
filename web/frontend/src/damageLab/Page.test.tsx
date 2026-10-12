import { act, cleanup, fireEvent, screen, waitFor } from '@testing-library/react';
import { renderZh as render } from '../__tests__/locale';
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
const project = { project_id: 'p', revision: 1, project: { id: 'p', revision:1, name: 'Rig',
  loading_conditions: [{ id: 'normal', label: 'Normal' }], compartments: [], geometry: {} } } as unknown as ProjectView;
const queued = { id: 'r', project_id: 'p', revision: 1, condition_id: 'normal', status: 'queued',
  request_fingerprint: 'frozen', request: { schema:'plimsoll-damage-lab-request-1',condition_id:'normal',method_versions:{},experiment }, result: null, error: null, cancel_requested: false } as LabRun;
const result = { final_state:{time_s:0,event_index:-1,ship:null,modules:[],crew_groups:[],compartments:[],capabilities:{shaft_power_kw:null,known_shaft_power_subtotal_kw:0}}, status:'completed',condition_id:'normal', request_fingerprint: 'frozen', snapshots: [{ time_s: 0, event_index: -1,
  ship: null, modules: [], crew_groups: [], compartments: [], capabilities: { shaft_power_kw: null } }],
  request: queued.request, input_snapshot: project.project, simulated_duration_s: 0,
  core_analysis: { stages: { flooding: { status: 'completed', data: { stop_reason: 'requested_duration' } } } },
  assumptions: [], diagnostics: [], validity: {}, method_versions: {}, events: [] } as unknown as LabResult;

afterEach(cleanup);
beforeEach(() => {
  vi.clearAllMocks(); sessionStorage.clear();
  vi.mocked(api.readProject).mockResolvedValue(project);
  vi.mocked(api.readSetup).mockResolvedValue({ revision: 1, experiment, diagnostics: [] });
  vi.mocked(api.listRuns).mockResolvedValue([]);
  vi.mocked(api.enqueue).mockResolvedValue(queued);
  vi.mocked(api.readDemo).mockResolvedValue({project:project.project,experiment});
  vi.mocked(api.preview).mockImplementation(async(_id,_revision,_condition,experiment)=>({experiment:experiment as Experiment,request_fingerprint:'preview'}));
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

  it('explains a vessel a preset cannot describe, and runs nothing', async () => {
    render(<DamageLabPage projectId="p" onBack={vi.fn()} onProject={vi.fn()} />);
    // This fixture's project declares no compartments, so the declared origin
    // falls in no room: the page says so rather than guessing a wall.
    fireEvent.click(await screen.findByRole('button', { name: '舱壁屏蔽' }));
    expect(await screen.findByText(/无法把声明的原点落在任一舱室内/)).toBeVisible();
    expect(api.enqueue).not.toHaveBeenCalled();
  });

  it('prepares a preset draft and its assumptions without running anything', async () => {
    const compartments = [
      { id: 'starboard-machinery', label: 'Starboard machinery', x_m: -4, y_m: 1.6, keel_to_bottom_m: 0.8,
        length_m: 8, beam_m: 3.2, height_m: 3.2, permeability: 0.8 },
      { id: 'port-machinery', label: 'Port machinery', x_m: -4, y_m: -1.6, keel_to_bottom_m: 0.8,
        length_m: 8, beam_m: 3.2, height_m: 3.2, permeability: 0.8 },
      { id: 'forward-control', label: 'Forward control', x_m: 4, y_m: 0, keel_to_bottom_m: 1.2,
        length_m: 7, beam_m: 5, height_m: 2.8, permeability: 0.8 },
    ];
    vi.mocked(api.readProject).mockResolvedValue({
      ...project, project: { ...project.project, compartments } } as unknown as ProjectView);
    vi.mocked(api.readSetup).mockResolvedValue({ revision: 1, diagnostics: [], experiment: {
      ...experiment, impact: { ...experiment.impact, position_m: [-4, 1.6, 2.4] } } });
    vi.mocked(api.readDemo).mockResolvedValue({project:{...project.project,compartments} as never,experiment:{...experiment,impact:{...experiment.impact,position_m:[-4,1.6,2.4]}}});
    render(<DamageLabPage projectId="p" onBack={vi.fn()} onProject={vi.fn()} />);

    fireEvent.click(await screen.findByRole('button', { name: '舱壁屏蔽' }));
    expect(await screen.findByText(/内舱壁/)).toBeVisible();
    // Preparing a draft is not running one: the form's own submit is the only
    // path that enqueues, and nobody pressed it.
    expect(api.enqueue).not.toHaveBeenCalled();
    expect(api.preview).toHaveBeenCalledTimes(1);
    expect(vi.mocked(api.preview).mock.calls[0][3]).toMatchObject({impact:{radius_m:8},breaches:[]});
  });

  it('reads a comparison record only after it is chosen, and restores nothing', async () => {
    const older = { ...queued, id: 'older-run', status: 'completed', has_result: true, result } as unknown as LabRun;
    vi.mocked(api.listRuns).mockResolvedValue([older]);
    vi.mocked(api.readRun).mockResolvedValue(older);
    render(<DamageLabPage projectId="p" onBack={vi.fn()} onProject={vi.fn()} />);
    await screen.findByRole('button', { name: '运行命中试验' });

    // Nothing is read for the comparison until a side has been chosen…
    expect(api.readRun).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('试验 A'), { target: { value: 'older-run' } });
    // …and choosing a side reads that record without restoring it as the trial
    // the page is looking at, and without running anything.
    await waitFor(() => expect(api.readRun).toHaveBeenCalledWith('older-run', expect.anything()));
    expect(api.enqueue).not.toHaveBeenCalled();
  });

  it('lets both comparison reads finish independently and discards an older selection on one side', async () => {
    const jobs = ['a','b','c'].map(id=>({...queued,id,status:'completed',has_result:true,result}) as LabRun);
    vi.mocked(api.listRuns).mockResolvedValue(jobs);
    const reads = new Map<string,{signal:AbortSignal;finish:(job:LabRun)=>void}>();
    vi.mocked(api.readRun).mockImplementation((id,signal)=>new Promise(resolve=>{reads.set(id,{signal:signal!,finish:resolve});}));
    render(<DamageLabPage projectId="p" onBack={vi.fn()} onProject={vi.fn()} />);
    await screen.findByRole('button',{name:'运行命中试验'});
    fireEvent.change(screen.getByLabelText('试验 A'),{target:{value:'a'}});
    fireEvent.change(screen.getByLabelText('试验 B'),{target:{value:'b'}});
    expect(reads.get('a')!.signal.aborted).toBe(false);
    fireEvent.change(screen.getByLabelText('试验 A'),{target:{value:'c'}});
    expect(reads.get('a')!.signal.aborted).toBe(true);expect(reads.get('b')!.signal.aborted).toBe(false);
    await act(async()=>{reads.get('a')!.finish(jobs[0]);reads.get('b')!.finish(jobs[1]);reads.get('c')!.finish(jobs[2]);});
    expect(screen.getByLabelText('试验 A')).toHaveValue('c');expect(screen.getByLabelText('试验 B')).toHaveValue('b');
    expect(api.enqueue).not.toHaveBeenCalled();
  });

  it('refuses to restore an old revision before replacing the current draft', async () => {
    const old={...queued,id:'old-revision',revision:0,status:'completed',result:{...result,input_snapshot:{...project.project,revision:0},request:{...queued.request,experiment:{...experiment,impact:{...experiment.impact,severity:0.9}}}}} as LabRun;
    vi.mocked(api.listRuns).mockResolvedValue([old]);vi.mocked(api.readRun).mockResolvedValue(old);
    render(<DamageLabPage projectId="p" onBack={vi.fn()} onProject={vi.fn()} />);
    await screen.findByRole('button',{name:'运行命中试验'});
    fireEvent.click(document.querySelector('.lab-record button') as HTMLElement);
    await screen.findByText(/属于其他修订/);expect(screen.getByLabelText('命中强度')).toHaveValue('0.5');
  });
});
