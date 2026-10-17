# -*- coding: utf-8 -*-
"""Focused tests for the native ship-design mass ledger bridge.

Covers the recovered source split (H0 structure, one-counted load, separate
gun/mount/armour roles), unknown/negative propagation, the concept-role mapping
and mixed-aggregate conservatism, and the reconcile contract (managed group, no
coordinates, declared preservation, condition-scoped overlay, no input mutation).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from plimsoll import project_io, ship_design_mass, sps_compat

FIXTURE = Path(__file__).parent / 'fixtures' / 'sps3b3-synthetic.json'
LT = ship_design_mass.LONG_TON_T


def source_design():
    return json.loads(FIXTURE.read_text(encoding='utf-8-sig'))


def source_result():
    return sps_compat.compute(source_design())


def reading_source():
    """A minimal object shaped like ``sps_compat.compute`` output."""
    return {
        'status': 'available',
        'diagnostics': [],
        'hull': {'displacement': 1000.0},
        'guns': {'gunWeight': 10.0, 'mountWeight': 20.0, 'armWeight': 5.0, 'magazine': 8.0},
        'auxiliary': {'weight': 30.0, 'miscWeightVital': 1.0, 'miscWeightHull': 2.0,
                      'miscWeightDeck': 3.0, 'miscWeightAbove': 4.0, 'voidWeight': 5.0},
        'armour': {'weightBeltMain': 11.0, 'weightBeltEnds': 12.0, 'weightBeltUpper': 13.0,
                   'weightBulkhead': 14.0, 'weightBulge': 15.0, 'weightDeck': 16.0,
                   'weightConning': 17.0},
        'engine': {'hullWeightDisplayed': 100.0, 'hullWeight': 999.0, 'engineWeight': 50.0,
                   'loadWeight': 90.0, 'bunker': 25.0},
    }


def project_with(items, conditions=None):
    project = project_io.new_project('Mass fixture')
    project['weight_groups'] = [{'id': 'g', 'label': 'G', 'required': True, 'items': items}]
    project['loading_conditions'] = conditions or [
        {'id': 'design-normal', 'label': 'Design', 'overrides': {}}]
    return project


def manual_item(item_id, mass_t):
    return {'id': item_id, 'mass_t': mass_t, 'x_m': None, 'y_m': None, 'kg_m': None,
            'source': 'manual', 'estimate': False}


# ------------------------------------------------------------------ estimate

def test_structure_is_the_h0_residual_not_the_h1_strength_hull():
    masses = ship_design_mass.estimate(reading_source())
    assert masses['structure'] == pytest.approx(100.0 * LT)
    assert masses['structure'] != pytest.approx(999.0 * LT)


def test_load_is_counted_once_as_stores_after_bunker_and_magazine():
    masses = ship_design_mass.estimate(reading_source())
    assert masses['fuel'] == pytest.approx(25.0 * LT)
    assert masses['ammunition'] == pytest.approx(8.0 * LT)
    assert masses['stores'] == pytest.approx((90.0 - 25.0 - 8.0) * LT)


def test_guns_mounts_and_gun_armour_stay_separate_roles():
    masses = ship_design_mass.estimate(reading_source())
    assert masses['guns'] == pytest.approx(10.0 * LT)
    assert masses['mounts'] == pytest.approx(20.0 * LT)
    assert masses['gun_armour'] == pytest.approx(5.0 * LT)


def test_fixed_armour_regions_and_miscellaneous_roles_read_real_fields():
    masses = ship_design_mass.estimate(reading_source())
    assert masses['belt_main'] == pytest.approx(11.0 * LT)
    assert masses['belt_ends'] == pytest.approx(12.0 * LT)
    assert masses['belt_upper'] == pytest.approx(13.0 * LT)
    assert masses['bulkhead'] == pytest.approx(14.0 * LT)
    assert masses['bulge'] == pytest.approx(15.0 * LT)
    assert masses['deck'] == pytest.approx(16.0 * LT)
    assert masses['conning'] == pytest.approx(17.0 * LT)
    assert masses['misc_vital'] == pytest.approx(1.0 * LT)
    assert masses['misc_void'] == pytest.approx(5.0 * LT)


def test_other_role_has_no_source_estimate_and_is_not_inferred_from_legacy_other():
    masses = ship_design_mass.estimate(reading_source())
    assert masses['other'] == 0.0
    assert 'other' not in ship_design_mass.CONCEPT_ROLE_MAP
    assert ship_design_mass.CONCEPT_ROLE_MAP.get('other') is None


def test_negative_residual_stays_unknown_and_never_becomes_a_negative_mass():
    result = reading_source()
    result['engine']['hullWeightDisplayed'] = -3.0
    detail = ship_design_mass.estimate_detail(result)
    assert detail['masses']['structure'] is None
    assert any(d['code'] == 'ship_design.mass_negative' for d in detail['diagnostics'])


def test_unknown_reading_propagates_none_rather_than_zero():
    result = reading_source()
    result['guns'] = {key: value for key, value in result['guns'].items()
                      if key != 'gunWeight'}
    detail = ship_design_mass.estimate_detail(result)
    assert detail['masses']['guns'] is None
    assert any(d['code'] == 'ship_design.mass_unknown' for d in detail['diagnostics'])


def test_synthetic_empty_ledger_metric_sum_matches_the_deep_displacement():
    detail = ship_design_mass.estimate_detail(source_result())
    total = sum(value for value in detail['masses'].values() if value is not None)
    assert total == pytest.approx(detail['displacement_t'], rel=1e-6)
    assert detail['displacement_t'] > 0


# --------------------------------------------------------------- infer_bindings

def test_infer_bindings_uses_only_explicit_known_concept_roles():
    project = project_with([manual_item('hull', 1.0), manual_item('mystery', 2.0)])
    project['concept_design'] = {'balance': {'roles': {'hull': 'structure',
                                                       'mystery': 'other'}}}
    bindings, pending = ship_design_mass.infer_bindings(project)
    assert bindings == {'structure': {'item_ids': ['hull'], 'mode': 'declared'}}
    assert pending == ['mystery']


def test_infer_bindings_leaves_a_mixed_aggregate_pending():
    item = manual_item('whole-battery', 400.0)
    item['includes'] = ['guns', 'mounts', 'gun_armour']
    project = project_with([item])
    project['concept_design'] = {'balance': {'roles': {'whole-battery': 'mounts'}}}
    bindings, pending = ship_design_mass.infer_bindings(project)
    assert pending == ['whole-battery']
    assert 'mounts' not in bindings


def test_infer_bindings_leaves_an_unknown_token_aggregate_pending():
    item = manual_item('armour-total', 90.0)
    item['includes'] = ['armour.main-turret.rotating']
    project = project_with([item])
    project['concept_design'] = {'balance': {'roles': {'armour-total': 'gun_armour'}}}
    bindings, pending = ship_design_mass.infer_bindings(project)
    assert pending == ['armour-total']
    assert bindings == {}


# ------------------------------------------------------------------- reconcile

def test_reconcile_empty_ledger_creates_a_tagged_group_without_any_cg():
    project = project_with([])
    out = ship_design_mass.reconcile(project, source_result(), 'design-normal', None)
    group = next(g for g in out['project']['weight_groups']
                 if g['id'] == ship_design_mass.AUTO_GROUP_ID)
    assert group['owner'] == 'ship_design'
    assert group['required'] is False
    assert {item['id'] for item in group['items']} == \
        {ship_design_mass.MANAGED_ITEM_PREFIX + role for role in ship_design_mass.SOURCE_ROLES}
    for item in group['items']:
        assert item['x_m'] is None and item['y_m'] is None and item['kg_m'] is None
        assert item['design_mass']['owner'] == 'ship_design'
        assert item['design_mass']['condition_id'] == 'design-normal'
    summary = out['summary']
    assert summary['complete'] is True
    assert summary['needs_binding'] == []
    assert summary['selected_mass_t'] == pytest.approx(summary['target_displacement_t'],
                                                       rel=1e-6)


def test_reconcile_needs_binding_blocks_managed_additions_and_preserves_manual():
    project = project_with([manual_item('manual-row', 12.0)])
    out = ship_design_mass.reconcile(project, source_result(), 'design-normal', None)
    assert out['summary']['needs_binding'] == ['manual-row']
    assert all(g['id'] != ship_design_mass.AUTO_GROUP_ID
               for g in out['project']['weight_groups'])
    item = out['project']['weight_groups'][0]['items'][0]
    assert item['mass_t'] == 12.0
    assert 'design_mass' not in item


def test_reconcile_explicitly_bound_other_completes_and_keeps_the_manual_base():
    project = project_with([manual_item('payload', 40.0)])
    bindings = {'other': {'item_ids': ['payload'], 'mode': 'declared'}}
    out = ship_design_mass.reconcile(project, source_result(), 'design-normal', bindings)
    assert out['summary']['needs_binding'] == []
    item = out['project']['weight_groups'][0]['items'][0]
    assert item['mass_t'] == 40.0
    assert 'design_mass' not in item
    assert out['summary']['roles']['other']['selected_mass_t'] == 40.0


def test_reconcile_estimated_overlay_takes_precedence_over_an_ordinary_override():
    project = project_with([manual_item('target', 10.0)],
                           [{'id': 'design-normal', 'label': 'Design',
                             'overrides': {'target': {'mass_t': 7.0}}}])
    out = ship_design_mass.reconcile(
        project, source_result(), 'design-normal',
        {'structure': {'item_ids': ['target'], 'mode': 'estimated'}})
    expected = ship_design_mass.estimate(source_result())['structure']
    assert out['summary']['roles']['structure']['selected_mass_t'] == pytest.approx(expected)
    # The ordinary override is untouched; only the scoped overlay is authoritative.
    condition = out['project']['loading_conditions'][0]
    assert condition['overrides']['target']['mass_t'] == 7.0
    assert out['summary']['roles']['structure']['item_ids'] == ['target']


def test_reconcile_does_not_mutate_the_input_project():
    project = project_with([manual_item('manual-row', 12.0)])
    snapshot = copy.deepcopy(project)
    ship_design_mass.reconcile(project, source_result(), 'design-normal', None)
    assert project == snapshot


def test_reconcile_rejects_a_duplicate_binding_and_blocks_managed_additions():
    project = project_with([manual_item('a', 1.0)])
    bindings = {'guns': {'item_ids': ['a'], 'mode': 'declared'},
                'mounts': {'item_ids': ['a'], 'mode': 'declared'}}
    out = ship_design_mass.reconcile(project, source_result(), 'design-normal', bindings)
    assert any(d['code'] == 'ship_design.binding_duplicate_item'
               for d in out['diagnostics'])
    assert all(g['id'] != ship_design_mass.AUTO_GROUP_ID
               for g in out['project']['weight_groups'])


def test_reconcile_clears_a_stale_managed_overlay_when_a_role_becomes_declared():
    project = project_with([])
    first = ship_design_mass.reconcile(project, source_result(), 'design-normal', None)
    project = first['project']
    # Switch the deck role to a declared manual row; the auto row must lose its
    # overlay rather than linger as an unbound, hand-editable overlay.
    manual = manual_item('deck-manual', 100.0)
    project['weight_groups'][0]['items'].append(manual)
    out = ship_design_mass.reconcile(
        project, source_result(), 'design-normal',
        {'deck': {'item_ids': ['deck-manual'], 'mode': 'declared'}})
    auto = next(item for g in out['project']['weight_groups']
                if g['id'] == ship_design_mass.AUTO_GROUP_ID
                for item in g['items'] if item['id'] == 'sd-deck')
    assert 'design_mass' not in auto


def test_reconcile_unbound_formerly_managed_override_blocks_until_classified():
    project = ship_design_mass.reconcile(
        project_with([]), source_result(), 'design-normal', None)['project']
    original = ship_design_mass.estimate(source_result())['structure']
    # The structure role becomes a retained declared override on the auto row, then a
    # fresh manual row replaces it as the estimated structure target.
    auto = next(item for g in project['weight_groups']
                if g['id'] == ship_design_mass.AUTO_GROUP_ID
                for item in g['items'] if item['id'] == 'sd-structure')
    auto.pop('design_mass', None)
    project['loading_conditions'][0]['overrides']['sd-structure'] = {'mass_t': original}
    project['weight_groups'][0]['items'].append(manual_item('replacement', 0.0))

    pending = ship_design_mass.reconcile(
        project, source_result(), 'design-normal',
        {'structure': {'item_ids': ['replacement'], 'mode': 'estimated'}})
    summary = pending['summary']
    # The orphan still carries an effective basis mass the loading resolver counts, so
    # the native balance must stay pending rather than claim a contradicting total.
    assert 'sd-structure' in summary['needs_binding']
    assert summary['selected_mass_t'] is None
    assert summary['complete'] is False
    assert pending['project']['loading_conditions'][0]['overrides']['sd-structure']['mass_t'] \
        == pytest.approx(original)

    closed = ship_design_mass.reconcile(
        pending['project'], source_result(), 'design-normal',
        {'structure': {'item_ids': ['replacement'], 'mode': 'estimated'},
         'other': {'item_ids': ['sd-structure'], 'mode': 'declared'}})
    closed_summary = closed['summary']
    assert closed_summary['needs_binding'] == []
    assert closed_summary['complete'] is True
    assert closed_summary['roles']['other']['estimate_t'] == 0.0
    assert closed_summary['roles']['structure']['selected_mass_t'] == pytest.approx(original)
    assert closed_summary['roles']['other']['selected_mass_t'] == pytest.approx(original)
    # The orphan is counted exactly once, so the closed ledger adds it to the estimate.
    assert closed_summary['selected_mass_t'] == pytest.approx(
        closed_summary['estimated_mass_t'] + original)
    assert closed['project']['loading_conditions'][0]['overrides']['sd-structure']['mass_t'] \
        == pytest.approx(original)


def test_reconcile_unbound_managed_row_with_unknown_mass_still_blocks():
    project = ship_design_mass.reconcile(
        project_with([]), source_result(), 'design-normal', None)['project']
    item = next(item for g in project['weight_groups']
                if g['id'] == ship_design_mass.AUTO_GROUP_ID
                for item in g['items'] if item['id'] == 'sd-deck')
    item.pop('design_mass', None)
    project['loading_conditions'][0]['overrides']['sd-deck'] = {'mass_t': None}
    out = ship_design_mass.reconcile(project, source_result(), 'design-normal', None)
    assert 'sd-deck' in out['summary']['needs_binding']
    assert out['summary']['selected_mass_t'] is None
