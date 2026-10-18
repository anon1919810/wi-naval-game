import { useRef,useState } from 'react';
import * as api from '../api';
import { useSps3b3Copy } from '../i18n/sps3b3';
import { useShipDesignCopy } from '../i18n/shipDesign';
import { formatNumber } from './units';
import { readFreeboardGeometry, profileX, profileY } from './freeboardProfileModel';
import { ArmourDiagram } from './ArmourDiagram';
import { ArmamentComposition } from './ArmamentComposition';
import { VesselDesignOverview } from './VesselDesignOverview';
import { nativeReadings, sps3b3ReportSections, sps3b3ReportText, sps3b3ResultOf } from './sps3b3Model';
import type { ShipDesignResult, Sps3b3Result } from '../types';
import '../styles/Sps3b3.css';

export function SpsFreeboardProfile({result}:{result:Sps3b3Result|null}) {
  const svgRef=useRef<SVGSVGElement>(null),w=useSps3b3Copy();
  const [exportError,setExportError]=useState('');
  const geometry=readFreeboardGeometry(result);
  if (!geometry) return null;
  const {xs,heights}=geometry;
  const x=(v:number)=>profileX(geometry,v),y=(v:number)=>profileY(geometry,v);
  const savePicture=()=>{
    const svg=svgRef.current;if(!svg)return;
    const clone=svg.cloneNode(true) as SVGSVGElement;
    clone.setAttribute('color','#171a19');
    const url=URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(clone)],{type:'image/svg+xml'}));
    const image=new Image();
    image.onload=()=>{
      const canvas=document.createElement('canvas');canvas.width=2000;canvas.height=360;
      const context=canvas.getContext('2d');
      if(context){context.fillStyle='white';context.fillRect(0,0,2000,360);context.drawImage(image,0,0,2000,360);
        const link=document.createElement('a');link.download='Plimsoll-freeboard.png';link.href=canvas.toDataURL('image/png');link.click();}
      URL.revokeObjectURL(url);
    };
    image.onerror=()=>{URL.revokeObjectURL(url);setExportError(w('sps.profile.error'));};image.src=url;
  };
  return <figure className="sps-profile"><svg ref={svgRef} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 180" role="img" aria-label="Freeboard profile / 干舷端点剖面">
    <line x1={x(0)} x2={x(geometry.length)} y1={y(0)} y2={y(0)} stroke="currentColor" strokeDasharray="8 6" />
    <polyline points={xs.map((v,i)=>`${x(v)},${y(heights[i] as number)}`).join(' ')} fill="none" stroke="currentColor" strokeWidth="3" />
    {xs.map((v,i)=><circle key={i} cx={x(v)} cy={y(heights[i] as number)} r="3" fill="currentColor"><title>{heights[i]?.toFixed(2)} ft</title></circle>)}
    <text x="30" y="175" fill="currentColor">Stern / 艉</text><text x="840" y="175" fill="currentColor">Bow / 艏</text>
  </svg><figcaption>Freeboard endpoints · 水线与八个干舷端点（示意）</figcaption><button className="sps-button no-print" onClick={savePicture}>{w('sps.profile.save')}</button>{exportError && <p role="alert">{exportError}</p>}</figure>;
}

export function Sps3b3Readings({data,runId,variant}:{data:unknown;runId?:string;variant?:'native'}) {
  const w=useSps3b3Copy(),d=useShipDesignCopy(),result=sps3b3ResultOf(data);
  const [notice,setNotice]=useState('');
  if (!result) return null;
  const title=variant==='native'?w('sps.readings.nativeTitle'):w('sps.readings.title');
  const native=variant==='native'?result as ShipDesignResult:null;
  const balance=native?.balance;
  const tonnes=(value:unknown)=>typeof value==='number' && Number.isFinite(value)?`${formatNumber(value)} t`:'—';
  const sections=sps3b3ReportSections(result),text=sps3b3ReportText(result);
  const copy=async()=>{
    try {if (!navigator.clipboard || !text) throw new Error();await navigator.clipboard.writeText(text);setNotice(w('sps.readings.copied'));}
    catch {setNotice(w('sps.readings.copyUnsupported'));}
  };
  const download=async(format:api.ExportFormat)=>{
    if(!runId)return;
    try{
      const blob=await api.exportBytes(runId,format),url=URL.createObjectURL(blob);
      const link=document.createElement('a');link.href=url;link.download=`plimsoll-${runId}.${format}`;link.click();
      setTimeout(()=>URL.revokeObjectURL(url),1000);
    }catch(error){setNotice(error instanceof Error?error.message:String(error));}
  };
  return <section className="sps-saved" aria-label={title}>
    <h2>{title}</h2>
    <p>{w('sps.readings.status',{status:result.status??'—'})}</p>
    {balance && <section className="ship-design-balance" aria-label={d('shipDesign.balance.title')}>
      <h3>{d('shipDesign.balance.title')}</h3>
      <p>{d('shipDesign.balance.basis',{condition:native?.basis_condition_id??'—'})}</p>
      <dl className="sps-readings">
        <div className="sps-reading"><dt>{d('shipDesign.ledger.selected')}</dt><dd>{tonnes(balance.selected_mass_t)}</dd></div>
        <div className="sps-reading"><dt>{d('shipDesign.ledger.estimate')}</dt><dd>{tonnes(balance.estimated_mass_t)}</dd></div>
        <div className="sps-reading"><dt>{d('shipDesign.ledger.target')}</dt><dd>{tonnes(balance.target_displacement_t)}</dd></div>
        <div className="sps-reading"><dt>{d('shipDesign.ledger.difference')}</dt><dd>{tonnes(balance.difference_t)}</dd></div>
      </dl>
      {!!native?.ledger?.needs_binding?.length && <p>{d('shipDesign.ledger.unboundItems',{items:native.ledger.needs_binding.join(', ')})}</p>}
      <p className="sps-hint">{d('shipDesign.empiricalNote')}</p>
    </section>}
    {runId && <div className="sps-row no-print">
      {(['sship','txt','rtf','ssr'] as const).map(format=><a className="button button--secondary" key={format} href={api.exportUrl(runId,format)} download onClick={event=>{event.preventDefault();void download(format);}}>{w(`sps.readings.${format}`)}</a>)}
      {text && <button className="button button--secondary" onClick={()=>void copy()}>{w('sps.readings.copy')}</button>}
      <button className="button button--secondary" onClick={()=>window.print()}>{w('sps.readings.print')}</button>
    </div>}
    {native && <p className="sps-hint">{d('shipDesign.formatHint')}</p>}
    {notice && <p role="status">{notice}</p>}
    {native && <VesselDesignOverview result={native} state="frozen"
      contextLabel={native.basis_condition_id ?? null} runId={runId ?? null} />}
    {native && <ArmamentComposition result={native} state="frozen"
      contextLabel={native.basis_condition_id ?? null} runId={runId ?? null} />}
    {native && <ArmourDiagram result={native} state="frozen"
      contextLabel={native.basis_condition_id ?? null} runId={runId ?? null} />}
    <SpsFreeboardProfile result={result} />
    {sections.length ? <div className="sps-report">{sections.map((s,i)=><section key={`${s.id}-${i}`}>
      {s.title && <h3>{s.title}</h3>}<pre>{s.lines.join('\n')}</pre>
    </section>)}</div> : <p>{w('sps.readings.reportMissing')}</p>}
    <details className="sps-native"><summary>{w('sps.readings.native')}</summary>
      {['hull','freeboard','guns','auxiliary','armour','engine','performance'].map(section=><details key={section}><summary>{section}</summary>
        <dl className="sps-readings">{nativeReadings(result,section).filter(row=>typeof row.value!=='object' || row.value===null).map(row=><div className="sps-reading" key={row.key}><dt>{row.key}</dt><dd>{row.value===null?'—':String(row.value)}</dd></div>)}</dl>
      </details>)}
    </details>
    <details><summary>{w('sps.readings.origin')}</summary><pre>{JSON.stringify(result.provenance,null,2)}</pre></details>
  </section>;
}
