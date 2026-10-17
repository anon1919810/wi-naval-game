"""Original pre-N2 dimensions and independent availability/serialization boundaries."""
import copy
import json
import math
from pathlib import Path

import pytest
from plimsoll import armour_defaults as kernel

FIXTURE=json.loads((Path(__file__).parent/'fixtures/concept/original-armour-defaults-vectors.json').read_text())
CONFIG={'source':'declared study','forecastle_fraction':.2,'quarterdeck_fraction':.15}
CONTEXT={'length_m':152,'beam_m':18.3,'draught_m':5.2,'block_coeff':.5,'freeboard_m':4.6}

def test_original_pre_n2_readings_and_product_guards():
    compared=guarded=rejected=0
    for row in FIXTURE['rows']:
        assert row['complete_method']
        raw=row['config']
        if raw['forecastle_fraction']+raw['quarterdeck_fraction']>1:
            with pytest.raises(kernel.ArmourDefaultsError):kernel.validate_config(raw)
            rejected+=1
            continue
        result=kernel.evaluate(kernel.validate_config(raw),row['context'])
        json.dumps(result,allow_nan=False)
        for key,expected in row['pre_n2_dimensions_m'].items():
            if expected<0:
                assert result['values'][key] is None,(row['id'],key)
                assert result['availability'][key]['state']=='unavailable'
                guarded+=1
            else:
                assert result['values'][key]==pytest.approx(expected,rel=2e-6,abs=2e-6),(row['id'],key)
                compared+=1
    assert (compared,guarded,rejected)==(220,12,1)

@pytest.mark.parametrize('field',['length_m','beam_m','draught_m','freeboard_m'])
def test_large_finite_metres_never_emit_nonfinite_provenance(field):
    result=kernel.evaluate(CONFIG,{**CONTEXT,field:1e308})
    json.dumps(result,allow_nan=False)
    assert result['diagnostics']
    assert result['provenance']['inputs'][field.removesuffix('_m')+'_ft'] is None

def test_malformed_origin_does_not_poison_finite_json():
    result=kernel.evaluate(CONFIG,{**CONTEXT,'length_m':{'value':152,'source':float('nan'),'estimate':False}})
    json.dumps(result,allow_nan=False)
    assert result['diagnostics']
    assert result['values']['main_length_m']==pytest.approx(98.8)

def test_negative_side_only_blocks_negative_final_dimensions():
    result=kernel.evaluate(CONFIG,{**CONTEXT,'block_coeff':.2,'freeboard_m':30})
    assert result['provenance']['inputs']['side_draught_ft']<0
    assert result['values']['bulkhead_height_m'] is None
    assert result['values']['main_height_m']>0
    assert result['values']['main_length_m']==pytest.approx(98.8)

@pytest.mark.parametrize('block',[None,0,1e-300])
def test_missing_or_extreme_block_keeps_independent_lengths_and_upper_height(block):
    result=kernel.evaluate(CONFIG,{**CONTEXT,'block_coeff':block})
    assert result['values']['main_length_m']==pytest.approx(98.8)
    assert result['values']['upper_height_m']==pytest.approx(2.4384)
    assert result['values']['bulkhead_height_m'] is None
    json.dumps(result,allow_nan=False)

def test_unknown_fractions_do_not_erase_known_heights_or_mutate_inputs():
    cfg={**CONFIG,'forecastle_fraction':None};original=copy.deepcopy((cfg,CONTEXT))
    result=kernel.evaluate(cfg,CONTEXT)
    assert result['values']['main_length_m'] is None
    assert result['values']['main_height_m'] is not None
    assert (cfg,CONTEXT)==original

@pytest.mark.parametrize('patch',[{'forecastle_fraction':True},{'quarterdeck_fraction':float('nan')},
    {'forecastle_fraction':-.1},{'forecastle_fraction':.8,'quarterdeck_fraction':.5},{'source':3},{'unexpected':1}])
def test_invalid_config_refused_structurally(patch):
    with pytest.raises(kernel.ArmourDefaultsError) as error:kernel.validate_config({**CONFIG,**patch})
    assert error.value.diagnostics
