"""Readonly torpedo deck area and submerged volume from the recovered 3b3 method.

The source's ``area`` variable has two dimensions. Locations 0..3 are ft²;
locations 4..8 are ft³. The two ratios have independent denominators and are
never added. Zero count is an explicit product policy, not native parity.
"""
from __future__ import annotations
import json
import math
try:
    from . import auxiliary_weapons as weapons
except ImportError:  # existing direct-module callers
    import auxiliary_weapons as weapons

METHOD_VERSION = 'sps-3b3-auxiliary-space-v1'
SOURCE_ASSEMBLY = weapons.SOURCE_ASSEMBLY
SOURCE_SHA256 = weapons.SOURCE_SHA256
SOURCE_LOCATION = 'WeaponControl.cs:325-357 sizeNweight; WeaponsControl.cs spaceNweightCalc'
ID = 'selected_torpedoes'
VALUE_KEYS = ('deck_area_m2', 'hull_volume_m3', 'deck_ratio', 'hull_ratio')
CONTEXT_KEYS = ('length_m', 'beam_m', 'draught_m', 'block_coeff', 'waterplane_area_m2')
DEFAULT_PATH = '$.concept_design.auxiliary_space'
M_PER_FT = .3048

def _diag(message, path, code='unavailable'):
    return dict(code='auxiliary_space.'+code, message=message, path=path, severity='warning', blocking=False)

class AuxiliarySpaceError(ValueError):
    def __init__(self, diagnostics):
        self.diagnostics = [dict(d, severity='error', blocking=True) for d in diagnostics]
        super().__init__('; '.join(d['message'] for d in diagnostics))

def _records(raw):
    # Existing normalized records also contain inactive fields set to None.
    # Accept precisely those nulls, without dropping a wrong-kind actual value.
    if isinstance(raw, list):
        raw = [{k:v for k,v in row.items() if not
                (k in weapons.ALL_FIELDS and k not in weapons.FIELDS_BY_KIND.get(
                    row.get('kind') if isinstance(row.get('kind'),str) else '', ()) and v is None)}
               if isinstance(row, dict) else row for row in raw]
    try:
        return weapons.validate_configs(raw)
    except weapons.AuxiliaryValidationError as error:
        raise AuxiliarySpaceError(error.diagnostics) from error

def validate_config(raw, auxiliary_records, path=DEFAULT_PATH):
    records = _records(auxiliary_records)
    if not isinstance(raw, dict):
        raise AuxiliarySpaceError([_diag('must be an object',path,'invalid')])
    diagnostics = [_diag('unsupported field',path+'.'+str(k),'invalid')
                   for k in set(raw)-{'source','torpedo_ids','bulged_beam_m'}]
    source = raw.get('source')
    if source is not None and not isinstance(source,str):
        diagnostics.append(_diag('source must be a string or null',path+'.source','invalid'))
    ids = raw.get('torpedo_ids')
    if ids is not None:
        if not isinstance(ids,list) or len(ids)>2 or any(not isinstance(i,str) or not i for i in ids):
            diagnostics.append(_diag('choose at most two explicit torpedo IDs',path+'.torpedo_ids','invalid'))
        else:
            known = {r['id']:r for r in records}
            if len(set(ids))!=len(ids):
                diagnostics.append(_diag('torpedo IDs must be unique',path+'.torpedo_ids','duplicate'))
            for identity in ids:
                if identity not in known or known[identity]['kind']!='torpedo':
                    diagnostics.append(_diag('reference must name an existing torpedo: '+identity,
                                             path+'.torpedo_ids','reference'))
    width = raw.get('bulged_beam_m')
    if width is not None:
        try:
            valid = not isinstance(width,bool) and isinstance(width,(int,float)) and math.isfinite(width) and 0<=width<=1000
        except OverflowError:
            valid = False
        if not valid:
            diagnostics.append(_diag('total beam including bulges must be finite in 0..1000 m',
                                     path+'.bulged_beam_m','domain'))
    if diagnostics:
        raise AuxiliarySpaceError(diagnostics)
    return dict(source=source.strip() or None if source is not None else None,
                torpedo_ids=None if ids is None else list(ids),
                bulged_beam_m=None if width is None else float(width))

def _finite(value):
    try:
        return not isinstance(value,bool) and isinstance(value,(int,float)) and math.isfinite(value) and value>=0
    except OverflowError:
        return False

def _fact(context,key,diagnostics,path):
    raw = context.get(key) if isinstance(context,dict) else None
    value = raw.get('value') if isinstance(raw,dict) else raw
    origin = {k:raw.get(k) for k in ('source','estimate')} if isinstance(raw,dict) else None
    if origin is not None:
        try:
            origin=json.loads(json.dumps(origin,allow_nan=False))
        except (ValueError,TypeError,OverflowError):
            origin=None
            diagnostics.append(_diag('context origin must be finite JSON',path+'.context.'+key,'invalid'))
    if value is None:
        return None,origin
    if not _finite(value):
        diagnostics.append(_diag('context fact must be finite and nonnegative',path+'.context.'+key,'domain'))
        return None,origin
    return float(value),origin

def _result(identity,values,reasons,diagnostics,provenance):
    available={key:dict(state='available' if values[key] is not None else 'unavailable',
                        reason=None if values[key] is not None else reasons.get(key,'required facts are unknown'))
               for key in VALUE_KEYS}
    count=sum(v is not None for v in values.values())
    return dict(id=identity,method_version=METHOD_VERSION,
                status='available' if count==4 else 'partial' if count else 'unavailable',
                values=values,availability=available,diagnostics=diagnostics,provenance=provenance)

def _safe(operation,diagnostics,path):
    try:
        value=operation()
        if _finite(value):return float(value)
    except (ValueError,OverflowError,ZeroDivisionError):
        pass
    diagnostics.append(_diag('derived quantity is outside the finite nonnegative domain',path,'range'))
    return None

def evaluate(records,context,config,path=DEFAULT_PATH):
    records=_records(records)
    config=validate_config(config,records,path)
    diagnostics=[];origins={};facts={}
    for key in CONTEXT_KEYS:
        facts[key],origins[key]=_fact(context,key,diagnostics,path)
    width=config['bulged_beam_m'];beam=facts['beam_m']
    if width is not None and beam is not None and width<beam:
        raise AuxiliarySpaceError([_diag('total beam including bulges must not be smaller than canonical beam',
                                         path+'.bulged_beam_m','domain')])
    provenance=dict(method_version=METHOD_VERSION,source_assembly=SOURCE_ASSEMBLY,
        source_sha256=SOURCE_SHA256,source_location=SOURCE_LOCATION,declared_source=config['source'],
        scope='Independent torpedo space only; not firing arcs, geometry, strength, mass or a real-ship validation.',
        units=dict(deck_area_m2='m²',hull_volume_m3='m³',deck_ratio='ratio',hull_ratio='ratio'),
        assumptions=['loads means sets; integer count // effective sets for rotating locations',
            'loads=0 has an effective value of 1 without rewriting the declaration',
            'zero count has zero occupancy by product policy, excluded from source parity',
            'source area is ft² for locations 0..3 and ft³ for 4..8; convert once with 0.3048',
            'deck ratio uses declared/versioned proxy waterplane; hull ratio uses L × total bulged beam × normal T × Cb'],
        inputs=dict(**facts,bulged_beam_m=width,torpedo_ids=config['torpedo_ids'],context_origins=origins))
    hull_denominator=None
    hull_facts=[facts['length_m'],width,facts['draught_m'],facts['block_coeff']]
    if all(v is not None and v>0 for v in hull_facts):
        hull_denominator=_safe(lambda:math.prod(hull_facts),diagnostics,path+'.hull_denominator_m3')
    deck_denominator=facts['waterplane_area_m2']
    provenance['denominators']=dict(waterplane_area_m2=deck_denominator,hull_volume_m3=hull_denominator)

    def ratios(values,local,where):
        for key,numerator,denominator in (
            ('deck_ratio','deck_area_m2',deck_denominator),('hull_ratio','hull_volume_m3',hull_denominator)):
            values[key]=None if values[numerator] is None or denominator is None or denominator<=0 else \
                _safe(lambda:values[numerator]/denominator,local,where+'.'+key)

    readings=[]
    by_id={r['id']:r for r in records}
    for identity in config['torpedo_ids'] or []:
        record=by_id[identity];local=[];values=dict.fromkeys(VALUE_KEYS);reasons={}
        count=record['count'];loc=record['location_index'];loads=record['loads']
        length=record['length_m'];diameter=record['diameter_mm'];effective_sets=None
        if count==0:
            values.update(deck_area_m2=0.,hull_volume_m3=0.)
            local.append(_diag('zero count: explicit product zero-occupancy policy',path+'['+identity+']','zero_count_policy'))
        elif loc is not None:
            active='deck_area_m2' if loc<4 else 'hull_volume_m3'
            values['hull_volume_m3' if loc<4 else 'deck_area_m2']=0.
            ready=count is not None and length is not None and diameter is not None
            if loc in (1,2):
                effective_sets=max(loads,1) if loads is not None else None
                if effective_sets is None or count is None or effective_sets>count:
                    ready=False
                    reasons[active]='rotating space needs known sets no greater than the positive count'
            if loc==2 and beam is None:
                ready=False;reasons[active]='centre rotating space requires canonical beam'
            if ready:
                length_ft=length/M_PER_FT;size=diameter/25.4;n=count
                def quantity():
                    if loc==0:return length_ft*size/12*n
                    if loc in (1,2):
                        q=n//effective_sets
                        w=q*size/12+(q-1)*.5
                        if loc==1:return math.pi*(math.hypot(length_ft,w)*.5)**2+w*.5*length_ft
                        return math.hypot(length_ft,w)*(beam/M_PER_FT)*effective_sets
                    if loc==3:return length_ft*1.5*(size+6)/12*n
                    if loc<8:return length_ft*2.5*(size*2.75/12)**2*n
                    return length_ft*1.5*(size*1.5/12)**2*n
                values[active]=_safe(lambda:quantity()*M_PER_FT**(2 if loc<4 else 3),local,path+'['+identity+'].'+active)
        ratios(values,local,path+'['+identity+']')
        for key in VALUE_KEYS:
            if values[key] is None:
                reasons.setdefault(key,'required occupancy facts or a positive corresponding denominator are unknown')
        reading=_result(identity,values,reasons,local,dict(provenance,inputs=dict(provenance['inputs'],
            record=record,effective_sets=effective_sets)))
        readings.append(reading)
    values=dict.fromkeys(VALUE_KEYS)
    if config['torpedo_ids'] is not None:
        for key in ('deck_area_m2','hull_volume_m3'):
            entries=[r['values'][key] for r in readings]
            if all(v is not None for v in entries):
                values[key]=_safe(lambda:sum(entries),diagnostics,path+'.'+key)
    ratios(values,diagnostics,path)
    reasons={k:('torpedo scope is unknown' if config['torpedo_ids'] is None else
                'selected occupancy or a positive corresponding denominator is unknown') for k in VALUE_KEYS}
    result=_result(ID,values,reasons,diagnostics,provenance)
    result['records']=readings
    return result
