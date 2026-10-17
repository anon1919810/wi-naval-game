"""Optional default dimensions remain independent readonly results across saved projects."""
import copy
import json
from pathlib import Path
import pytest
from plimsoll import analysis,concept_design,project_io,verification

def project():
    return json.loads((Path(__file__).parents[1]/'cases/projects/concept_cruiser.project.json').read_text())

def run(p):return analysis.compute_project(p,'normal',{'stages':['loading','systems','design_balance']})
def data(r):return r['stages']['design_balance']['data']
def proposals(r):return [{k:v for k,v in q.items() if k not in ('project_fingerprint','input_fingerprint','request_fingerprint')}
    for q in r['stages']['systems']['data']['update_proposals']]

def test_absent_and_null_keep_old_shapes():
    p=project();before=run(p)
    assert 'armour_defaults' not in project_io.normalize_project(p)['concept_design']
    p['concept_design']['armour_defaults']=None
    normalized=project_io.normalize_project(p)
    # Project extensions preserve an explicit user-supplied null. The adapted
    # configuration/result omits the disabled optional family, as other sections do.
    item_ids={item['id'] for group in normalized['weight_groups'] for item in group['items']}
    assert 'armour_defaults' not in concept_design.validate_config(normalized,item_ids)
    assert data(run(p))==data(before)

def test_saved_config_emits_reading_without_changing_mass_models_or_old_results():
    p=project();old=run(p)
    p['concept_design']['armour_defaults']={'source':'yard study','forecastle_fraction':.2,'quarterdeck_fraction':.15}
    p=project_io.normalize_project(p);original=copy.deepcopy(p);result=run(p)
    assert p==original
    assert proposals(result)==proposals(old)
    reading=data(result)['armour_defaults']
    assert reading['id']=='armour_defaults'
    assert reading['values']['main_length_m']==pytest.approx(p['hull']['lwl_m']*.65)
    assert result['stages']['design_balance']['method_versions']['methods']['armour_defaults']==reading['method_version']
    for key in ('strength','space','cost','fixed_armour','auxiliary_weapons'):
        assert data(result).get(key)==data(old).get(key)
    reopened=project_io.normalize_project(json.loads(json.dumps(p)))
    assert reopened==p
    assert reopened['loading_conditions']==original['loading_conditions']
    assert reopened['weight_groups']==original['weight_groups']
    assert verification._source_identity()['method_versions']['plimsoll.armour_defaults']==reading['method_version']

def test_independent_reading_precedes_unrelated_hull_or_balance_abort():
    p=project();p['concept_design'].update(armour_defaults={'source':None,'forecastle_fraction':.2,'quarterdeck_fraction':.15},
                                        stern=None,screws=None,freeboard_m=None,balance=None)
    result=run(p);reading=data(result)['armour_defaults']
    assert reading['values']['main_length_m'] is not None
    assert reading['values']['main_height_m'] is None
    assert reading['values']['bulkhead_height_m'] is not None

def test_invalid_optional_config_gets_project_diagnostics():
    p=project();p['concept_design']['armour_defaults']={'forecastle_fraction':.8,'quarterdeck_fraction':.8}
    with pytest.raises(project_io.ProjectValidationError) as error:project_io.normalize_project(p)
    assert any('armour_defaults' in d['path'] for d in error.value.diagnostics)
