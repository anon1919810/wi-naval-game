"""Pure source-compatible battery, auxiliary weapon and fixed armour totals.

The original internal units are ft, in, lb and long ton. This adapter reuses
the recovered component kernels, while keeping the original independent total
barrel count, two mount groups and source zero-count torpedo occupancy.
"""
from __future__ import annotations
import copy
import math
import struct
from decimal import Decimal, ROUND_HALF_UP

if __package__:
    from . import concept_estimates as k, battery_layout as layout_kernel
    from . import fixed_armour, armour_defaults, sship_fields
else:
    import concept_estimates as k, battery_layout as layout_kernel
    import fixed_armour, armour_defaults, sship_fields

METHOD_VERSION = 'sps-3b3-components-v1'
SOURCE_SHA256 = fixed_armour.SOURCE_SHA256
FT = .3048
INCH = 25.4
KG = .45359236
LT = 1.0160469088


def _number(raw):
    try:
        return float(raw) if isinstance(raw, (int, float)) and not isinstance(raw, bool) and math.isfinite(float(raw)) else None
    except (OverflowError, ValueError):
        return None


def _f32(raw):
    try:
        return struct.unpack('f', struct.pack('f', raw))[0]
    except (OverflowError, struct.error):
        return math.copysign(math.inf, raw)


def _n2(raw):
    return float(Decimal(raw).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))


def _diagnostic(diags, path, message, code='components.unavailable'):
    diags.append(dict(code=code, severity='warning', blocking=False, path=path, message=message))


def _calc(diags, path, function, *values):
    if any(value is None for value in values):
        _diagnostic(diags, path, 'Required source input is unknown')
        return None
    try:
        value = function(*values)
        if value is None or not math.isfinite(value):
            raise ValueError('original expression is not a finite real number')
        return value
    except (ArithmeticError, ValueError, TypeError, struct.error) as error:
        _diagnostic(diags, path, str(error))
        return None


def _sum(rows, key):
    values = [row.get(key) for row in rows]
    return None if any(value is None for value in values) else sum(values)


def _scale(parameters, name, value, imperial, metric):
    scale = parameters.get(name)
    raw = _number(value)
    return None if raw is None or scale not in (0, 1) or isinstance(scale, bool) else raw * (metric if scale == 1 else imperial)


def _position(index, count, freeboard):
    if index is None:
        return None
    if not float(index).is_integer():
        return None
    index = int(index)
    local = index % 9
    if local < 3 or index > 17:
        return float(count)
    fraction = freeboard.get('fdLength' if local < 6 else 'adLength')
    return None if fraction is None else (.25, .5, .75)[(local - 3) % 3] * fraction


def _gun(parameters, bank, hull, freeboard, diags):
    prefix = 'gun%d_' % bank
    get = lambda name: _number(parameters.get(prefix + name))
    out = dict(bank=bank, id='gun%d' % bank)
    direct = {'barrels': 'barrels', 'mounts': 'mounts', 'gunType': 'type',
              'mountType': 'mount_type', 'dateGun': 'year', 'calLength': 'barrel_length_calibres',
              'magazine': 'magazine_rounds', 'layoutG1': 'layout_group1', 'layoutG2': 'layout_group2',
              'mountSuperG1': 'super_mounts_group1', 'mountSubG1': 'sub_mounts_group1',
              'mountSuperG2': 'super_mounts_group2', 'mountDeckG2': 'deck_mounts_group2',
              'mountSubG2': 'sub_mounts_group2', 'selectorG1': 'barrels_per_mount_group1',
              'selectorG2': 'barrels_per_mount_group2'}
    out.update({name: get(key) for name, key in direct.items()})
    for name in ('barrels', 'mounts', 'dateGun', 'magazine', 'mountSuperG1',
                 'mountSubG1', 'mountSuperG2', 'mountDeckG2', 'mountSubG2'):
        value = out[name]
        out[name] = int(value) if value is not None and value.is_integer() else None
    # Registry calls these selectors "guns_in_mount", so use its authoritative keys.
    for group in (1, 2):
        name = sship_fields.NAMES[(sship_fields.BARRELS_PER_MOUNT_G1 if group == 1 else sship_fields.BARRELS_PER_MOUNT_G2) + bank - 1]
        selector = _number(parameters.get(name))
        out['selectorG%d' % group] = selector
        out['perMountG%d' % group] = (sship_fields.PER_MOUNT_BARRELS[int(selector)]
            if selector is not None and selector.is_integer() and 0 <= selector < 15 else None)
        out['weightAdjG%d' % group] = None if selector is None else (.75 if selector in sship_fields.SHARED_CRADLE_INDICES else 1.0)
    out['superSuper'] = parameters.get(prefix + 'superstructure_above')
    out['subSub'] = parameters.get(prefix + 'submarine_mount')
    out['calibre'] = _scale(parameters, prefix + 'scale', parameters.get(prefix + 'calibre'), 1, 1 / INCH)
    out['calMet'] = None if out['calibre'] is None else out['calibre'] * INCH
    for native, field in [('armFace', 'turret_face_armour'), ('armBack', 'turret_rear_armour'), ('armBottom', 'turret_bottom_armour')]:
        out[native] = _scale(parameters, 'armour_scale', parameters.get(prefix + field), 1, 1 / INCH)
    m = out['mountType']
    out['mountAdj'] = k.MOUNT_ADJUSTMENT[int(m)] if m is not None and m.is_integer() and 0 <= m < 7 else None
    out['mountsG2'] = _calc(diags, prefix + 'mountsG2', lambda *v: sum(v),
                           out['mountSuperG2'], out['mountDeckG2'], out['mountSubG2'])
    out['mountsG1'] = _calc(diags, prefix + 'mountsG1', lambda total, second: total - second, out['mounts'], out['mountsG2'])
    out['mountDeckG1'] = _calc(diags, prefix + 'mountDeckG1', lambda total, raised, lower: total - raised - lower,
                               out['mountsG1'], out['mountSuperG1'], out['mountSubG1'])
    for group in (1, 2):
        for level in ('Super', 'Sub'):
            out['gun%sG%d' % (level, group)] = _calc(diags, prefix + level,
                lambda number, per: number * per, out['mount%sG%d' % (level, group)], out['perMountG%d' % group])
    out['gunDeckG2'] = _calc(diags, prefix + 'gunDeckG2', lambda a, b: a * b, out['mountDeckG2'], out['perMountG2'])
    out['gunDeckG1'] = _calc(diags, prefix + 'gunDeckG1', lambda total, *v: total - sum(v),
        out['barrels'], out['gunSuperG1'], out['gunSubG1'], out['gunSuperG2'], out['gunSubG2'], out['gunDeckG2'])
    profile = dict(forecastle_fraction=freeboard.get('fcLength'),
                   forward_deck_fraction=freeboard.get('fdLength'),
                   forward_fore_m=freeboard.get('freeFDFor'),
                   forward_aft_m=freeboard.get('freeFDAft'),
                   aft_fore_m=freeboard.get('freeADFor'), aft_aft_m=freeboard.get('freeADAft'))
    for group in (1, 2):
        count, index = out['mountsG%d' % group], out['layoutG%d' % group]
        out['freeGunG%d' % group] = (0.0 if count == 0 or index == 18 else
            _calc(diags, prefix + 'freeGunG%d' % group, lambda loc, n: layout_kernel.free_gun_m(int(loc), n, profile), index, count))
        out['positionG%d' % group] = _position(index, 1 if group == 1 else 0, freeboard)
    out['freeGun'] = _calc(diags, prefix + 'freeGun', lambda a, b, x, y: (a*x+b*y)/(a+b) if a+b else 0.,
        out['mountsG1'], out['mountsG2'], out['freeGunG1'], out['freeGunG2'])
    out['weightAdj'] = _calc(diags, prefix + 'weightAdj', lambda a, b, x, y: (a*x+b*y)/(a+b) if a+b else 1.,
        out['mountsG1'], out['mountsG2'], out['weightAdjG1'], out['weightAdjG2'])
    if out['barrels'] == 0:
        out['super'] = 1.
    else:
        out['super'] = _calc(diags, prefix + 'super', lambda b, a, c, d, e, cal, free:
            ((a+c*(2 if out['superSuper'] else 1)-d-e*(2 if out['subSub'] else 1))/b*max(7.5,cal*.6)+free)/free,
            out['barrels'], out['gunSuperG1'], out['gunSuperG2'], out['gunSubG1'], out['gunSubG2'], out['calibre'], out['freeGun'])
    path = '$.guns.groups[%d]' % (bank - 1)
    empty = out['barrels'] == 0 or out['calibre'] == 0
    out['dateGunAdj'] = 0. if out['dateGun']==0 else _calc(diags, path + '.dateGunAdj', k.gun_date_factor, out['dateGun'])
    out['autoShellWeight'] = (0. if out['calibre'] == 0 else
        _calc(diags, path + '.autoShellWeight', k.estimated_shell_lb, out['calibre'], out['calLength'], out['dateGunAdj']))
    shell = get('shell_weight')
    # The original lb TextChanged also writes the n2 kg field, whose handler
    # converts it back. That round trip is observable in broadside/magazine.
    out['shellWeightDeclared'] = shell
    out['shellWeight'] = _calc(diags, path + '.shellWeight',
        lambda lb: _f32(_n2(_f32(_f32(lb) * _f32(KG))) / _f32(KG)), shell)
    out['gunWeight'] = 0. if empty else _calc(diags, path + '.gunWeight', k.gun_mass_long_tons,
        out['calibre'], out['calLength'], out['dateGunAdj'], out['barrels'])
    out['mountWeight'] = (0. if empty else _calc(diags, path + '.mountWeight',
        lambda mass, cal, gt, mt, adj: k.mount_mass_long_tons(mass, cal, k.GUN_TYPES[int(gt)], k.MOUNT_TYPES[int(mt)], weight_adjustment=adj),
        out['gunWeight'], out['calibre'], out['gunType'], out['mountType'], out['weightAdj']))
    out['magazineWeight'] = _calc(diags, path + '.magazineWeight', lambda b, r, s: b*r*s/2240*1.2444444,
        out['barrels'], out['magazine'], out['shellWeight'])
    out['broadsideWeight'] = _calc(diags, path + '.broadsideWeight', lambda b, s: b*s, out['barrels'], out['shellWeight'])
    armour = None
    if out['barrels'] == 0:
        out.update(armWeightFace=0., armWeightBack=0., armWeightBottom=0., armWeight=0.)
    elif all(out[key] is not None for key in ('calibre','gunType','mountType','barrels','dateGun')):
        groups = {}
        for group in (1, 2):
            group_barrels = (out['gunSuperG2'] + out['gunDeckG2'] + out['gunSubG2']) if group == 2 and all(out[x] is not None for x in ('gunSuperG2','gunDeckG2','gunSubG2')) else None
            if group == 1:
                second = out['gunSuperG2'], out['gunDeckG2'], out['gunSubG2']
                group_barrels = None if any(x is None for x in second) else out['barrels'] - sum(second)
            groups['group%d' % group] = dict(mounts=out['mountsG%d' % group], barrels=group_barrels,
                per_mount=out['perMountG%d' % group], mount_selector=out['selectorG%d' % group], weight_adjustment=out['weightAdjG%d' % group])
        declared = {key: None if out[native] is None else out[native]*INCH
                    for key, native in [('face_mm','armFace'),('rear_roof_mm','armBack'),('barbette_mm','armBottom')]}
        armour = layout_kernel._mixed_armour({'armour':declared}, groups,
            dict(calibre_mm=out['calibre']*INCH, gun_index=int(out['gunType']), mount_index=int(out['mountType']), year=out['dateGun'],
                 gun_type=k.GUN_TYPES[int(out['gunType'])], mount_type=k.MOUNT_TYPES[int(out['mountType'])],
                 selector_g1=out['selectorG1'], selector_g2=out['selectorG2'],
                 mounts_g1=out['mountsG1'], mounts_g2=out['mountsG2'], barrels=out['barrels']),
            None if out['freeGun'] is None else out['freeGun']*FT, out['super'], path, diags)
        values = armour['values']
        out.update(armWeightFace=values.get('face_long_tons'), armWeightBack=values.get('rear_roof_long_tons'),
                   armWeightBottom=values.get('barbette_long_tons'), armWeight=values.get('total_long_tons'))
    else:
        out.update(armWeightFace=None, armWeightBack=None, armWeightBottom=None, armWeight=None)
    out['armour_reading'] = armour
    out['totalWeight'] = _sum([out], 'gunWeight')
    out['totalWeight'] = _calc(diags, path + '.totalWeight', lambda *a: sum(a),
        out['gunWeight'], out['mountWeight'], out['armWeight'])
    out['weight'] = out['autoShellWeight']
    return out


def _auxiliary(parameters, hull, diags):
    rows = []
    for name, kind in [('torpedo1','torpedo'),('torpedo2','torpedo'),('mine1','mine'),('deck_gun1','depth_charge'),('deck_gun2','depth_charge')]:
        get = lambda key: _number(parameters.get(name + '_' + key))
        group = dict(id=name, kind=kind, number=get('count'), loads=get('rounds'),
            size=_scale(parameters,name+'_scale',get('size'),1,1/(INCH if kind=='torpedo' else KG)),
            length=_scale(parameters,name+'_scale',get('length'),1,1/FT) if kind=='torpedo' else None,
            location=get('location'))
        n, size, length, loads, loc = [group[key] for key in ('number','size','length','loads','location')]
        if kind == 'torpedo':
            if loads == 0:
                loads = group['loads'] = 1.
            group['weaponWeight'] = (0. if n == 0 or size == 0 or length == 0 else
                _calc(diags,'$.auxiliary.'+name+'.weaponWeight',lambda n,s,l,y:
                    (math.pi*s*s*l/((max(1907-y,0)+25)*937)+.004*(y-1890))*n,
                    n,size,length,hull.get('dateHull')))
            def area(n,s,l,sets,location):
                if location == 0:return l*s/12*n
                if location in (1,2):
                    q=int(n/sets); w=q*s/12+(q-1)*.5
                    return math.pi*(math.hypot(l,w)*.5)**2+w*.5*l if location==1 else math.hypot(l,w)*hull['beam']*sets
                if location == 3:return l*1.5*(s+6)/12*n
                if 4 <= location <= 7:return l*2.5*(s*2.75/12)**2*n
                if location == 8:return l*1.5*(s*1.5/12)**2*n
                return 0.
            group['area'] = _calc(diags,'$.auxiliary.'+name+'.area',area,n,size,length,loads,loc)
            coeff = .25 if loc in (0,3,8) else (1. if loc in (1,2,4,5,6,7) else 0. if loc is not None else None)
        else:
            group['area'] = 0.
            group['weaponWeight'] = _calc(diags,'$.auxiliary.'+name+'.weaponWeight',lambda n,r,s:(n+r)*s/2240,n,loads,size)
            coeff = ({0:.25,1:1.,2:1.,3:1.} if kind=='mine' else {0:.25,1:.5,2:.5,3:10.}).get(loc,0. if loc is not None else None)
        group['mountWeight'] = _calc(diags,'$.auxiliary.'+name+'.mountWeight',lambda a,b:a*b,group['weaponWeight'],coeff)
        group['totalWeight'] = _calc(diags,'$.auxiliary.'+name+'.totalWeight',lambda a,b:a+b,group['weaponWeight'],group['mountWeight'])
        rows.append(group)
    result = dict(groups=rows, weight=_sum(rows,'totalWeight'))
    torpedoes=rows[:2]
    for field, predicate, denominator in [
        ('spaceDeck',lambda loc:loc<4,hull.get('waterplaneArea')),
        ('spaceHull',lambda loc:loc>3,_calc(diags,'$.auxiliary.hullVolume',lambda *v:math.prod(v),
                                          hull.get('length'),hull.get('beamBulges'),hull.get('draught'),hull.get('block')))]:
        selected=[row for row in torpedoes if row['location'] is not None and predicate(row['location'])]
        numerator = None if any(row['location'] is None for row in torpedoes) else _sum(selected,'area')
        result[field]=_calc(diags,'$.auxiliary.'+field,lambda a,b:a/b,numerator,denominator)
    mapping={'miscWeightVital':'misc_weight_vital','miscWeightHull':'misc_weight_hull',
             'miscWeightDeck':'misc_weight_deck','miscWeightAbove':'misc_weight_above','voidWeight':'misc_weight_void'}
    result.update({key:_number(parameters.get(value)) for key,value in mapping.items()})
    result['miscWeight']=_sum([{'value':result[key]} for key in mapping],'value')
    return result


def _armour(parameters, hull, freeboard, guns, diags, machinery_mass_lt=0., editing=None):
    result={}
    scalar=[('beltMain','armour_belt_main_thickness',False),('beltEnds','armour_belt_ends_thickness',False),
            ('beltUpper','armour_belt_upper_thickness',False),('bulkhead','armour_bulkhead_thickness',False),
            ('bulge','armour_bulge_thickness',False),('deck','armour_deck_thickness',False),
            ('deckFC','armour_deck_forecastle_thickness',False),('deckQD','armour_deck_quarterdeck_thickness',False),
            ('conningFor','armour_conning_forward_thickness',False),('conningAft','armour_conning_aft_thickness',False)]
    for label,prefix in [('beltMain','armour_belt_main'),('beltEnds','armour_belt_ends'),('beltUpper','armour_belt_upper'),
                         ('bulkhead','armour_bulkhead'),('bulge','armour_bulge')]:
        scalar.extend([(label+'Length',prefix+'_length',True),(label+'Height',prefix+'_height',True)])
    scalar.append(('bulkheadBeam','armour_bulkhead_beam',True))
    for key,name,length in scalar:
        result[key]=_scale(parameters,'armour_scale',parameters.get(name),1,1/FT if length else 1/INCH)
    result['beltsIncline']=_number(parameters.get('armour_belt_main_inclination'))
    result['bulkheadType']=_number(parameters.get('armour_bulkhead_type'))
    result['deckCoverage']=_number(parameters.get('armour_deck_coverage'))
    context={key:None if hull.get(source) is None else hull[source]*factor for key,source,factor in [
        ('length_m','length',FT),('beam_m','beam',FT),('co_waterplane','coWaterPlane',1),
        ('waterplane_area_m2','waterplaneArea',FT*FT),('displacement_t','displacement',LT)]}
    saved_context = (editing or {}).get('armour_read_context', {})
    if 'deck_machinery_lt' in saved_context:
        machinery_mass_lt = saved_context['deck_machinery_lt']
    context.update(machinery_mass_t=None if machinery_mass_lt is None else machinery_mass_lt*LT,
                   ammunition_mass_t=None if guns.get('magazine') is None else guns['magazine']*LT)
    readings=[]
    read_context={'deck_machinery_lt': machinery_mass_lt}
    for kind,label in [('belt_main','beltMain'),('belt_ends','beltEnds'),('belt_upper','beltUpper'),
                       ('bulkhead','bulkhead'),('bulge','bulge'),('deck','deck'),('conning','conningFor')]:
        record=dict(id=kind,kind=kind,source='SpringSharp3b3 source inputs',
                    thickness_mm=None if result[label] is None else result[label]*INCH)
        if kind in ('belt_main','belt_ends','belt_upper','bulkhead','bulge'):
            record.update(length_m=None if result[label+'Length'] is None else result[label+'Length']*FT,
                          height_m=None if result[label+'Height'] is None else result[label+'Height']*FT)
        if kind=='deck':
            record.update(coverage_index=result['deckCoverage'],forecastle_fraction=freeboard.get('fcLength'),
                          quarterdeck_fraction=freeboard.get('qdLength'),
                          forecastle_mm=None if result['deckFC'] is None else result['deckFC']*INCH,
                          quarterdeck_mm=None if result['deckQD'] is None else result['deckQD']*INCH)
        if kind=='conning':record['aft_mm']=None if result['conningAft'] is None else result['conningAft']*INCH
        reading=fixed_armour.evaluate(record,context,path='$.armour.'+kind)
        if kind in ('belt_main', 'belt_upper'):
            # The source opens a file after ClearMenu has set shafts to zero.
            # Belts are evaluated before the final shaft input; the later
            # waterplane update refreshes the deck but does not refresh belts.
            # Keep that observable file-open context separate from the current
            # deck/waterplane coefficient. Edit commands can supply a snapshot.
            belt_context = dict(context)
            block = hull.get('block')
            stern = parameters.get('stern')
            if block is not None and stern in (-1, 0, 1, 2, 3):
                try:
                    belt_context['co_waterplane'] = k.waterplane_coefficient(
                        block, sship_fields.STERN_TYPES[int(stern)] if stern >= 0 else 'cruiser', 1)
                except (ValueError, ArithmeticError):
                    belt_context['co_waterplane'] = None
            context_key = 'belt_main_cwp' if kind == 'belt_main' else 'belt_upper_cwp'
            if context_key in saved_context:
                belt_context['co_waterplane'] = saved_context[context_key]
            read_context[context_key] = belt_context['co_waterplane']
            reading = fixed_armour.evaluate(record, belt_context, path='$.armour.'+kind)
        readings.append(reading)
        diags.extend(reading['diagnostics'])
        result[{'belt_main':'weightBeltMain','belt_ends':'weightBeltEnds','belt_upper':'weightBeltUpper',
                'bulkhead':'weightBulkhead','bulge':'weightBulge','deck':'weightDeck','conning':'weightConning'}[kind]]=reading['values']['total_long_tons']
    result['readings']=readings
    result['read_context']=read_context
    result['weightBelts']=_calc(diags,'$.armour.weightBelts',lambda *v:sum(v),result['weightBeltMain'],result['weightBeltEnds'],result['weightBeltUpper'])
    result['weight']=_calc(diags,'$.armour.weight',lambda *v:sum(v),result['weightBelts'],result['weightBulkhead'],result['weightBulge'],result['weightDeck'],result['weightConning'],guns['armWeight'])
    result['beltCover']=_calc(diags,'$.armour.beltCover',lambda l,L:l/L/.65,result['beltMainLength'],hull.get('length'))
    result['maxBeltHeight']=_calc(diags,'$.armour.maxBeltHeight',lambda t,f,a:(t+f)/math.cos(abs(a*math.pi/180))+.02,
        hull.get('draught'),freeboard.get('freeDistributed'),result['beltsIncline'])
    if 'belt_height_ft' in saved_context:
        result['maxBeltHeight']=saved_context['belt_height_ft']
    read_context['belt_height_ft']=result['maxBeltHeight']
    result['armourWarn']=None if result['weight'] is None or hull.get('displacement') is None else result['weight']>=hull['displacement']>0
    return result


def evaluate(parameters, hull, freeboard, *, machinery_mass_lt=0., editing=None):
    """Compute only declared empirical components; no project ledger is read."""
    parameters=parameters if isinstance(parameters,dict) else {}
    hull=hull if isinstance(hull,dict) else {}
    freeboard=freeboard if isinstance(freeboard,dict) else {}
    diags=[]
    groups=[_gun(parameters,bank,hull,freeboard,diags) for bank in range(1,6)]
    for row in groups:
        context=(editing or {}).get('shell_weight_lb',{})
        if str(row['bank']) in context:
            row['shellWeight']=context[str(row['bank'])]
            row['magazineWeight']=_calc(diags,'$.guns.magazine',lambda b,r,s:b*r*s/2240*1.2444444,row['barrels'],row['magazine'],row['shellWeight'])
            row['broadsideWeight']=_calc(diags,'$.guns.broadside',lambda b,s:b*s,row['barrels'],row['shellWeight'])
    guns={'groups':groups}
    for name,field in [('unfixedWeight','gunWeight'),('gunWeight','gunWeight'),('mountWeight','mountWeight'),('magazine','magazineWeight'),
                       ('broadside','broadsideWeight'),('armWeight','armWeight')]:
        guns[name]=_sum(groups,field)
    guns['gunsWeight']=_calc(diags,'$.guns.gunsWeight',lambda a,b:a+b,guns['gunWeight'],guns['mountWeight'])
    guns['borneWeight']=_calc(diags,'$.guns.borneWeight',lambda *v:sum(v),
        *[_calc(diags,'$.guns.borneWeight',lambda w,a:2*w*a,row['gunWeight'],row['mountAdj']) for row in groups])
    denominator=_calc(diags,'$.guns.superFactor',lambda a,b:a+b,guns['gunsWeight'],guns['armWeight'])
    guns['superFactor']=(1. if denominator==0 else _calc(diags,'$.guns.superFactor',lambda *v:sum(v)/denominator,
        *[_calc(diags,'$.guns.superFactor',lambda t,s,a:t*s*a,row['totalWeight'],row['super'],row['mountAdj']) for row in groups]))
    guns['gunWarn']=None if hull.get('displacement') is None or guns['broadside'] is None else 0<hull['displacement']<=guns['broadside']/4
    auxiliary=_auxiliary(parameters,hull,diags)
    armour=_armour(parameters,hull,freeboard,guns,diags,machinery_mass_lt,editing)
    return dict(method_version=METHOD_VERSION,status='partial' if diags else 'available',guns=guns,auxiliary=auxiliary,armour=armour,
                diagnostics=diags,provenance=dict(source_sha256=SOURCE_SHA256,units='ft / in / lb / long ton',
                source='Recovered 3b3 empirical component methods; not physical mass or CG.'))


def apply_edit(parameters, editing, command, *, hull=None, freeboard=None):
    """Batch shell controls and original default dimensions; no persistence."""
    params=copy.deepcopy(parameters);edit=copy.deepcopy(editing or {});diags=[]
    groups=command.get('groups','all')
    banks=list(range(1,6)) if groups=='all' else groups
    kind=command.get('kind')
    if kind=='set_shell_weight':
        bank=command.get('group');unit=command.get('unit');value=_number(command.get('value'))
        if type(bank) is not int or not 1<=bank<=5 or unit not in ('lb','kg') or value is None:
            _diagnostic(diags,'$.command','Choose group 1..5, lb or kg, and a finite shell weight','components.command_invalid')
        elif bank in edit.get('locked_shell_groups',[]):
            _diagnostic(diags,'$.command','Unlock this shell weight before editing it','components.shell_locked')
        else:
            lb=value if unit=='lb' else _n2(_f32(_f32(value)/_f32(KG)))
            params['gun%d_shell_weight'%bank]=lb
            if unit=='kg':edit.setdefault('shell_weight_lb',{})[str(bank)]=_f32(lb)
            else:edit.setdefault('shell_weight_lb',{}).pop(str(bank),None)
    elif kind == 'set_parameter':
        name = command.get('name')
        value = command.get('value')
        if name not in sship_fields.NAMES[:sship_fields.PADDING_FIRST]:
            _diagnostic(diags, '$.command.name', 'Unknown source field', 'components.command_invalid')
        else:
            params[name] = value
            if name.startswith('gun') and len(name) > 5 and name[3] in '12345':
                bank = int(name[3])
                suffix = name[5:]
                if suffix=='shell_weight':
                    edit.setdefault('shell_weight_lb',{}).pop(str(bank),None)
                if suffix == 'barrels' and params.get('gun%d_mounts' % bank) == 0:
                    params['gun%d_mounts' % bank] = value
                if suffix in ('calibre', 'barrel_length_calibres', 'year') and bank not in edit.get('locked_shell_groups', []):
                    current = _gun(params, bank, hull or {}, freeboard or {}, diags)
                    auto = current['autoShellWeight']
                    if auto is not None:
                        params['gun%d_shell_weight' % bank] = _n2(auto)
                        edit.setdefault('shell_weight_lb',{})[str(bank)]=_f32(auto)
    elif kind in ('lock_shells','unlock_shells'):
        if not isinstance(banks,list) or any(type(n) is not int or not 1<=n<=5 for n in banks):
            _diagnostic(diags,'$.command.groups','Select groups 1..5','components.command_invalid')
        else:
            locked=set(edit.get('locked_shell_groups',[]))
            for bank in banks:
                if kind=='lock_shells':locked.add(bank)
                else:
                    locked.discard(bank)
            edit['locked_shell_groups']=sorted(locked)
    elif kind=='armour_defaults':
        h,f=hull or {},freeboard or {}
        config=dict(source='Original 3b3 default dimensions',forecastle_fraction=f.get('fcLength'),quarterdeck_fraction=f.get('qdLength'))
        context={name:None if h.get(key) is None else h[key]*factor for name,key,factor in [
            ('length_m','length',FT),('beam_m','beam',FT),('draught_m','draught',FT),('block_coeff','block',1)]}
        context['freeboard_m']=None if f.get('freeDistributed') is None else f['freeDistributed']*FT
        values=armour_defaults.evaluate(config,context)['values']
        mapping={'main_length_m':'armour_belt_main_length','main_height_m':'armour_belt_main_height','ends_length_m':'armour_belt_ends_length',
                 'ends_height_m':'armour_belt_ends_height','upper_length_m':'armour_belt_upper_length','upper_height_m':'armour_belt_upper_height',
                 'bulkhead_length_m':'armour_bulkhead_length','bulkhead_height_m':'armour_bulkhead_height'}
        for key,name in mapping.items():
            value=values[key]
            if value is not None:params[name]=_n2(value if params.get('armour_scale')==1 else value/FT)
    else:
        _diagnostic(diags,'$.command.kind','Unsupported component command','components.command_invalid')
    return dict(parameters=params,editing=edit,diagnostics=diags)

