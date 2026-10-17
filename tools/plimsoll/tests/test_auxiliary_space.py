"""Native numeric observations and deliberately separate product guards."""
import copy
import json
import math
from pathlib import Path
import pytest
from plimsoll import auxiliary_space as kernel

CONTEXT=dict(length_m=150,beam_m=18,draught_m=5,block_coeff=.5,waterplane_area_m2=2000)
def record(**changes):
    return dict(dict(id='tube',kind='torpedo',count=8,loads=3,location_index=1,
                     diameter_mm=533.4,length_m=6.096),**changes)
def read(records=None,ids=('tube',),width=19,context=None):
    records=[record()] if records is None else records
    cfg=kernel.validate_config(dict(torpedo_ids=None if ids is None else list(ids),bulged_beam_m=width),records)
    return kernel.evaluate(records,CONTEXT if context is None else context,cfg)

def test_native_observations():
    fixture=json.loads((Path(__file__).parent/'fixtures/concept/original-auxiliary-space-vectors.json').read_text())
    assert len(fixture['rows'])==53
    for row in fixture['rows']:
        original=copy.deepcopy(row)
        result=read(row['records'],[r['id'] for r in row['records']],row['bulged_beam_m'],row['context'])
        for key,value in row['expected'].items():
            assert result['values'][key]==pytest.approx(value,rel=2e-6,abs=2e-6),(row['id'],key)
        assert row==original
        json.dumps(result,allow_nan=False)

@pytest.mark.parametrize('loc',range(9))
def test_known_zero_policy_precedes_missing_size_and_sets(loc):
    result=read([record(count=0,loads=None,diameter_mm=None,length_m=None,location_index=loc)])
    assert all(result['values'][key]==0 for key in kernel.VALUE_KEYS)
    assert any(d['code'].endswith('zero_count_policy') for d in result['records'][0]['diagnostics'])

def test_unknown_and_empty_scope_are_different_even_for_zero_count():
    assert all(v is None for v in read(ids=None)['values'].values())
    assert all(v==0 for v in read(ids=[])['values'].values())
    assert read([record(count=0,location_index=None)])['values']['deck_area_m2']==0

def test_branches_and_unknown_members_are_independent():
    rows=[record(location_index=1,loads=9),record(id='sub',location_index=4,count=4)]
    result=read(rows,['tube','sub'],width=None)
    assert result['values']['deck_area_m2'] is None
    assert result['values']['hull_volume_m3']>0
    assert result['values']['hull_ratio'] is None
    assert result['records'][0]['values']['hull_volume_m3']==0
    missing=read([record(count=None,location_index=4)])['values']
    assert missing['deck_area_m2']==0 and missing['hull_volume_m3'] is None

def test_loads_zero_is_effective_one_and_not_written_back_and_zero_diameter_is_not_mass_guard():
    rows=[record(loads=0,diameter_mm=0)];before=copy.deepcopy(rows)
    value=read(rows)['values']['deck_area_m2']
    assert value>0 and rows==before
    assert value==read([record(loads=1,diameter_mm=0)])['values']['deck_area_m2']

@pytest.mark.parametrize('key',['waterplane_area_m2','length_m','draught_m','block_coeff'])
def test_zero_numerator_still_requires_positive_denominator(key):
    context=dict(CONTEXT);context[key]=0
    values=read(ids=[],context=context)['values']
    assert values['deck_ratio' if key=='waterplane_area_m2' else 'hull_ratio'] is None
    assert values['deck_area_m2']==0 and values['hull_volume_m3']==0

@pytest.mark.parametrize('key,value',[('count',-1),('count',1.5),('loads',True),('diameter_mm',float('inf')),
                                     ('length_m',-1),('location_index',9)])
def test_structurally_invalid_records_rejected(key,value):
    with pytest.raises(kernel.AuxiliarySpaceError):read([record(**{key:value})])

@pytest.mark.parametrize('ids',[['missing'],['tube','tube'],['tube','a','b'],[None]])
def test_bad_scope_rejected(ids):
    with pytest.raises(kernel.AuxiliarySpaceError):read(ids=ids)

def test_nontorpedo_and_contradictory_total_width_rejected():
    with pytest.raises(kernel.AuxiliarySpaceError):read([dict(id='mine',kind='mine')],['mine'])
    with pytest.raises(kernel.AuxiliarySpaceError):read(width=17)
    with pytest.raises(kernel.AuxiliarySpaceError):read([record(kind=[])])

def test_overflow_and_bad_provenance_remain_finite_json_and_occupancy_survives():
    context=dict(CONTEXT,length_m=1e308,draught_m=1e308,beam_m=1e308,
                 waterplane_area_m2={'value':1e-320,'source':float('inf')})
    # Width is unknown so the contradictory-width check does not mask overflow.
    result=read([record(location_index=2)],width=None,context=context)
    json.dumps(result,allow_nan=False)
    assert result['values']['deck_area_m2'] is None
    assert result['values']['hull_volume_m3']==0
    result=read(context=dict(CONTEXT,length_m=1e308,draught_m=1e308),width=19)
    assert result['values']['deck_area_m2']>0 and result['values']['hull_ratio'] is None
    json.dumps(result,allow_nan=False)
