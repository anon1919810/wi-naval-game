"""Auxiliary import and reviewed adoption, through real normalized projects."""
import copy
import hashlib
import pytest
from test_fixed_armour_workflow import project, run
from test_sship_import import build, imperial_fields
from plimsoll import analysis, project_io, sship_import, auxiliary_weapons as aw


def test_five_source_rows_keep_their_own_scales_and_unknown_mass_targets():
    updates = {9:'0',77:'12',179:'3',79:'21',182:'20',184:'1',
               136:'1',78:'4',180:'1',181:'450',183:'5',185:'4',
               137:'1',186:'20',187:'10',188:'500',189:'0',
               138:'0',190:'12',192:'24',194:'300',196:'1',
               139:'1',191:'4',193:'12',195:'200',197:'3',201:'-30'}
    raw = build(imperial_fields(updates))
    p = sship_import.preview(raw)['project']
    records = {r['id']: r for r in p['concept_design']['auxiliary_weapons']}
    assert len(records) == 5
    assert records['sship_torpedo1']['diameter_mm'] == pytest.approx(533.4)
    assert records['sship_torpedo2']['length_m'] == 5
    assert records['sship_mine1']['unit_mass_kg'] == 500
    assert records['sship_depth_charge1']['unit_mass_kg'] == pytest.approx(300 * .45359237)
    assert records['sship_depth_charge2']['unit_mass_kg'] == 200
    assert p['concept_design']['armour_review']['belt_inclination_deg'] == -30
    assert p['concept_design'].get('balance') is None and not p['concept_design'].get('cost')
    items = {i['id']:i for g in p['weight_groups'] for i in g['items']}
    assert all(items[r['item_id']]['mass_t'] is None for r in records.values())
    assert p['migration']['source']['sha256'] == hashlib.sha256(raw).hexdigest()
    assert project_io.normalize_project(copy.deepcopy(p))['migration'] == p['migration']


def test_out_of_table_mine_location_is_archived_without_poisoning_import():
    p = sship_import.preview(build(imperial_fields({186:'20',187:'10',188:'500',189:'8'})))['project']
    mine = next(r for r in p['concept_design']['auxiliary_weapons'] if r['kind'] == 'mine')
    assert mine['location_index'] is None
    assert p['migration']['raw_fields'][189] == '8'


@pytest.mark.parametrize('bad', [None, 123, 'bad', []])
def test_bad_auxiliary_elements_have_structured_validation(bad):
    with pytest.raises(aw.AuxiliaryValidationError):
        aw.validate_configs([bad])


def test_auxiliary_adoption_is_selected_condition_only_and_cannot_share_a_gun_target():
    p = project()
    p['loading_conditions'].append(dict(id='other', overrides={}))
    p['concept_design']['auxiliary_weapons'] = [dict(id='stores', kind='mine',
        system_id='weapons.misc_weight', item_id='weapons.other', source='synthetic',
        count=20, loads=10, unit_mass_kg=500, location_index=0)]
    p = project_io.normalize_project(p)
    before = copy.deepcopy(p)
    result = run(p)
    proposals = result['stages']['systems']['data']['update_proposals']
    proposal = next(q for q in proposals if q['source_model_id'] == 'concept_auxiliary.stores')
    assert proposal['proposed_mass_t'] == pytest.approx(18.75)
    updated = analysis.apply_mass_proposals(p, 'normal', [proposal], current_request=result['request'])['project']
    assert updated['weight_groups'] == before['weight_groups']
    assert updated['loading_conditions'][1] == before['loading_conditions'][1]
    assert p == before
    p['concept_design']['auxiliary_weapons'][0].update(system_id='weapons.main', item_id='weapons.guns')
    with pytest.raises(ValueError):
        project_io.normalize_project(p)
