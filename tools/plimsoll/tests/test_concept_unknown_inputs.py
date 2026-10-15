"""Independent contract checks written by the accepting reviewer."""
import copy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from plimsoll import analysis, project_io


def project():
    return json.loads((ROOT / 'tools/plimsoll/cases/projects/concept_cruiser.project.json').read_text(encoding='utf-8-sig'))


def run(p):
    return analysis.compute_project(p, 'normal', {'stages': ['systems', 'design_balance']})


def models(result):
    data = result['stages']['systems']['data']
    assert data is not None, result['stages']['systems']
    return {m['id']: m for row in data['systems'].values() for m in row['mass_models']}


def proposals(result):
    return result['stages']['systems']['data']['update_proposals']


def item(p, key):
    return next(i for g in p['weight_groups'] for i in g['items'] if i['id'] == key)


INPUTS = [
    ('target_displacement_t',), ('hull_year',), ('freeboard_m',), ('stern',), ('screws',),
    *[('batteries', 0, k) for k in ('calibre_mm', 'barrel_calibres', 'year', 'gun_type',
        'mount_type', 'mount_count', 'barrels_per_mount', 'shared_cradle', 'rounds_per_gun')],
    *[('machinery', k) for k in ('year', 'kind', 'coal_pct', 'speed_kn')],
    ('fuel', 'range_nm'), ('fuel', 'cruise_speed_kn'),
    *[('balance', k) for k in ('steadiness', 'space_hull_fraction', 'space_deck_fraction',
        'super_factor', 'super_factor_long', 'concentration', 'strength_target')],
]


@pytest.mark.parametrize('path', INPUTS)
@pytest.mark.parametrize('missing', [False, True])
def test_missing_computational_input_is_editable_and_diagnosed(path, missing):
    p = project()
    cursor = p['concept_design']
    for key in path[:-1]:
        cursor = cursor[key]
    if missing:
        del cursor[path[-1]]
    else:
        cursor[path[-1]] = None
    normalized = project_io.normalize_project(p)
    r = run(normalized)
    for stage in ('systems', 'design_balance'):
        assert r['stages'][stage]['status'] != 'failed', r['stages'][stage]
    ds = r['stages']['systems'].get('diagnostics', []) + r['stages']['design_balance'].get('diagnostics', [])
    assert ds, (path, r)
    if path[0] in ('target_displacement_t', 'hull_year', 'freeboard_m', 'stern', 'screws', 'balance', 'fuel', 'machinery'):
        assert 'concept.main.guns' in models(r), 'Independent gun estimate must survive unrelated missing inputs'


def test_gun_estimate_does_not_require_hull_geometry_inputs():
    p = project()
    p['hull']['block_coeff'] = 0.1
    r = run(p)
    assert 'concept.main.guns' in models(r)


def test_empty_role_membership_is_zero_without_dummy_ledger_items():
    p = project()
    p['weight_groups'][0]['items'] = [i for i in p['weight_groups'][0]['items'] if i['id'] != 'misc.void']
    p['systems']['weapons']['misc_weight']['weight_item_ids'].remove('misc.void')
    del p['concept_design']['balance']['roles']['misc.void']
    r = run(p)
    assert 'concept.machinery' in models(r)
    assert r['stages']['design_balance']['data']['roles']['misc_void'] == 0


@pytest.mark.parametrize('mass', [None, 10.0])
def test_unclassified_mass_prevents_dependent_structure_and_engine(mass):
    p = project()
    p['weight_groups'][0]['items'].append({'id': 'unmapped', 'mass_t': mass,
        'x_m': 1.0, 'y_m': 0.0, 'kg_m': 1.0, 'estimate': True, 'source': 'test'})
    r = run(p)
    m = models(r)
    assert 'concept.main.guns' in m
    assert 'concept.structure' not in m
    assert 'concept.machinery' not in m
    d = r['stages']['design_balance']['data']
    assert 'unmapped' in d['unclassified_item_ids']
    assert not d.get('strength')
    assert d['values'].get('remaining_structural_budget_long_tons') is None


@pytest.mark.parametrize('key', ['weapons.other', 'armour.belt_main'])
def test_unknown_fixed_mass_blocks_structure_requirement(key):
    p = project()
    item(p, key)['mass_t'] = None
    r = run(p)
    assert 'concept.structure' not in models(r)


def test_unknown_adjustable_structure_keeps_demand_and_budget():
    p = project()
    item(p, 'hull.structure')['mass_t'] = None
    r = run(p)
    assert r['stages']['design_balance']['status'] != 'failed'
    d = r['stages']['design_balance']['data']
    assert d['values']['remaining_structural_budget_long_tons'] is not None
    assert d['structure']['current_structure_long_tons'] is None
    assert d['structure']['required_adjustable_long_tons'] > 0
    assert not d.get('strength')
    q = next(q for q in proposals(r) if q['source_model_id'] == 'concept.structure')
    accepted = analysis.apply_mass_proposals(p, 'normal', [q], current_request=r['request'])
    assert accepted['changes'][0]['old_mass_t'] is None
    project_io.normalize_project(accepted['project'])


def test_target_strength_is_used_in_warning():
    p = project()
    p['concept_design']['balance']['strength_target'] = 2.0
    r = run(p)
    demand = r['stages']['design_balance']['data']['structure']['required_total_long_tons']
    item(p, 'hull.structure')['mass_t'] = demand * 1.0160469088 * 0.75
    d = run(p)['stages']['design_balance']['data']
    assert d['strength']['composite'] == pytest.approx(1.5)
    codes = [w['code'] for w in d.get('design_warnings', [])]
    assert 'design_balance.structure_shortfall' in codes
    assert 'design_balance.structure_sufficient' not in codes


def test_roles_must_match_component_target_semantics():
    p = project()
    p['concept_design']['balance']['roles']['weapons.guns'] = 'other'
    with pytest.raises(project_io.ProjectValidationError):
        project_io.normalize_project(p)


def test_no_false_crew_loss_when_structure_is_unknown():
    p = project()
    item(p, 'hull.structure')['mass_t'] = None
    d = run(p)['stages']['design_balance']['data']
    assert d is not None
    assert d.get('crew', {}).get('crew_min', 0) > 0


def test_bulkhead_beam_missing_hides_dependent_space_instead_of_faking_unrestricted_room():
    p = project()
    p['concept_design']['balance']['bulkhead_beam_m'] = None
    d = run(p)['stages']['design_balance']['data']
    assert d['status'] == 'unavailable'
    assert not d.get('space')
    assert d['strength']['composite'] > 0


def test_capacity_display_survives_systems_result_without_becoming_a_second_mass():
    r = run(project())
    fuel = models(r)['concept.fuel']
    assert fuel['capacity_estimate_t'] == pytest.approx(fuel['calculated_mass_t'] * 1.8)
    q = next(q for q in proposals(r) if q['source_model_id'] == 'concept.fuel')
    assert q['proposed_mass_t'] == fuel['calculated_mass_t']
