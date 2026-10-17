"""Independently reproduced review defects, through public calculation paths."""
import pytest

from test_fixed_armour_workflow import with_regions, item, run
from plimsoll import fixed_armour as fa, project_io


@pytest.mark.parametrize('bad', [None, 123, 'bad', []])
def test_bad_armour_elements_have_structured_validation(bad):
    with pytest.raises(fa.ArmourValidationError):
        fa.validate_configs([bad])


@pytest.mark.parametrize('mass', [None, 10])
def test_cost_cannot_price_unbound_unknown_or_positive_guns(mass):
    p = with_regions(cost={'source': None})
    p['concept_design']['batteries'] = []
    item(p, 'weapons.guns')['mass_t'] = mass
    data = run(project_io.normalize_project(p))['stages']['design_balance']['data']
    assert data['cost']['status'] == 'unavailable'
    assert data['cost']['values']['usd_million'] is None


def test_negative_central_deck_area_cannot_be_offset_by_positive_end_plates():
    result = fa.evaluate({'id': 'deck', 'kind': 'deck', 'coverage_index': 0,
                         'thickness_mm': 1, 'forecastle_mm': 200, 'quarterdeck_mm': 200,
                         'forecastle_fraction': .26, 'quarterdeck_fraction': .2},
                        {'length_m': 100, 'beam_m': 20, 'co_waterplane': .8,
                         'waterplane_area_m2': 10})
    assert result['status'] == 'unavailable'
    assert result['values']['total_long_tons'] is None


def test_zero_central_box_plate_does_not_need_box_loads():
    result = fa.evaluate({'id': 'deck', 'kind': 'deck', 'coverage_index': 4,
                         'thickness_mm': 0, 'forecastle_mm': 100, 'quarterdeck_mm': 0,
                         'forecastle_fraction': .2, 'quarterdeck_fraction': 0},
                        {'length_m': 100, 'beam_m': 20, 'co_waterplane': .8})
    assert result['status'] == 'available'
    assert result['values']['central_long_tons'] == 0
    assert result['values']['fore_long_tons'] > 0


def test_zero_end_areas_do_not_need_waterplane_coefficient_for_box():
    result = fa.evaluate({'id': 'deck', 'kind': 'deck', 'coverage_index': 4,
                         'thickness_mm': 10, 'forecastle_mm': None, 'quarterdeck_mm': None,
                         'forecastle_fraction': 0, 'quarterdeck_fraction': 0},
                        {'length_m': 100, 'beam_m': 20, 'displacement_t': 1000,
                         'machinery_mass_t': 10})
    assert result['status'] == 'available'
    assert result['values']['fore_long_tons'] == result['values']['quarter_long_tons'] == 0
