"""The source-compatible component graph consumes original independent units."""
import copy
import json
from pathlib import Path
import pytest
from plimsoll import sps_hull, sps_file_io


def reference():
    return json.loads((Path(__file__).parent / 'fixtures/sps3b3-synthetic.json').read_text(encoding='utf-8-sig'))


def compute(design):
    try:
        from plimsoll import sps_components
    except ImportError:
        pytest.fail('The source-compatible components are not implemented')
    hull = sps_hull.evaluate(design['parameters'], editing=design['editing'])
    return sps_components.evaluate(design['parameters'], hull['hull'], hull['freeboard'])


def test_same_independent_page_inputs_produce_native_whole_battery_and_fixed_totals():
    design = reference()
    before = copy.deepcopy(design)
    result = compute(design)
    for section, expected in {
        'guns': {'gunsWeight': 342.8402, 'borneWeight': 147.028046,
                 'broadside': 1200.02026, 'magazine': 100.001678, 'superFactor': 1.18676472},
        'auxiliary': {'weight': 96.80333, 'spaceDeck': .0134866452, 'spaceHull': .00371845},
        'armour': {'weight': 3059.30762, 'weightBeltMain': 923.445,
                   'weightDeck': 1154.74414, 'weightConning': 195.391174},
    }.items():
        for key, value in expected.items():
            assert result[section][key] == pytest.approx(value, rel=1e-5)
    assert design == before


def test_missing_torpedo_size_does_not_erase_known_guns_or_fixed_armour():
    design = reference()
    design['parameters']['torpedo1_size'] = None
    result = compute(design)
    assert result['auxiliary']['weight'] is None
    assert result['guns']['gunsWeight'] == pytest.approx(342.8402, rel=1e-5)
    assert result['armour']['weight'] == pytest.approx(3059.30762, rel=1e-5)


def test_explicit_empty_batteries_are_known_zero_and_do_not_need_a_positive_calibre():
    design = reference()
    defaults = sps_file_io.default_design()['parameters']
    design['parameters'].update({key: value for key, value in defaults.items() if key.startswith('gun')})
    result = compute(design)
    assert result['guns']['gunsWeight'] == 0
    assert result['guns']['broadside'] == 0
    assert result['guns']['superFactor'] == 1


def test_fractional_deck_positions_accept_registry_integer_values_after_number_conversion():
    design = reference()
    design['parameters']['gun1_layout_group1'] = 3
    result = compute(design)
    assert result['guns']['groups'][0]['positionG1'] == pytest.approx(.25 * .30)
    assert result['guns']['gunsWeight'] is not None


def test_metric_shell_entry_keeps_the_original_focused_metric_text_roundtrip():
    from plimsoll import sps_compat
    result=sps_compat.apply_edit(reference(),dict(kind='set_shell_weight',group=1,unit='kg',value=52.5))
    # Original visible Guns/Bank1 page, metric-shell focus and 52.5kg entry.
    assert result['design']['parameters']['gun1_shell_weight']==115.74
    assert result['preview']['guns']['groups'][0]['shellWeight']==pytest.approx(115.74,rel=1e-7)
    assert sps_compat.compute(result['design'])['guns']['broadside']==result['preview']['guns']['broadside']
