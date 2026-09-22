"""Loaded equilibrium of a finite polygon-section envelope and moving liquids.

Public angles describe z = d + tan(trim)*x + tan(heel)*y, not Euler rotations.
Numerical convergence does not certify historical geometry or overall safety.
"""
from __future__ import annotations

import copy
import math

try:
    from . import geometry, offsets, tank_geometry
except ImportError:
    import geometry
    import offsets
    import tank_geometry

METHOD_VERSION = 'loaded-projected-equilibrium-1'
RESIDUAL_TOLERANCE = 1e-6


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite real number')
    return float(value)


def _diagnostic(code, message, blocking=False):
    return dict(code=code, message=message, severity='error' if blocking else 'warning',
                path='$.stability', blocking=blocking)


def _axes(p, q):
    s, t = math.sqrt(1+p*p+q*q), math.sqrt(1+q*q)
    return ((1+q*q)/(s*t), -p*q/(s*t), p/(s*t)), (0,1/t,q/t), (-p/s,-q/s,1/s)


def _dot(a,b):
    return math.fsum(x*y for x,y in zip(a,b))


def _simple_polygon(poly, endpoint):
    # Consecutive coincident points and repeated closure are harmless. Pointed
    # ends may collapse to a point/line; interior degenerate sections are rejected.
    points = []
    for point in poly:
        if not points or point != points[-1]:
            points.append(point)
    if len(points)>1 and points[0] == points[-1]:
        points.pop()
    if len(points)<3:
        if endpoint:
            return poly
        raise ValueError('degenerate interior section')
    def orient(a,b,c):
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    if endpoint and all(orient(points[0],points[1],p)==0 for p in points[2:]):
        return points
    for i,a in enumerate(points):
        b = points[(i+1)%len(points)]
        for j in range(i+2,len(points)):
            if i == 0 and j == len(points)-1:
                continue
            c,e = points[j],points[(j+1)%len(points)]
            if max(a[0],b[0])<min(c[0],e[0]) or max(c[0],e[0])<min(a[0],b[0]):
                continue
            if max(a[1],b[1])<min(c[1],e[1]) or max(c[1],e[1])<min(a[1],b[1]):
                continue
            if orient(a,b,c)*orient(a,b,e)<=0 and orient(c,e,a)*orient(c,e,b)<=0:
                raise ValueError('self-intersecting or touching section boundary')
    area = abs(geometry.polygon_area_moments(points)[0])
    if not math.isfinite(area) or area == 0:
        raise ValueError('section area must be finite and positive')
    return points


def _prepare(hull, options):
    source, estimate, schema = None, None, 'legacy_stationed_hull'
    if isinstance(hull,dict):
        if hull.get('kind') != 'offsets':
            raise ValueError('materialized offsets geometry is required')
        keel = _number(hull.get('keel_offset_m'),'keel_offset_m')
        payload = hull.get('offsets')
        if not isinstance(payload,dict):
            raise ValueError('offsets payload is required')
        schema = payload.get('schema')
        source, estimate = copy.deepcopy(hull.get('source')), hull.get('estimate')
        stations = payload.get('stations')
        if schema == 'plimsoll-offsets-1':
            deck = _number(payload.get('deck_z_m'),'deck_z_m')
            if deck <= 0 or not isinstance(stations,(list,tuple)) or len(stations)<5:
                raise ValueError('legacy offsets require positive deck and five stations')
            table = []
            for row in stations:
                if not isinstance(row,(list,tuple)) or len(row)!=5:
                    raise ValueError('legacy offsets rows need five numbers')
                row = [_number(v,'offset') for v in row]
                if min(row[1],row[2],row[4])<0 or row[3]>=0:
                    raise ValueError('legacy offsets need nonnegative widths and keel below z=0')
                if table and row[0]<=table[-1][0]:
                    raise ValueError('station x positions must be strictly increasing')
                table.append(row)
            stations = offsets.build_hull(table,deck_z=deck).stations
        elif schema != 'plimsoll-section-polygons-1':
            raise ValueError('unrecognized materialized geometry schema')
    else:
        keel = _number(options.get('keel_offset_m'),'explicit keel_offset_m')
        stations = getattr(hull,'stations',None)
    if not isinstance(stations,(list,tuple)) or len(stations)<3:
        raise ValueError('at least three stations are required')
    copied = []
    for i,row in enumerate(stations):
        if not isinstance(row,(list,tuple)) or len(row)!=2:
            raise ValueError('station must be [x, polygon]')
        x = _number(row[0],'station x')
        if copied and x<=copied[-1][0]:
            raise ValueError('station x positions must be strictly increasing')
        if not isinstance(row[1],(list,tuple)) or len(row[1])<3:
            raise ValueError('section requires at least three points')
        poly = []
        for point in row[1]:
            if not isinstance(point,(list,tuple)) or len(point)!=2:
                raise ValueError('section point must be [y,z]')
            poly.append(tuple(_number(v,'section coordinate') for v in point))
        copied.append((x,_simple_polygon(poly,i in (0,len(stations)-1))))
    obj = geometry.StationedHull(copied)
    vertices = [(x,y,z) for x,poly in copied for y,z in poly]
    bounds = [[min(v[i] for v in vertices),max(v[i] for v in vertices)] for i in range(3)]
    scales = [b-a for a,b in bounds]
    if any(not math.isfinite(v) or v<=0 for v in scales):
        raise ValueError('geometry must have finite positive extent on every axis')
    capacity = obj.integrate(0,bounds[2][1])['volume']
    if not math.isfinite(capacity) or capacity<=0:
        raise ValueError('sealed-envelope capacity must be positive and finite')
    metadata = dict(schema=schema,keel_offset_m=keel,source=source,estimate=estimate,
                    bounds_m=bounds,station_count=len(copied),
                    section_vertex_counts=[len(p) for _,p in copied],
                    quadrature='trapezoidal_station_areas_and_first_moments',
                    sealed_envelope_capacity_m3=capacity)
    return obj,vertices,scales,metadata


def _linear_solve(matrix, rhs):
    a = [list(row)+[value] for row,value in zip(matrix,rhs)]
    size = len(rhs)
    norm = max(abs(v) for row in matrix for v in row)
    for i in range(size):
        pivot = max(range(i,size),key=lambda j:abs(a[j][i]))
        if abs(a[pivot][i])<=max(1e-13,norm*1e-10):
            raise ValueError('singular equilibrium Jacobian; no unique resolved state')
        a[i],a[pivot] = a[pivot],a[i]
        divisor = a[i][i]
        a[i] = [v/divisor for v in a[i]]
        for j in range(size):
            if j != i:
                factor = a[j][i]
                a[j] = [x-factor*y for x,y in zip(a[j],a[i])]
    return [row[-1] for row in a]


def _bounds(options, name, default):
    bounds = options.get(name,default)
    if not isinstance(bounds,(list,tuple)) or len(bounds)!=2:
        raise ValueError(f'{name} requires [lower, upper]')
    a,b = (_number(v,name) for v in bounds)
    if not -89<a<b<89:
        raise ValueError(f'{name} must be ordered strictly inside (-89,89) degrees')
    return [a,b]


def _solve(prepared, state, options):
    hull, vertices, scales, metadata = prepared
    keel = metadata['keel_offset_m']
    if not isinstance(state,dict):
        raise ValueError('loading state must be an object')
    if state.get('complete_mass') is not True or state.get('complete_cg') is not True:
        raise ValueError('complete mass and three-axis CG are required')
    if any(d.get('blocking') for d in state.get('diagnostics',[])):
        raise ValueError('loading has blocking diagnostics')
    values = state['values']
    base_mass = _number(values.get('total_mass_t'),'total_mass_t')
    base_cg = [_number(values.get(k),k) for k in ('lcg_m','tcg_m','kg_m')]
    base_cg[2] += keel
    rho = _number(options.get('rho_t_m3',1.025),'rho_t_m3')
    if base_mass<=0 or rho<=0:
        raise ValueError('mass and water density must be positive')
    liquids = copy.deepcopy(options.get('liquid_loads',[]))
    if not isinstance(liquids,list):
        raise ValueError('liquid_loads must be a list')
    ids, added = set(), 0.0
    ledger_ids = {v.get('id') for v in state.get('effective_items',[])}
    for liquid in liquids:
        tank = liquid['tank']
        identity = tank.get('id')
        if not isinstance(identity,str) or not identity or identity in ids or identity in ledger_ids:
            raise ValueError('liquids need unique IDs absent from base weight ledger')
        ids.add(identity)
        volume = _number(liquid.get('volume_m3'),'liquid volume')
        density = _number(liquid.get('fluid_density_t_m3'),'liquid density')
        if volume<0 or density<=0:
            raise ValueError('liquid volume must be nonnegative and density positive')
        liquid['mass_t'] = volume*density
        if volume>0 and (liquid['mass_t']==0 or not math.isfinite(liquid['mass_t'])):
            raise ValueError('liquid mass is outside the representable positive range')
        added += liquid['mass_t']
    mass = base_mass+added
    target = mass/rho
    if not math.isfinite(target) or not 0<target<metadata['sealed_envelope_capacity_m3']*(1-1e-12):
        raise ValueError('displacement exceeds capacity or is saturated/non-unique')
    hb = _bounds(options,'heel_bounds_deg',[-85,85])
    tb = _bounds(options,'trim_bounds_deg',[-45,45])
    fixed = options.get('heel_deg')
    if fixed is not None:
        fixed = _number(fixed,'heel_deg')
        if not hb[0]<=fixed<=hb[1]:
            raise ValueError('prescribed heel outside model angle bounds')
    count = options.get('max_iterations',50)
    if isinstance(count,bool) or not isinstance(count,int) or count<1 or count>1000:
        raise ValueError('max_iterations must be an integer in [1,1000]')
    length,beam,height = scales
    factor = [height,height/length,height/beam]
    p_bounds = [math.tan(math.radians(v)) for v in tb]
    q_bounds = [math.tan(math.radians(v)) for v in hb]
    initial = options.get('initial',{})
    initial_trim = _number(initial.get('trim_deg',0),'initial trim')
    initial_heel = fixed if fixed is not None else _number(initial.get('heel_deg',0),'initial heel')
    if not tb[0]<=initial_trim<=tb[1] or not hb[0]<=initial_heel<=hb[1]:
        raise ValueError('initial angles outside model bounds')
    p = math.tan(math.radians(initial_trim))
    q = math.tan(math.radians(initial_heel))

    def support(p,q):
        supports = [z-p*x-q*y for x,y,z in vertices]
        margin = max(height,abs(min(supports)),abs(max(supports)))*1e-12+1e-11
        return min(supports)-margin,max(supports)+margin

    def evaluate(x):
        d,p = x[0]*factor[0], x[1]*factor[1]
        q = x[2]*factor[2] if fixed is None else math.tan(math.radians(fixed))
        hydro = hull.integrate(math.atan(q),d,math.atan(p))
        moments = [base_mass*v for v in base_cg]
        snapshots = []
        for liquid in liquids:
            snapshot = tank_geometry.liquid_state(liquid['tank'],liquid['volume_m3'],
                heel_deg=math.degrees(math.atan(q)),trim_deg=math.degrees(math.atan(p)))
            snapshot['tank_id'] = liquid['tank']['id']
            snapshot['mass_t'] = liquid['mass_t']
            snapshots.append(snapshot)
            if liquid['mass_t']:
                cg = snapshot['centroid_m'][:]
                cg[2] += keel
                for i in range(3):
                    moments[i] += liquid['mass_t']*cg[i]
        cg = [v/mass for v in moments]
        b = [hydro['xlcb'],hydro['yb'],hydro['zb']]
        u,v,n = _axes(p,q)
        delta = [a-g for a,g in zip(b,cg)]
        raw = [(hydro['volume']-target),_dot(delta,u),_dot(delta,v)]
        scaled = [raw[0]/target,raw[1]/length,raw[2]/beam]
        if not all(math.isfinite(v) for v in [*cg,*b,*scaled,*moments,hydro['awp']]):
            raise ValueError('derived geometry/loading exceeds numerical range')
        residual = scaled if fixed is None else scaled[:2]
        return residual,dict(hydro=hydro,cg=cg,b=b,raw=raw,scaled=scaled,liquids=snapshots,
                            p=p,q=q,d=d,axes=dict(u=list(u),v=list(v),n=list(n)),moments=moments)

    # One initial slope-aware displacement bracket. Subsequent Newton/Jacobian
    # evaluations vary d,p,q together, avoiding nested scalar root solves.
    lo,hi = support(p,q)
    for _ in range(48):
        d = (lo+hi)/2
        volume = hull.integrate(math.atan(q),d,math.atan(p))['volume']
        if volume<target:
            lo=d
        else:
            hi=d
    x = [d/factor[0],p/factor[1]] + ([q/factor[2]] if fixed is None else [])
    evaluations = 0
    difference_step = 1e-5
    for iteration in range(count):
        residual,detail = evaluate(x); evaluations+=1
        jacobian = [[] for _ in x]
        for j in range(len(x)):
            step = difference_step*max(1,abs(x[j]))
            xp,xm = x[:],x[:]
            xp[j]+=step; xm[j]-=step
            rp,_ = evaluate(xp); rm,_ = evaluate(xm); evaluations+=2
            for i in range(len(x)):
                jacobian[i].append((rp[i]-rm[i])/(2*step))
        correction = _linear_solve(jacobian,[-v for v in residual])
        norm = max(abs(v) for v in residual)
        if norm<=1e-10:
            break
        accepted = False
        for backtrack in range(25):
            damping = .5**backtrack
            candidate = [v+damping*dx for v,dx in zip(x,correction)]
            cp = candidate[1]*factor[1]
            cq = candidate[2]*factor[2] if fixed is None else q
            if not p_bounds[0]<=cp<=p_bounds[1] or not q_bounds[0]<=cq<=q_bounds[1]:
                continue
            low,high = support(cp,cq)
            if not low<candidate[0]*factor[0]<high:
                continue
            trial,_ = evaluate(candidate); evaluations+=1
            if max(abs(v) for v in trial)<norm:
                x = candidate; accepted=True; break
        if not accepted:
            # Section/deck contact makes a coarse finite-difference Jacobian
            # average two local branches. Shrink its stencil before abandoning
            # the state, without relaxing the residual acceptance criterion.
            if difference_step>1.01e-7:
                difference_step /= 10
                continue
            raise ValueError('bounded equilibrium iteration cannot reduce residuals')
    else:
        raise ValueError('equilibrium iteration budget exhausted')
    residual,detail = evaluate(x); evaluations+=1
    if any(abs(v)>RESIDUAL_TOLERANCE for v in residual):
        raise ValueError('returned equilibrium failed independent residual check')
    d,p,q = detail['d'],detail['p'],detail['q']
    diagnostics = copy.deepcopy(state.get('diagnostics',[]))
    if metadata['source'] is None or metadata['estimate'] is None:
        diagnostics.append(_diagnostic('stability.geometry_provenance_unknown','geometry source/estimate is unknown'))
    for liquid in detail['liquids']:
        diagnostics.extend(copy.deepcopy(liquid['diagnostics']))
    names = ['volume','longitudinal']+(['transverse'] if fixed is None else [])
    return dict(converged=True,method_version=METHOD_VERSION,diagnostics=diagnostics,
        input_fingerprint=state.get('input_fingerprint'),loading=copy.deepcopy(state),geometry=metadata,
        validity=dict(complete=True,model_applicable=True,historical_validated=None,safe=None),
        angle_convention='waterplane_slope_angles_not_Euler_rotations',
        mode='free' if fixed is None else 'prescribed_heel',
        waterline_d_m=d,waterline_above_keel_m=d-keel,p=p,q=q,
        heel_deg=math.degrees(math.atan(q)),trim_deg=math.degrees(math.atan(p)),
        volume_m3=detail['hydro']['volume'],target_volume_m3=target,rho_t_m3=rho,
        waterplane_area_m2=detail['hydro']['awp'],waterplane_area_convention='geometric_intersection_including_contact_not_one_sided_derivative',
        buoyancy_centre_m=detail['b'],buoyancy_centre_keel_m=[*detail['b'][:2],detail['b'][2]-keel],
        effective_loading=dict(base_mass_t=base_mass,added_mass_t=added,total_mass_t=mass,
            cg_m=detail['cg'],cg_keel_m=[*detail['cg'][:2],detail['cg'][2]-keel],
            base_moments_t_m=[base_mass*v for v in base_cg],
            added_moments_t_m=[total-base_mass*cg for total,cg in zip(detail['moments'],base_cg)],
            moments_t_m=detail['moments']),
        liquids=detail['liquids'],fsc_policy='centroid_geometry_no_additional_fsc',gz_m=detail['raw'][2],
        axes=detail['axes'],residuals=dict(raw=dict(zip(names,detail['raw'])),
            scaled=dict(zip(names,detail['scaled'])),tolerance=RESIDUAL_TOLERANCE,
            scales=dict(volume_m3=target,longitudinal_m=length,transverse_m=beam)),
        solver=dict(method='safeguarded_simultaneous_Newton_central_Jacobian',iterations=iteration+1,
            max_iterations=count,evaluations=evaluations,heel_bounds_deg=hb,trim_bounds_deg=tb,
            finite_difference_step=difference_step,
            intercept_support_m=list(support(p,q))))


def _failed(state, error):
    return dict(converged=False,method_version=METHOD_VERSION,
        input_fingerprint=state.get('input_fingerprint') if isinstance(state,dict) else None,
        loading=copy.deepcopy(state),
        validity=dict(complete=False,model_applicable=False,historical_validated=None,safe=None),
        diagnostics=copy.deepcopy(state.get('diagnostics',[])) + [_diagnostic('stability.unresolved',str(error),True)]
            if isinstance(state,dict) else [_diagnostic('stability.unresolved',str(error),True)])


def solve_loaded_equilibrium(hull, loading_state, options=None):
    """Solve displacement and projected moments; return explicit failure diagnostics.

    Args:
        hull: Materialized canonical geometry or legacy stationed hull.
        loading_state: Complete resolved base mass/CG, before additional liquids.
        options: Density, explicit bounds, iteration limit, prescribed heel,
            initial angles, liquid loads, and legacy explicit keel datum.
    """
    try:
        if options is not None and not isinstance(options,dict):
            raise ValueError('options must be an object')
        options = copy.deepcopy(options) if options is not None else {}
        prepared = _prepare(hull,options)
        try:
            return _solve(prepared,loading_state,options)
        except ValueError as initial_error:
            # A suggested starting attitude is not a constraint. A steep initial
            # plane can lie on another moment branch; retry the neutral seed once
            # with all physical bounds, loading and tolerances unchanged.
            if 'initial' not in options or 'bounded equilibrium iteration' not in str(initial_error):
                raise
            retry = {key:value for key,value in options.items() if key!='initial'}
            result = _solve(prepared,loading_state,retry)
            result['solver']['restarted_from_neutral_seed'] = True
            result['diagnostics'].append(_diagnostic('stability.initial_seed_failed',str(initial_error)))
            return result
    except (ValueError,TypeError,KeyError,OverflowError,ZeroDivisionError) as error:
        return _failed(loading_state,error)


def stability_curve(hull, state, angles_deg, openings=None, options=None):
    """Solve each prescribed heel, bracket zeros and supplied opening immersion.

    Opening z_m is above the explicit keel. Empty definitions mean supplied
    no openings; None means unknown. Stiffness is dGZ/d(heel radians) at zero,
    with trim free, and is not a general GM or stability certificate. Optional
    options use the same datum/density/bounds/liquid definitions as the solver;
    each sample overrides only prescribed heel.
    """
    diagnostics = []
    rows, zeros = [], []
    downflooding = None
    angles = [_number(a,'curve angle') for a in angles_deg]
    if any(b<=a for a,b in zip(angles,angles[1:])):
        raise ValueError('curve angles must be strictly increasing')
    if options is not None and not isinstance(options,dict):
        raise ValueError('options must be an object')
    options = copy.deepcopy(options) if options is not None else {}
    try:
        prepared = _prepare(hull,options)
    except (ValueError,TypeError,KeyError,OverflowError,ZeroDivisionError) as error:
        failed = _failed(state,error)
        return dict(method_version=METHOD_VERSION,converged=False,
            validity=dict(complete=False,model_applicable=False,historical_validated=None,safe=None),
            rows=[dict(angle_deg=angle,gz_m=None,equilibrium=copy.deepcopy(failed),
                validity=dict(model_applicable=False,intact_valid=False)) for angle in angles],
            zero_crossings=[],avs_deg=None,maximum=None,
            endpoint=dict(kind='failed_sample' if angles else 'no_samples',angle_deg=angles[-1] if angles else None,gz_m=None),
            initial_stiffness_m=None,downflooding=None,deck_edge_immersion=None,
            diagnostics=failed['diagnostics'],safe=None,input_fingerprint=state.get('input_fingerprint'),
            loading=copy.deepcopy(state))
    keel = prepared[3]['keel_offset_m']
    open_points = []
    if openings is None:
        diagnostics.append(_diagnostic('stability.openings_unknown','downflooding is unknown without supplied opening definitions'))
    else:
        ids = set()
        for point in openings:
            if not isinstance(point.get('open'),bool) or not isinstance(point.get('id'),str) or point['id'] in ids:
                raise ValueError('openings need unique IDs and explicit boolean open state')
            ids.add(point['id'])
            coords = [_number(point.get(k),k) for k in ('x_m','y_m','z_m')]
            if point['open']:
                open_points.append((point['id'],coords))
    def solve(angle):
        try:
            return _solve(prepared,state,{**options,'heel_deg':angle})
        except (ValueError,TypeError,KeyError,OverflowError,ZeroDivisionError) as error:
            return _failed(state,error)
    def clearance(result):
        if not open_points:
            return None
        s = math.sqrt(1+result['p']**2+result['q']**2)
        return min(((z+keel-result['p']*x-result['q']*y-result['waterline_d_m'])/s,identity)
                   for identity,(x,y,z) in open_points)
    def bracket(a,b,kind):
        ra,rb = solve(a),solve(b)
        def value(r):
            return r['gz_m'] if kind=='zero' else clearance(r)[0]
        if not ra['converged'] or not rb['converged'] or value(ra)*value(rb)>=0:
            return None
        for _ in range(45):
            mid=(a+b)/2; rm=solve(mid)
            if not rm['converged']:
                return None
            if abs(value(rm))<=1e-9:
                return mid,rm
            if value(ra)*value(rm)<=0:
                b,rb=mid,rm
            else:
                a,ra=mid,rm
        return (a+b)/2,rm
    previous = None
    for angle in angles:
        result = solve(angle)
        clear = clearance(result) if result['converged'] else None
        if clear is not None and clear[0]<=0 and downflooding is None:
            crossing = bracket(previous[0],angle,'opening') if previous and previous[2] and previous[2][0]>0 else None
            downflooding = dict(angle_deg=crossing[0] if crossing else angle,
                kind='bracketed_immersion' if crossing else 'already_immersed_sample',opening_id=clear[1])
        if previous and result['converged'] and previous[1]['converged']:
            if previous[1]['gz_m']*result['gz_m']<0 and abs(previous[1]['gz_m'])>1e-8 and abs(result['gz_m'])>1e-8:
                root = bracket(previous[0],angle,'zero')
                if root:
                    zeros.append(dict(kind='bracketed_zero',angle_deg=root[0],gz_m=root[1]['gz_m'],
                        bracket_deg=[previous[0],angle],direction='positive_to_negative' if previous[1]['gz_m']>0 else 'negative_to_positive'))
        rows.append(dict(angle_deg=angle,gz_m=result.get('gz_m'),equilibrium=result,
            opening_normal_clearance_m=clear[0] if clear else None,
            validity=dict(model_applicable=result['converged'],
                intact_valid=(result['converged'] and downflooding is None) if openings is not None else None,
                deck_edge_immersion=None,deck_edge_status='unknown_no_explicit_deck_edges')))
        previous=(angle,result,clear) if result['converged'] else None
    for root in zeros:
        root['intact_valid'] = (downflooding is None or root['angle_deg']<downflooding['angle_deg']) if openings is not None else None
    valid_rows = [row for row in rows if row['equilibrium']['converged']]
    maximum = None
    if valid_rows:
        highest = max(valid_rows,key=lambda row:row['gz_m'])
        maximum = dict(kind='sampled_maximum',angle_deg=highest['angle_deg'],gz_m=highest['gz_m'])
    plus,minus = solve(.01),solve(-.01)
    stiffness = ((plus['gz_m']-minus['gz_m'])/math.radians(.02)) if plus['converged'] and minus['converged'] else None
    endpoint = dict(kind='no_samples',angle_deg=None,gz_m=None)
    if rows:
        last=rows[-1]
        limits = _bounds(options,'heel_bounds_deg',[-85,85])
        kind = 'model_limit' if not last['equilibrium']['converged'] and not limits[0]<=last['angle_deg']<=limits[1] else (
            'failed_sample' if not last['equilibrium']['converged'] else 'positive_sample' if last['gz_m']>0 else 'nonpositive_sample')
        endpoint = dict(kind=kind,angle_deg=last['angle_deg'],gz_m=last['gz_m'])
    avs = next((r['angle_deg'] for r in zeros if r['direction']=='positive_to_negative' and r['intact_valid'] is True),None)
    complete = bool(rows) and len(valid_rows)==len(rows)
    return dict(method_version=METHOD_VERSION,converged=complete,
        validity=dict(complete=complete,model_applicable=complete,historical_validated=None,safe=None),
        rows=rows,zero_crossings=zeros,avs_deg=avs,
        maximum=maximum,endpoint=endpoint,initial_stiffness_m=stiffness,
        stiffness_definition='dGZ/dheel_rad_at_zero_with_longitudinal_equilibrium',
        downflooding=downflooding,deck_edge_immersion=None,diagnostics=diagnostics,safe=None,
        input_fingerprint=state.get('input_fingerprint'),loading=copy.deepcopy(state))
