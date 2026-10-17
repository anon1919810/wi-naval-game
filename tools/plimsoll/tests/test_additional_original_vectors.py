"""Frozen direct original-method observations; policy refusals are separate."""
import json
from pathlib import Path
import pytest
from test_fixed_armour_workflow import project  # establishes the package path
from plimsoll import armour_review as ar, auxiliary_weapons as aw

VECTORS = json.loads((Path(__file__).parent / 'fixtures/concept/original-auxiliary-review-vectors.json')
                     .read_text(encoding='utf-8'))


@pytest.mark.parametrize('row', VECTORS['auxiliary'], ids=lambda r: r['id'])
def test_original_auxiliary_mass(row):
    actual = aw.evaluate(row['record'], row['context'])
    assert actual['status'] == 'available'
    for field, expected in row['outputs'].items():
        assert actual['values'][field] == pytest.approx(expected, rel=1e-5, abs=1e-9)


@pytest.mark.parametrize('row', VECTORS['guarded'], ids=lambda r: r['id'])
def test_unsupported_source_defaults_do_not_become_valid_estimates(row):
    assert aw.evaluate(row['record'], row['context'])['status'] == 'unavailable'


@pytest.mark.parametrize('row', VECTORS['review'], ids=lambda r: r['id'])
def test_original_height_and_normal_length(row):
    result = ar.evaluate([row['record']], row['context'], row['config'])
    checks = {c['id']: c for c in result['checks']}
    assert checks['height:main']['values']['maximum_height_m'] == pytest.approx(row['outputs']['maximum_height_m'], rel=1e-5)
    assert checks['normal_length:main']['values']['normal_length_ratio'] == pytest.approx(row['outputs']['normal_length_ratio'], rel=1e-5)


@pytest.mark.parametrize('row', VECTORS['minimum'])
def test_original_minimum_length_gate_and_display_scale(row):
    actual = ar.evaluate([], row['context'], {})['values']['minimum_main_belt_length_m']
    if row['expected'] is None:
        assert actual is None
    else:
        assert actual == pytest.approx(row['expected'], rel=1e-5)
