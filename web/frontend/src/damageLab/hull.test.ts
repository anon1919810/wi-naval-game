import { describe, expect, it, vi } from 'vitest';
import { buildHullEnvelope, cutHullFaces } from './hull';
import type { Vec3 } from './types';

// Load the actual Python fixture through the test runner, outside Vite's public root.
const { readFileSync } = await vi.importActual<{
  readFileSync(path: string, encoding: 'utf8'): string;
}>('node:fs');

const rectangle = [[-2,0],[2,0],[2,4],[-2,4]];
const boxStations: Array<[number,number[][]]> = [[10,rectangle],[12,rectangle],[14,rectangle]];
const area = (points: number[][]) => points.reduce((sum,p,i)=>sum+p[0]*points[(i+1)%points.length][1]-p[1]*points[(i+1)%points.length][0],0)/2;
const volume = (faces: Vec3[][]) => faces.reduce((sum,f)=>sum+f.slice(1,-1).reduce((s,b,i)=>{
  const a=f[0],c=f[i+2];
  return s+(a[0]*(b[1]*c[2]-b[2]*c[1])+a[1]*(b[2]*c[0]-b[0]*c[2])+a[2]*(b[0]*c[1]-b[1]*c[0]))/6;
},0),0);

describe('canonical hull envelope',()=>{
  it('closes the declared keel, deck and both end profiles with outward normals',()=>{
    const hull=buildHullEnvelope(boxStations,0);
    expect(volume(hull.faces)).toBeCloseTo(64,8);
    expect(hull.faces.some(f=>f.every(p=>p[0]===10))).toBe(true);
    expect(hull.faces.some(f=>f.every(p=>p[0]===14))).toBe(true);
    expect(hull.faces.some(f=>f.every(p=>p[2]===4))).toBe(true);
  });
  it('preserves every original vessel corner and every section area exactly',()=>{
    const project=JSON.parse(readFileSync('../../tools/plimsoll/cases/damage_lab/synthetic-vessel.project.json','utf8'));
    const stations=project.geometry.offsets.stations as Array<[number,number[][]]>;
    const hull=buildHullEnvelope(stations,0);
    stations.forEach(([x,polygon],i)=>{
      const contour=hull.sections[i];
      for(const [y,z] of polygon)expect(contour.some(p=>Math.hypot(p[0]-x,p[1]-y,p[2]-z)<1e-8)).toBe(true);
      expect(area(contour.map(p=>[p[1],p[2]]))).toBeCloseTo(area(polygon),7);
    });
  });
  it('aligns unequal vertex counts, reversed windings and cyclic origins without a twisted loft',()=>{
    const split=[[-2,4],[-2,2],[-2,0],[0,0],[2,0],[2,4],[0,4]];
    const hull=buildHullEnvelope([[10,rectangle],[12,[...split].reverse()],[14,[...rectangle.slice(2),...rectangle.slice(0,2)]]],0);
    expect(volume(hull.faces)).toBeCloseTo(64,8);
    for(const section of hull.sections)expect(area(section.map(p=>[p[1],p[2]]))).toBeCloseTo(16,8);
    for(const f of hull.faces.filter(f=>!f.every(p=>p[0]===f[0][0]))) {
      // Identical physical contours must make parallel longitudinal strips.
      expect(f[0][1]).toBeCloseTo(f[f.length-1][1],8);
      expect(f[0][2]).toBeCloseTo(f[f.length-1][2],8);
    }
  });
  it('handles a shifted raw keel datum and non-centered station coordinates',()=>{
    const hull=buildHullEnvelope(boxStations.map(([x,p])=>[x,p.map(([y,z])=>[y,z-7])]),-7);
    expect(Math.min(...hull.faces.flat().map(p=>p[0]))).toBe(10);
    expect(Math.max(...hull.faces.flat().map(p=>p[0]))).toBe(14);
    expect(Math.min(...hull.faces.flat().map(p=>p[2]))).toBe(0);
    expect(Math.max(...hull.faces.flat().map(p=>p[2]))).toBe(4);
    expect(volume(hull.faces)).toBeCloseTo(64,8);
  });
  it('triangulates concave end sections without filling the missing notch',()=>{
    const concave=[[0,0],[2,0],[2,1],[1,1],[1,2],[0,2]];
    expect(volume(buildHullEnvelope([[0,concave],[2,concave],[4,concave]],0).faces)).toBeCloseTo(12,8);
  });
  it('keeps the deck edge on the deck when adjacent stations narrow sharply',()=>{
    const wide=[[-4,0],[4,0],[4,4],[-4,4]],narrow=[[-.2,2],[.2,2],[.2,4],[-.2,4]];
    const hull=buildHullEnvelope([[0,wide],[2,wide],[4,narrow]],0);
    for(const f of hull.faces.filter(f=>f.length===4)){
      const deckEdge=(a:Vec3,b:Vec3)=>a[2]===4 && b[2]===4 && Math.abs(a[1]-b[1])>1e-8;
      if(deckEdge(f[0],f[1]) || deckEdge(f[2],f[3]))expect(f.every(p=>Math.abs(p[2]-4)<1e-8)).toBe(true);
    }
  });
});

describe('local starboard cutaway',()=>{
  it('cuts the original triangles without reshaping a nonplanar shell panel',()=>{
    // The original fan diagonal from a to c crosses y=0 at (2,0,.5).
    // Clipping this nonplanar quad as one polygon would instead yield z=.25 there.
    const face:Vec3[]=[[0,-2,0],[0,2,0],[4,2,1],[4,-2,0]];
    const cut=cutHullFaces([face]);
    expect(cut.flat().some(p=>Math.hypot(p[0]-2,p[1],p[2]-.5)<1e-9)).toBe(true);
    expect(cut.flat().every(p=>p[1]<=0)).toBe(true);
  });
  it('retains the port shell and half deck while opening the center plane',()=>{
    const full=buildHullEnvelope(boxStations,0),cut=cutHullFaces(full.faces);
    expect(cut.length).toBeGreaterThan(0);
    expect(cut.flat().every(p=>p[1]<=1e-9)).toBe(true);
    expect(cut.flat().some(p=>p[1]===-2)).toBe(true);
    expect(cut.flat().some(p=>Math.abs(p[1])<1e-9)).toBe(true);
    expect(cut.some(f=>f.every(p=>p[2]===4))).toBe(true);
    expect(cut.some(f=>f.every(p=>Math.abs(p[1])<1e-9))).toBe(false);
    expect(full.faces.flat().some(p=>p[1]===2)).toBe(true);
  });
});
