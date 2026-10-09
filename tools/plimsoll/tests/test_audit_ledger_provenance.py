"""Selected ledger aggregation and provenance regressions, using generic inputs."""
import copy
import unittest

from plimsoll import analysis, loading, page_rows, project_io, systems


def item(identity, mass, estimate=False):
    return dict(id=identity, mass_t=mass, x_m=0, y_m=0, kg_m=2,
                source={'citation': identity}, estimate=estimate)


def project(items):
    p = project_io.new_project('Ledger regression', 'ledger-regression')
    p['weight_groups'] = [dict(id='outfit', required=True, items=items)]
    p['loading_conditions'] = [dict(id='normal', overrides={})]
    return p


def battery():
    p = project([item('gun', 1), item('a', 10), item('b', 20)])
    p['systems'] = dict(weapons=dict(main=dict(weight_item_ids=['gun', 'a', 'b'],
        installed_guns=2, broadside_guns=1, rounds_per_gun=100,
        source='battery declaration', estimate=False,
        facts=dict(projectile_mass_kg=dict(value=40, source='shell specification', estimate=False)),
        page_rows=[dict(row='guns', weight_item_ids=['gun']),
                   dict(row='ammunition', weight_item_ids=['a', 'b'])])))
    return p


def propulsion():
    p = project([item('plant', 20), item('coal', 80), item('oil', 5)])
    p['systems'] = dict(propulsion=dict(weight_item_ids=['plant'], source='plant', estimate=False,
        facts={key: dict(value=value, source='measured', estimate=False)
               for key, value in (('shafts', 2), ('design_power_kw', 1000), ('max_speed_kn', 20))},
        fuel_bindings={name: dict(weight_item_ids=[name], source='selected ledger', estimate=False)
                       for name in ('coal', 'oil')}))
    p['endurance_scenarios'] = [dict(id='fixed', method='steady_simultaneous_fuel_consumption',
        speed_kn=12, power_kw=500, source='fixed burn', estimate=False,
        fuels=dict(coal=dict(required=True, burn_t_per_day=10, reserve_t=0),
                   oil=dict(required=False, burn_t_per_day=0, reserve_t=0)))]
    return p


class LedgerProvenanceAuditTests(unittest.TestCase):
    def test_ammunition_outfit_aggregates_selected_items_and_unknowns(self):
        for mass, expected in ((20, 30), (None, None), (0, 10)):
            p = battery()
            p['loading_conditions'][0]['overrides'] = {'b': {'mass_t': mass}}
            state = loading.resolve_loading(p, 'normal')
            view = page_rows.guns_rows(state, systems.summary(p, state),
                                      'weapons', 'main', p['systems']['weapons']['main'])
            self.assertEqual(view['ship_wide_ammunition_t'], expected)
            self.assertEqual(view['broadside_mass_kg'], 40)

    def test_row_estimates_use_three_states(self):
        for estimates, expected in (((False, True), True), ((False, None), None),
                                    ((True, None), True), ((False, False), False)):
            p = battery()
            for row, flag in zip(p['weight_groups'][0]['items'][1:], estimates):
                row['estimate'] = flag
            state = loading.resolve_loading(p, 'normal')
            view = page_rows.project_declared_rows(state, systems.summary(p, state),
                'weapons', 'main', p['systems']['weapons']['main']['page_rows'])
            self.assertIs(view['rows'][1]['estimate'], expected)

    def test_estimated_fuel_reaches_native_trace_and_endurance(self):
        p = propulsion()
        p['weight_groups'][0]['items'][1]['estimate'] = True
        result = analysis.compute_project(p, 'normal',
            dict(stages=['endurance'], endurance_scenario_id='fixed'))
        values = result['stages']['endurance']['data']['values']
        self.assertEqual(values['hours'], 192)
        self.assertEqual(values['range_nm'], 2304)
        self.assertIs(values['estimate'], True)
        trace = {t['key']: t for t in result['stages']['propulsion']['data']['trace']}
        self.assertIs(trace['coal_t']['estimate'], True)

    def test_position_override_does_not_taint_fuel_mass(self):
        p = propulsion()
        p['loading_conditions'][0].update(overrides={'coal': {'x_m': 3}},
            override_provenance={'coal': {'x_m': dict(source='estimated position', estimate=True)}})
        r = analysis.compute_project(p, 'normal', dict(stages=['endurance'], endurance_scenario_id='fixed'))
        self.assertIs(r['stages']['endurance']['data']['values']['estimate'], False)

    def test_binding_sources_and_explicit_absence_reach_local_traces(self):
        for flag in (False, True):
            p = propulsion()
            coal_source = {'citation': 'coal ownership declaration'}
            absent_source = {'citation': 'survey confirms no oil'}
            bindings = p['systems']['propulsion']['fuel_bindings']
            bindings['coal']['source'] = coal_source
            bindings['oil'] = dict(weight_item_ids=[], absent=True,
                                   source=absent_source, estimate=flag)
            r = analysis.compute_project(p, 'normal', dict(stages=['endurance'],
                                                           endurance_scenario_id='fixed'))
            trace = {t['key']: t for t in r['stages']['propulsion']['data']['trace']}
            self.assertIn(coal_source, trace['coal_t']['source'])
            for key in ('oil_t', 'bunker_total_t', 'pct_coal'):
                self.assertIs(trace[key]['estimate'], flag)
            self.assertIn(absent_source, trace['oil_t']['source'])
            endurance = r['stages']['endurance']['data']['values']
            self.assertIn(coal_source, endurance['input_sources']['fuel_masses']['coal'])
            self.assertIs(endurance['estimate'], False)

    def test_deck_mixed_sources_and_estimates_survive(self):
        deck = dict(points=[dict(id='a', x_m=0, freeboard_m=dict(value=1, source={'survey': 'a'}, estimate=False)),
                            dict(id='b', x_m=20, freeboard_m=dict(value=3, source={'survey': 'b'}, estimate=True))],
                    segments=[dict(id='deck', aft_point_id='a', fore_point_id='b')])
        values = page_rows.freeboard_rows(deck)['values']
        self.assertIs(values['weighted_mean_estimate'], True)
        self.assertEqual(values['weighted_mean_source'], [{'survey': 'a'}, {'survey': 'b'}])

    def test_invalid_source_types_are_rejected_but_unknown_drafts_are_allowed(self):
        for source in ([], False, 0):
            p = project([item('a', 10)])
            p['weight_groups'][0]['items'][0]['source'] = source
            with self.subTest(source=source), self.assertRaises(project_io.ProjectValidationError):
                project_io.normalize_project(p)
        for source in (None, '', '  ', {}):
            p = project([item('a', 10)])
            p['weight_groups'][0]['items'][0]['source'] = source
            result = loading.resolve_loading(p, 'normal')
            self.assertFalse(result['provenance']['provenance_complete'])
            self.assertFalse(result['uncertainty']['certified'])

    def test_migration_rejects_explicit_incompatible_datum(self):
        ship = dict(schema='plimsoll-ship-1', name='Generic legacy', hull={})
        for datum in ('model', 'waterline'):
            weights = dict(schema='plimsoll-weights-1', datum=datum, groups=[])
            with self.assertRaisesRegex(ValueError, 'datum|基准'):
                project_io.migrate_legacy(ship, weights)


if __name__ == '__main__':
    unittest.main()
