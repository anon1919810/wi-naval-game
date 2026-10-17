"""Explicit torpedo-space scope survives saved projects without changing old estimates."""
import copy
import json
from pathlib import Path
import pytest
from plimsoll import analysis, project_io, verification

def project():
    p=json.loads((Path(__file__).parents[1]/'cases/projects/concept_cruiser.project.json').read_text())
    p['concept_design']['auxiliary_weapons']=[dict(id='tube',kind='torpedo',count=8,loads=3,
        location_index=1,diameter_mm=533.4,length_m=6.096)]
    return p

def run(p):return analysis.compute_project(p,'normal',{'stages':['loading','systems','design_balance']})
def data(r):return r['stages']['design_balance']['data']
def proposals(r):return [{k:v for k,v in q.items() if k not in
    ('project_fingerprint','input_fingerprint','request_fingerprint')}
    for q in r['stages']['systems']['data']['update_proposals']]

def test_optional_space_is_independent_and_preserves_saved_mass_and_old_results():
    p=project();old=run(p)
    p['concept_design']['auxiliary_space']=dict(source='declared scope',torpedo_ids=['tube'],bulged_beam_m=30)
    p=project_io.normalize_project(p);before=copy.deepcopy(p);r=run(p);space=data(r)['auxiliary_space']
    assert p==before
    assert space['values']['deck_area_m2']>0
    assert space['values']['hull_volume_m3']==0
    assert r['stages']['design_balance']['method_versions']['methods']['auxiliary_space']==space['method_version']
    assert verification._source_identity()['method_versions']['plimsoll.auxiliary_space']==space['method_version']
    assert proposals(r)==proposals(old)
    for key in ('space','strength','cost','auxiliary_weapons'):assert data(r).get(key)==data(old).get(key)
    assert project_io.normalize_project(json.loads(json.dumps(p)))==p

def test_space_does_not_require_freeboard_or_balance_and_does_not_infer_bulged_beam():
    p=project();p['concept_design'].update(freeboard_m=None,balance=None,
        auxiliary_space=dict(torpedo_ids=['tube'],bulged_beam_m=None))
    values=data(run(p))['auxiliary_space']['values']
    assert values['deck_area_m2']>0 and values['deck_ratio'] is not None
    assert values['hull_volume_m3']==0 and values['hull_ratio'] is None

@pytest.mark.parametrize('ids,width',[(['missing'],30),(['tube','tube'],30),(['tube'],1)])
def test_invalid_reference_or_contradictory_width_rejected(ids,width):
    p=project();p['concept_design']['auxiliary_space']=dict(torpedo_ids=ids,bulged_beam_m=width)
    with pytest.raises(project_io.ProjectValidationError):project_io.normalize_project(p)

def test_disabled_optional_family_keeps_old_shape():
    p=project();old=run(p);p['concept_design']['auxiliary_space']=None
    assert data(run(p))==data(old)
    assert 'auxiliary_space' not in data(old)
