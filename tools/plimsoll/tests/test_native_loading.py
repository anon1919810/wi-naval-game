"""Native ledger integration: case isolation and a single adoption authority."""
import copy
import json
from pathlib import Path
from unittest.mock import patch

from plimsoll import analysis, exports, loading, project_io, ship_design, ship_design_mass, sps_file_io, systems
from test_loading import analytic_project
from test_systems_integration import fixture as systems_fixture


def source():
    return json.loads((Path(__file__).parent / 'fixtures' / 'sps3b3-synthetic.json').read_text('utf-8'))


def test_fresh_design_uses_documented_original_product_defaults_without_cg():
    p = ship_design.initialize(project_io.new_project('Fresh'))['project']
    reopened = sps_file_io.loads(sps_file_io.dumps(ship_design.to_source(p['ship_design'])))
    assert reopened['parameters']['hull_year'] == 1950
    assert reopened['parameters']['hull_scale'] == 0
    assert reopened['parameters']['gun1_barrels'] == 0
    assert p['geometry'] is None
    assert all(i.get('kg_m') is None for g in p['weight_groups'] for i in g['items'])


def test_new_native_ledger_is_loading_mass_only_in_design_case():
    p = ship_design.initialize(project_io.new_project('Native loading'), source())['project']
    basis = p['ship_design']['condition_id']
    p['loading_conditions'] += [
        dict(id='other', label='Other case', overrides={}),
        dict(id='derived', label='Existing inherited case', overrides={}, definition=dict(
            kind='standard', base_condition_id=basis, excluded_item_ids=[], source='explicit study', estimate=True))]
    before = copy.deepcopy(p)
    native = ship_design.compute(p)
    state = loading.resolve_loading(p, basis)
    assert abs(state['values']['total_mass_t'] - native['balance']['selected_mass_t']) < 1e-8
    assert not state['complete_cg']  # Never synthesize positions from empirical mass.
    for condition_id in ('other', 'derived'):
        assert loading.resolve_loading(p, condition_id)['values']['total_mass_t'] == 0
    assert p == before


def test_existing_manual_base_overrides_and_derived_case_survive_estimation():
    p = analytic_project()
    p['loading_conditions'].append(dict(id='derived', label='Inherited normal', overrides={}, definition=dict(
        kind='standard', base_condition_id='normal', excluded_item_ids=[], source='explicit study', estimate=True)))
    native = ship_design.from_source(source(), condition_id='normal')
    native['mass_bindings'] = {'structure': dict(item_ids=['first'], mode='estimated'),
                               'other': dict(item_ids=['second'], mode='declared')}
    p['ship_design'] = native
    initial = copy.deepcopy(p)
    p = ship_design.initialize(p)['project']
    selected = loading.resolve_loading(p, 'normal')
    expected = next(i for g in p['weight_groups'] for i in g['items'] if i['id'] == 'first')['design_mass']['mass_t']
    effective = next(i for i in selected['effective_items'] if i['id'] == 'first')
    assert effective['mass_t'] == expected
    assert effective['provenance']['fields']['mass_t']['origin'] == 'ship_design'
    # The old condition and derived case still carry the original manual totals.
    assert loading.resolve_loading(p, 'light')['values']['total_mass_t'] == 200
    assert loading.resolve_loading(p, 'derived')['values']['total_mass_t'] == 400
    assert p['loading_conditions'] == initial['loading_conditions']
    for before, after in zip(initial['weight_groups'][0]['items'], p['weight_groups'][0]['items']):
        assert {k: after[k] for k in before} == before


def test_native_bound_physical_models_remain_readonly_without_legacy_adoption():
    p, state = systems_fixture()
    assert [r['item_id'] for r in systems.summary(p, state)['update_proposals']] == ['armour']
    p['ship_design'] = {'mass_bindings': {'deck': dict(item_ids=['armour'], mode='declared')}}
    p['concept_design'] = {'retained': 'old declaration for provenance'}
    before = copy.deepcopy(p)
    with patch('concept_design.generated_models', side_effect=AssertionError('superseded authority ran')):
        result = systems.summary(p, state)
    assert result['update_proposals'] == []
    model = result['systems']['armament']['mass_models'][1]
    assert model['calculated_mass_t'] == 39.25
    assert model['adoption_allowed'] is False
    assert p == before


def test_mixed_aggregate_cannot_be_inferred_as_a_single_detail_role():
    p = analytic_project()
    p['weight_groups'][0]['items'] = [dict(id='whole-battery', mass_t=400, x_m=0, y_m=0, kg_m=4,
        source='reviewed total', estimate=False, includes=['guns', 'mounts', 'gun_armour'])]
    p['concept_design'] = {'balance': {'roles': {'whole-battery': 'mounts'}}}
    bindings, pending = ship_design_mass.infer_bindings(p)
    assert pending == ['whole-battery']
    assert 'mounts' not in bindings


def test_binding_pending_does_not_withhold_complete_saved_source_report():
    p = ship_design.initialize(analytic_project(), source())['project']
    run = analysis.compute_project(p, p['ship_design']['condition_id'], {'stages': ['ship_design']})
    stage = run['stages']['ship_design']
    assert stage['status'] == 'partial'
    assert stage['data']['ledger']['needs_binding']
    assert stage['data']['balance']['selected_mass_t'] is None
    assert stage['data']['ledger']['roles']['guns']['selected_mass_t'] is None
    assert stage['data']['source_result']['status'] == 'available'
    assert exports.serialize_report(run, 'txt') == stage['data']['report']['text']


def test_declared_ledger_does_not_bypass_native_field_validation():
    p = ship_design.initialize(project_io.new_project('Validation'), source())['project']
    for binding in p['ship_design']['mass_bindings'].values():
        binding['mode'] = 'declared'
    for group in p['weight_groups']:
        for item in group['items']:
            item.pop('design_mass', None)
    p['ship_design']['parameters']['gun1_calibre'] = True
    assert any(d['severity'] == 'error' for d in project_io.validate_project(p))


def test_manually_chosen_item_prefix_does_not_grant_design_ownership():
    p = analytic_project()
    p['weight_groups'][0]['items'] = [dict(id='sd-survey-mass', mass_t=400, x_m=0, y_m=0, kg_m=4,
        source='survey', estimate=False)]
    reply = ship_design.initialize(p, source())
    assert reply['preview']['ledger']['needs_binding'] == ['sd-survey-mass']
    assert not any(g.get('owner') == 'ship_design' for g in reply['project']['weight_groups'])


def test_removing_design_cannot_leave_silently_ignored_managed_mass():
    p = ship_design.initialize(project_io.new_project('Orphan guard'), source())['project']
    del p['ship_design']
    assert any(d['severity'] == 'error' for d in project_io.validate_project(p))


def test_clearing_design_dimension_clears_its_shared_projection():
    p = ship_design.initialize(project_io.new_project('Unknown dimension'), source())['project']
    replacement = source()
    replacement['parameters']['beam_moulded'] = None
    reply = ship_design.initialize(p, replacement)
    assert reply['project']['ship_design']['parameters']['beam_moulded'] is None
    assert reply['project']['hull']['beam_m'] is None


def test_declared_bindings_must_name_existing_ledger_items():
    p = ship_design.initialize(project_io.new_project('Missing target'), source())['project']
    p['ship_design']['mass_bindings']['deck'] = {'mode': 'declared', 'item_ids': ['missing']}
    for group in p['weight_groups']:
        for item in group['items']:
            if item['id'] == 'sd-deck':
                item.pop('design_mass')
    assert any('binding_item_unknown' in d['code'] for d in project_io.validate_project(p))


def test_replacing_source_preserves_explicit_manual_mass_adoption():
    p = ship_design.initialize(project_io.new_project('Manual replacement'), source())['project']
    p = ship_design.preview(p, {'kind': 'bind_mass', 'role': 'deck', 'item_ids': ['sd-deck'],
                                'mode': 'declared', 'mass_t': 42})['project']
    updated = source()
    updated['parameters']['armour_belt_main_thickness'] += 1
    reply = ship_design.initialize(p, updated)
    assert reply['project']['ship_design']['mass_bindings']['deck']['mode'] == 'declared'
    state = loading.resolve_loading(reply['project'], reply['project']['ship_design']['condition_id'])
    assert next(i for i in state['effective_items'] if i['id'] == 'sd-deck')['mass_t'] == 42
