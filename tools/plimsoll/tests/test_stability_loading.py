"""Independent loaded-equilibrium anchors and failure/validity contracts."""
import copy
import importlib.util
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import geometry

try:
    import stability
except ModuleNotFoundError:
    stability = None


def oracle(name):
    path = Path(__file__).resolve().parents[3] / 'docs/plimsoll-1.0/evidence' / name
    spec = importlib.util.spec_from_file_location('independent_oracle', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.oracle()


def record(stations, keel=0):
    return dict(kind='offsets', keel_offset_m=keel, source='analytical fixture',
                estimate=False, offsets=dict(schema='plimsoll-section-polygons-1', stations=stations))


def box(n=81, shift=0, length=40, beam=10, depth=10):
    poly = [[-beam/2, shift], [beam/2, shift], [beam/2, depth+shift], [-beam/2, depth+shift]]
    return record([[-length/2+length*i/(n-1), copy.deepcopy(poly)] for i in range(n)], shift)


def ellipsoid(n, m):
    stations = []
    for i in range(n):
        x = -20*math.cos(math.pi*i/(n-1))
        r = math.sqrt(max(0, 1-(x/20)**2))
        stations.append([x, [[5*r*math.cos(2*math.pi*j/m), 5+5*r*math.sin(2*math.pi*j/m)] for j in range(m)]])
    return record(stations)


def load(mass=1640, cg=(0, 0, 3)):
    return dict(complete_mass=True, complete_cg=True, input_fingerprint='fixture',
                condition_id='selected', project_id='box', diagnostics=[],
                provenance={'estimate': True}, uncertainty={'status': 'unknown'},
                values=dict(total_mass_t=mass, lcg_m=cg[0], tcg_m=cg[1], kg_m=cg[2]),
                coverage={'reference_displacement_t': mass*9})


class PrimitiveRegression(unittest.TestCase):
    def test_triangle_winding_closure_and_tangent_contact(self):
        poly = [(1,0),(5,0),(1,4)]
        for shape in (poly,poly[::-1],poly+[poly[0]]):
            h = geometry.StationedHull([(x,shape) for x in (-5,0,5)])
            r = h.integrate(0,2)
            self.assertAlmostEqual(r['volume'],60)
            self.assertAlmostEqual(r['yb'],23/9)
            self.assertAlmostEqual(r['zb'],8/9)
            self.assertAlmostEqual(r['awp'],20)
            self.assertEqual(h.integrate(0,4)['awp'],0)

    def test_concave_waterplane_is_sum_of_occupied_intervals(self):
        poly = [(-3,0),(3,0),(3,4),(1,4),(1,1),(-1,1),(-1,4),(-3,4)]
        h = geometry.StationedHull([(x, poly) for x in (-5,0,5)])
        r = h.integrate(0, 2)
        self.assertAlmostEqual(r['volume'], 100)
        self.assertAlmostEqual(r['awp'], 40)

    def test_exact_deck_contact_reports_geometric_area(self):
        poly = [(-1,0),(1,0),(1,4),(-1,4)]
        h = geometry.StationedHull([(x, poly) for x in (-5,0,5)])
        self.assertAlmostEqual(h.integrate(0,4)['awp'], 20)
        self.assertEqual(h.integrate(0,4.01)['awp'], 0)


class LoadedStability(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(stability, 'loaded stability API is not implemented')

    def solved(self, result):
        self.assertTrue(result['converged'], result)
        for value in result['residuals']['scaled'].values():
            self.assertLessEqual(abs(value), 1e-6)
        # Reconstruct the physical arms independently of serialized residuals.
        dx,dy,dz=[b-g for b,g in zip(result['buoyancy_centre_m'],result['effective_loading']['cg_m'])]
        p,q=result['p'],result['q']
        longitudinal=((1+q*q)*dx-p*q*dy+p*dz)/math.sqrt((1+p*p+q*q)*(1+q*q))
        transverse=(dy+q*dz)/math.sqrt(1+q*q)
        scales=result['residuals']['scales']
        self.assertLessEqual(abs(longitudinal)/scales['longitudinal_m'],1e-6)
        self.assertAlmostEqual(transverse,result['gz_m'],places=10)
        if result['mode']=='free':self.assertLessEqual(abs(transverse)/scales['transverse_m'],1e-6)
        self.assertLessEqual(abs(result['volume_m3']-result['target_volume_m3'])/result['target_volume_m3'],1e-6)

    def test_upright_mass_and_explicit_keel_translation(self):
        for shift in (0, 13.25):
            r = stability.solve_loaded_equilibrium(box(shift=shift), load())
            self.solved(r)
            self.assertAlmostEqual(r['waterline_d_m']-shift, 4, places=7)
            self.assertAlmostEqual(r['buoyancy_centre_keel_m'][2], 2, places=7)
            self.assertEqual(r['effective_loading']['total_mass_t'], 1640)
            self.assertEqual(r['effective_loading']['cg_m'][2],3+shift)

    def test_free_coupled_box_and_mirror(self):
        o = oracle('coupled_box_oracles.py')
        for mirror in (1,-1):
            cg = o['free_equilibrium_cg_m'][:]
            cg[1] *= mirror
            r = stability.solve_loaded_equilibrium(box(161), load(o['mass_t'], cg))
            self.solved(r)
            self.assertAlmostEqual(r['p'], .01, delta=1e-6)
            self.assertAlmostEqual(r['q'], mirror*.1, delta=1e-6)
            self.assertAlmostEqual(r['gz_m'], 0, delta=1e-6)

    def test_prescribed_heel_uses_projected_longitudinal_axis(self):
        o = oracle('coupled_box_oracles.py')
        r = stability.solve_loaded_equilibrium(box(641), load(o['mass_t'], o['constrained_heel_cg_m']),
                                              {'heel_deg': o['waterplane']['heel_deg']})
        self.solved(r)
        self.assertAlmostEqual(r['p'], .01, delta=2e-7)
        self.assertAlmostEqual(r['gz_m'], .25, delta=1e-6)

    def test_keel_need_not_equal_lowest_vertex_and_inputs_not_mutated(self):
        h, s, options = box(), load(cg=(0,0,5)), {'rho_t_m3':1.025}
        h['keel_offset_m'] = -2
        before = copy.deepcopy((h,s,options))
        r = stability.solve_loaded_equilibrium(h,s,options)
        self.solved(r)
        self.assertEqual((h,s,options), before)
        self.assertAlmostEqual(r['buoyancy_centre_keel_m'][2], 4)
        self.assertEqual(r['loading']['uncertainty'], s['uncertainty'])
        self.assertEqual(r['input_fingerprint'], 'fixture')

    def test_invalid_loading_and_options_never_converge(self):
        for value in (0,-1,True,float('nan'),float('inf')):
            with self.subTest(value=value):
                self.assertFalse(stability.solve_loaded_equilibrium(box(),load(value))['converged'])
                self.assertFalse(stability.solve_loaded_equilibrium(box(),load(),{'rho_t_m3':value})['converged'])
        for opts in ({'max_iterations':0},{'heel_bounds_deg':[-90,90]}, {'heel_deg':89}, {'trim_bounds_deg':[1,-1]}):
            self.assertFalse(stability.solve_loaded_equilibrium(box(),load(cg=(1,1,3)),opts)['converged'])
        s = load(); s['complete_cg'] = False
        self.assertFalse(stability.solve_loaded_equilibrium(box(),s)['converged'])

    def test_overload_saturation_and_unreachable_cg_fail(self):
        for s in (load(4800*1.025),load(4000*1.025),load(cg=(1000,0,3))):
            self.assertFalse(stability.solve_loaded_equilibrium(box(),s)['converged'])

    def test_strict_readiness(self):
        fixtures = []
        h = box(); h['keel_offset_m'] = None; fixtures.append(h)
        h = box(); h['offsets']['schema'] = 'unknown'; fixtures.append(h)
        h = box(); h['offsets']['stations'][1][0] = h['offsets']['stations'][0][0]; fixtures.append(h)
        h = box(); h['offsets']['stations'][0][1][0][0] = True; fixtures.append(h)
        fixtures.append(record([(x,[(-1,0),(1,2),(-1,2),(1,0)]) for x in (-1,0,1)]))
        fixtures.append({'kind':'offsets_reference','reference':{'path':'never-read.json'},'keel_offset_m':0})
        for h in fixtures:
            self.assertFalse(stability.solve_loaded_equilibrium(h,load())['converged'])

    def test_legacy_object_requires_explicit_datum(self):
        h = geometry.StationedHull(box()['offsets']['stations'])
        self.assertFalse(stability.solve_loaded_equilibrium(h,load())['converged'])
        self.solved(stability.solve_loaded_equilibrium(h,load(),{'keel_offset_m':0}))

    def test_slope_aware_support_with_shallow_trimmed_envelope(self):
        h = box(161,length=100,beam=10,depth=1)
        # A steep seed lies on a different moment-response branch. A neutral
        # restart is permitted, but every returned residual still has to pass.
        r = stability.solve_loaded_equilibrium(h,load(102.5,cg=(40,0,.5)),
                                              {'initial':{'trim_deg':20,'heel_deg':0}})
        self.solved(r)
        self.assertAlmostEqual(r['volume_m3'],100,delta=1e-4)

    def test_nonbox_refinement_and_nonzero_gz(self):
        o = oracle('coupled_ellipsoid_oracles.py')
        results = []
        for n,m in ((41,32),(81,64),(161,128)):
            h = ellipsoid(n,m)
            free = stability.solve_loaded_equilibrium(h,load(o['mass_t'],o['free_equilibrium_cg_m']))
            fixed = stability.solve_loaded_equilibrium(h,load(o['mass_t'],o['constrained_heel_cg_m']),
                                                     {'heel_deg':o['waterplane']['heel_deg']})
            self.solved(free); self.solved(fixed)
            results.append((free,fixed))
        for a,b in zip(results[-2],results[-1]):
            for key,scale in (('p',.01),('q',.1),('waterline_d_m',4),('gz_m',1)):
                self.assertLess(abs(a[key]-b[key])/scale,.01)
            for x,y in zip(a['buoyancy_centre_m'],b['buoyancy_centre_m']):
                self.assertLess(abs(x-y)/max(1,abs(y)),.01)
        self.assertAlmostEqual(results[-1][1]['gz_m'],.15,delta=.001)

    def test_curve_initial_stiffness_and_positive_endpoint_are_separate(self):
        r = stability.stability_curve(box(),load(),[0,1,5,10])
        self.assertAlmostEqual(r['initial_stiffness_m'],2+100/48-3,delta=2e-5)
        self.assertIsNone(r['avs_deg'])
        self.assertEqual(r['endpoint']['kind'],'positive_sample')
        self.assertIsNone(r['downflooding'])
        self.assertIsNone(r['safe'])

    def test_downflood_cutoff_and_model_limit(self):
        openings = [{'id':'door','x_m':0,'y_m':5,'z_m':4.5,'open':True}]
        r = stability.stability_curve(box(),load(),[0,5,10,30,89],openings)
        self.assertAlmostEqual(r['downflooding']['angle_deg'],math.degrees(math.atan(.1)),delta=.01)
        self.assertFalse(r['rows'][2]['validity']['intact_valid'])
        self.assertFalse(r['rows'][-1]['equilibrium']['converged'])
        self.assertEqual(r['endpoint']['kind'],'model_limit')

    def test_actual_sign_bracket_distinct_from_sampled_maximum(self):
        r = stability.stability_curve(box(),load(cg=(0,0,4.5)),[0,10,20,30,40,50,60,70,80],[])
        self.assertTrue(r['zero_crossings'])
        for root in r['zero_crossings']:
            self.assertLessEqual(abs(root['gz_m']),1e-6)
            self.assertEqual(root['kind'],'bracketed_zero')
        self.assertEqual(r['maximum']['kind'],'sampled_maximum')

    def test_moving_liquid_conserves_mass_and_its_stiffness_has_no_second_fsc(self):
        tank = dict(id='water',length_m=10,beam_m=8,height_m=4,x_m=0,y_m=0,keel_to_bottom_m=0,permeability=1)
        s = load(1480,cg=(0,0,3))
        options = {'liquid_loads':[{'tank':tank,'volume_m3':160,'fluid_density_t_m3':1}]}
        r = stability.solve_loaded_equilibrium(box(),s,options)
        self.solved(r)
        self.assertEqual(r['effective_loading']['total_mass_t'],1640)
        self.assertEqual(r['effective_loading']['added_mass_t'],160)
        plus = stability.solve_loaded_equilibrium(box(),s,{**options,'heel_deg':.01})
        minus = stability.solve_loaded_equilibrium(box(),s,{**options,'heel_deg':-.01})
        expected = 2+100/48-(1480*3+160*1)/1640-(10*8**3/12)/1640
        self.assertAlmostEqual((plus['gz_m']-minus['gz_m'])/math.radians(.02),expected,delta=2e-6)
        self.assertEqual(r['liquids'][0]['fsc_policy'],'centroid_geometry_no_additional_fsc')

    def test_curve_options_preserve_liquid_and_density_and_datum(self):
        tank = dict(id='water',length_m=10,beam_m=8,height_m=4,x_m=0,y_m=0,keel_to_bottom_m=0,permeability=1)
        options = {'liquid_loads':[{'tank':tank,'volume_m3':160,'fluid_density_t_m3':1}]}
        curve = stability.stability_curve(box(),load(1480),[0,5],[],options)
        expected = 2+100/48-(1480*3+160)/1640-(10*8**3/12)/1640
        self.assertAlmostEqual(curve['initial_stiffness_m'],expected,delta=2e-6)
        self.assertEqual(curve['rows'][1]['equilibrium']['effective_loading']['added_mass_t'],160)

    def test_liquid_inputs_fail_without_double_counting_or_underflow(self):
        tank = dict(id='water',length_m=10,beam_m=8,height_m=4,x_m=0,y_m=0,keel_to_bottom_m=0,permeability=1)
        liquid = {'tank':tank,'volume_m3':160,'fluid_density_t_m3':1}
        for liquids in ([liquid,liquid],[{**liquid,'volume_m3':500}], [{**liquid,'fluid_density_t_m3':True}]):
            self.assertFalse(stability.solve_loaded_equilibrium(box(),load(),{'liquid_loads':liquids})['converged'])
        s=load();s['effective_items']=[{'id':'water'}]
        self.assertFalse(stability.solve_loaded_equilibrium(box(),s,{'liquid_loads':[liquid]})['converged'])
        tiny = {**liquid,'volume_m3':1e-200,'fluid_density_t_m3':1e-200}
        self.assertFalse(stability.solve_loaded_equilibrium(box(),load(),{'liquid_loads':[tiny]})['converged'])

    def test_neutral_initial_configuration_is_singular(self):
        r = stability.solve_loaded_equilibrium(box(),load(cg=(0,0,2+100/48)))
        self.assertFalse(r['converged'])
        self.assertIn('singular',r['diagnostics'][-1]['message'])

    def test_axes_are_orthonormal_right_handed_at_coupled_solution(self):
        o=oracle('coupled_box_oracles.py')
        r=stability.solve_loaded_equilibrium(box(81),load(o['mass_t'],o['free_equilibrium_cg_m']))
        self.solved(r)
        u,v,n=[r['axes'][k] for k in ('u','v','n')]
        for a in (u,v,n): self.assertAlmostEqual(sum(x*x for x in a),1,places=10)
        for a,b in ((u,v),(u,n),(v,n)): self.assertAlmostEqual(sum(x*y for x,y in zip(a,b)),0,places=10)
        cross=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
        for a,b in zip(cross,n):self.assertAlmostEqual(a,b,places=10)

    def test_legacy_offsets_explicit_box_materialization(self):
        h=dict(kind='offsets',keel_offset_m=-5,source='explicit box table',estimate=True,
               offsets=dict(schema='plimsoll-offsets-1',deck_z_m=5,
                            stations=[[x,5,5,-5,5] for x in (-20,-10,0,10,20)]))
        r=stability.solve_loaded_equilibrium(h,load())
        self.solved(r)
        self.assertAlmostEqual(r['waterline_above_keel_m'],4,places=7)
        self.assertIs(r['geometry']['estimate'],True)

    def test_iteration_exhaustion_never_reuses_a_good_state(self):
        o=oracle('coupled_box_oracles.py')
        s=load(o['mass_t'],o['free_equilibrium_cg_m'])
        r=stability.solve_loaded_equilibrium(box(),s,{'max_iterations':1})
        self.assertFalse(r['converged'])
        self.assertNotIn('gz_m',r)
        self.assertIn('budget',r['diagnostics'][-1]['message'])

    def test_refinement_of_stations_and_sections_separately(self):
        o=oracle('coupled_ellipsoid_oracles.py')
        results={}
        for n,m in ((81,128),(161,128),(161,64)):
            r=stability.solve_loaded_equilibrium(ellipsoid(n,m),load(o['mass_t'],o['constrained_heel_cg_m']),
                                                {'heel_deg':o['waterplane']['heel_deg']})
            self.solved(r);results[n,m]=r
        fine=results[161,128]
        for key in ((81,128),(161,64)):
            rough=results[key]
            for field,scale in (('p',.01),('waterline_d_m',4),('gz_m',1)):
                self.assertLess(abs(rough[field]-fine[field])/scale,.01)

    def test_missing_geometry_is_explicit_curve_failure(self):
        r=stability.stability_curve({'kind':'parameters','parameters':{'block_coeff':.7}},load(),[0,10])
        self.assertEqual(len(r['rows']),2)
        self.assertTrue(all(not row['equilibrium']['converged'] for row in r['rows']))
        self.assertIsNone(r['initial_stiffness_m'])

    def test_supplied_closed_opening_and_root_after_immersion(self):
        opening={'id':'door','x_m':0,'y_m':5,'z_m':4.5,'open':False}
        closed=stability.stability_curve(box(),load(),[0,10],[opening])
        self.assertIsNone(closed['downflooding'])
        flooded=stability.stability_curve(box(),load(cg=(0,0,4.5)),[0,10,20,30,40,50,60,70,80],[{**opening,'open':True}])
        self.assertTrue(flooded['zero_crossings'])
        self.assertIsNone(flooded['avs_deg'])
        self.assertTrue(all(root['intact_valid'] is False for root in flooded['zero_crossings']))

    def test_collinear_pointed_end_sections_are_valid(self):
        middle=box()['offsets']['stations'][0][1]
        end=[(0,0),(0,2),(0,4),(0,6),(0,4),(0,2)]
        h=record([[-20,end],[0,middle],[20,end]])
        self.solved(stability.solve_loaded_equilibrium(h,load()))

    def test_invalid_slope_initial_cannot_wrap_tangent_into_valid_domain(self):
        r=stability.solve_loaded_equilibrium(box(),load(),{'initial':{'trim_deg':180}})
        self.assertFalse(r['converged'])

    def test_inclined_explicit_keel_translation_preserves_physical_attitude(self):
        o=oracle('coupled_box_oracles.py')
        answers=[stability.solve_loaded_equilibrium(box(161,shift=shift),load(o['mass_t'],o['free_equilibrium_cg_m']))
                 for shift in (0,13.25)]
        for r in answers:self.solved(r)
        for key in ('p','q','gz_m','waterline_above_keel_m'):
            self.assertAlmostEqual(answers[0][key],answers[1][key],places=8)

    def test_failed_row_does_not_bridge_an_intact_root_claim(self):
        # A severe iteration budget must produce explicit failure at each sample.
        r=stability.stability_curve(box(),load(cg=(1,0,3)),[0,5,10],[],{'max_iterations':1})
        self.assertTrue(all(not row['equilibrium']['converged'] for row in r['rows']))
        self.assertIsNone(r['avs_deg'])
        self.assertEqual(r['zero_crossings'],[])

    def test_reachable_high_trim_draft_lies_outside_uninclined_z_bounds(self):
        # Independent integrals of h(x)=clamp(p*(x-40)+.5,0,1):
        # integral(h dx)=10, Bx=45-1/(240*p^2), Bz=.5-1/(120*p).
        p=math.tan(math.radians(20))
        cg=(45-1/(240*p*p)-1/120,0,.5)
        r=stability.solve_loaded_equilibrium(box(1601,length=100,beam=10,depth=1),load(102.5,cg),
            {'heel_deg':0,'initial':{'trim_deg':20}})
        self.solved(r)
        self.assertLess(r['waterline_d_m'],-10)
        self.assertLess(abs(r['p']-p)/p,.01)


if __name__ == '__main__':
    unittest.main()
