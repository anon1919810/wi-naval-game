import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { boundaryCandidates, FragmentEvidence } from './Detonation';
import type { Experiment, Fragmentation, LabState, Room } from './types';

afterEach(cleanup);
const room=(id:string,x:number)=>({id,x_m:x,y_m:0,keel_to_bottom_m:0,length_m:4,beam_m:2,height_m:2}) as Room;
const experiment={modules:[{id:'engine',label:'Engine'}],crew_groups:[]} as unknown as Experiment;
const report={compartment_id:'a',position_m:[0,0,1],seed:42,fragment_count:1,boundaries:[],module_exposure:{engine:.2},
  traces:[{index:0,termination:'sealed_boundary',blocked_by:'wall',segments:[{compartment_id:'a',transmission:1}],hits:[{kind:'module',id:'engine',exposure:.2}]}]} as unknown as Fragmentation;

it('offers one shared boundary and never offers it as a sea face',()=>{
  const candidates=boundaryCandidates([room('a',0),room('b',4)]);
  expect(candidates.filter(c=>c.to_id!=='sea')).toHaveLength(1);
  expect(candidates.filter(c=>c.to_id==='sea')).toHaveLength(10);
  expect(candidates.some(c=>c.to_id==='sea'&&c.position_m[0]===2)).toBe(false);
});

it('hides future paths before detonation and links accepted paths to modules',()=>{
  const onTrace=vi.fn(),onInspect=vi.fn();
  const {rerender}=render(<FragmentEvidence report={report} state={null} experiment={experiment} selected={null} onTrace={onTrace} onInspect={onInspect} />);
  expect(screen.queryByText('Engine')).not.toBeInTheDocument();
  expect(screen.getByText(/当前是起爆前状态/)).toBeInTheDocument();
  rerender(<FragmentEvidence report={report} state={{detonation_occurred:true} as LabState} experiment={experiment} selected={null} onTrace={onTrace} onInspect={onInspect} />);
  fireEvent.click(screen.getByRole('button',{name:'检查路径 ↗'}));
  expect(onTrace).toHaveBeenCalledWith(0);
  expect(onInspect).toHaveBeenCalledWith({kind:'module',id:'engine'});
});
