"""Source dimensional rules and selected-result integration."""
import json
import math
import pytest
from test_fixed_armour_workflow import with_regions, region, run
from plimsoll import armour_review as ar, project_io

CONTEXT = dict(length_m=100, draught_m=5, freeboard_m=3, room_hull_ratio=.8, composite_strength=.5)
RECORDS = [dict(id='main', kind='belt_main', thickness_mm=100, length_m=40, height_m=9),
           dict(id='ends', kind='belt_ends', thickness_mm=50, length_m=70, height_m=9),
           dict(id='upper', kind='belt_upper', thickness_mm=50, length_m=40, height_m=4),
           dict(id='bulge', kind='bulge', thickness_mm=0, height_m=9),
           dict(id='bulkhead', kind='bulkhead', thickness_mm=20, height_m=8)]


def evaluate(angle=0, context=None, records=None):
    return ar.evaluate(RECORDS if records is None else records, CONTEXT if context is None else context,
                       dict(source='synthetic', belt_inclination_deg=angle))


def checks(result):
    return {c['id']: c for c in result['checks']}


def test_length_and_distinct_height_source_margins():
    result = evaluate()
    rows = checks(result)
    assert result['status'] == 'available'
    assert result['values']['minimum_main_belt_length_m'] == pytest.approx(52.003048)
    assert rows['normal_length:main']['values']['normal_length_ratio'] == pytest.approx(40 / 65)
    assert rows['height:main']['values']['maximum_height_m'] == pytest.approx(8.006096)
    assert rows['height:upper']['values']['maximum_height_m'] == pytest.approx(3.003048)
    assert rows['height:bulge']['values']['maximum_height_m'] == 8
    assert rows['height:bulkhead']['status'] == 'pass'
    assert rows['minimum:main']['status'] == rows['belt_pair']['status'] == 'warning'


def test_angle_symmetry_and_region_independence():
    plus, minus = checks(evaluate(30)), checks(evaluate(-30))
    assert plus == minus
    assert plus['height:main']['values']['maximum_height_m'] == pytest.approx(8 / math.cos(math.pi / 6) + .006096)
    assert plus['height:upper']['values'] == checks(evaluate())['height:upper']['values']


@pytest.mark.parametrize('strength', [None, .499])
def test_minimum_requires_supported_strength(strength):
    result = evaluate(context=dict(CONTEXT, composite_strength=strength))
    assert result['values']['minimum_main_belt_length_m'] is None
    assert checks(result)['minimum:main']['status'] == 'unavailable'
    assert checks(result)['height:main']['status'] == 'warning'


def test_missing_or_ambiguous_regions_cannot_pass_pair():
    for records in (RECORDS[1:], RECORDS + [dict(RECORDS[0], id='extra')]):
        assert checks(evaluate(records=records))['belt_pair']['status'] == 'unavailable'


def test_zero_belt_short_circuit_does_not_apply_to_bulge():
    records = [dict(RECORDS[0], thickness_mm=0), RECORDS[3]]
    rows = checks(evaluate(angle=None, context={}, records=records))
    assert rows['height:main']['status'] == 'pass'
    assert rows['height:bulge']['status'] == 'unavailable'


@pytest.mark.parametrize('value', [True, float('nan'), float('inf'), -90, 90, '30'])
def test_invalid_inclination_is_structured(value):
    with pytest.raises(ar.ReviewValidationError):
        ar.validate_config(dict(belt_inclination_deg=value))


def test_overflow_receipt_is_json_finite():
    result = evaluate(context=dict(CONTEXT, length_m=1e308, room_hull_ratio=1e308))
    assert result['values']['minimum_main_belt_length_m'] is None
    json.dumps(result, allow_nan=False)


def test_review_has_no_mass_model_and_angle_cannot_change_mass():
    r = region('main', 'belt_main', 'armour.fixed', 'armour.belt_main',
               thickness_mm=100, length_m=70, height_m=3)
    p = with_regions(r)
    p['concept_design']['armour_review'] = dict(source='synthetic', belt_inclination_deg=0)
    first = run(project_io.normalize_project(p))
    p['concept_design']['armour_review']['belt_inclination_deg'] = 30
    later = run(project_io.normalize_project(p))
    first_data = first['stages']['design_balance']['data']
    later_data = later['stages']['design_balance']['data']
    assert first_data['fixed_armour'][0]['values']['mass_t'] == later_data['fixed_armour'][0]['values']['mass_t']
    assert later_data['methods']['armour_review'] == ar.METHOD_VERSION
    assert 'minimum_main_belt_length_m' in later_data['armour_review']['values']
