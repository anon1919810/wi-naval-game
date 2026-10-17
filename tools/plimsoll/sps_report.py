"""One immutable 3b3 report model for the screen, text, RTF and .ssr files."""
from __future__ import annotations
import math
if __package__:
    from . import sps_gun_review as review_api, sps_field_catalog as catalog
else:
    import sps_gun_review as review_api, sps_field_catalog as catalog
METHOD_VERSION='sps-3b3-report-v1'
SCHEMA='plimsoll-sps3b3-report-1'
fmt=review_api.fmt
scaled=review_api.scaled


def _section(identity,title,lines):
    return dict(id=identity,title=title,lines=lines)


def _both(value,places=2,*,thickness=False):
    return fmt(value,places)+('" / '+fmt(scaled(value,25.4))+' mm' if thickness else ' ft / '+fmt(scaled(value,.3048),places)+' m')


def _hull_description(free):
    pairs=[('freeFCAft','freeFDFor','raised forecastle','low forecastle'),
           ('freeFDAft','freeADFor','rise forward of midbreak','rise aft of midbreak'),
           ('freeQDFor','freeADAft','raised quarterdeck','low quarterdeck')]
    parts=[]
    for first,second,high,low in pairs:
        a,b=free.get(first),free.get(second)
        if a is None or b is None:return 'Hull form undetermined'
        if a!=b:parts.append(high if a>b else low)
    return 'Hull has '+(', '.join(parts) if parts else 'a flush deck')


def build(result):
    """Read the supplied result only. Never looks up or recomputes a project."""
    if not isinstance(result,dict):raise ValueError('a compatibility result is required')
    if result.get('schema')==SCHEMA:return result
    design=result.get('design') or {};parameters=design.get('parameters') or {}
    h,f,g,w,a,e,p=[result.get(key) or {} for key in ('hull','freeboard','guns','auxiliary','armour','engine','performance')]
    review=result.get('review') or review_api.evaluate(parameters,h,g,w,a,e,p,freeboard=f)
    sections=[]
    year=lambda value: '—' if value is None else str(int(value))
    identity=str(parameters.get('ship_name') or 'Unnamed ship')+', '+str(parameters.get('country') or '')+' '+str(parameters.get('ship_type') or '')+' laid down '+year(h.get('dateHull'))
    if h.get('dateHull')!=h.get('dateEngine'):identity+=' (Engine '+year(h.get('dateEngine'))+')'
    sections.append(_section('header','',[identity]+list(review.get('ship_type',[]))+[item['message'] for item in review.get('design_failures',[])]))
    sections.append(_section('displacements','Displacement:',[
        '\t'+fmt(p.get('dispLight'))+' t light; '+fmt(p.get('dispStandard'))+' t standard; '+fmt(h.get('displacement'))+' t normal; '+fmt(p.get('dispMaxLoad'))+' t full load']))
    deep=p.get('draughtDeep')
    def dims(factor,unit):
        text='\t('+fmt(scaled(h.get('lengthOA'),factor),2)+' '+unit+' / '+fmt(scaled(h.get('length'),factor),2)+' '+unit+') x '+fmt(scaled(h.get('beam'),factor),2)+' '+unit
        if h.get('beamBulges')!=h.get('beam'):text+=' (Bulges '+fmt(scaled(h.get('beamBulges'),factor),2)+' '+unit+')'
        return text+' x ('+fmt(scaled(h.get('draught'),factor),2)+' / '+fmt(scaled(deep,factor),2)+' '+unit+')'
    sections.append(_section('dimensions','Dimensions: Length (overall / waterline) x beam x draught (normal/deep)',[dims(1,'ft'),dims(.3048,'m')]))
    armament=[]
    for index,group in enumerate(g.get('groups',[])):
        if (group.get('barrels') or 0)>0 and (group.get('calibre') or 0)>0:
            armament.append(review['gun_descriptions'][index])
    if (g.get('broadside') or 0)>0:armament.append('      Weight of broadside '+fmt(g.get('broadside'))+' lbs / '+fmt(scaled(g.get('broadside'),.45359236))+' kg')
    for index,group in enumerate(w.get('groups',[])):
        if (group.get('number') or 0)>0:armament.append(review['auxiliary_descriptions'][index])
    if not armament:
        known_empty=all(group.get('barrels')==0 for group in g.get('groups',[])) and bool(g.get('groups')) and all(group.get('number')==0 for group in w.get('groups',[])) and bool(w.get('groups'))
        armament=['      No armament' if known_empty else '      Armament inputs undetermined']
    sections.append(_section('armament','Armament:',armament))
    armour=[]
    if any((a.get(key) or 0)>0 for key in ('beltMain','beltEnds','beltUpper')):
        armour.append('   - Belts:\t\tWidth (max)\tLength (avg)\tHeight (avg)')
        for name,label in [('beltMain','Main'),('beltEnds','Ends'),('beltUpper','Upper')]:
            if (a.get(name) or 0)>0:
                armour.append('\t'+label+':\t'+_both(a.get(name),2,thickness=True)+'\t'+_both(a.get(name+'Length'))+'\t'+_both(a.get(name+'Height')))
            if name=='beltEnds' and None not in (h.get('length'),a.get('beltMainLength'),a.get('beltEndsLength')):
                unarmoured=h['length']-a['beltMainLength']-a['beltEndsLength']
                if unarmoured>0:armour.append('\t  '+_both(unarmoured)+' Unarmoured ends')
        armour.append('\t  Main Belt covers '+fmt(scaled(a.get('beltCover'),100))+'% of normal length')
        if a.get('beltCover') is not None and p.get('roomHull') is not None and a['beltCover']<p['roomHull']:
            armour.append('\t  Main belt does not fully cover magazines and engineering spaces')
        if (a.get('beltsIncline') or 0)!=0:armour.append('\t  Main Belt inclined '+fmt(a['beltsIncline'],2)+' degrees (positive = in)')
    if (a.get('bulkhead') or 0)>0:
        armour += ['   - Torpedo Bulkhead - '+('Strengthened structural bulkheads:' if a.get('bulkheadType')==1 else 'Additional damage containing bulkheads:'),
                   '\t\t'+_both(a.get('bulkhead'),2,thickness=True)+'\t'+_both(a.get('bulkheadLength'))+'\t'+_both(a.get('bulkheadHeight')),
                   '\tBeam between torpedo bulkheads '+_both(a.get('bulkheadBeam'))]
    if (a.get('weightBulge') or 0)>.01 or (w.get('voidWeight') or 0)>0:
        armour += ['   - '+('Hull void:' if h.get('beam')==h.get('beamBulges') else 'Hull Bulges:'),
                   '\t\t'+_both(a.get('bulge'),2,thickness=True)+'\t'+_both(a.get('bulgeLength'))+'\t'+_both(a.get('bulgeHeight'))]
    for index,group in enumerate(g.get('groups',[])):
        if (group.get('armWeight') or 0)>.01:
            armour += ['   - '+review_api.GUN_NAMES[index]+': face / other gunhouse / below deck',
                       '\t'+'\t'.join('—' if group.get(key)==0 else _both(group.get(key),1 if (group.get(key) or 0)>=10 else 2,thickness=True) for key in ('armFace','armBack','armBottom'))]
    if any((a.get(key) or 0)>0 for key in ('deck','deckFC','deckQD')):
        coverage=a.get('deckCoverage')
        label=catalog.DECK_COVERAGE_CHOICES[int(coverage)] if coverage is not None and 0<=coverage<7 else 'Deck coverage undetermined'
        armour += ['   - '+label+':','\tFor and Aft decks: '+_both(a.get('deck'),2,thickness=True),
                   '\tForecastle: '+_both(a.get('deckFC'),2,thickness=True)+'  Quarter deck: '+_both(a.get('deckQD'),2,thickness=True)]
    if (a.get('conningFor') or 0)>0 or (a.get('conningAft') or 0)>0:
        armour.append('   - Conning towers: Forward '+_both(a.get('conningFor'),2,thickness=True)+', Aft '+_both(a.get('conningAft'),2,thickness=True))
    known_unarmoured=all(a.get(key)==0 for key in ('beltMain','beltEnds','beltUpper','bulkhead','bulge','deck','deckFC','deckQD','conningFor','conningAft')) and g.get('armWeight')==0
    sections.append(_section('armour','Armour:',armour or ['      No armour' if known_unarmoured else '      Armour inputs undetermined']))
    machinery=[]
    if e.get('speedMax')==0:machinery=['\tImmobile floating battery']
    else:
        machinery += ['\t'+str(e.get('fuelString') or '')+str(e.get('engineString1') or '')+str(e.get('engineString2') or ''),
            '\t'+str(e.get('driveString') or 'Drive undetermined')+', '+fmt(parameters.get('shafts'))+(' shaft, ' if parameters.get('shafts')==1 else ' shafts, ')+
            fmt(e.get('hpMax'))+(' ihp / ' if parameters.get('engine_simple') or parameters.get('engine_compound') else ' shp / ')+fmt(scaled(e.get('hpMax'),.746))+' Kw = '+fmt(e.get('speedMax'),2)+' kts']
        speeds=[value for value in (e.get('speedCruise'),e.get('speedMax')) if value is not None]
        machinery += ['\tRange '+fmt(e.get('range'))+'nm at '+fmt(min(speeds) if speeds else None,2)+' kts',
                     '\tBunker at max displacement = '+fmt(e.get('bunkerMax'))+' tons'+(' ('+fmt(e.get('pctCoal'))+'% coal)' if (e.get('pctCoal') or 0)>0 else '')]
        shafts=parameters.get('shafts')
        if shafts and e.get('hpMax') is not None:
            per_shaft=e['hpMax']/shafts
            if per_shaft>20000 and not parameters.get('engine_turbine') and (parameters.get('engine_simple') or parameters.get('engine_compound')):
                machinery.append('\t  Caution: Too much power for reciprocating engines')
            elif per_shaft>75000:machinery.append('\t  Caution: Too much power for number of propellor shafts')
        if e.get('engineWeight') is not None and e.get('engine') is not None and e['engineWeight']<e['engine']/5:
            machinery.append('\t  Caution: Delicate, lightweight machinery')
    sections.append(_section('machinery','Machinery:',machinery))
    sections.append(_section('complement','Complement:',['\t'+fmt(h.get('crewMin'))+' - '+fmt(h.get('crewMax'))]))
    sections.append(_section('cost','Cost:',['\t£'+fmt(p.get('costPounds'),3)+' million / $'+fmt(p.get('costDollars'),3)+' million']))
    distribution=[]
    def weight(label,mass):
        percentage=None if mass is None or not h.get('displacement') else mass/h['displacement']*100
        return '\t'+label+': '+fmt(mass)+' tons, '+fmt(percentage,1)+'%'
    armament_weight=None if g.get('gunsWeight') is None or w.get('weight') is None else g['gunsWeight']+w['weight']
    distribution.append(weight('Armament',armament_weight))
    if (g.get('gunsWeight') or 0)>0:distribution.append(weight('   - Guns',g['gunsWeight']))
    if (w.get('weight') or 0)>0:distribution.append(weight('   - Weapons',w['weight']))
    if a.get('weight') is None or a['weight']>.01:distribution.append(weight('Armour',a.get('weight')))
    for label,mass in [('Belts',a.get('weightBelts')),('Torpedo bulkhead',a.get('weightBulkhead')),
                       ('Void' if h.get('beam')==h.get('beamBulges') else 'Bulges',a.get('weightBulge')),
                       ('Armament',g.get('armWeight')),('Armour Deck',a.get('weightDeck')),('Conning Towers',a.get('weightConning'))]:
        if mass is not None and mass>.01:distribution.append(weight('   - '+label,mass))
    distribution += [weight('Machinery',e.get('engineWeight')),weight('Hull, fittings & equipment',e.get('hullWeightDisplayed')),
                     weight('Fuel, ammunition & stores',e.get('loadWeight')),weight('Miscellaneous weights',w.get('miscWeight'))]
    for label,key in [('Hull below water','miscWeightVital'),('Bulge void weights' if (h.get('beamBulges') or 0)>(h.get('beam') or 0) else 'Hull void weights','voidWeight'),
                      ('Hull above water','miscWeightHull'),('On freeboard deck','miscWeightDeck'),('Above deck','miscWeightAbove')]:
        if (w.get(key) or 0)>.01:distribution.append('\t   - '+label+': '+fmt(w[key])+' tons')
    sections.append(_section('distribution','Distribution of weights at normal displacement:',distribution))
    survivability=['\tSurvivability (Non-critical penetrating hits needed to sink ship):',
        '\t  '+fmt(p.get('flotation'))+' lbs / '+fmt(scaled(p.get('flotation'),.45359236))+' Kg = '+fmt(p.get('damageShell'),1)+' x '+fmt(p.get('damageShellCalibreIn'),1 if ((g.get('groups') or [{}])[0].get('calibre') or 0)>0 else 0)+' " / '+fmt(scaled(p.get('damageShellCalibreIn'),25.4))+' mm shells or '+fmt(p.get('damageTorp'),1)+' torpedoes',
        '\tStability (Unstable if below 1.00): '+fmt(p.get('stabilityAdj'),2),'\tMetacentric height '+_both(p.get('metacentre'),1),
        '\tRoll period: '+fmt(p.get('rollPeriod'),1)+' seconds','\tSteadiness - As gun platform (Average = 50 %): '+fmt(p.get('steadinessAdj'))+' %',
        '\tRecoil effect (Restricted arc if above 1.00): '+fmt(p.get('recoil'),2),'\tSeaboat quality (Average = 1.00): '+fmt(p.get('seakeeping'),2)]
    sections.append(_section('survivability','Overall survivability and seakeeping ability:',survivability))
    bows=('a normal bow','a straight bulbous bow','an extended bulbous bow','a ram bow')
    sterns=('a cruiser stern','small transom stern','large transom stern','a round stern')
    bow=parameters.get('bow');stern=parameters.get('stern')
    form=['\t'+_hull_description(f)+',','\t  '+(bows[int(bow)] if bow is not None and 0<=bow<4 else 'bow undetermined')+' and '+(sterns[int(stern)] if stern is not None and 0<=stern<4 else 'stern undetermined'),
        '\tBlock coefficient (normal/deep): '+fmt(h.get('block'),3)+' / '+fmt(p.get('blockDeep'),3),
        '\tLength to Beam Ratio: '+fmt(h.get('lengthBeam'),2)+' : 1', "\t'Natural speed' for length: "+fmt(h.get('speedNatural'),2)+' kts',
        '\tPower going to wave formation at top speed: '+fmt(e.get('powerWaveMax'))+' %',
        '\tTrim (Max stability = 0, Max steadiness = 100): '+str(parameters.get('trim') if parameters.get('trim') is not None else '—'),
        '\tBow angle (Positive = bow angles forward): '+fmt(f.get('lengthBow'),2)+' degrees',
        '\tStern overhang: '+_both(f.get('lengthStern')),
        '\tFreeboard (% = length of deck as a percentage of waterline length):']
    for label,fraction,first,last in [('Forecastle','fcLength','freeFCFor','freeFCAft'),('Forward deck','fdLength','freeFDFor','freeFDAft'),('Aft deck','adLength','freeADFor','freeADAft'),('Quarter deck','qdLength','freeQDFor','freeQDAft')]:
        form.append('\t   - '+label+': '+fmt(scaled(f.get(fraction),100),2)+'%, '+_both(f.get(first))+', '+_both(f.get(last)))
    form.append('\t   - Average freeboard: '+_both(f.get('freeboard')))
    if f.get('freeFCFor') is not None and h.get('length') is not None and h['length']>=0 and f['freeFCFor']<round(1.1*math.sqrt(h['length']),2):form.append('\tShip tends to be wet forward')
    sections.append(_section('hull-form','Hull form characteristics:',form))
    structure=scaled(p.get('structWeight'),.45359236/.092903)
    comments=['\tSpace - Hull below water (magazines/engines, low = better): '+fmt(scaled(p.get('roomHull'),100),1)+'%',
        '\tAbove water (accommodation/working, high = better): '+fmt(scaled(p.get('roomDeck'),100),1)+'%',
        '\tWaterplane Area: '+fmt(h.get('waterplaneArea'))+' Square feet or '+fmt(scaled(h.get('waterplaneArea'),.092903))+' Square metres',
        '\tDisplacement factor (Displacement / loading): '+fmt(scaled(e.get('dispFactor'),100))+'%',
        '\tStructure weight / hull surface area: '+fmt(p.get('structWeight'))+' lbs/sq ft or '+fmt(structure)+' Kg/sq metre',
        '\tHull strength (Relative):','\t  - Cross-sectional: '+fmt(p.get('strengthCross'),2),
        '\t  - Longitudinal: '+fmt(p.get('strengthLong'),2),'\t  - Overall: '+fmt(p.get('strengthComp'),2)]
    ratings=review.get('ratings',{})
    comments.extend('\t'+str(ratings[key]) for key in ('roomHull','roomDeck') if key in ratings)
    comments.extend('\t'+str(line) for line in ratings.get('comments',[]))
    sections.append(_section('space-strength','Ship space, strength and comments:',comments))
    warnings=[];seen=set()
    for item in list(result.get('diagnostics',[]))+list(review.get('warnings',[])):
        if not isinstance(item,dict):continue
        message=item.get('message')
        if message and message not in seen:
            seen.add(message);warnings.append(str(message))
    if warnings:sections.append(_section('warnings','Warnings and diagnostics:',warnings))
    notes=design.get('notes')
    if notes:sections.append(_section('notes','',[str(notes)]))
    text='\n\n'.join((section['title']+'\n' if section['title'] else '')+'\n'.join(section['lines']) for section in sections)+'\n'
    return dict(schema=SCHEMA,method_version=METHOD_VERSION,sections=sections,text=text,
                diagnostics=result.get('diagnostics',[]),source_method=result.get('method_version'),
                scope='SpringSharp3b3 empirical design report; source units and method, not physical hydrostatics.')


def _rtf(text):
    output=['{\\rtf1\\ansi\\deff0{\\fonttbl{\\f0 Calibri;}}\\uc1\\f0\\fs20 ']
    for char in text.replace('\r\n','\n').replace('\r','\n'):
        if char=='\n':output.append('\\par\n')
        elif char=='\t':output.append('\\tab ')
        elif char in '\\{}':output.append('\\'+char)
        elif 32<=ord(char)<127:output.append(char)
        else:
            encoded=char.encode('utf-16-le')
            for offset in range(0,len(encoded),2):
                unit=int.from_bytes(encoded[offset:offset+2],'little')
                output.append('\\u%d?'%(unit if unit<32768 else unit-65536))
    return ''.join(output)+'}'


def serialize(result,format='txt'):
    if format not in ('txt','rtf','ssr'):raise ValueError('format must be txt, rtf or ssr')
    text=build(result)['text']
    return text if format=='txt' else _rtf(text)

