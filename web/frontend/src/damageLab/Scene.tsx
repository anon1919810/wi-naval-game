import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import type { ProjectDocument } from '../types';
import type { Experiment, Fragmentation, LabState, Room, Vec3 } from './types';
import { attitudeRows, bodyPoint, acceptedWaterFaces, roomBox, seaHeight } from './geometry';
import { buildHullEnvelope, cutHullFaces, HullGeometryError } from './hull';
import { draftIdentity } from './model';
import type { InspectionTarget } from './narrative';
import { useLabCopy, type LabKey } from '../i18n/lab';
import type { HullErrorCode } from './hull';

function faceGeometry(faces:Vec3[][], classifyDeck=false):THREE.BufferGeometry {
  const batches:number[][]=[[],[]];
  for(const face of faces){
    for(let j=1;j<face.length-1;j++){
      const triangle=[face[0],face[j],face[j+1]];
      let material=0;
      if(classifyDeck){
        const [a,b,c]=triangle.map(p=>new THREE.Vector3(...p));
        material=b.sub(a).cross(c.sub(a)).normalize().z>.65 ? 1 : 0;
      }
      for(const point of triangle)batches[material].push(...bodyPoint(point));
    }
  }
  const geometry=new THREE.BufferGeometry();
  geometry.setAttribute('position',new THREE.Float32BufferAttribute(batches.flat(),3));
  geometry.computeVertexNormals();
  if(classifyDeck){
    let start=0;
    batches.forEach((vertices,material)=>{
      if(vertices.length)geometry.addGroup(start,vertices.length/3,material);
      start+=vertices.length/3;
    });
  }
  return geometry;
}

type Controller={update:(experiment:Experiment,state:LabState|null,selected:string,section:boolean,water:boolean,inspection:InspectionTarget|null,targets:InspectionTarget[],fragments:Fragmentation|null,selectedTrace:number|null,paths:boolean)=>void;focus:(target:InspectionTarget)=>void;reset:()=>void;destroy:()=>void};

function createInspector(host:HTMLDivElement,project:ProjectDocument,experiment:Experiment,onSelect:(id:string)=>void,onLost:()=>void):Controller {
  const rooms=(project.compartments ?? []) as Room[];
  const geometry=project.geometry as {keel_offset_m?:number;offsets?:{stations?:Array<[number,number[][]]>}};
  const keel=geometry.keel_offset_m ?? 0;
  const envelope=buildHullEnvelope(geometry.offsets?.stations ?? [],keel);
  const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(38,1,.05,100000);
  const resources=new Set<{dispose:()=>void}>(),off:Array<()=>void>=[];
  const own=<T extends {dispose:()=>void}>(resource:T):T=>{resources.add(resource);return resource;};
  const body=new THREE.Group(),interior=new THREE.Group(),waterGroup=new THREE.Group();
  scene.add(body);body.add(interior);interior.add(waterGroup);
  const fragmentGroup=new THREE.Group(),breachGroup=new THREE.Group();body.add(fragmentGroup,breachGroup);
  let fragmentKey:Fragmentation|null|undefined,traceKey:number|null|undefined,breachKey='';
  const clearLines=(group:THREE.Group)=>{for(const child of [...group.children]){(child as THREE.LineSegments).geometry.dispose();group.remove(child);}};
  let renderer:THREE.WebGLRenderer|undefined,raf=0,destroyed=false;
  const clearWater=()=>{for(const child of [...waterGroup.children]){(child as THREE.Mesh).geometry.dispose();waterGroup.remove(child);}};
  const destroy=()=>{
    if(destroyed)return;destroyed=true;cancelAnimationFrame(raf);
    for(const unsubscribe of off.reverse())unsubscribe();
    clearWater();clearLines(fragmentGroup);clearLines(breachGroup);for(const resource of resources)resource.dispose();resources.clear();
    renderer?.dispose();renderer?.forceContextLoss();renderer?.domElement.remove();
  };
  try {
    renderer=new THREE.WebGLRenderer({antialias:true,alpha:false});
    const view=renderer;
    view.setPixelRatio(Math.min(devicePixelRatio,2));host.append(view.domElement);
    const controls=new OrbitControls(camera,view.domElement);off.push(()=>controls.dispose());
    const motion=matchMedia('(prefers-reduced-motion: reduce)');
    controls.enableDamping=!motion.matches;controls.dampingFactor=.12;controls.maxPolarAngle=Math.PI*.93;
    const invalidate=()=>{if(!destroyed&&!raf)raf=requestAnimationFrame(draw);};
    let move:{start:number;from:THREE.Vector3;to:THREE.Vector3;targetFrom:THREE.Vector3;targetTo:THREE.Vector3}|null=null;
    const draw=()=>{
      raf=0;if(destroyed)return;
      if(move){
        const progress=motion.matches ? 1 : Math.min(1,(performance.now()-move.start)/420),ease=1-(1-progress)**3;
        camera.position.lerpVectors(move.from,move.to,ease);controls.target.lerpVectors(move.targetFrom,move.targetTo,ease);
        if(progress===1)move=null;
      }
      const changed=controls.update();view.render(scene,camera);if(changed||move)invalidate();
    };
    const manual=()=>{move=null;};controls.addEventListener('start',manual);off.push(()=>controls.removeEventListener('start',manual));
    controls.addEventListener('change',invalidate);off.push(()=>controls.removeEventListener('change',invalidate));
    const reduce=()=>{controls.enableDamping=!motion.matches;invalidate();};
    motion.addEventListener('change',reduce);off.push(()=>motion.removeEventListener('change',reduce));

    scene.add(new THREE.HemisphereLight(0xffffff,0x7a8189,2));
    const keyLight=new THREE.DirectionalLight(0xffffff,2.5);keyLight.position.set(2,5,-4);scene.add(keyLight);
    const fillLight=new THREE.DirectionalLight(0xdce5f2,.65);fillLight.position.set(-4,2,3);scene.add(fillLight);
    const shellMaterial=own(new THREE.MeshStandardMaterial({color:0xaeb7b5,roughness:.86,side:THREE.DoubleSide}));
    const deckMaterial=own(new THREE.MeshStandardMaterial({color:0xd7dace,roughness:.95,side:THREE.DoubleSide}));
    const edgeMaterial=own(new THREE.LineBasicMaterial({color:0x515c59,transparent:true,opacity:.35}));
    const roomMaterial=own(new THREE.LineBasicMaterial({color:0x697977,transparent:true,opacity:.65}));
    let selectionInk=0x202622;
    const locators=new Map<string,THREE.LineSegments<THREE.EdgesGeometry,THREE.LineDashedMaterial>>();
    const fullGeometry=own(faceGeometry(envelope.faces,true)),cutGeometry=own(faceGeometry(cutHullFaces(envelope.faces),true));
    const hull=new THREE.Mesh(fullGeometry,[shellMaterial,deckMaterial]);body.add(hull);
    const fullEdges=own(new THREE.EdgesGeometry(fullGeometry,26)),cutEdges=own(new THREE.EdgesGeometry(cutGeometry,26));
    const outline=new THREE.LineSegments(fullEdges,edgeMaterial);body.add(outline);
    const palette=()=>{
      const style=getComputedStyle(host),background=new THREE.Color(style.getPropertyValue('--surface').trim()||'#f6f6f3');
      scene.background=background;
      const dark=(background.r+background.g+background.b)/3<.3;
      shellMaterial.color.setHex(dark ? 0x71817f : 0xaeb7b5);
      deckMaterial.color.setHex(dark ? 0xa0aca3 : 0xd7dace);
      edgeMaterial.color.setHex(dark ? 0xd0d9d3 : 0x515c59);
      roomMaterial.color.setHex(dark ? 0xc6d2cd : 0x697977);
      selectionInk=dark ? 0xf0f2e8 : 0x202622;
      for(const locator of locators.values())if(locator.userData.selected)locator.material.color.setHex(selectionInk);
      invalidate();
    };
    const themeObserver=new MutationObserver(palette);off.push(()=>themeObserver.disconnect());
    themeObserver.observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});palette();

    for(const room of rooms){
      const box=roomBox(room),roomGeometry=new THREE.BoxGeometry(room.length_m,room.height_m,room.beam_m);
      const edges=own(new THREE.EdgesGeometry(roomGeometry));roomGeometry.dispose();
      const boundary=new THREE.LineSegments(edges,roomMaterial);boundary.position.set(...bodyPoint(box.center_m));interior.add(boundary);
    }
    const modules=new Map<string,THREE.Mesh<THREE.BoxGeometry,THREE.MeshStandardMaterial>>();
    const moduleOutlines=new Map<string,THREE.LineBasicMaterial>();
    for(const module of experiment.modules){
      const [x,y,z]=module.box.size_m;
      const mesh=new THREE.Mesh(own(new THREE.BoxGeometry(x,z,y)),own(new THREE.MeshStandardMaterial({color:0x68746d,roughness:.78})));
      mesh.position.set(...bodyPoint(module.box.center_m));mesh.userData.id=module.id;interior.add(mesh);modules.set(module.id,mesh);
      const line=own(new THREE.LineBasicMaterial({color:0x39443f}));moduleOutlines.set(module.id,line);
      mesh.add(new THREE.LineSegments(own(new THREE.EdgesGeometry(mesh.geometry)),line));
    }
    const bounds=new THREE.Box3().setFromPoints(envelope.sections.flat().map(p=>new THREE.Vector3(...bodyPoint(p))));
    const center=bounds.getCenter(new THREE.Vector3()),size=bounds.getSize(new THREE.Vector3());
    const extent=Math.max(size.x,size.y,size.z),radius=size.length()/2;
    const pathMaterial=own(new THREE.LineBasicMaterial({color:0x977d48,transparent:true,opacity:.2,depthTest:false,depthWrite:false}));
    const selectedPathMaterial=own(new THREE.LineBasicMaterial({color:0xe52b24,transparent:true,opacity:.95,depthTest:false,depthWrite:false}));
    const stopMaterial=own(new THREE.PointsMaterial({color:0xe52b24,size:extent*.004,transparent:true,opacity:.7,depthTest:false,depthWrite:false}));
    const holeMaterial=own(new THREE.PointsMaterial({color:0x3857e7,size:extent*.012,depthTest:false,depthWrite:false}));
    const positions=(points:Vec3[])=>new THREE.BufferGeometry().setAttribute('position',new THREE.Float32BufferAttribute(points.flatMap(point=>bodyPoint(point)),3));
    const drawPaths=(fragments:Fragmentation|null,selectedTrace:number|null)=>{
      if(fragments===fragmentKey&&selectedTrace===traceKey)return;
      fragmentKey=fragments;traceKey=selectedTrace;clearLines(fragmentGroup);
      if(!fragments)return;
      const points:Vec3[]=[],selectedPoints:Vec3[]=[],stops:Vec3[]=[];
      for(const trace of fragments.traces){
        for(const segment of trace.segments){points.push(segment.from_m,segment.to_m);if(trace.index===selectedTrace)selectedPoints.push(segment.from_m,segment.to_m);}
        if(trace.termination==='sealed_boundary'&&trace.segments.length)stops.push(trace.segments.at(-1)!.to_m);
      }
      fragmentGroup.add(new THREE.LineSegments(positions(points),pathMaterial));
      if(selectedPoints.length)fragmentGroup.add(new THREE.LineSegments(positions(selectedPoints),selectedPathMaterial));
      if(stops.length)fragmentGroup.add(new THREE.Points(positions(stops),stopMaterial));
      fragmentGroup.renderOrder=4;
    };
    const boxes=new Map<string,{center_m:Vec3;size_m:Vec3}>();
    const locator=(kind:InspectionTarget['kind'],id:string,box:{center_m:Vec3;size_m:Vec3})=>{
      const [x,y,z]=box.size_m,base=new THREE.BoxGeometry(x,z,y);
      const edge=own(new THREE.EdgesGeometry(base));base.dispose();
      const material=own(new THREE.LineDashedMaterial({color:selectionInk,dashSize:extent*.008,gapSize:extent*.004,depthTest:false,transparent:true,opacity:.9}));
      const line=new THREE.LineSegments(edge,material);line.computeLineDistances();line.position.set(...bodyPoint(box.center_m));
      line.scale.setScalar(1.035);line.visible=false;line.renderOrder=5;body.add(line);
      boxes.set(`${kind}:${id}`,box);locators.set(`${kind}:${id}`,line);
    };
    for(const room of rooms)locator('compartment',room.id,roomBox(room));
    for(const module of experiment.modules)locator('module',module.id,module.box);
    for(const crew of experiment.crew_groups ?? [])locator('crew',crew.id,crew.station_box);
    const impact=new THREE.Mesh(own(new THREE.SphereGeometry(Math.max(.04,extent*.005),12,8)),own(new THREE.MeshBasicMaterial({color:0xe52b24})));interior.add(impact);
    const influence=new THREE.Mesh(own(new THREE.SphereGeometry(1,24,16)),own(new THREE.MeshBasicMaterial({color:0xe52b24,wireframe:true,transparent:true,opacity:.12,depthWrite:false})));interior.add(influence);
    const waterMaterial=own(new THREE.MeshBasicMaterial({color:0x3857e7,transparent:true,opacity:.3,depthWrite:false,side:THREE.DoubleSide}));
    const sea=new THREE.Mesh(own(new THREE.PlaneGeometry(size.x*1.35,size.z*2)),own(new THREE.MeshBasicMaterial({color:0x3857e7,transparent:true,opacity:.08,depthWrite:false,side:THREE.DoubleSide})));
    sea.rotation.x=-Math.PI/2;sea.position.set(center.x,0,center.z);scene.add(sea);sea.visible=false;
    const reset=()=>{
      move=null;
      const vertical=THREE.MathUtils.degToRad(camera.fov)/2,horizontal=Math.atan(Math.tan(vertical)*camera.aspect);
      const distance=radius/Math.sin(Math.min(vertical,horizontal))*1.08;
      camera.position.copy(center).addScaledVector(new THREE.Vector3(.55,.5,-1.25).normalize(),distance);
      camera.near=Math.max(.01,extent/10000);camera.far=extent*100;camera.updateProjectionMatrix();
      controls.minDistance=extent*.16;controls.maxDistance=extent*15;controls.target.copy(center);controls.update();invalidate();
    };
    const focus=(target:InspectionTarget)=>{
      const box=boxes.get(`${target.kind}:${target.id}`);if(!box||destroyed)return;
      body.updateMatrixWorld(true);
      const point=body.localToWorld(new THREE.Vector3(...bodyPoint(box.center_m)));
      const direction=camera.position.clone().sub(controls.target).normalize();
      const distance=Math.max(new THREE.Vector3(...box.size_m).length()*1.8,extent*.25);
      move={start:performance.now(),from:camera.position.clone(),to:point.clone().addScaledVector(direction,distance),targetFrom:controls.target.clone(),targetTo:point};
      invalidate();
    };
    let firstSize=true;
    const resize=()=>{
      const width=host.clientWidth,height=host.clientHeight;if(!width||!height)return;
      view.setSize(width,height,false);camera.aspect=width/height;camera.updateProjectionMatrix();
      if(firstSize){firstSize=false;reset();}invalidate();
    };
    reset();const observer=new ResizeObserver(resize);off.push(()=>observer.disconnect());observer.observe(host);resize();
    const raycaster=new THREE.Raycaster();let down:{id:number;x:number;y:number}|null=null,cutaway=false;
    const pointerDown=(event:PointerEvent)=>{if(event.button===0)down={id:event.pointerId,x:event.clientX,y:event.clientY};};
    const pointerUp=(event:PointerEvent)=>{
      const start=down;down=null;
      if(!cutaway||!start||start.id!==event.pointerId||Math.hypot(event.clientX-start.x,event.clientY-start.y)>5)return;
      const rect=view.domElement.getBoundingClientRect();if(!rect.width||!rect.height)return;
      scene.updateMatrixWorld(true);camera.updateMatrixWorld(true);
      raycaster.setFromCamera(new THREE.Vector2((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1),camera);
      const hit=raycaster.intersectObjects([hull,...modules.values()],false)[0];
      if(hit && hit.object!==hull)onSelect(String(hit.object.userData.id));
    };
    const pointerCancel=()=>{down=null;};const lost=(event:Event)=>{event.preventDefault();onLost();};
    view.domElement.addEventListener('pointerdown',pointerDown);view.domElement.addEventListener('pointerup',pointerUp);
    view.domElement.addEventListener('pointercancel',pointerCancel);view.domElement.addEventListener('webglcontextlost',lost);
    off.push(()=>{view.domElement.removeEventListener('pointerdown',pointerDown);view.domElement.removeEventListener('pointerup',pointerUp);view.domElement.removeEventListener('pointercancel',pointerCancel);view.domElement.removeEventListener('webglcontextlost',lost);});

    return {reset,destroy,focus,update(next,state,selected,section,showWater,inspection,targets,fragments,selectedTrace,showPaths){
      if(destroyed)return;cutaway=section;
      hull.geometry=section ? cutGeometry : fullGeometry;outline.geometry=section ? cutEdges : fullEdges;interior.visible=section;
      const rows=attitudeRows(state?.ship?.equilibrium.p ?? 0,state?.ship?.equilibrium.q ?? 0);
      body.matrixAutoUpdate=false;body.matrix.set(...[...rows[0],0,...rows[1],0,...rows[2],0,0,0,0,1] as Parameters<THREE.Matrix4['set']>);body.matrixWorldNeedsUpdate=true;
      for(const [id,mesh] of modules){
        const availability=state?.modules.find(m=>m.id===id)?.effective_availability;
        mesh.material.color.setHex(availability==null ? 0x68746d : availability===0 ? 0xd9362b : availability<1 ? 0xb58a3c : 0x3857e7);
        moduleOutlines.get(id)!.color.setHex(id===selected ? selectionInk : 0x39443f);
      }
      const chosen=inspection ?? {kind:'module',id:selected};
      const keys=new Set(targets.map(t=>`${t.kind}:${t.id}`));
      const selectedKey=`${chosen.kind}:${chosen.id}`;keys.add(selectedKey);
      const owner=chosen.kind==='module' ? next.modules.find(m=>m.id===chosen.id)?.compartment_id
        : chosen.kind==='crew' ? next.crew_groups?.find(c=>c.id===chosen.id)?.compartment_id : chosen.id;
      if(owner)keys.add(`compartment:${owner}`);
      for(const [key,line] of locators){
        line.visible=keys.has(key);line.userData.selected=key===selectedKey||key===`compartment:${owner}`;
        line.material.color.setHex(line.userData.selected ? selectionInk : 0xb58a3c);
      }
      impact.position.set(...bodyPoint(next.detonation?.position_m ?? next.impact.position_m));influence.position.copy(impact.position);influence.scale.setScalar(next.impact.radius_m);influence.visible=!next.detonation&&next.impact.radius_m>0;
      drawPaths(fragments,selectedTrace);fragmentGroup.visible=showPaths&&!!state?.detonation_occurred;
      const holes=state?.generated_breaches ?? [],holeKey=JSON.stringify(holes);
      if(holeKey!==breachKey){breachKey=holeKey;clearLines(breachGroup);if(holes.length)breachGroup.add(new THREE.Points(positions(holes.map(b=>b.position_m)),holeMaterial));}
      breachGroup.visible=showPaths&&!!state?.detonation_occurred;
      clearWater();sea.visible=showWater&&!!state?.ship;
      if(state?.ship){
        sea.position.y=seaHeight(state.ship.equilibrium,keel);
        if(showWater)for(const tank of state.ship.tanks){
          const room=rooms.find(r=>'lab-water:'+r.id===tank.tank_id);if(!room)continue;
          const faces=acceptedWaterFaces(roomBox(room),tank);if(faces.length)waterGroup.add(new THREE.Mesh(faceGeometry(faces),waterMaterial));
        }
      }
      invalidate();
    }};
  }catch(error){destroy();throw error;}
}

/**
 * Why the three-dimensional view is not on screen.
 *
 * A reason key rather than a sentence, because the failure outlives the render
 * that produced it and may be printed in a language that changed in between. The
 * browser's own cause, when there is one, is kept beside it and printed
 * verbatim: it is the evidence for the sentence above it.
 */
type SceneFailure = { reason: 'scene.contextLost' | 'scene.unavailable' | HullErrorCode; cause?: string };

export default function DamageLabScene({project,experiment,state,selected,inspection=null,eventTargets=[],fragments=null,selectedTrace=null,onSelect}:{
  project:ProjectDocument;experiment:Experiment;state:LabState|null;selected:string;inspection?:InspectionTarget|null;eventTargets?:InspectionTarget[];fragments?:Fragmentation|null;selectedTrace?:number|null;onSelect:(id:string)=>void;
}) {
  const host=useRef<HTMLDivElement>(null),controller=useRef<Controller|null>(null),latest=useRef({experiment,state,selected,onSelect});
  latest.current={experiment,state,selected,onSelect};
  const l=useLabCopy();
  const [section,setSection]=useState(false),[water,setWater]=useState(true),[paths,setPaths]=useState(true),[failure,setFailure]=useState<SceneFailure|null>(null),[retry,setRetry]=useState(0);
  const key=draftIdentity({geometry:project.geometry,compartments:project.compartments,modules:experiment.modules,crew:experiment.crew_groups});
  const chosen=inspection ?? {kind:'module' as const,id:selected};
  const selectedCrew=chosen.kind==='crew' ? experiment.crew_groups?.find(c=>c.id===chosen.id) : null;
  const selectedRoom=chosen.kind==='compartment' ? (project.compartments as Room[]|undefined)?.find(r=>r.id===chosen.id) : null;
  const name=selectedCrew?.label ?? selectedRoom?.label ?? selectedRoom?.id ?? experiment.modules.find(m=>m.id===chosen.id)?.label ?? chosen.id;
  useEffect(()=>{
    if(!host.current)return;setFailure(null);
    try{
      // The context-loss callback is given a reason, not a sentence: it is held
      // by the renderer for its lifetime, and a sentence captured here would be
      // frozen in whatever language the page happened to be in when the frame
      // was created. It is translated where it is printed instead, and the
      // renderer's own dependency list stays exactly as it was.
      controller.current=createInspector(host.current,project,experiment,id=>latest.current.onSelect(id),()=>{controller.current?.destroy();controller.current=null;setFailure({reason:'scene.contextLost'});});
      controller.current.update(latest.current.experiment,latest.current.state,latest.current.selected,section,water,inspection,eventTargets,fragments,selectedTrace,paths);
    }catch(error){
      controller.current?.destroy();controller.current=null;
      // A geometry refusal carries its own code, so it reads in the language
      // chosen after the failure, not the one current when it was raised. Any
      // other error keeps its own message as the raw evidence beside the frame.
      setFailure(error instanceof HullGeometryError
        ? {reason:error.code}
        : {reason:'scene.unavailable',cause:error instanceof Error ? error.message : String(error)});
    }
    return()=>{controller.current?.destroy();controller.current=null;};
    // Layout owns the graphics lifetime; changing a frame never resets orbit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[key,retry]);
  useEffect(()=>controller.current?.update(experiment,state,selected,section,water,inspection,eventTargets,fragments,selectedTrace,paths),[experiment,state,selected,section,water,inspection,eventTargets,fragments,selectedTrace,paths]);
  return <div className="lab-scene-wrap">
    <div ref={host} className="lab-scene" role="img" aria-label={l('scene.label')} />
    {failure && <div className="lab-webgl-fallback" role="status"><p>{l(failure.reason)}{failure.cause ? ` ${failure.cause}` : ''}</p><button onClick={()=>setRetry(v=>v+1)}>{l('scene.retry')}</button></div>}
    <div className="lab-scene-tools"><button onClick={()=>controller.current?.reset()} disabled={!!failure}>{l('scene.reset')}</button><button onClick={()=>controller.current?.focus(chosen)} disabled={!!failure||!chosen.id}>{l('scene.focus')}</button><label><input type="checkbox" checked={section} onChange={e=>setSection(e.target.checked)} />{l('scene.section')}</label><label><input type="checkbox" checked={water} onChange={e=>setWater(e.target.checked)} />{l('scene.water')}</label>{experiment.detonation&&<label><input type="checkbox" checked={paths} onChange={e=>setPaths(e.target.checked)} />{l('scene.paths')}</label>}</div>
    {experiment.detonation&&<p className="lab-path-caption">{l('scene.pathCaption')}</p>}
    <div className="lab-spatial-selection"><span className="lab-kicker">INSPECTING / {chosen.kind.toUpperCase()}</span><strong>{name}</strong><span>{l('scene.selectionNote')}</span></div>
    <div className="lab-scene-caption"><span>{section ? 'STARBOARD CUTAWAY / PORT SHELL RETAINED' : 'FULL HULL / CANONICAL OFFSETS'}</span><span>{state?.ship ? 'ACCEPTED CORE ATTITUDE' : 'DECLARED LAYOUT / ATTITUDE UNSOLVED'}</span></div>
    <div className="lab-legend"><span><i style={{background:'#68746d'}} />{l('scene.legend.pending')}</span><span><i style={{background:'#3857e7'}} />{l('scene.legend.available')}</span><span><i style={{background:'#b58a3c'}} />{l('scene.legend.damaged')}</span><span><i style={{background:'#d9362b'}} />{l('scene.legend.disabled')}</span><span>{section ? l('scene.legend.section') : l('scene.legend.full')}</span></div>
  </div>;
}
