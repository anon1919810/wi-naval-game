"""Original 3b3 cross-field warnings and readable armament descriptions.

Checks report source conditions without changing declarations or blocking
independent readings. Unknown inputs produce undecidable rule entries.
"""
from __future__ import annotations
import math
from decimal import Decimal, ROUND_HALF_UP, localcontext
if __package__:
    from . import sship_fields as fields, sps_field_catalog as catalog
else:
    import sship_fields as fields, sps_field_catalog as catalog
METHOD_VERSION='sps-3b3-review-v1'
MOUNT_LABELS=('Single mount','2 row twin mount','4 row quad mount','Twin mount','2-gun mount',
              '2 row quad mount','Triple mount','3-gun mount','2 row sextuple mount','Quad mount',
              '4-gun mount','2 row octuple mount','Quintuple mount','5-gun mount','2 row decuple mount')
GUN_NAMES=('Main Battery','2nd Battery','3rd Battery','4th Battery','5th Battery')


def fmt(value, places=0):
    if value is None or not isinstance(value,(int,float)) or not math.isfinite(value):return '—'
    # .NET Framework Single's N-format uses its seven significant digits before
    # decimal rounding; a double formatter changes reachable half-ton readouts.
    with localcontext() as context:
        context.prec=350
        number=Decimal(format(value,'.7g')).quantize(Decimal(1).scaleb(-places),rounding=ROUND_HALF_UP)
        return format(number,',.%df'%places)


def scaled(value,factor):
    return None if value is None else value*factor


def _item(code,message,path='$',condition=True,source='SpringSharp3b3'):
    return dict(code=code,message=message,path=path,condition=condition,source_rule=source,
                severity='warning',blocking=False)


def gun_rules(group):
    aliases={'m':'mountType','t':'gunType','y':'dateGun','c':'calibre','f':'armFace','r':'armBack','b':'armBottom',
             'n':'barrels','a':'mounts','d':'mountDeckG1','s1':'mountSubG1','s2':'mountSubG2',
             'g1':'mountsG1','g2':'mountsG2','l1':'layoutG1','l2':'layoutG2','shell':'shellWeight','auto':'autoShellWeight'}
    v={key:group.get(name) for key,name in aliases.items()}
    definitions=[
      ('central_broadside','m g1 g2 l1 l2',lambda: (v['g1']>0 and v['m']==0 and v['l1']<9) or (v['g2']>0 and v['m']==0 and v['l2']<9),'Centrally mounted broadsides not allowed'),
      ('muzzle_turret','m t',lambda:v['m']==3 and v['t']==0,'Muzzle loading modern turret not allowed'),
      ('mount_qf','m t',lambda:v['m']<2 and v['t']==2,'Wrong mount for quickfiring gun'),
      ('mount_aa','m t',lambda:(v['m']<3 or v['m']>5) and v['t']==3,'Wrong mount for anti-aircraft gun'),
      ('mount_dp','m t',lambda:(v['m']<3 or v['m']>5) and v['t']==4,'Wrong mount for dual purpose gun'),
      ('mount_rapid','m t',lambda:(v['m']<3 or v['m']>4) and v['t']==5,'Wrong mount for rapid fire gun'),
      ('mount_mg','m t',lambda:v['m']<5 and v['t']==6,'Wrong mount for machine gun'),
      ('era_full_turret','m y',lambda:v['y']<1860 and v['m']==1,'Date too early for a full turret'),
      ('era_open_barbette','m y',lambda:v['y']<1860 and v['m']==2,'Date too early for an open barbette'),
      ('era_hoist','m y',lambda:v['y']<1860 and v['m']==4,'Date too early for pivot gun with hoist'),
      ('era_modern_turret','m y',lambda:v['y']<1880 and v['m']==3,'Date too early for a modern turret'),
      ('era_qf','t y',lambda:v['y']<1880 and v['t']==2,'Date too early for quickfiring gun'),
      ('era_mg','t y',lambda:v['y']<1880 and v['t']==6,'Date too early for machine gun'),
      ('era_aa','t y',lambda:v['y']<1910 and v['t']==3,'Date too early for anti-air gun'),
      ('era_dual_purpose','t y',lambda:v['y']<1920 and v['t']==4,'Date too early for dual purpose gun'),
      ('era_rapid','t y',lambda:v['y']<1940 and v['t']==5,'Date too early for rapid fire gun'),
      ('calibre_large','t c',lambda:v['t']<2 and v['c']>22,'Calibre too large'),
      ('calibre_qf_aa_dp','t c',lambda:1<v['t']<5 and v['c']>6.5,'Calibre too large for QF, AA or DP gun'),
      ('calibre_rapid','t c',lambda:v['t']==5 and v['c']>8.5,'Calibre too large for rapid fire gun'),
      ('calibre_mg','t c',lambda:v['t']==6 and v['c']>1.1,'Calibre too large for machine gun'),
      ('armour_mount','m c f r b',lambda:v['m'] in (4,5) and v['c']<4 and max(v['f'],v['r'],v['b'])>3,'Armour too thick for mount'),
      ('armour_type','t f r b',lambda:v['t'] in (3,6) and (v['f']>2 or v['r']>1 or v['b']>1),'Armour too thick for type'),
      ('armour_below','m b',lambda:(v['m']<2 or v['m']==5) and v['b']>0,'mount cannot have below deck armour'),
      ('armour_above','m f r',lambda:v['m']==2 and (v['f']>0 or v['r']>0),'mount cannot have above deck armour'),
      ('below_freeboard','m s1 s2',lambda:0<v['m']<4 and v['s1']+v['s2']>0,'mount cannot be below freeboard deck'),
      ('broadside_face_only','m s1 s2 r',lambda:v['m']==0 and v['s1']+v['s2']>0 and v['r']>0,'Low broadside gun only have face armour'),
      ('turret_face','m f',lambda:v['m'] in (1,3) and v['f']==0,'Turret mount must have face armour'),
      ('barbette_armour','m b',lambda:v['m'] in (2,3) and v['b']==0,'mount must have barbette armour'),
      ('mount_count','m n a',lambda:v['m'] in (0,6) and v['n']!=v['a'],'No. of mounts must equal No. of gun'),
      ('location_count','d',lambda:v['d']<0,'Too many mounts in specific locations'),
      ('shell_heavy','shell auto',lambda:v['shell']>v['auto']*1.5,'Shell weight too heavy'),
      ('shell_light','shell auto',lambda:v['shell']<v['auto']*.5,'Shell weight too light')]
    result=[]
    bank=int(group.get('bank') or 1)
    for index,(code,deps,test,message) in enumerate(definitions):
        known=all(v[key] is not None for key in deps.split())
        condition=bool(test()) if known else None
        result.append(_item('gun.'+code,'Warning: '+message+' - '+GUN_NAMES[bank-1],
             '$.parameters.gun%d'%bank,condition,'GunControl.gunWarningsAll rule %d/32'%(index+1)))
    return result


def layout_text(index,mounts,freeboard):
    if index is None or mounts is None:return 'layout undetermined'
    if index==18:return 'layout not set'
    if index==0:
        if mounts==1:return 'on centreline forward' if freeboard.get('fcLength',0)+freeboard.get('fdLength',0)>=.5 else 'on centreline aft'
        return 'on centreline, evenly spread'
    if index==9:return 'on sides amidships' if mounts<3 else 'on sides, evenly spread'
    if index in (1,2,10,11):
        centre=index<9; forward=index in (1,10); minimum=1 if centre else 2
        if mounts<=minimum:return ('on centreline' if centre else 'on sides')+(' forward' if forward else ' aft')
        base='on centreline ends' if centre else 'on side ends'
        return base+(', evenly spread' if mounts%(2 if centre else 4)==0 else ', majority '+('forward' if forward else 'aft'))
    position=int(index%9)
    side='on centreline' if index<9 else 'on sides'
    deck='forward' if position<6 else 'aft'
    part=('forward','centre','aft')[(position-3)%3]
    if part=='centre' and mounts>(1 if index<9 else 2):return side+', '+deck+' evenly spread'
    return side+', '+deck+' deck '+part


def gun_description(group,freeboard):
    n=group.get('barrels');c=group.get('calibre')
    if n is None or c is None:return 'Armament inputs undetermined'
    if n<=0 or c<=0:return 'No '+GUN_NAMES[int(group.get('bank',1))-1]
    plural='s' if n>1 else ''
    shell=group.get('shellWeight');calmm=c*25.4
    gt,mt=group.get('gunType'),group.get('mountType')
    gun_type=fields.GUN_TYPES[int(gt)] if gt is not None and 0<=gt<7 else 'Gun type undetermined'
    mount_type=fields.MOUNT_TYPES[int(mt)] if mt is not None and 0<=mt<7 else 'mount type undetermined'
    mounts=(group.get('mountsG1') or 0)+(group.get('mountsG2') or 0)
    lines=['      '+fmt(n)+' - '+fmt(c,2)+'" / '+fmt(calmm,1 if calmm<100 else 0)+' mm '+fmt(group.get('calLength'),1)+' cal gun'+plural+
           ' - '+fmt(shell,2)+'lbs / '+fmt(scaled(shell,.45359236),2)+'kg shells, '+fmt(group.get('magazine'))+' per gun',
           '\t  '+gun_type+plural+' '+mount_type+('s' if mounts>1 else '')+', '+str(group.get('dateGun') if group.get('dateGun') is not None else '—')+' Model']
    for g in (1,2):
        count=group.get('mountsG%d'%g)
        if count is None or count<=0:continue
        selector=group.get('selectorG%d'%g);index=group.get('layoutG%d'%g)
        label=MOUNT_LABELS[int(selector)] if selector is not None and 0<=selector<15 else 'undetermined mount'
        lines.append('\t  '+fmt(count)+' x '+label+('s' if count>1 else '')+' '+layout_text(index,count,freeboard))
        raised=group.get('mountSuperG%d'%g) or 0;lower=group.get('mountSubG%d'%g) or 0
        aft=index in (2,6,7,8,11,15,16,17) and group.get('bank')==1
        if raised>0:
            line='\t\t'+fmt(raised)+(' double' if g==2 and group.get('superSuper') else '')+' raised mount'+('s' if raised>1 else ' aft' if aft else '')
            rhs=mounts-(group.get('mountSuperG2') or 0) if g==1 else 2*count-raised
            if mt is not None and 2<mt<6 and raised<rhs and index not in (0,4,7,9,13,16,18):line+=' - superfiring'
            lines.append(line)
        if lower>0:
            double=g==2 and group.get('subSub')
            line='\t\t'+fmt(lower)+' hull mount'+('s' if lower>1 else '')
            if mt==0:line+=' on gun deck' if double else ' on upper deck'
            else:line+=' in '+('lower ' if double else '')+('casemates' if lower>1 else 'casemate')
            free=group.get('freeGun')
            if free is not None:
                line+='- Limited use in '+('any sea' if free<12 or double and free<19 else 'all but light seas' if free<16 or double and free<23 else 'heavy seas')
            lines.append(line)
    return '\n'.join(lines)


def auxiliary_description(group,index):
    names=('Main Torpedoes','2nd Torpedoes','Mines','Main DC/AS Mortars','2nd DC/AS Mortars')
    n,s,l,w,r,loc=[group.get(key) for key in ('number','size','length','weaponWeight','loads','location')]
    if n is None or s is None:return names[index]+': inputs undetermined'
    lines=['      '+names[index]]
    if group.get('kind')=='torpedo':
        line='      '+fmt(n)+' - '+fmt(s,1)+'" / '+fmt(s*25.4)+' mm, '+fmt(l,2)+' ft / '+fmt(scaled(l,.3048),2)+' m torpedo'+('es' if n>1 else '')
        if n>1:line+=' - '+fmt(None if w is None else w/n,3)+' t each, '
        else:line+=' - '
        lines.append(line+fmt(w,3)+' t total')
        if loc is not None and 0<=loc<9:
            label=catalog.TORPEDO_LOCATION_CHOICES[int(loc)]
            if loc>3:
                if n==1 and loc==6:label='submerged bow OR stern tube'
                lines.append('\t'+label+('s' if n>1 else ''))
            else:lines.append('\tIn '+(fmt(r)+' sets of ' if n>1 else 'a ')+label+('s' if n>1 else ''))
    else:
        kind='mine' if group.get('kind')=='mine' else 'Depth Charge' if loc is None or loc<2 else 'ahead throwing AS Mortar' if loc==2 else 'trainable AS Mortar'
        lines.append('      '+fmt(n)+' - '+fmt(s,2)+' lbs / '+fmt(s*.45359236,2)+' kg '+kind+('s' if n>1 else '')+
                     (' + '+fmt(r)+' reloads' if r is not None and r>0 else '')+' - '+fmt(w,3)+' t total')
        if loc is not None and 0<=loc<2:
            labels=catalog.MINE_LOCATION_CHOICES if group.get('kind')=='mine' else catalog.DC_LOCATION_CHOICES
            lines.append('\tin '+labels[int(loc)])
    return '\n'.join(lines)


def ship_classification(guns,armour,hull,freeboard):
    groups=guns.get('groups',[])
    if not groups:return []
    result=[]
    if any(g.get('mountType')==2 for g in groups[:2]):result.append('Barbette ship')
    main=groups[0]
    if main.get('layoutG1') in (4,10) and (main.get('mountAdj') or 0)>.6 and (hull.get('dateHull') or 1950)<1895:result.append('Central citadel ship')
    if any(g.get('mountType')==0 for g in groups[:3]):
        low=any(g.get('mountType')==0 and (g.get('gunSubG1') or 0)+(g.get('gunSubG2') or 0)>0 for g in groups[:3])
        if (armour.get('weightBelts') or 0)>0:
            if any(g.get('mountType')==0 and (g.get('armBack') or 0)>0 for g in groups[:3]):result.append('Armoured Casemate Ship')
            else:result.append('Armoured '+('Frigate' if low else 'Corvette')+' ('+('Broadside' if (freeboard.get('fcLength') or 0)+(freeboard.get('qdLength') or 0)<.5 else 'Central battery')+' ironclad)')
        else:result.append(('Frigate' if low else 'Corvette')+' (Unarmoured)')
    return result


def design_rules(parameters,hull,freeboard,armour):
    """Source page warnings, with explicit unknown conditions."""
    definitions = [
        ('block', [('hull','block')], lambda: not (.3 < hull['block'] <= 1), 'Block Coefficient must be 0.3 to 1.00'),
        ('bow_angle', [('free','lengthBow')], lambda: abs(freeboard['lengthBow']) >= 90, 'Bow angle cannot be 90 degrees or more'),
        ('forecastle_length', [('free','fcLength')], lambda: freeboard['fcLength'] > 1.00001, 'Forecastle too long'),
        ('forward_length', [('free','fdLength')], lambda: freeboard['fdLength'] > 1.00001, 'Forward deck too long'),
        ('quarter_length', [('free','qdLength')], lambda: freeboard['qdLength'] > 1.00001, 'Quarter deck too long'),
        ('deck_length_total', [('free','adLength')], lambda: freeboard['adLength'] < 0, 'Forecastle + forward deck + Quarter deck too long'),
        ('belt_length', [('armour','beltMainLength'),('armour','beltEndsLength'),('hull','length')],
         lambda: armour['beltMainLength'] + armour['beltEndsLength'] > hull['length'], 'Warning: Armour belts longer than ship'),
        ('belt_height', [('armour',key) for key in ('beltMain','beltEnds','beltUpper','beltMainHeight','beltEndsHeight','beltUpperHeight','maxBeltHeight')] + [('free','freeDistributed')],
         lambda: (armour['beltMain'] > 0 and armour['beltMainHeight'] > armour['maxBeltHeight']) or
                 (armour['beltEnds'] > 0 and armour['beltEndsHeight'] > armour['maxBeltHeight']) or
                 (armour['beltUpper'] > 0 and armour['beltUpperHeight'] > freeboard['freeDistributed'] + .01), 'Warning: Armour belts too tall for hull'),
        ('bulkhead_height', [('armour','bulkheadHeight'),('hull','draught'),('free','freeDistributed')],
         lambda: armour['bulkheadHeight'] > hull['draught'] + freeboard['freeDistributed'], 'Warning: Torpedo Bulkhead too tall for hull'),
        ('bulge_height', [('armour','bulgeHeight'),('hull','draught'),('free','freeDistributed')],
         lambda: armour['bulgeHeight'] > hull['draught'] + freeboard['freeDistributed'], 'Warning: Bulge too tall for hull'),
        ('bulkhead_beam', [('armour','bulkheadType'),('armour','bulkheadBeam'),('hull','beam')],
         lambda: (armour['bulkheadType']==0 and armour['bulkheadBeam']>=hull['beam']-6) or
                 (armour['bulkheadType']==1 and armour['bulkheadBeam']>hull['beam']), 'Warning: Beam between bulkheads too wide'),
    ]
    sections={'hull':hull,'free':freeboard,'armour':armour}
    return [_item('design.'+key,message,'$',bool(test()) if all(sections[section].get(name) is not None for section,name in deps) else None,
                  'HullControl / FreeboardControl / ArmourControl source warning')
            for key,deps,test,message in definitions]


def evaluate(parameters,hull,guns,auxiliary,armour,engine,performance,*,freeboard=None):
    hull,guns,auxiliary,armour,engine,performance=[value if isinstance(value,dict) else {} for value in (hull,guns,auxiliary,armour,engine,performance)]
    # This report helper also receives the freeboard profile through source
    # percentages; armament layout descriptions need only these fractions.
    fractions={key:None if parameters.get(name) is None else parameters[name]/100 for key,name in
               [('fcLength','freeboard_forecastle_length'),('fdLength','freeboard_flat_deck_length'),('qdLength','freeboard_quarterdeck_length')]}
    freeboard = dict(freeboard or {}, **fractions)
    groups=guns.get('groups',[])
    checks=[rule for group in groups for rule in gun_rules(group)]
    page_checks=design_rules(parameters,hull,freeboard,armour)
    warnings=[rule for rule in checks+page_checks if rule['condition'] is True]
    warnings.extend(_item('engine.'+d.get('code','warning'),d.get('message',''),d.get('field','$'),True,'EngineControl')
                    for d in engine.get('warnings',[]) if isinstance(d,dict))
    failures=[]
    predicates=[('dimensions',None if hull.get('block') is None else hull['block']<=0 or hull['block']>1,'Displacement impossible with given dimensions'),
                ('guns',guns.get('gunWarn'),'Gun weight too much for hull'),('armour',armour.get('armourWarn'),'Armour weight too much for hull'),
                ('load',None if performance.get('strengthComp') is None else performance['strengthComp']<.5,'Overall load weight too much for hull'),
                ('capsize',performance.get('capsizeWarn'),'Ship will capsize')]
    for key,condition,message in predicates:
        if condition:failures.append(_item('design_failure.'+key,'DESIGN FAILURE: '+message,'$',True,'ReportControl.reportMaker'))
    ratings={}
    room=performance.get('roomHull');deck=performance.get('roomDeck')
    if room is not None:ratings['roomHull']=('Excellent' if room<5/6 else 'Adequate' if room<1.1111112 else 'Cramped' if room<=2 else 'Extremely poor')+' machinery, storage, compartmentation space'
    if deck is not None:ratings['roomDeck']=('Excellent' if deck>1.2 else 'Adequate' if deck>.9 else 'Cramped' if deck>=.5 else 'Extremely poor')+' accommodation and workspace room'
    flags=[('steady','Ship has slow, easy roll, a good, steady gun platform'),('unsteady','Ship has quick, lively roll, not a steady gun platform'),
           ('badSea','Caution: Lacks seaworthiness - very limited seakeeping ability'),('poorSea','Poor seaboat, wet and uncomfortable, reduced performance in heavy weather'),
           ('goodSea','Good seaboat, rides out heavy weather easily'),('fineSea','Excellent seaboat, comfortable'+(', can fire her guns in the heaviest weather' if (guns.get('gunsWeight') or 0)>0 else ', rides out heavy weather easily'))]
    ratings['comments']=[message for key,message in flags if performance.get(key)]
    if performance.get('tenderWarn') and not performance.get('capsizeWarn'):ratings['comments'].insert(0,'Caution: Poor stability - excessive risk of capsizing')
    if performance.get('strengthComp') is not None and .5<=performance['strengthComp']<.995 and ((engine.get('speedMax') or 0)<24 or (hull.get('displacement') or 0)>4000):ratings['comments'].insert(0,'Caution: Hull subject to strain in open-sea')
    return dict(method_version=METHOD_VERSION,warnings=warnings,design_failures=failures,gun_rules=checks,design_rules=page_checks,
                undetermined_rules=[rule for rule in checks+page_checks if rule['condition'] is None],
                gun_descriptions=[gun_description(group,freeboard) for group in groups],
                auxiliary_descriptions=[auxiliary_description(group,index) for index,group in enumerate(auxiliary.get('groups',[]))],
                ship_type=ship_classification(guns,armour,hull,freeboard),ratings=ratings)

