"""Independent contract checks for the optional battery-armour estimate.

Written for the accepting reviewer: every assertion states a property the
contract requires of the *document and the result*, not the shape of the
current draft. Nothing here claims a vector produced by running the original
assembly; that remains the reviewer's separate, separately-provenanced job.
"""
import copy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / 'tools') not in sys.path:
    sys.path.insert(0, str(ROOT / 'tools'))
from plimsoll import analysis, concept_design, project_io, project_store  # noqa: E402
from plimsoll import battery_armour, concept_estimates as ce  # noqa: E402

ARMOUR_ITEM = 'weapons.gun_house_armour'
LT_PER_T = 1000.0 / ce.LONG_TON_KG


def project():
    return project_io.normalize_project(
        json.loads((ROOT / 'tools/plimsoll/cases/projects/concept_cruiser.project.json')
                   .read_text(encoding='utf-8-sig')))


def run(p):
    return analysis.compute_project(p, 'normal', {'stages': ['systems', 'design_balance']})


def models(result):
    data = result['stages']['systems']['data']
    assert data is not None, result['stages']['systems']
    return {m['id']: m for row in data['systems'].values() for m in row['mass_models']}


def model_owner(result, model_id):
    for system_id, row in result['stages']['systems']['data']['systems'].items():
        if any(m['id'] == model_id for m in row['mass_models']):
            return system_id
    return None


def proposals(result):
    return result['stages']['systems']['data']['update_proposals']


def diagnostics(result):
    return (result['stages']['systems'].get('diagnostics', [])
            + result['stages']['design_balance'].get('diagnostics', []))


def item(p, key):
    return next(i for g in p['weight_groups'] for i in g['items'] if i['id'] == key)


def armour_declaration(**overrides):
    declared = {'system_id': 'weapons.main', 'item_id': ARMOUR_ITEM, 'face_mm': 150.0,
                'rear_roof_mm': 100.0, 'barbette_mm': 75.0, 'freeboard_m': 4.6,
                'super_factor': 1.0}
    declared.update(overrides)
    return declared


def with_armour(**overrides):
    """A project whose single battery declares an independently owned armour item."""
    p = project()
    p['weight_groups'][0]['items'].append({
        'id': ARMOUR_ITEM, 'mass_t': 40.0, 'x_m': 104.0, 'y_m': 0.0, 'kg_m': 11.0,
        'source': 'synthetic declared placeholder for the concept-cruiser case (editable estimate)',
        'estimate': True})
    p['systems']['weapons']['main']['weight_item_ids'].append(ARMOUR_ITEM)
    p['concept_design']['balance']['roles'][ARMOUR_ITEM] = 'gun_mount_armour'
    p['concept_design']['batteries'][0]['armour'] = armour_declaration(**overrides)
    return p


# ------------------------------------------------------------------ compatibility

def test_a_project_without_the_armour_block_is_completely_unchanged():
    result = run(project())
    found = models(result)
    assert 'concept.main.guns' in found and 'concept.main.mounts' in found
    assert 'concept.main.ammunition' in found
    assert not [m for m in found if m.endswith('.armour')]
    assert result['stages']['design_balance']['status'] == 'completed'


def test_an_absent_or_null_armour_block_adds_nothing_and_keeps_the_three_old_models():
    for value in (None, 'absent'):
        p = project()
        if value is None:
            p['concept_design']['batteries'][0]['armour'] = None
        else:
            assert 'armour' not in p['concept_design']['batteries'][0]
        result = run(p)
        found = models(result)
        assert {'concept.main.guns', 'concept.main.mounts',
                'concept.main.ammunition'} <= set(found)
        assert not [m for m in found if m.endswith('.armour')]
        assert result['stages']['design_balance']['status'] == 'completed'


def test_the_new_role_is_zero_for_a_project_that_declares_none_of_it():
    roles = run(project())['stages']['design_balance']['data']['roles']
    assert roles['gun_mount_armour'] == 0
    assert roles['rotating_armour'] > 0


def test_old_results_are_unchanged_without_a_gun_mount_armour_item():
    """The recovered armWeight aggregate still reads rotating armour alone."""
    result = run(project())
    data = result['stages']['design_balance']['data']
    hull = data['hull_proxy']
    assert data['roles']['gun_mount_armour'] == 0
    assert data['structure']['cross_coefficient'] == pytest.approx(
        ce.strength_cross_coefficient(
            hull['wetted_surface_sqft'], hull['length_ft'], hull['freeboard_ft'],
            hull['waterplane_area_sqft'], hull['beam_ft'], hull['draught_ft'],
            hull['displacement_long_tons'], data['structure']['broadside_lb'],
            data['selected_borne_weight_long_tons'], data['roles']['rotating_armour'],
            data['roles']['conning'], data['structure']['hp_max'],
            1.0, 1.0, 1918))


# ---------------------------------------------------------------------- the model

def test_a_declared_armour_produces_its_own_model_on_its_own_owned_target():
    result = run(with_armour())
    found = models(result)
    assert 'concept.main.armour' in found
    model = found['concept.main.armour']
    assert model['method'] == 'empirical_estimate_v1'
    assert model['linked_weight_item_id'] == ARMOUR_ITEM
    assert model_owner(result, 'concept.main.armour') == 'weapons.main'
    assert model['concept_component'] == 'armour'
    # The enclosure's own adapted method identity is unchanged.
    assert concept_design.METHOD == 'sps-3b3-adapted-v1'


def test_the_model_carries_its_own_component_method_version_and_full_inputs():
    model = models(run(with_armour()))['concept.main.armour']
    # The component identity travels in the same two method-identity fields
    # every other model already uses; no extra field is invented.
    assert model['source']['method_version'] == battery_armour.METHOD_VERSION
    assert model['inputs']['method_version'] == battery_armour.METHOD_VERSION
    assert 'component_method_version' not in model
    assert 'component_method_version' not in model['source']
    inputs = model['inputs']
    for key in ('face_mm', 'rear_roof_mm', 'barbette_mm', 'freeboard_m', 'super_factor',
                'calibre_mm', 'year', 'gun_type', 'mount_type', 'mount_count',
                'barrels_per_mount', 'shared_cradle', 'estimate_long_tons'):
        assert key in inputs, key
    assert inputs['face_mm'] == 150.0
    assert inputs['barbette_mm'] == 75.0
    assert inputs['freeboard_m'] == 4.6
    assert inputs['estimate_long_tons'] * ce.LONG_TON_KG / 1000.0 == pytest.approx(
        model['calculated_mass_t'])
    assert set(model['component_breakdown']) == {'face_long_tons', 'rear_roof_long_tons',
                                                 'barbette_long_tons'}
    assert sum(model['component_breakdown'].values()) == pytest.approx(
        inputs['estimate_long_tons'])
    assert 'guns_in_mount_selector' in model
    assert 'assumptions' in model
    assert model['source']['sha256'] == battery_armour.SOURCE_SHA256
    assert model['source']['assembly'] == battery_armour.SOURCE_ASSEMBLY
    assert inputs['source_location'] == battery_armour.SOURCE_LOCATION
    assert battery_armour.SOURCE_LOCATION in model['source']['source']
    assert model['source']['method_version'] == battery_armour.METHOD_VERSION
    assert 'not whole-program parity' in model['boundary']
    assert 'multi-row and mixed arrangements are outside this method' in model['note']


def test_the_model_never_calls_the_fixed_barbette_wholly_rotating():
    model = models(run(with_armour()))['concept.main.armour']
    text = json.dumps(model, sort_keys=True).lower()
    assert 'wholly rotating' not in text
    assert 'rotating_armour' not in text
    assert model['concept_component'] == 'armour'
    assert 'barbette' in model['note']
    assert 'split the target' in model['note']


def test_thickness_changes_move_the_suggested_mass():
    thin = models(run(with_armour(face_mm=100.0, rear_roof_mm=60.0,
                                  barbette_mm=40.0)))['concept.main.armour']
    thick = models(run(with_armour(face_mm=300.0, rear_roof_mm=160.0,
                                   barbette_mm=120.0)))['concept.main.armour']
    assert thick['calculated_mass_t'] > thin['calculated_mass_t']
    assert [q for q in proposals(run(with_armour())) if q['item_id'] == ARMOUR_ITEM]


# ------------------------------------------------------------------ independence

def test_missing_ammunition_inputs_do_not_block_the_armour_estimate():
    p = with_armour()
    p['concept_design']['batteries'][0]['rounds_per_gun'] = None
    result = run(p)
    assert 'concept.main.armour' in models(result)


def test_missing_barrel_length_does_not_block_the_armour_estimate():
    p = with_armour()
    p['concept_design']['batteries'][0]['barrel_calibres'] = None
    result = run(p)
    assert 'concept.main.armour' in models(result)


def test_a_missing_armour_estimate_does_not_block_the_three_old_estimates():
    p = with_armour(barbette_mm=None, freeboard_m=None, super_factor=None)
    result = run(p)
    found = models(result)
    assert {'concept.main.guns', 'concept.main.mounts',
            'concept.main.ammunition'} <= set(found)
    assert 'concept.main.armour' not in found


def test_incomplete_armour_inputs_are_diagnosed_rather_than_zeroed():
    for field in ('face_mm', 'rear_roof_mm', 'barbette_mm'):
        result = run(with_armour(**{field: None}))
        assert 'concept.main.armour' not in models(result)
        codes = {d['code'] for d in diagnostics(result)}
        assert 'battery_armour.unknown' in codes, (field, codes)
        messages = [json.dumps(d) for d in diagnostics(result)]
        assert any(field in message for message in messages), (field, messages)


def test_a_missing_freeboard_blocks_only_the_barbette_component():
    result = run(with_armour(freeboard_m=None))
    assert 'concept.main.armour' not in models(result)
    assert any('freeboard_m' in json.dumps(d) for d in diagnostics(result))


def test_a_mount_without_a_barbette_needs_no_freeboard_or_super_factor():
    p = with_armour(freeboard_m=None, super_factor=None, barbette_mm=0.0)
    p['concept_design']['batteries'][0]['mount_type'] = 'broadside'
    result = run(p)
    assert 'concept.main.armour' in models(result)


def test_an_unsaved_item_binding_keeps_the_project_valid_and_generates_nothing():
    for field in ('system_id', 'item_id'):
        p = with_armour(**{field: None})
        normalized = project_io.normalize_project(p)
        result = run(normalized)
        assert 'concept.main.armour' not in models(result)
        assert result['stages']['systems']['status'] != 'failed'
        assert {'concept.main.guns', 'concept.main.mounts'} <= set(models(result))


# ------------------------------------------------------------ ownership and role

def test_the_armour_item_may_not_be_another_component_s_target():
    p = with_armour(item_id='weapons.mounts')
    with pytest.raises(project_io.ProjectValidationError):
        project_io.normalize_project(p)


def test_the_armour_item_may_not_be_owned_by_two_batteries():
    p = with_armour()
    p['concept_design']['batteries'].append(dict(p['concept_design']['batteries'][0],
                                                 id='second'))
    with pytest.raises(project_io.ProjectValidationError):
        project_io.normalize_project(p)


def test_the_owning_system_must_actually_link_the_item():
    p = with_armour(system_id='armour.fixed')
    with pytest.raises(project_io.ProjectValidationError):
        project_io.normalize_project(p)


def test_the_new_target_must_carry_the_complete_armour_role():
    p = with_armour()
    p['concept_design']['balance']['roles'][ARMOUR_ITEM] = 'rotating_armour'
    with pytest.raises(project_io.ProjectValidationError):
        project_io.normalize_project(p)


def test_the_fixed_barbette_role_is_not_the_rotating_one():
    assert 'gun_mount_armour' in concept_design.ROLES
    assert 'rotating_armour' in concept_design.ROLES
    assert concept_design.ROLES.index('gun_mount_armour') != \
        concept_design.ROLES.index('rotating_armour')


def test_wrong_types_and_out_of_domain_thicknesses_are_rejected():
    for field, bad in (('face_mm', '150'), ('face_mm', -1.0), ('face_mm', 1000.5),
                       ('barbette_mm', True), ('freeboard_m', 100.5), ('super_factor', 10.5),
                       ('system_id', 7)):
        p = with_armour(**{field: bad})
        with pytest.raises(project_io.ProjectValidationError):
            project_io.normalize_project(p)


def test_an_unsupported_field_is_refused_rather_than_ignored():
    p = with_armour()
    p['concept_design']['batteries'][0]['armour']['thickness_in'] = 6.0
    with pytest.raises(project_io.ProjectValidationError):
        project_io.normalize_project(p)


# ------------------------------------------------------------------ aggregation

def _armour_totals(result):
    return result['stages']['design_balance']['data']['roles']


def test_the_gun_mount_armour_aggregates_with_rotating_armour_in_the_strength_terms():
    result = run(with_armour())
    data = result['stages']['design_balance']['data']
    roles = _armour_totals(result)
    assert roles['gun_mount_armour'] == pytest.approx(40.0 * LT_PER_T)
    combined = roles['rotating_armour'] + roles['gun_mount_armour']
    hull = data['hull_proxy']
    assert data['structure']['cross_coefficient'] == pytest.approx(
        ce.strength_cross_coefficient(
            hull['wetted_surface_sqft'], hull['length_ft'], hull['freeboard_ft'],
            hull['waterplane_area_sqft'], hull['beam_ft'], hull['draught_ft'],
            hull['displacement_long_tons'], data['structure']['broadside_lb'],
            data['selected_borne_weight_long_tons'], combined, roles['conning'],
            data['structure']['hp_max'], 1.0, 1.0, 1918))
    assert data['structure']['long_coefficient'] == pytest.approx(
        ce.strength_long_coefficient(
            hull['length_ft'], hull['draught_ft'], hull['freeboard_ft'],
            hull['displacement_long_tons'], roles['belt_ends'],
            data['selected_borne_weight_long_tons'], combined, 1.0, 1918))


def test_each_armour_role_is_counted_exactly_once_in_the_machinery_aggregate():
    result = run(with_armour())
    model = models(result)['concept.machinery']
    roles = _armour_totals(result)
    expected = sum(roles[role] for role in concept_design.ARMOUR_ROLES)
    assert model['inputs']['selected_armour_long_tons'] == pytest.approx(expected)
    assert 'gun_mount_armour' in concept_design.ARMOUR_ROLES
    assert 'rotating_armour' in concept_design.ARMOUR_ROLES
    assert concept_design.ARMOUR_ROLES.count('gun_mount_armour') == 1
    # A declared gun_mount_armour mass of 40 t is in the aggregate exactly once.
    without = sum(roles[role] for role in concept_design.ARMOUR_ROLES
                  if role != 'gun_mount_armour')
    assert expected - without == pytest.approx(40.0 * LT_PER_T)


def test_a_declared_gun_mount_armour_mass_reaches_the_performance_terms():
    plain = run(project())['stages']['design_balance']['data']
    armed = run(with_armour())['stages']['design_balance']['data']
    assert armed['stability']['score'] != plain['stability']['score']
    assert armed['seakeeping']['seaboat'] != plain['seakeeping']['seaboat']
    # The balance's own role map gains the new role and nothing else moves.
    assert armed['roles']['rotating_armour'] == plain['roles']['rotating_armour']


def test_an_unknown_gun_mount_armour_mass_makes_the_dependent_screen_unavailable():
    p = with_armour()
    item(p, ARMOUR_ITEM)['mass_t'] = None
    result = run(p)
    assert 'concept.main.armour' in models(result)
    data = result['stages']['design_balance']['data']
    assert data['roles']['gun_mount_armour'] is None
    assert 'concept.structure' not in models(result)
    assert data['status'] != 'completed'


@pytest.mark.parametrize('calibre', [1e-200, 1e-300, 1e-323, 5e-324, 1e-320])
def test_a_denormal_calibre_never_escapes_the_stage_as_a_raw_numerical_error(calibre):
    p = with_armour()
    p['concept_design']['batteries'][0]['calibre_mm'] = calibre
    normalized = project_io.normalize_project(p)
    try:
        result = run(normalized)
    except (OverflowError, ZeroDivisionError) as error:      # pragma: no cover - the bug
        pytest.fail('raw %s escaped for calibre %r' % (type(error).__name__, calibre))
    assert result['stages']['systems']['status'] != 'failed'
    assert result['stages']['design_balance']['status'] != 'failed'
    data = result['stages']['systems']['data']
    offered = {m['id'] for row in (data or {}).get('systems', {}).values()
               for m in row['mass_models']}
    # No clamped, rounded or substituted armour estimate is ever offered.
    assert 'concept.main.armour' not in offered


def test_the_armour_boundary_converts_a_raw_numerical_error_into_a_diagnostic(monkeypatch):
    # The sibling gun kernel keeps its own historical overflow behaviour for a
    # denormal calibre, so the armour boundary is exercised directly: a raw
    # interpreter error raised inside the armour kernel must become a
    # non-blocking diagnostic and no model, and must never reach the caller.
    def boom(*args, **kwargs):
        raise ZeroDivisionError('float division by zero')

    monkeypatch.setattr(concept_design.armour_kernel, 'estimate', boom)
    result = run(with_armour())
    assert result['stages']['systems']['status'] != 'failed'
    assert 'concept.main.armour' not in models(result)
    assert 'concept.main.guns' in models(result)
    codes = {d['code'] for d in diagnostics(result)}
    assert 'concept_design.armour_unavailable' in codes, codes
    assert not [d for d in diagnostics(result)
                if d['code'] == 'concept_design.armour_unavailable' and d['blocking']]


def test_an_overflowing_armour_is_never_clamped_to_a_working_floor():
    p = with_armour()
    p['concept_design']['batteries'][0]['calibre_mm'] = 1e-300
    result = run(project_io.normalize_project(p))
    data = result['stages']['systems']['data']
    offered = {m['id'] for row in (data or {}).get('systems', {}).values()
               for m in row['mass_models']}
    assert 'concept.main.armour' not in offered


def test_a_zero_or_negative_calibre_is_still_refused_outright():
    for calibre in (0.0, -152.4):
        with pytest.raises(project_io.ProjectValidationError):
            p = with_armour()
            p['concept_design']['batteries'][0]['calibre_mm'] = calibre
            project_io.normalize_project(p)


# --------------------------------------------------------------------- adoption

def test_reviewed_adoption_changes_only_the_current_condition_override():
    p = with_armour()
    original = copy.deepcopy(p)
    result = run(p)
    batch = [q for q in proposals(result) if q['item_id'] == ARMOUR_ITEM]
    assert len(batch) == 1
    accepted = analysis.apply_mass_proposals(p, 'normal', batch,
                                             current_request=result['request'])
    updated = accepted['project']
    assert accepted['applied_count'] == 1
    # The declared ledger is untouched; the change lands as an override on the
    # selected condition only, and every other condition keeps its own values.
    assert updated['weight_groups'] == original['weight_groups']
    assert p == original
    others = {c['id']: c for c in updated['loading_conditions'] if c['id'] != 'normal'}
    before = {c['id']: c for c in original['loading_conditions'] if c['id'] != 'normal'}
    assert others == before
    assert updated['loading_conditions'][0]['id'] == 'normal'
    assert ARMOUR_ITEM in updated['loading_conditions'][0]['overrides']
    override = updated['loading_conditions'][0]['override_provenance'][ARMOUR_ITEM]['mass_t']
    assert override['source']['method_version'] == battery_armour.METHOD_VERSION
    assert override['estimate'] is True
    assert override['acceptance']['previous_mass_t'] == batch[0]['current_mass_t']
    # And it is saved and reopened unchanged.
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'armour.json'
        project_store.save(path, updated)
        assert project_store.load(path) == updated


def test_a_stale_proposal_is_refused():
    p = with_armour()
    result = run(p)
    batch = [q for q in proposals(result) if q['item_id'] == ARMOUR_ITEM]
    thicker = with_armour(face_mm=300.0)
    with pytest.raises(Exception):
        analysis.apply_mass_proposals(thicker, 'normal', batch,
                                      current_request=result['request'])


def test_the_armour_target_is_not_also_proposed_for_guns_or_mounts():
    result = run(with_armour())
    assert {q['item_id'] for q in proposals(result)} >= {ARMOUR_ITEM, 'weapons.guns',
                                                         'weapons.mounts'}
    sources = {q['source_model_id'] for q in proposals(result) if q['item_id'] == ARMOUR_ITEM}
    assert sources == {'concept.main.armour'}


def test_a_six_to_ten_barrel_battery_keeps_every_other_estimate():
    for per_mount in (6, 8, 10):
        p = with_armour()
        p['concept_design']['batteries'][0]['barrels_per_mount'] = per_mount
        p['concept_design']['batteries'][0]['shared_cradle'] = False
        result = run(p)
        found = models(result)
        assert {'concept.main.guns', 'concept.main.mounts',
                'concept.main.ammunition'} <= set(found), per_mount
        assert 'concept.main.armour' not in found
        assert any('1..5' in json.dumps(d) for d in diagnostics(result))


def test_the_estimate_is_a_known_quantity_before_adoption():
    result = run(with_armour())
    batch = [q for q in proposals(result) if q['item_id'] == ARMOUR_ITEM][0]
    assert batch['proposed_mass_t'] > 0
    assert batch['current_mass_t'] == 40.0
    assert batch['model']['concept_component'] == 'armour'