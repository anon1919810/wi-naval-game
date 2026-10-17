import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderZh as render, zhCopy as w } from './locale';
import { Workbench } from '../pages/Workbench';
import { ProjectNav } from '../components/ProjectNav';
import * as api from '../api';
import type { ProjectDocument, ProjectView } from '../types';
vi.mock('../api', async original => ({...await original<typeof import('../api')>(),getProject:vi.fn(),saveProject:vi.fn(),listRuns:vi.fn(),getRun:vi.fn(),enqueueRun:vi.fn()}));
const project={schema:'plimsoll-project-1',id:'p',revision:1,name:'Rig',hull:{loa_m:90,beam_m:20,draught_normal_m:4},geometry:null,weight_groups:[],loading_conditions:[{id:'normal',label:'Normal'}]} as ProjectDocument;
const view={project_id:'p',revision:1,project} as ProjectView;
beforeEach(()=>{vi.clearAllMocks();vi.stubGlobal('matchMedia',()=>({matches:false,addEventListener:()=>{},removeEventListener:()=>{}}));vi.mocked(api.getProject).mockResolvedValue(view);vi.mocked(api.listRuns).mockResolvedValue([]);});
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const open=async()=>{render(<Workbench projectId="p" onBack={vi.fn()} onRun={vi.fn()}/>);await screen.findByRole('button',{name:'项目数据'});};
describe('draft and read protection',()=>{
  it('blocks running until unapplied JSON is applied or discarded',async()=>{
    await open();fireEvent.click(screen.getByRole('button',{name:'项目数据'}));
    fireEvent.change(screen.getByLabelText('项目 JSON'),{target:{value:'unapplied'}});
    expect(screen.getByRole('button',{name:'运行计算 ↗'})).toBeDisabled();expect(screen.getByText('JSON 修改尚未应用')).toBeVisible();
    fireEvent.click(screen.getByRole('button',{name:'保存修订'}));expect(api.saveProject).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button',{name:w('editor.json.discard')}));
    expect(screen.getByRole('button',{name:'运行计算 ↗'})).toBeEnabled();expect(api.enqueueRun).not.toHaveBeenCalled();
  });
  it('keeps edits made while a conflict reload is pending',async()=>{
    vi.mocked(api.saveProject).mockRejectedValue(new api.ApiError(409,{current_revision:2}));
    await open();fireEvent.click(screen.getByRole('button',{name:'船型与几何'}));
    fireEvent.change(screen.getByLabelText('船长'),{target:{value:'91'}});fireEvent.click(screen.getByRole('button',{name:'保存修订'}));
    await screen.findByRole('button',{name:'重新载入'});
    let finish!:(v:ProjectView)=>void;vi.mocked(api.getProject).mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve;}));
    fireEvent.click(screen.getByRole('button',{name:'重新载入'}));fireEvent.change(screen.getByLabelText('型宽'),{target:{value:'21'}});
    finish({...view,revision:2,project:{...project,revision:2}});
    await screen.findByText(/重载期间又有新修改/);expect(screen.getByLabelText('型宽')).toHaveValue(21);expect(screen.getByLabelText('船长')).toHaveValue(91);
  });
  it('shows failed history as a failed read and retries without starting a calculation',async()=>{
    vi.mocked(api.listRuns).mockRejectedValueOnce(new Error('offline')).mockResolvedValue([]);
    await open();const title=(await screen.findAllByText('运行记录读取失败')).find(node=>node.closest('.read-failed'))!;
    expect(screen.queryByText(w('overview.history.empty'))).toBeNull();
    fireEvent.click(within(title.closest('.read-failed') as HTMLElement).getByRole('button'));
    await screen.findByText(w('overview.history.empty'));expect(api.listRuns).toHaveBeenCalledTimes(2);expect(api.enqueueRun).not.toHaveBeenCalled();
  });
  it('searches both languages without changing canonical chapter IDs or selecting on typing',()=>{
    const select=vi.fn();render(<ProjectNav name="Rig" active="overview" onSelect={select} onBack={vi.fn()}/>);
    const input=screen.getByRole('searchbox');fireEvent.change(input,{target:{value:'Hull'}});
    expect(screen.getByRole('button',{name:'船型与几何'})).toBeVisible();expect(select).not.toHaveBeenCalled();
    fireEvent.keyDown(input,{key:'Enter'});expect(select).toHaveBeenCalledWith('hull');
    fireEvent.keyDown(input,{key:'Escape'});expect(input).toHaveValue('');expect(document.querySelectorAll('.nav-item')).toHaveLength(12);
  });
});
