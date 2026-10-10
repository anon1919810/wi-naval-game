import type { Box, Equilibrium, Room, TankState, Vec3 } from './types';

/** Raw offsets have a geometry datum; layout points are already keel-relative. */
export const bodyPoint = ([x, y, z]: Vec3, keelOffset = 0): Vec3 => [x, z-keelOffset, -y];
export const roomBox = (r: Room): Box => ({ center_m: [r.x_m, r.y_m, r.keel_to_bottom_m+r.height_m/2], size_m: [r.length_m, r.beam_m, r.height_m] });
export const seaHeight = (e: Pick<Equilibrium, 'p' | 'q' | 'waterline_d_m'>, keelOffset: number) =>
  (e.waterline_d_m-keelOffset)/Math.sqrt(1+e.p*e.p+e.q*e.q);

/** Same orthonormal axes as the core, expressed in Three's Y-up coordinates. */
export function attitudeRows(p: number, q: number): Vec3[] {
  const s = Math.sqrt(1+p*p+q*q), t = Math.sqrt(1+q*q);
  return [[(1+q*q)/(s*t), p/(s*t), p*q/(s*t)], [-p/s, 1/s, q/s], [0, -q/t, 1/t]];
}

export function clippedBoxFaces(box: Box, normal: Vec3, offset: number): Vec3[][] {
  const points: Vec3[] = [];
  for (let i=0; i<8; i++) points.push(box.center_m.map((c, a) => c+((i>>a)&1 ? 1 : -1)*box.size_m[a]/2) as Vec3);
  const indices = [[0, 2, 3, 1], [4, 5, 7, 6], [0, 1, 5, 4], [2, 6, 7, 3], [0, 4, 6, 2], [1, 3, 7, 5]];
  const distance = (p: Vec3) => p.reduce((sum, v, i) => sum+v*normal[i], -offset);
  const cap: Vec3[] = [], faces: Vec3[][] = [];
  for (const face of indices) {
    const clipped: Vec3[] = [];
    for (let i=0; i<face.length; i++) {
      const a=points[face[i]], b=points[face[(i+1)%face.length]], da=distance(a), db=distance(b);
      if (da<=1e-9) clipped.push(a);
      if (da>1e-9 && db<-1e-9 || da<-1e-9 && db>1e-9) {
        const f=da/(da-db), intersection = a.map((v,j)=>v+(b[j]-v)*f) as Vec3;
        clipped.push(intersection);
        if (!cap.some(p=>Math.hypot(...p.map((v,j)=>v-intersection[j]))<1e-8)) cap.push(intersection);
      }
    }
    if (clipped.length>=3) faces.push(clipped);
  }
  if (cap.length>=3) {
    const center = cap.reduce((sum,p)=>sum.map((v,i)=>v+p[i]/cap.length) as Vec3, [0,0,0] as Vec3);
    const u = cap[0].map((v,i)=>v-center[i]) as Vec3;
    const v: Vec3 = [normal[1]*u[2]-normal[2]*u[1], normal[2]*u[0]-normal[0]*u[2], normal[0]*u[1]-normal[1]*u[0]];
    const angle=(p: Vec3)=>Math.atan2(p.reduce((s,c,i)=>s+(c-center[i])*v[i],0)/Math.hypot(...v),
                                    p.reduce((s,c,i)=>s+(c-center[i])*u[i],0)/Math.hypot(...u));
    cap.sort((a,b)=>angle(a)-angle(b)); faces.push(cap);
  }
  return faces;
}

/** Full native tanks have no internal free surface; missing partial planes stay unknown. */
export function acceptedWaterFaces(box: Box, tank: TankState): Vec3[][] {
  if(tank.volume_m3<=0)return [];
  if(tank.fill_fraction>=1)return clippedBoxFaces(box,[0,0,1],box.center_m[2]+box.size_m[2]/2);
  if(!tank.plane_normal || tank.plane_offset_m==null)return [];
  return clippedBoxFaces(box,tank.plane_normal,tank.plane_offset_m);
}

export function resamplePolygon(points: number[][], count=32): number[][] {
  const lengths = points.map((p,i)=>Math.hypot(...p.map((v,j)=>v-points[(i+1)%points.length][j])));
  const total=lengths.reduce((a,b)=>a+b,0);
  if (!total) return [];
  return Array.from({length: count}, (_,k)=>{
    let position=k*total/count, index=0;
    while (index<lengths.length-1 && position>=lengths[index]) { position-=lengths[index]; index++; }
    const a=points[index], b=points[(index+1)%points.length], f=lengths[index] ? position/lengths[index] : 0;
    return a.map((v,j)=>v+(b[j]-v)*f);
  });
}
