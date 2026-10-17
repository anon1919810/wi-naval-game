import { StrictMode } from 'react';
import { act,cleanup,fireEvent,render,screen,waitFor } from '@testing-library/react';
import { afterEach,beforeEach,expect,it,vi } from 'vitest';
import { Workbench } from '../pages/Workbench';
import { Sps3b3Readings } from '../components/Sps3b3Readings';
import { Sps3b3Queue,readSps3b3Catalog,withSps3b3Design } from '../components/sps3b3Model';
import { workspaceCopy } from '../i18n/workspace';
import type { DesignReply,ProjectDocument,ShipDesign,Sps3b3Design,Sps3b3Preview } from '../types';
import * as api from '../api';

// The workbench no longer previews through the compatibility endpoint: the one
// authoritative declaration is the native design, so the host is wired to the
// `design/*` endpoints. The remaining tests here exercise the recovered queue and
// widgets directly and need none of these.
vi.mock('../api',async original=>({...await original<typeof import('../api')>(),getProject:vi.fn(),listRuns:vi.fn(),getRun:vi.fn(),saveProject:vi.fn(),enqueueRun:vi.fn(),designCatalog:vi.fn(),designInitialize:vi.fn(),designPreview:vi.fn()}));
const w=(key:any)=>workspaceCopy('en',key);
const design:Sps3b3Design={schema:'plimsoll-sps3b3-design-1',source:'controlled test',parameters:{ship_name:'Original',length_waterline:180},editing:{},notes:''};
const project:ProjectDocument={schema:'plimsoll-project-1',id:'p1',name:'SPS test',revision:1,hull:{length_m:90,beam_m:20,draft_m:4},geometry:null,weight_groups:[],loading_conditions:[{id:'loaded',label:'Loaded'}],sps_3b3_design:design};
const catalogue={fields:{ship_name:{name:'ship_name',page:'hull',label:'Ship name',kind:'text'},length_waterline:{name:'length_waterline',page:'hull',label:'Length at waterline',kind:'number'}},page_order:['hull','freeboard','guns','weapons','armour','engine','performance'],pages:Object.fromEntries(['hull','freeboard','guns','weapons','armour','engine','performance'].map(page=>[page,{fields:page==='hull'?['ship_name','length_waterline']:[]}]))};

/** The whole governed project the core answers with: one declaration, no legacy section. */
function governed(parameters:Record<string,unknown>):ProjectDocument {
  const base:Record<string,unknown>={...(project as unknown as Record<string,unknown>)};
  delete base.sps_3b3_design;
  base.hull={...(project.hull),lwl_m:parameters.length_waterline??null};
  base.ship_design={schema:'plimsoll-ship-design-1',source:'controlled test',parameters,editing:{},notes:null,condition_id:'loaded',mass_bindings:{}};
  return base as unknown as ProjectDocument;
}
/** One reply: the command applied to the declaration it was asked from. */
function nativeReply(command?:Record<string,unknown>,base:Sps3b3Design=design):DesignReply {
  const parameters={...base.parameters};
  if(command?.kind==='set_parameter')parameters[String(command.name)]=command.value??null;
  return {project:governed(parameters),design:{schema:'plimsoll-sps3b3-design-1',source:base.source,parameters,editing:{},notes:null},preview:null,status:'available',diagnostics:[]};
}
function reply(base:Sps3b3Design,command?:Record<string,unknown>):Sps3b3Preview {
  const next=structuredClone(base);
  if(command?.kind==='set_parameter')next.parameters[String(command.name)]=command.value;
  return {design:next,preview:{status:'available',design:next,hull:{length:590.55}},diagnostics:[],status:'available'};
}
beforeEach(()=>{
  vi.clearAllMocks();vi.mocked(api.getProject).mockResolvedValue({project_id:'p1',revision:1,project});
  vi.mocked(api.listRuns).mockResolvedValue([]);vi.mocked(api.designCatalog).mockResolvedValue(catalogue as any);
  vi.mocked(api.designInitialize).mockImplementation(async()=>nativeReply());
  vi.mocked(api.designPreview).mockImplementation(async(_project,command,base)=>nativeReply(command,base));
  vi.mocked(api.saveProject).mockImplementation(async(_,input)=>({project_id:'p1',revision:2,project:input.project}));
  vi.mocked(api.enqueueRun).mockResolvedValue({id:'new-run',status:'queued'} as any);
});
afterEach(cleanup);

it('upgrades a legacy project under StrictMode, permits serial text and number edits, blocks saving until they settle, then saves the native declaration and runs its one stage',async()=>{
  let finishName!:(reply:DesignReply)=>void;
  vi.mocked(api.designPreview).mockImplementation((_project,command,base)=>{
    if(command?.kind==='set_parameter'&&command.name==='ship_name')return new Promise<DesignReply>(resolve=>{finishName=resolve;});
    return Promise.resolve(nativeReply(command,base));
  });
  const onRun=vi.fn();
  render(<StrictMode><Workbench projectId="p1" onBack={vi.fn()} onRun={onRun}/></StrictMode>);
  // The old compatibility section is upgraded once, by the core, into the one
  // declaration; the legacy section is exactly what the upgrade is asked for, and
  // the request is not replayed by StrictMode's doubled mount effects.
  await waitFor(()=>expect(api.designCatalog).toHaveBeenCalled());
  expect(api.designInitialize).toHaveBeenCalledTimes(1);
  const upgraded=vi.mocked(api.designInitialize).mock.calls[0][0] as Record<string,unknown>;
  expect(upgraded.sps_3b3_design).toBeTruthy();expect(upgraded.ship_design).toBeUndefined();
  // Settle the upgrade's own preview refresh, so the first edit below is not queued behind it.
  await waitFor(()=>expect(screen.getByRole('button',{name:w('workbench.save.action')})).toBeEnabled());
  // The upgraded project opens on its own ordinary hull chapter.
  fireEvent.click(await screen.findByRole('button',{name:w('chapter.hull.label')}));
  const name=await screen.findByLabelText('Ship name');
  fireEvent.change(name,{target:{value:'Edited ship'}});fireEvent.blur(name);
  await waitFor(()=>expect(finishName).toBeTypeOf('function'));
  // A declared edit still in the air blocks the save.
  expect(screen.getByRole('button',{name:w('workbench.save.action')})).toBeDisabled();
  // The next declared field is still editable: the queue is serial, not modal.
  const length=screen.getByLabelText('Length at waterline');
  expect(length).not.toBeDisabled();fireEvent.change(length,{target:{value:'190'}});fireEvent.blur(length);
  await act(async()=>{finishName(nativeReply({kind:'set_parameter',name:'ship_name',value:'Edited ship'},design));});
  await waitFor(()=>expect(screen.getByRole('button',{name:w('workbench.save.action')})).toBeEnabled());
  fireEvent.click(screen.getByRole('button',{name:w('workbench.save.action')}));
  await waitFor(()=>expect(api.saveProject).toHaveBeenCalled());
  const saved=vi.mocked(api.saveProject).mock.calls[0][1].project;
  // The one canonical declaration is what is saved; the legacy section is gone.
  expect(saved.sps_3b3_design).toBeUndefined();
  expect((saved.ship_design as ShipDesign).parameters).toMatchObject({ship_name:'Edited ship',length_waterline:190});
  // The native request is exactly the one design stage, never the compatibility one.
  await waitFor(()=>expect(screen.getByRole('button',{name:w('workbench.run.action')})).toBeEnabled());
  fireEvent.click(screen.getByRole('button',{name:w('workbench.run.action')}));
  await waitFor(()=>expect(api.enqueueRun).toHaveBeenCalledWith('p1',expect.objectContaining({revision:2,options:{stages:['ship_design']}})));
});

it('drops an old asynchronous queue reply when the confirmed project baseline changes',async()=>{
  let resolveOld!:(value:Sps3b3Preview)=>void;
  let calls=0;
  const queue=new Sps3b3Queue({catalogue:()=>readSps3b3Catalog(catalogue),scaleRefsOf:()=>[],allScaleNames:()=>[],confirm:request=>++calls===1?new Promise<Sps3b3Preview>(resolve=>{resolveOld=resolve;}):Promise.resolve(reply(request.design,request.command))});
  queue.start(design);
  const replacement={...design,parameters:{...design.parameters,ship_name:'Another project'}};
  queue.start(replacement);
  await act(async()=>{resolveOld(reply(design));await Promise.resolve();});
  expect(queue.getState().confirmed?.parameters.ship_name).toBe('Another project');
  expect(queue.getState().pending).toBe(0);queue.dispose();
});

it('renders the stored report and exposes downloads for its exact saved run',()=>{
  render(<Sps3b3Readings runId="owned-run" data={{status:'available',report:{text:'Frozen text',sections:[{id:'armour',title:'Armour:',lines:['Frozen armour 123 tons']}]}}}/>);
  expect(screen.getByText('Frozen armour 123 tons')).toBeVisible();
  for(const format of ['sship','txt','rtf','ssr'])expect(document.querySelector(`a[href="/api/runs/owned-run/export?format=${format}"]`)).not.toBeNull();
});

it('enables a runnable design identity on a blank project without inventing mass or CG',()=>{
  const blank={...project,loading_conditions:[]};
  const next=withSps3b3Design(blank,design);
  expect(next.loading_conditions).toEqual([{id:'sps-design',label:'SPS 3b3 design'}]);
  expect(next.weight_groups).toEqual([]);expect(next.geometry).toBeNull();expect(next.hull).toBe(blank.hull);
  expect(withSps3b3Design(project,design).loading_conditions).toBe(project.loading_conditions);
});
