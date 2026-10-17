"""Source Single arithmetic at the observable hull/performance boundaries.

The continuous component kernels remain reusable; this adapter supplies the
32-bit storage and arithmetic that the original desktop display observes.
"""
import math
import struct

class Single(float):
    def __new__(cls,value):
        return float.__new__(cls,struct.unpack('f',struct.pack('f',value))[0])
    def __add__(a,b):return Single(float(a)+float(Single(b)))
    __radd__=__add__
    def __sub__(a,b):return Single(float(a)-float(Single(b)))
    def __rsub__(a,b):return Single(float(Single(b))-float(a))
    def __mul__(a,b):return Single(float(a)*float(Single(b)))
    __rmul__=__mul__
    def __truediv__(a,b):return Single(float(a)/float(Single(b)))
    def __rtruediv__(a,b):return Single(float(Single(b))/float(a))


def hull_readings(parameters,editing,hull,freeboard):
    """Round native page reads before downstream source Single expressions."""
    h=dict(hull or {});f=dict(freeboard or {})
    S=Single
    try:
        scale=parameters['hull_scale']
        if scale not in (0,1):return h,f
        def length(name):
            value=S(parameters[name])
            return value/S(.3048) if scale==1 else value
        L=S(h['length']) if editing.get('length_driver')=='overall' else length('length_waterline')
        B,BB,T=[length(name) for name in ('beam_moulded','beam_at_bulges','draught_normal')]
        if editing.get('displacement_driver')=='displacement':
            D=S(editing['normal_displacement_lt']);Cb=D/(L*BB*T/35)
        else:
            Cb=S(parameters['block_coefficient_normal']);D=L*BB*T*Cb/35
        block=max(float(Cb),.4);ratio=block/(1.006-.0056*block**-3.56)
        stern=parameters['stern'];shafts=parameters['shafts']
        if stern==2:cwp=min(.262+.81*ratio,1)
        elif stern==1:cwp=min(.262+.79*ratio,1)
        elif shafts<2 or Cb>=.75:cwp=min(.175+.875*ratio,1)
        else:cwp=.262+.76*ratio
        cwp=S(cwp)
        if Cb<.4:cwp=cwp-S(.0281-(float(Cb)-.3)**1.55)
        updates=dict(length=L,beam=B,beamBulges=BB,draught=T,block=Cb,displacement=D,
                     lengthBeam=L/BB,coWaterPlane=cwp,waterplaneArea=cwp*L*B,
                     wettedSurface=S(float(L*T)*1.7+float(D*35/T)))
        if any(not math.isfinite(v) for v in updates.values()):return h,f
        h.update({k:float(v) for k,v in updates.items()})
        endpoints=dict(freeFCFor='forecastle_fore',freeFCAft='forecastle_aft',freeFDFor='flat_deck_fore',freeFDAft='flat_deck_aft',freeADFor='afterdeck_fore',freeADAft='afterdeck_aft',freeQDFor='quarterdeck_fore',freeQDAft='quarterdeck_aft')
        # Locked-depth writebacks are solved by the hull editor before this read.
        for key,suffix in endpoints.items():f[key]=float(length('freeboard_'+suffix))
        for key,suffix in [('fcLength','forecastle_length'),('fdLength','flat_deck_length'),('qdLength','quarterdeck_length')]:f[key]=float(S(parameters['freeboard_'+suffix])/100)
        f['adLength']=float(S(1)-S(f['fcLength'])-S(f['fdLength'])-S(f['qdLength']))
        for key,fore,aft,factor in [('freeFC','freeFCFor','freeFCAft',.4),('freeFD','freeFDAft','freeFDFor',.5),('freeAD','freeADAft','freeADFor',.5),('freeQD','freeQDAft','freeQDFor',.5)]:
            f[key]=float(S(f[aft])+(S(f[fore])-S(f[aft]))*factor)
        f['freeboard']=float(sum((S(f[key])*S(f[part]) for key,part in [('freeFC','fcLength'),('freeFD','fdLength'),('freeAD','adLength'),('freeQD','qdLength')]),S(0)))
        f['freeDistributed']=float((S(f['freeFD'])*S(f['fdLength'])+S(f['freeAD'])*S(f['adLength']))/(S(f['fdLength'])+S(f['adLength'])))
        avg=S(f['freeboard'])
        f['freeboardCap']=float(avg*avg/(B/3) if avg>B/3 else avg-6 if editing.get('submerged_casemate') else avg)
    except (KeyError,TypeError,ValueError,ArithmeticError,struct.error):
        return dict(hull or {}),dict(freeboard or {})
    return h,f


def flotation(values):
    S=Single;v={key:S(value) if type(value) in (int,float) else value for key,value in values.items()}
    comp,st,room=v['composite_strength'],v['stability_adjusted'],v['room_float']
    if comp>=0:
        free=v['freeboard_cap_ft' if v['use_capped_freeboard'] else 'freeboard_distributed_ft']
        result=(free*v['waterplane_sqft']/35+v['displacement_lt'])/2
        result=result*S(math.sqrt(st) if st>1 else math.pow(st,4))
        if comp<1:result=result*comp
    else:result=S(0)
    result=result/(S(math.pow(room,2)) if room>1 else room)*v['date_float']
    return float(result)
