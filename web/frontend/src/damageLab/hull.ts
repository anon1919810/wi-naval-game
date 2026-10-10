import type { Vec3 } from './types';
import { ShapeUtils, Vector2 } from 'three';

type Contour = { x:number; points:number[][]; knots:number[]; perimeter:number };
const EPS=1e-10;

function contour(x:number, raw:number[][]):Contour {
  if(!Number.isFinite(x) || raw.some(p=>p.length!==2 || p.some(v=>!Number.isFinite(v))))throw new Error('型线包含无效坐标。');
  let points=raw.filter((p,i)=>i===0 || Math.hypot(p[0]-raw[i-1][0],p[1]-raw[i-1][1])>EPS).map(p=>[...p]);
  if(points.length>1 && Math.hypot(points[0][0]-points.at(-1)![0],points[0][1]-points.at(-1)![1])<EPS)points.pop();
  if(points.length<2)throw new Error('型线剖面没有可绘制的边。');
  if(ShapeUtils.area(points.map(p=>new Vector2(...p as [number,number])))<0)points.reverse();
  // Anchor at the port deck corner, independent of file winding/cyclic origin.
  const anchor=points.reduce((best,p,i)=>p[1]>points[best][1]+EPS || Math.abs(p[1]-points[best][1])<=EPS && p[0]<points[best][0] ? i : best,0);
  points=[...points.slice(anchor),...points.slice(0,anchor)];
  const knots=[0];let perimeter=0;
  for(let i=0;i<points.length;i++){
    const a=points[i],b=points[(i+1)%points.length];perimeter+=Math.hypot(a[0]-b[0],a[1]-b[1]);knots.push(perimeter);
  }
  if(perimeter<=EPS)throw new Error('型线剖面长度为零。');
  const starboardDeck=points.reduce((best,p,i)=>p[1]>points[best][1]+EPS || Math.abs(p[1]-points[best][1])<=EPS && p[0]>points[best][0] ? i : best,0);
  const deckStart=knots[starboardDeck];
  // Match sheer edges separately so narrowing stations cannot pull deck into side shell.
  const parameters=starboardDeck>0 && perimeter-deckStart>EPS
    ? knots.slice(0,-1).map(v=>v<=deckStart ? .5*v/deckStart : .5+.5*(v-deckStart)/(perimeter-deckStart))
    : knots.slice(0,-1).map(v=>v/perimeter);
  return {x,points,knots:parameters,perimeter};
}

function at(row:Contour, t:number, keel:number):Vec3 {
  const exact=row.knots.findIndex(k=>Math.abs(t-k)<=EPS);
  if(exact>=0)return [row.x,row.points[exact][0],row.points[exact][1]-keel];
  let edge=row.knots.length-1;
  for(let i=0;i<row.knots.length-1;i++)if(t<row.knots[i+1]){edge=i;break;}
  const a=row.points[edge],b=row.points[(edge+1)%row.points.length],end=row.knots[edge+1] ?? 1;
  const fraction=(t-row.knots[edge])/(end-row.knots[edge]);
  return [row.x,a[0]+(b[0]-a[0])*fraction,a[1]+(b[1]-a[1])*fraction-keel];
}

/** Every original section vertex survives. New points lie on original edges. */
export function buildHullEnvelope(stations:Array<[number,number[][]]>, keelOffset:number):{sections:Vec3[][];faces:Vec3[][]} {
  if(stations.length<2 || !Number.isFinite(keelOffset))throw new Error('需要有效的内联站位型线。');
  const rows=stations.map(([x,p])=>contour(x,p)).sort((a,b)=>a.x-b.x);
  if(rows.some((r,i)=>i>0 && r.x<=rows[i-1].x))throw new Error('型线站位必须互不重复。');
  const knots=rows.flatMap(r=>r.knots).sort((a,b)=>a-b).filter((v,i,all)=>i===0 || v-all[i-1]>EPS);
  // Keep exact corners, or report unavailable; never silently simplify input.
  if(rows.length*knots.length>250000)throw new Error('精确型线检查网格过大；文字报告和计算结果仍可使用。');
  const sections=rows.map(r=>knots.map(t=>at(r,t,keelOffset))),faces:Vec3[][]=[];
  for(let i=1;i<sections.length;i++)for(let j=0;j<knots.length;j++){
    const next=(j+1)%knots.length;
    faces.push([sections[i-1][j],sections[i-1][next],sections[i][next],sections[i][j]]);
  }
  // Ear triangulation also respects concave end profiles. Explicitly orient caps.
  for(const [index,sign] of [[0,-1],[sections.length-1,1]]){
    const section=sections[index],points=section.map(p=>new Vector2(p[1],p[2]));
    for(const indices of ShapeUtils.triangulateShape(points,[])){
      const triangle=indices.map(i=>section[i]);
      const [a,b,c]=triangle;
      const normal=(b[1]-a[1])*(c[2]-a[2])-(b[2]-a[2])*(c[1]-a[1]);
      if(Math.abs(normal)>EPS)faces.push(normal*sign>0 ? triangle : [a,c,b]);
    }
  }
  return {sections,faces};
}

/** Keep the port half shell/deck. The inspection plane deliberately has no cap. */
export function cutHullFaces(faces:Vec3[][]):Vec3[][] {
  const output:Vec3[][]=[];
  // Clip the same fan triangles used by the full renderer. Loft quads may be
  // nonplanar; clipping a quad first would change its retained physical surface.
  for(const polygon of faces)for(let triangle=1;triangle<polygon.length-1;triangle++){
    const face=[polygon[0],polygon[triangle],polygon[triangle+1]];
    const clipped:Vec3[]=[];
    for(let i=0;i<face.length;i++){
      const a=face[i],b=face[(i+1)%face.length],insideA=a[1]<=0,insideB=b[1]<=0;
      if(insideA)clipped.push([...a]);
      if(insideA!==insideB){const t=a[1]/(a[1]-b[1]);clipped.push([a[0]+(b[0]-a[0])*t,0,a[2]+(b[2]-a[2])*t]);}
    }
    const unique=clipped.filter((p,i)=>i===0 || Math.hypot(...p.map((v,j)=>v-clipped[i-1][j]))>EPS);
    if(unique.length>1 && Math.hypot(...unique[0].map((v,j)=>v-unique.at(-1)![j]))<EPS)unique.pop();
    if(unique.length>=3)output.push(unique);
  }
  return output;
}
