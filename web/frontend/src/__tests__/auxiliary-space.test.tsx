import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, expect, it } from 'vitest';
import { ConceptDesignEditor } from '../components/ConceptDesignEditor';
import { ConceptComponentReadings } from '../components/ConceptComponentReadings';
import { newConcept } from '../components/conceptDesign';
import { UnitProvider } from '../components/UnitProvider';
import { reportMetrics } from '../components/reportMetrics';
import { compareReports } from '../components/reportComparison';
import { workspaceCopy } from '../i18n/workspace';
import type { AnalysisResult, ProjectDocument, StageEnvelope } from '../types';

afterEach(cleanup);
const cfg=()=>({...newConcept(),auxiliary_weapons:[{id:'tube',kind:'torpedo',count:8,loads:3},
  {id:'mine',kind:'mine',count:3},{id:'sub',kind:'torpedo',count:4}],auxiliary_space:{source:null,torpedo_ids:['tube'],bulged_beam_m:null}});
function Editor({enabled=true}:{enabled?:boolean}) {
  const initial=cfg();if(!enabled)delete (initial as Record<string,unknown>).auxiliary_space;
  const [project,setProject]=useState({schema:'plimsoll-project-1',id:'p',revision:1,name:'study',
    hull:{beam_m:18},weight_groups:[],systems:{},loading_conditions:[],concept_design:initial} as unknown as ProjectDocument);
  return <UnitProvider preferences={null}><ConceptDesignEditor project={project} onChange={setProject}/>
    <output data-testid="draft">{JSON.stringify(project)}</output></UnitProvider>;
}
it('enables a scope with unknown references without selecting a row',()=>{
  render(<Editor enabled={false}/>);
  fireEvent.click(screen.getByRole('checkbox',{name:'Enable torpedo space reading'}));
  const p=JSON.parse(screen.getByTestId('draft').textContent!);
  expect(p.concept_design.auxiliary_space.torpedo_ids).toBeNull();
  expect(p.concept_design.auxiliary_space.bulged_beam_m).toBeNull();
});
it('protects referenced rows against removal, kind changes and renaming',()=>{
  render(<Editor/>);
  expect(screen.getAllByRole('button',{name:'Delete this auxiliary weapon'})[0]).toBeDisabled();
  expect(screen.getAllByLabelText('Recovered family')[0]).toBeDisabled();
  expect(screen.getAllByLabelText('Weapon id')[0]).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Space torpedo row 1'),{target:{value:''}});
  expect(screen.getAllByRole('button',{name:'Delete this auxiliary weapon'})[0]).not.toBeDisabled();
  fireEvent.click(screen.getAllByRole('button',{name:'Delete this auxiliary weapon'})[0]);
  expect(JSON.parse(screen.getByTestId('draft').textContent!).concept_design.auxiliary_weapons.map((r:any)=>r.id)).toEqual(['mine','sub']);
});

it('keeps unknown distinct from explicit empty scope and filters nontorpedo choices',()=>{
  render(<Editor/>);
  const select=screen.getByLabelText('Space torpedo row 2') as HTMLSelectElement;
  expect([...select.options].map(o=>o.value)).toEqual(['','tube','sub']);
  expect([...select.options].find(o=>o.value==='tube')!.disabled).toBe(true);
  fireEvent.change(select,{target:{value:'sub'}});
  expect(JSON.parse(screen.getByTestId('draft').textContent!).concept_design.auxiliary_space.torpedo_ids).toEqual(['tube','sub']);
  fireEvent.click(screen.getByLabelText('The torpedo selection is explicit'));
  expect(JSON.parse(screen.getByTestId('draft').textContent!).concept_design.auxiliary_space.torpedo_ids).toBeNull();
  fireEvent.click(screen.getByLabelText('The torpedo selection is explicit'));
  expect(JSON.parse(screen.getByTestId('draft').textContent!).concept_design.auxiliary_space.torpedo_ids).toEqual([]);
});

const method='sps-3b3-auxiliary-space-v1';
function reading(id:string,deck=12):Record<string,any>{return {id,method_version:method,status:'partial',
  values:{deck_area_m2:deck,hull_volume_m3:4,deck_ratio:.1,hull_ratio:null},
  availability:Object.fromEntries(['deck_area_m2','hull_volume_m3','deck_ratio','hull_ratio']
    .map(key=>[key,{state:key==='hull_ratio'?'unavailable':'available'}])),diagnostics:[],provenance:{}};}
function stage(records=[reading('tube'),reading('sub',0)],over:Record<string,any>={}):StageEnvelope {
  return {requested:true,status:'completed',method_versions:{kernel:'sps-3b3-adapted-v1',methods:{auxiliary_space:method}},
    validity:{complete:true},data:{auxiliary_space:{...reading('selected_torpedoes'),records,...over}}} as unknown as StageEnvelope;
}
function result(stage:StageEnvelope):AnalysisResult {return {project_id:'p',condition_id:'normal',
  method_versions:{coordinator:'analysis-1'},units:{mass:'t'},request_fingerprint:'request',request:{},
  input_snapshot:{id:'p',revision:1},stages:{design_balance:stage}} as unknown as AnalysisResult;}

it('compares by selected record IDs after reordering and keeps missing fields unavailable',()=>{
  const a=stage(),b=stage([reading('sub',0),reading('tube',15)]);
  const comparison=compareReports({result:result(a)},{result:result(b)},(key,params)=>workspaceCopy('en',key,params));
  const cells=comparison.groups.flatMap(g=>g.cells);
  expect(cells.find(c=>c.path.includes('records[tube]')&&c.key==='auxiliary_space_deck_area_m2')?.delta).toBe(3);
  expect(cells.find(c=>c.path.includes('records[sub]')&&c.key==='auxiliary_space_deck_area_m2')?.delta).toBe(0);
  expect(cells.filter(c=>c.key==='auxiliary_space_hull_ratio').every(c=>c.delta===null)).toBe(true);
  expect(reportMetrics('design_balance',a).filter(m=>m.key==='auxiliary_space_deck_area_m2').every(m=>m.canonicalUnit==='m²')).toBe(true);
});

it.each(['missing','duplicate','own method','family method','parent identity','availability'])('blocks %s identity or availability',reason=>{
  const s=stage();const parent=(s.data as any).auxiliary_space;
  if(reason==='missing')delete parent.records[0].id;
  if(reason==='duplicate')parent.records[1].id='tube';
  if(reason==='own method')parent.records[0].method_version='other';
  if(reason==='family method')delete (s.method_versions as any).methods.auxiliary_space;
  if(reason==='parent identity')parent.id='wrong';
  if(reason==='availability')parent.records[0].availability.deck_area_m2.state='unavailable';
  const metrics=reportMetrics('design_balance',s).filter(m=>m.id.includes(':record:')&&m.key==='auxiliary_space_deck_area_m2');
  expect(metrics.find(m=>m.path.includes(reason==='missing'?'records[?0]':'records[tube]'))?.blocked).toBe(true);
});

it.each([{requested:false,status:'completed'},{requested:true,status:'failed'},{requested:true,status:'unavailable'}])(
  'does not expose full-report numbers when parent gate refuses %j',gate=>{
    const s=stage();Object.assign(s,gate);
    render(<UnitProvider preferences={null}><ConceptComponentReadings data={s.data} envelope={s}/></UnitProvider>);
    expect(screen.queryByText('12.000 m²')).not.toBeInTheDocument();
  });
it('prints independent units and hides residual values behind the full-report gate',()=>{
  const reading={id:'selected_torpedoes',method_version:'sps-3b3-auxiliary-space-v1',status:'partial',
    values:{deck_area_m2:12,hull_volume_m3:4,deck_ratio:.1,hull_ratio:null},
    availability:{deck_area_m2:{state:'available'},hull_volume_m3:{state:'available'},deck_ratio:{state:'available'},
      hull_ratio:{state:'unavailable',reason:'explicit bulged beam missing'}},records:[],diagnostics:[],provenance:{}};
  const {rerender}=render(<UnitProvider preferences={null}><ConceptComponentReadings
    data={{auxiliary_space:reading}} policy="independent"/></UnitProvider>);
  expect(screen.getByText('12.000 m²')).toBeInTheDocument();
  expect(screen.getByText('4.000 m³')).toBeInTheDocument();
  expect(screen.getByText('explicit bulged beam missing')).toBeInTheDocument();
  rerender(<UnitProvider preferences={null}><ConceptComponentReadings data={{auxiliary_space:reading}}
    envelope={{requested:true,status:'failed'} as StageEnvelope} policy="report"/></UnitProvider>);
  expect(screen.queryByText('12.000 m²')).not.toBeInTheDocument();
});
