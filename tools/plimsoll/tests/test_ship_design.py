# -*- coding: utf-8 -*-
"""Focused tests for the native ship-design module and its source adapter.

Covers the adapter/known readings, initialize/preview/compute reply authority and
shape, the shared hull/ledger projection, the source edit path updating owned rows
once, the strict validate boundary, and the bind_mass/set_declared_mass commands.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from plimsoll import project_io, ship_design, ship_design_mass

FIXTURE = Path(__file__).parent / 'fixtures' / 'sps3b3-synthetic.json'


def source():
    return json.loads(FIXTURE.read_text(encoding='utf-8-sig'))


def initialized():
    return ship_design.initialize(project_io.new_project('Native design'), source())['project']


def auto_group(project):
    return next(g for g in project['weight_groups']
                if g['id'] == ship_design_mass.AUTO_GROUP_ID)


def design_mass_of(project, item_id):
    item = next(i for g in project['weight_groups'] for i in g['items']
                if i['id'] == item_id)
    return item['design_mass']['mass_t']


def error_codes(diagnostics):
    return [d['code'] for d in diagnostics if d.get('severity', 'error') == 'error']


# ------------------------------------------------------------------ adapter

def test_from_source_builds_the_native_schema_and_round_trips_the_source_view():
    native = ship_design.from_source(source())
    assert native['schema'] == ship_design.SCHEMA
    assert native['condition_id'] == 'design-normal'
    view = ship_design.to_source(native)
    assert view['schema'] == ship_design.SOURCE_SCHEMA
    expected = ship_design.from_source(source())
    assert view['parameters'] == expected['parameters']
    assert view['editing'] == expected['editing']


def test_source_adapter_reproduces_the_known_readings_and_projection():
    native = ship_design.from_source(source())
    result = ship_design.compute({'ship_design': native})
    assert result['status'] == 'available'
    assert result['hull']['draughtDeep'] == result['performance']['draughtDeep']
    expected = {'draughtDeep': 28.74623, 'blockDeep': .5605253, 'concentration': .9457416,
                'strengthComp': 1.48599, 'flotation': 28596.51, 'damageTorp': 3.37437558}
    for key, value in expected.items():
        assert result['performance'][key] == pytest.approx(value, rel=1e-5)
    assert result['hull_projection']['draught_deep_m'] == pytest.approx(
        28.74623 * 0.3048, rel=1e-5)


def test_from_source_rejects_a_non_source_declaration():
    with pytest.raises(ship_design.ShipDesignError):
        ship_design.from_source({'schema': 'not-a-source'})


# --------------------------------------------------------------- initialize

def test_initialize_upgrades_a_legacy_design_in_the_draft_only():
    project = project_io.new_project('Legacy')
    project['sps_3b3_design'] = source()
    snapshot = copy.deepcopy(project)
    reply = ship_design.initialize(project)
    assert 'sps_3b3_design' not in reply['project']
    assert reply['project']['ship_design']['schema'] == ship_design.SCHEMA
    assert project == snapshot


def test_initialize_refuses_a_dual_declaration():
    project = project_io.new_project('Dual')
    project['sps_3b3_design'] = source()
    project['ship_design'] = ship_design.from_source(source())
    reply = ship_design.initialize(project)
    assert 'ship_design.dual_declaration' in error_codes(reply['diagnostics'])
    assert reply['status'] == 'partial'


def test_initialize_never_makes_a_derived_condition_the_design_owner():
    project = project_io.new_project('Derived')
    project['loading_conditions'] = [
        {'id': 'design-normal', 'label': 'Study', 'overrides': {},
         'definition': {'kind': 'x'}}]
    reply = ship_design.initialize(project, source())
    assert 'ship_design.condition_derived' in error_codes(reply['diagnostics'])
    owner = reply['project']['ship_design']['condition_id']
    condition = next(c for c in reply['project']['loading_conditions'] if c['id'] == owner)
    assert 'definition' not in condition
    assert owner != 'design-normal'


# ------------------------------------------------------------- reply shape

def test_reply_carries_the_source_view_and_the_authoritative_native_project():
    reply = ship_design.initialize(project_io.new_project('Shape'), source())
    assert {'project', 'design', 'preview', 'status', 'diagnostics'} <= set(reply)
    assert reply['design']['schema'] == ship_design.SOURCE_SCHEMA
    assert reply['project']['ship_design']['schema'] == ship_design.SCHEMA
    assert reply['project']['ship_design'] is not reply['design']


def test_preview_result_has_the_native_schema_and_lifted_source_sections():
    reply = ship_design.initialize(project_io.new_project('Preview'), source())
    preview = reply['preview']
    assert preview['schema'] == ship_design.RESULT_SCHEMA
    for key in ('hull', 'freeboard', 'guns', 'auxiliary', 'armour', 'engine',
                'performance', 'review'):
        assert preview.get(key) is not None, key
    assert preview['report'] is not None
    assert preview['ledger']['schema'] == ship_design_mass.LEDGER_SCHEMA
    assert preview['balance']['selected_mass_t'] is not None
    assert preview['balance']['basis_condition_id'] == \
        reply['project']['ship_design']['condition_id']


def test_initialized_ledger_closes_to_the_normal_displacement():
    reply = ship_design.initialize(project_io.new_project('Closure'), source())
    ledger = reply['preview']['ledger']
    assert ledger['complete'] is True
    assert ledger['needs_binding'] == []
    assert ledger['selected_mass_t'] == pytest.approx(ledger['target_displacement_t'],
                                                      rel=1e-6)
    assert ledger['estimated_mass_t'] == pytest.approx(ledger['target_displacement_t'],
                                                       rel=1e-6)


# ------------------------------------------------------------ source edits

def test_calibre_edit_updates_the_owned_row_once():
    project = initialized()
    before_count = len(auto_group(project)['items'])
    before = design_mass_of(project, 'sd-guns')
    snapshot = copy.deepcopy(project)
    reply = ship_design.preview(project, {'kind': 'set_parameter', 'name': 'gun1_calibre',
                                          'value': 8})
    assert len(auto_group(reply['project'])['items']) == before_count
    after = design_mass_of(reply['project'], 'sd-guns')
    assert after != before
    assert after == pytest.approx(
        ship_design_mass.estimate(reply['preview']['source_result'])['guns'])
    assert project == snapshot
    assert error_codes(ship_design.validate(reply['project'])) == []


def test_armour_edit_updates_the_owned_row_once():
    project = initialized()
    before_count = len(auto_group(project)['items'])
    before = design_mass_of(project, 'sd-belt_main')
    reply = ship_design.preview(project, {'kind': 'set_parameter',
                                          'name': 'armour_belt_main_thickness', 'value': 8})
    assert len(auto_group(reply['project'])['items']) == before_count
    after = design_mass_of(reply['project'], 'sd-belt_main')
    assert after != before
    assert after == pytest.approx(
        ship_design_mass.estimate(reply['preview']['source_result'])['belt_main'])
    assert error_codes(ship_design.validate(reply['project'])) == []


def test_edit_only_diagnostics_are_preserved_and_mirrored_in_the_result():
    project = initialized()
    reply = ship_design.preview(project, {'kind': 'set_parameter', 'name': 'gun1_barrels',
                                          'value': True})
    codes = [d['code'] for d in reply['diagnostics']]
    assert 'invalid_parameter_type' in codes
    assert [d['code'] for d in reply['preview']['diagnostics']] == codes
    assert reply['status'] == reply['preview']['status']


# --------------------------------------------------------------- compute

def test_compute_never_lets_a_requested_condition_impersonate_the_basis():
    project = initialized()
    project['loading_conditions'].append({'id': 'study', 'label': 'Study', 'overrides': {}})
    result = ship_design.compute(project, 'study')
    assert result['condition_id'] == 'study'
    assert result['basis_condition_id'] == project['ship_design']['condition_id']
    assert result['ledger']['condition_id'] == project['ship_design']['condition_id']


def test_compute_on_a_project_without_a_native_design_is_unavailable():
    result = ship_design.compute(project_io.new_project('Empty'))
    assert result['status'] == 'unavailable'
    assert result['schema'] == ship_design.RESULT_SCHEMA
    assert result['ledger'] is None
    assert 'ship_design.missing' in error_codes(result['diagnostics'])


def test_no_surface_mutates_the_input_project():
    project = initialized()
    snapshot = copy.deepcopy(project)
    ship_design.compute(project)
    ship_design.preview(project, {'kind': 'set_parameter', 'name': 'gun1_calibre', 'value': 8})
    ship_design.validate(project)
    assert project == snapshot


# --------------------------------------------------------------- validate

def test_validate_accepts_a_freshly_initialized_project():
    assert ship_design.validate(initialized()) == []


def test_validate_flags_a_legacy_only_project_as_a_non_blocking_warning():
    project = project_io.new_project('Legacy only')
    project['sps_3b3_design'] = source()
    diagnostics = ship_design.validate(project)
    assert [d['code'] for d in diagnostics] == ['ship_design.legacy_active']
    assert diagnostics[0]['severity'] == 'warning'


def test_validate_rejects_a_null_or_malformed_native_declaration():
    assert 'ship_design.schema_invalid' in error_codes(
        ship_design.validate({'ship_design': None}))
    assert 'ship_design.schema_invalid' in error_codes(
        ship_design.validate({'ship_design': {'schema': 'wrong'}}))


def test_validate_rejects_a_hull_projection_conflict_and_a_missing_key():
    project = initialized()
    conflicting = copy.deepcopy(project)
    conflicting['hull']['lwl_m'] = 1.0
    assert 'ship_design.projection_conflict' in error_codes(
        ship_design.validate(conflicting))
    missing = copy.deepcopy(project)
    del missing['hull']['beam_m']
    assert 'ship_design.projection_missing' in error_codes(ship_design.validate(missing))


def test_validate_rejects_a_missing_owner_condition():
    project = initialized()
    project['loading_conditions'] = []
    assert 'ship_design.condition_missing' in error_codes(ship_design.validate(project))


def test_validate_rejects_a_removed_or_altered_managed_overlay():
    project = initialized()
    removed = copy.deepcopy(project)
    item = next(i for g in removed['weight_groups'] for i in g['items']
                if i['id'] == 'sd-guns')
    del item['design_mass']
    assert 'ship_design.estimated_overlay_missing' in error_codes(
        ship_design.validate(removed))
    altered = copy.deepcopy(project)
    item = next(i for g in altered['weight_groups'] for i in g['items']
                if i['id'] == 'sd-guns')
    item['design_mass']['mass_t'] = 1.0
    assert 'ship_design.estimated_mass_altered' in error_codes(
        ship_design.validate(altered))


def test_validate_rejects_an_unbound_managed_overlay():
    project = initialized()
    item = next(i for g in project['weight_groups'] for i in g['items']
                if i['id'] == 'sd-guns')
    project['ship_design']['mass_bindings'].pop('guns')
    assert 'ship_design.unbound_overlay' in error_codes(ship_design.validate(project))


def test_validate_rejects_an_aggregate_ownership_conflict_only_when_real():
    project = initialized()
    items = project['weight_groups'][0]['items']
    items.append({'id': 'turret', 'mass_t': 10.0, 'x_m': None, 'y_m': None, 'kg_m': None,
                  'source': 'a', 'estimate': False})
    items.append({'id': 'mount', 'mass_t': 20.0, 'x_m': None, 'y_m': None, 'kg_m': None,
                  'source': 'b', 'estimate': False, 'includes': ['turret']})
    assert 'ship_design.aggregate_conflict' in error_codes(ship_design.validate(project))
    # A zero-mass placeholder claiming the same token is not a real conflict.
    items.append({'id': 'vacant', 'mass_t': 0.0, 'x_m': None, 'y_m': None, 'kg_m': None,
                  'source': 'c', 'estimate': False, 'includes': ['turret']})
    codes = error_codes(ship_design.validate(project))
    assert codes.count('ship_design.aggregate_conflict') == 1


# --------------------------------------------------------------- commands

def test_bind_mass_refuses_an_unknown_item_and_a_duplicate_owner():
    project = initialized()
    unknown = ship_design.preview(project, {'kind': 'bind_mass', 'role': 'guns',
                                            'mode': 'declared', 'item_ids': ['nope']})
    assert 'ship_design.binding_item_unknown' in error_codes(unknown['diagnostics'])
    duplicate = ship_design.preview(
        project, {'kind': 'bind_mass', 'role': 'guns', 'mode': 'declared',
                  'item_ids': ['sd-deck']})
    assert 'ship_design.binding_duplicate_item' in error_codes(duplicate['diagnostics'])


def test_bind_mass_estimated_permits_exactly_one_target():
    project = initialized()
    reply = ship_design.preview(project, {'kind': 'bind_mass', 'role': 'guns',
                                          'mode': 'estimated',
                                          'item_ids': ['sd-guns', 'sd-mounts']})
    assert 'ship_design.binding_estimated_multiple' in error_codes(reply['diagnostics'])


def test_switching_estimated_to_declared_retains_the_effective_mass():
    project = initialized()
    before = design_mass_of(project, 'sd-deck')
    reply = ship_design.preview(project, {'kind': 'bind_mass', 'role': 'deck',
                                          'mode': 'declared', 'item_ids': ['sd-deck']})
    condition = next(c for c in reply['project']['loading_conditions']
                     if c['id'] == reply['project']['ship_design']['condition_id'])
    assert condition['overrides']['sd-deck']['mass_t'] == pytest.approx(before)


def test_set_declared_mass_requires_an_explicit_declared_binding_first():
    project = initialized()
    refused = ship_design.preview(project, {'kind': 'set_declared_mass',
                                            'item_id': 'sd-guns', 'value': 5.0})
    assert 'ship_design.declared_requires_binding' in error_codes(refused['diagnostics'])


def test_preview_commandless_design_adopts_the_authoritative_source_view():
    project = initialized()
    view = ship_design.to_source(project['ship_design'])
    view['source'] = 'queue-replace source'
    view['notes'] = 'queue-replace notes'
    condition_id = project['ship_design']['condition_id']
    bindings = copy.deepcopy(project['ship_design']['mass_bindings'])
    owner = next(c for c in project['loading_conditions'] if c['id'] == condition_id)
    owner['overrides']['sd-deck'] = {'mass_t': 123.0}
    snapshot = copy.deepcopy(project)
    reply = ship_design.preview(project, design=view)
    assert reply['design']['source'] == 'queue-replace source'
    assert reply['design']['notes'] == 'queue-replace notes'
    assert reply['preview']['design']['source'] == 'queue-replace source'
    # The native basis condition, its bindings and manual overrides are preserved.
    assert reply['project']['ship_design']['condition_id'] == condition_id
    assert reply['project']['ship_design']['mass_bindings'] == bindings
    owner_after = next(c for c in reply['project']['loading_conditions']
                       if c['id'] == condition_id)
    assert owner_after['overrides']['sd-deck'] == {'mass_t': 123.0}
    assert project == snapshot


def test_preview_rejects_a_dual_declaration_without_a_mixed_success():
    project = initialized()
    project['sps_3b3_design'] = source()
    reply = ship_design.preview(project)
    assert 'ship_design.dual_declaration' in error_codes(reply['diagnostics'])
    assert reply['status'] == 'partial'
    assert reply['preview'] is None
    assert 'sps_3b3_design' in reply['project']


def test_preview_rejects_an_unusable_supplied_source_view_without_losing_data():
    project = initialized()
    before = copy.deepcopy(project['ship_design'])
    reply = ship_design.preview(project, design={'schema': 'not-a-source', 'source': 'x'})
    assert error_codes(reply['diagnostics'])
    assert reply['project']['ship_design'] == before


def test_manual_declared_mass_is_scoped_to_the_owner_condition_only():
    project = initialized()
    project['loading_conditions'].append({'id': 'light', 'label': 'Light', 'overrides': {}})
    reply = ship_design.preview(project, {'kind': 'bind_mass', 'role': 'guns',
                                          'mode': 'declared', 'item_ids': ['sd-guns']})
    reply = ship_design.preview(reply['project'], {'kind': 'set_declared_mass',
                                                   'item_id': 'sd-guns', 'value': 42.0})
    owner = next(c for c in reply['project']['loading_conditions']
                 if c['id'] == reply['project']['ship_design']['condition_id'])
    light = next(c for c in reply['project']['loading_conditions'] if c['id'] == 'light')
    assert owner['overrides']['sd-guns']['mass_t'] == 42.0
    assert owner['override_provenance']['sd-guns']['mass_t']['source']['owner'] == \
        'ship_design'
    assert light['overrides'] == {}
    assert 'design_mass' not in next(
        i for g in reply['project']['weight_groups'] for i in g['items']
        if i['id'] == 'sd-guns')
    assert error_codes(ship_design.validate(reply['project'])) == []
