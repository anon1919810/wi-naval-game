import { useConceptCopy } from '../i18n/concept';
import { number, object, stringList, type Raw } from './formModel';
import { auxiliaryWeapons } from './conceptDesign';
import { QuantityField } from './QuantityField';

/** Ordinary declarations only. All space calculations live in the core. */
export function AuxiliarySpacePanel({config,commit}:{config:Raw;commit:(next:Raw)=>void}) {
  const c=useConceptCopy();const enabled=config.auxiliary_space!=null;
  const value=object(config.auxiliary_space);const known=Array.isArray(value.torpedo_ids);
  const selected=stringList(value.torpedo_ids);const torpedoes=auxiliaryWeapons(config).filter(r=>r.kind==='torpedo');
  function patch(next:Raw){commit({...config,auxiliary_space:{...value,...next}});}
  function choose(slot:number,id:string){
    const ids=[selected[0]??'',selected[1]??''];ids[slot]=id;
    patch({torpedo_ids:ids.filter(Boolean)});
  }
  const invalid=selected.length>2 || new Set(selected).size!==selected.length
    || selected.some(id=>torpedoes.filter(row=>row.id===id).length!==1);
  return <div className="form-card">
    <h3>{c('space.title')}</h3>
    <label className="field-label"><input type="checkbox" checked={enabled} aria-label={c('space.enable')}
      onChange={event=>{if(event.target.checked)commit({...config,auxiliary_space:{source:null,torpedo_ids:null,bulged_beam_m:null}});
        else {const next={...config};delete next.auxiliary_space;commit(next);}}}/>{c('space.enable')}</label>
    <p className="form-hint">{c('space.note')}</p>
    {!enabled?null:<>
      <label className="field-label">{c('space.source')}<input value={typeof value.source==='string'?value.source:''}
        aria-label={c('space.source')} onChange={event=>patch({source:event.target.value||null})}/></label>
      <label className="field-label"><input type="checkbox" checked={known} aria-label={c('space.scopeKnown')}
        onChange={event=>patch({torpedo_ids:event.target.checked?[]:null})}/>{c('space.scopeKnown')}</label>
      <p className="form-hint">{c(known?'space.scopeEmptyHint':'space.scopeUnknown')}</p>
      {!known?null:<div className="form-grid">{[0,1].map(slot=><label className="field-label" key={slot}>
        {c('space.row',{slot:slot+1})}<select value={selected[slot]??''} aria-label={c('space.row',{slot:slot+1})}
          onChange={event=>choose(slot,event.target.value)}>
          <option value="">{c('space.noRow')}</option>
          {selected[slot]&&!torpedoes.some(row=>row.id===selected[slot])
            ?<option value={selected[slot]}>{selected[slot]} — {c('space.invalid')}</option>:null}
          {torpedoes.map((row,index)=><option key={index} value={String(row.id)}
            disabled={selected.some((id,i)=>i!==slot&&id===row.id)}>{String(row.id)}</option>)}
        </select></label>)}</div>}
      {invalid?<p className="form-error" role="alert">{c('space.invalid')}</p>:null}
      <QuantityField label={c('space.width')} dimension="length" storedUnit="m" kind="nonnegative"
        value={number(value.bulged_beam_m)} onChange={next=>patch({bulged_beam_m:next})} hint={c('space.widthHint')}/>
    </>}
  </div>;
}
