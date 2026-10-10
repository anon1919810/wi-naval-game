import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import type { ProjectDocument } from '../types';
import type { Experiment, LabState } from './types';
import Scene from './Scene';
import * as THREE from 'three';

const graphics = vi.hoisted(() => ({ fail: false, failControls:false, frames:[] as FrameRequestCallback[], renderers: [] as Array<{
  domElement: HTMLCanvasElement; dispose: ReturnType<typeof vi.fn>; forceContextLoss: ReturnType<typeof vi.fn>; render:ReturnType<typeof vi.fn>;
}>, controls: [] as Array<{ dispose: ReturnType<typeof vi.fn> }> }));
vi.mock('three', async original => {
  const actual = await original<typeof import('three')>();
  class Renderer {
    domElement = document.createElement('canvas');
    dispose = vi.fn(); forceContextLoss = vi.fn(); render=vi.fn();
    constructor() { if(graphics.fail)throw new Error('No WebGL'); graphics.renderers.push(this); }
    setPixelRatio() {} setSize() {}
  }
  return { ...actual, WebGLRenderer: Renderer };
});
vi.mock('three/addons/controls/OrbitControls.js', async () => {
  const { Vector3 } = await import('three');
  class Controls {
    target = new Vector3(); dispose = vi.fn();
    camera:THREE.Camera;
    constructor(camera:THREE.Camera) { if(graphics.failControls)throw new Error('Controls failed');this.camera=camera;graphics.controls.push(this); }
    update() { this.camera.lookAt(this.target);return false; } addEventListener() {} removeEventListener() {}
  }
  return { OrbitControls: Controls };
});

const observerDisconnect = vi.fn(), mediaRemove = vi.fn();
beforeEach(() => {
  vi.clearAllMocks(); graphics.fail=false;graphics.failControls=false;graphics.frames=[]; graphics.renderers=[]; graphics.controls=[];
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect=observerDisconnect; });
  vi.stubGlobal('matchMedia', () => ({ matches: false, addEventListener: vi.fn(), removeEventListener: mediaRemove }));
  vi.stubGlobal('requestAnimationFrame', vi.fn((callback:FrameRequestCallback)=>{graphics.frames.push(callback);return 1;})); vi.stubGlobal('cancelAnimationFrame', vi.fn());
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

const project = { hull: { lwl_m: 20, beam_m: 10, depth_m: 6 }, compartments: [],
  geometry: { kind: 'offsets', offsets: { stations: [
    [-10, [[-5,0], [5,0], [5,6], [-5,6]]], [10, [[-5,0], [5,0], [5,6], [-5,6]]],
  ] } } } as unknown as ProjectDocument;
const experiment = { modules: [{ id: 'engine', box: { center_m: [0,0,2], size_m: [1,1,1] } }],
  impact: { position_m: [0,0,2], radius_m: 1 } } as unknown as Experiment;
const props = { project, experiment, selected: 'engine', onSelect: vi.fn(), state: null };

function rendered(){
  graphics.frames.splice(0).forEach(callback=>callback(0));
  const renderer=graphics.renderers.at(-1)!;
  const [scene,camera]=renderer.render.mock.calls.at(-1) as [THREE.Scene,THREE.PerspectiveCamera];
  scene.updateMatrixWorld(true);camera.updateMatrixWorld(true);
  return {renderer,scene,camera};
}
function clickModule(scene:THREE.Scene,camera:THREE.PerspectiveCamera,canvas:HTMLCanvasElement,drag=false){
  let module:THREE.Object3D|undefined;
  scene.traverse(object=>{if(object.userData.id==='engine')module=object;});
  const point=module!.getWorldPosition(new THREE.Vector3()).project(camera);
  vi.spyOn(canvas,'getBoundingClientRect').mockReturnValue(new DOMRect(0,0,640,640));
  const x=(point.x+1)*320,y=(1-point.y)*320;
  for(const type of ['pointerdown','pointerup']){
    const event=new MouseEvent(type,{clientX:x+(drag&&type==='pointerup' ? 12 : 0),clientY:y,button:0,bubbles:true});
    Object.defineProperty(event,'pointerId',{value:1});fireEvent(canvas,event);
  }
}

it('offers a readable retry when WebGL is unavailable', () => {
  graphics.fail=true;
  render(<Scene {...props} />);
  expect(screen.getByText(/此浏览器无法创建三维视图/)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '复位视角' })).toBeDisabled();
  expect(screen.getByRole('checkbox', { name: '局部剖视' })).toBeEnabled();
  expect(screen.getByRole('button', { name: '重试三维视图' })).toBeEnabled();
});
it('keeps the same viewer through replay and disposes it on exit', () => {
  const mounted=render(<Scene {...props} />);
  const canvas=graphics.renderers[0].domElement;
  mounted.rerender(<Scene {...props} state={{ modules: [], ship: null } as unknown as LabState} />);
  expect(graphics.renderers).toHaveLength(1);
  expect(graphics.controls).toHaveLength(1);
  mounted.unmount();
  expect(graphics.renderers[0].dispose).toHaveBeenCalledOnce();
  expect(graphics.renderers[0].forceContextLoss).toHaveBeenCalledOnce();
  expect(graphics.controls[0].dispose).toHaveBeenCalledOnce();
  expect(observerDisconnect).toHaveBeenCalledOnce();
  expect(mediaRemove).toHaveBeenCalledOnce();
  expect(canvas.isConnected).toBe(false);
});
it('cleans a lost context and can create a fresh viewer on retry', () => {
  render(<Scene {...props} />);
  const renderer=graphics.renderers[0];
  fireEvent(renderer.domElement,new Event('webglcontextlost',{cancelable:true}));
  expect(screen.getByText(/三维上下文中断/)).toBeInTheDocument();
  expect(renderer.dispose).toHaveBeenCalledOnce();
  expect(renderer.domElement.isConnected).toBe(false);
  fireEvent.click(screen.getByRole('button',{name:'重试三维视图'}));
  expect(graphics.renderers).toHaveLength(2);
  expect(screen.queryByText(/三维上下文中断/)).not.toBeInTheDocument();
  expect(graphics.renderers[1].domElement.isConnected).toBe(true);
});
it('releases a renderer and its canvas when later initialization fails',()=>{
  graphics.failControls=true;
  render(<Scene {...props} />);
  expect(screen.getByRole('button',{name:'重试三维视图'})).toBeInTheDocument();
  expect(graphics.renderers[0].dispose).toHaveBeenCalledOnce();
  expect(graphics.renderers[0].domElement.isConnected).toBe(false);
});
it('keeps an opaque half shell and supports exposed picking without selecting through retained skin',()=>{
  const onSelect=vi.fn();render(<Scene {...props} onSelect={onSelect} />);
  let {renderer,scene,camera}=rendered();
  clickModule(scene,camera,renderer.domElement);
  expect(onSelect).not.toHaveBeenCalled();
  const originalPosition=camera.position.clone();
  fireEvent.click(screen.getByRole('checkbox',{name:/剖视/}));
  ({renderer,scene,camera}=rendered());
  expect(camera.position.equals(originalPosition)).toBe(true);
  expect(graphics.renderers).toHaveLength(1);
  clickModule(scene,camera,renderer.domElement);
  expect(onSelect).toHaveBeenLastCalledWith('engine');
  onSelect.mockClear();
  clickModule(scene,camera,renderer.domElement,true);
  expect(onSelect).not.toHaveBeenCalled();
  // From outside port, the retained shell must occlude that same internal module.
  camera.position.set(0,2,20);camera.lookAt(0,2,0);camera.updateMatrixWorld(true);
  clickModule(scene,camera,renderer.domElement);
  expect(onSelect).not.toHaveBeenCalled();
});

it('batches hull triangles by material rather than submitting one draw per face',()=>{
  render(<Scene {...props} />);
  const {scene}=rendered();
  const hulls:THREE.Mesh[]=[];
  scene.traverse(object=>{if(object instanceof THREE.Mesh && Array.isArray(object.material))hulls.push(object);});
  expect(hulls).toHaveLength(1);
  const hull=hulls[0];
  for(const section of [false,true]){
    if(section){fireEvent.click(screen.getByRole('checkbox',{name:'局部剖视'}));rendered();}
    expect(hull.geometry.groups).toHaveLength(2);
    expect(hull.geometry.groups.reduce((sum,group)=>sum+group.count,0)).toBe(hull.geometry.getAttribute('position').count);
  }
});
