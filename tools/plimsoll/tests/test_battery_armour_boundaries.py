"""Public-stage numerical-range regressions from independent acceptance review."""
import copy
import json
import math
from pathlib import Path

import pytest

from plimsoll import analysis, concept_design, loading

CASE = Path(__file__).resolve().parents[1] / 'cases/projects/concept_cruiser.project.json'


def project(calibre, rounds):
    p = json.loads(CASE.read_text(encoding='utf-8-sig'))
    battery = p['concept_design']['batteries'][0]
    battery.update(calibre_mm=calibre, rounds_per_gun=rounds, mount_count=1)
    battery['armour'] = {'system_id': 'weapons.main', 'item_id': 'weapons.rotating_armour',
                         'face_mm': 1000, 'rear_roof_mm': 100, 'barbette_mm': 0,
                         'freeboard_m': None, 'super_factor': None}
    p['concept_design']['balance']['roles']['weapons.rotating_armour'] = 'gun_mount_armour'
    return p


def assert_finite(value):
    if isinstance(value, dict):
        for child in value.values():
            assert_finite(child)
    elif isinstance(value, list):
        for child in value:
            assert_finite(child)
    elif isinstance(value, float):
        assert math.isfinite(value)


@pytest.mark.parametrize('calibre', [1e-200, 1e-300, 1e-323])
@pytest.mark.parametrize('rounds', [120, None])
def test_complete_and_ammunition_incomplete_batteries_contain_numeric_failures(calibre, rounds):
    p = project(calibre, rounds)
    before = copy.deepcopy(p)
    state = loading.resolve_loading(p, 'normal')
    generated = concept_design.generated_models(p, state)
    assert generated['diagnostics']
    assert not any(m['id'] == 'concept.main.armour'
                   for models in generated['systems'].values() for m in models)
    result = analysis.compute_project(p, 'normal', {'stages': ['loading', 'systems', 'design_balance']})
    assert result['stages']['systems']['data'] is not None
    assert_finite(result)
    assert p == before


def test_finite_long_tons_do_not_overflow_the_existing_tonnes_pipeline():
    p = project(1e-151, None)
    result = analysis.compute_project(p, 'normal', {'stages': ['loading', 'systems']})
    data = result['stages']['systems']['data']
    assert data is not None
    assert_finite(data)
    assert not any(row['source_model_id'] == 'concept.main.armour'
                   for row in data['update_proposals'])
    assert any(d['code'] == 'concept_design.armour_unavailable'
               for d in result['stages']['systems']['diagnostics'])
