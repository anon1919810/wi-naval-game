import { describe, expect, it } from 'vitest';
import { compareReports } from '../components/reportComparison';
import { zhCopy as w } from './locale';
import type { AnalysisResult, RunView, StageEnvelope } from '../types';
const stage = (data: Record<string,unknown>, over: Partial<StageEnvelope> = {}): StageEnvelope => ({status:'completed',requested:true,reason:null,assumptions:[],diagnostics:[],method_versions:{kernel:'1'},validity:{complete:true,converged:true,model_applicable:true,historical_validated:null},data,...over});
const result = (stages: AnalysisResult['stages'], over: Partial<AnalysisResult> = {}): AnalysisResult => ({schema:'plimsoll-analysis-1',status:'completed',project_id:'p',condition_id:'normal',project_fingerprint:'p',input_fingerprint:'i',request_fingerprint:'r',request:{},input_snapshot:{id:'p',revision:1,hull:{loa_m:90}},units:{mass:'t'},method_versions:{coordinator:'1'},sources:{},diagnostics:[],validity:{complete:true,converged:true,model_applicable:true,historical_validated:null},stages,...over} as AnalysisResult);
const cells = (a:AnalysisResult,b:AnalysisResult) => compareReports({result:a},{result:b},w).groups.flatMap(g=>g.cells);
describe('frozen report comparison',()=>{
  it('reads actual nested mass, hydrostatics and propulsion outputs',()=>{
    const a=result({loading:stage({values:{total_mass_t:900}}),hydrostatics:stage({values:{awp_m2:100}}),propulsion:stage({values:{power_design_kw:1000}})});
    const b=result({loading:stage({values:{total_mass_t:880}}),hydrostatics:stage({values:{awp_m2:130}}),propulsion:stage({values:{power_design_kw:1200}})});
    const values=cells(a,b);
    expect(values.map(c=>c.delta)).toEqual([-20,30,200]);
    expect(values[0].path).toBe('stages.loading.data.values.total_mass_t');
  });
  it('knows canonical hydrostatic length units without treating every m/kn suffix as convertible',()=>{
    const a=result({hydrostatics:stage({values:{lcb_m:1,reference_draft_midships_m:2,ambiguous_kn:3}})});
    const b=result({hydrostatics:stage({values:{lcb_m:2,reference_draft_midships_m:3,ambiguous_kn:4}})});
    const rows=cells(a,b);expect(rows.find(r=>r.key==='lcb_m')).toMatchObject({dimension:'length',storedUnit:'m',delta:1});expect(rows.find(r=>r.key==='reference_draft_midships_m')!.delta).toBe(1);expect(rows.find(r=>r.key==='ambiguous_kn')!.delta).toBeNull();
  });
  it('keeps true zero, missing and nonfinite values distinct',()=>{
    const a=result({loading:stage({values:{known_mass_t:0,total_mass_t:null,lcg_m:Infinity}})});
    const b=result({loading:stage({values:{known_mass_t:0,total_mass_t:880,lcg_m:4}})});
    const byKey=Object.fromEntries(cells(a,b).map(c=>[c.key,c]));
    expect(byKey.known_mass_t).toMatchObject({state:'known',delta:0});
    expect(byKey.total_mass_t).toMatchObject({state:'unknown',delta:null});
    expect(byKey.lcg_m).toMatchObject({state:'unknown',delta:null});
  });
  it('lists snapshot and request changes while allowing the same project across revisions',()=>{
    const a=result({loading:stage({values:{total_mass_t:900}})});
    const b=structuredClone(a);b.input_snapshot.revision=2;b.input_snapshot.hull.loa_m=95;b.request={stages:['loading','gz']};
    const comparison=compareReports({result:a,revision:1},{result:b,revision:2},w);
    expect(comparison.compatible).toBe(true);expect(comparison.comparison.revision).toBe(2);
    expect(comparison.inputChanges.join(' ')).toContain('input.hull.loa_m');
    expect(comparison.inputChanges.join(' ')).toContain('request.stages');
    expect(comparison.warnings.join(' ')).toContain('不能直接归因');
    const c=structuredClone(a);c.input_snapshot.weight_groups=[{id:'lightship',items:[{id:'base-mass',mass_t:900}]}] as never;
    const d=structuredClone(c);d.input_snapshot.weight_groups[0].items[0].mass_t=910;
    expect(compareReports({result:c},{result:d},w).inputChanges.join(' ')).toContain('input.weight_groups[0].items[0].mass_t');
  });
  it('does not mistake property order for a changed method or input',()=>{
    const a=result({loading:stage({values:{total_mass_t:900}})},{method_versions:{a:'1',b:'2'}});
    const b=structuredClone(a);b.method_versions={b:'2',a:'1'};
    expect(compareReports({result:a},{result:b},w).inputChanges).toEqual([]);
    expect(compareReports({result:a},{result:b},w).compatible).toBe(true);
  });
  it.each(['project','condition','method','kernel'] as const)('withholds differences for a changed %s basis',kind=>{
    const a=result({loading:stage({values:{total_mass_t:900}})}),b=structuredClone(a);
    if(kind==='project'){b.project_id='other';b.input_snapshot.id='other';}
    if(kind==='condition')b.condition_id='ballast';
    if(kind==='method')b.method_versions={coordinator:'2'};
    if(kind==='kernel')b.stages.loading.method_versions={kernel:'2'};
    const comparison=compareReports({result:a},{result:b},w);
    expect(comparison.compatible).toBe(false);expect(cells(a,b)[0].delta).toBeNull();
  });
  it('checks run wrapper identity against its frozen result',()=>{
    const a=result({loading:stage({values:{total_mass_t:900}})});
    const run={id:'run-a',project_id:'p',revision:2,condition_id:'normal',status:'completed',request_fingerprint:'r',result:a} as RunView;
    expect(compareReports({result:a,run},{result:a},w).compatible).toBe(false);
  });
  it('keeps an unrequested or failed stage from exposing residual numbers',()=>{
    const a=result({deck:stage({minimum_clearance_m:4.2})});
    const b=result({deck:stage({minimum_clearance_m:4.4},{requested:false,status:'not_requested'})});
    expect(cells(a,b)[0]).toMatchObject({state:'unrequested',current:4.2,comparison:null,delta:null});
    b.stages.deck=stage({minimum_clearance_m:4.4},{status:'failed'});
    expect(cells(a,b)[0].comparison).toBeNull();
  });
  it('compares valid completed stages within an overall partial run',()=>{
    const a=result({loading:stage({values:{total_mass_t:900}})},{status:'partial'});
    const b=result({loading:stage({values:{total_mass_t:950}})},{status:'canceled'});
    expect(cells(a,b)[0].delta).toBe(50);
  });
  it('matches resistance points by speed and GZ by angle, never by row order',()=>{
    const point=(speed:number,value:number)=>({speed_kn:speed,total_resistance_kn:value,complete:true,primary_result:true,model_applicable:true});
    const a=result({resistance:stage({rows:[point(10,100),point(12,150)]}),gz:stage({rows:[{angle_deg:0,gz_m:0},{angle_deg:20,gz_m:0.4}]})});
    const b=result({resistance:stage({rows:[point(12,160),point(10,110)]}),gz:stage({rows:[{angle_deg:20,gz_m:0.5},{angle_deg:0,gz_m:0}]})});
    expect(cells(a,b).map(c=>c.delta)).toEqual([10,10,0,0.09999999999999998]);
    expect(cells(a,b)[0].canonicalUnit).toBe('kN');
  });
  it('withholds duplicated and out-of-scope points without interpolation',()=>{
    const point={speed_kn:10,shaft_power_kw:1000,complete:true,primary_result:true,model_applicable:true};
    const a=result({resistance:stage({power_rows:[point]})});
    const b=result({resistance:stage({power_rows:[point,{...point,shaft_power_kw:1200}]})});
    expect(cells(a,b).every(c=>c.delta===null)).toBe(true);
    b.stages.resistance=stage({power_rows:[{...point,model_applicable:false}]});
    expect(cells(a,b)[0].state).toBe('incompatible');
  });
  it('warns when snapshots or methods are unavailable and never mutates evidence',()=>{
    const a=result({loading:stage({values:{total_mass_t:900}})});const b=structuredClone(a);b.input_snapshot={} as never;b.method_versions=undefined as never;
    const before=JSON.stringify([a,b]);const c=compareReports({result:a},{result:b},w);
    expect(c.warnings.join(' ')).toContain('缺少输入快照');expect(c.compatible).toBe(false);expect(JSON.stringify([a,b])).toBe(before);
  });
});
