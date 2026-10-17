"""Compatibility graph entry points must work in the shipped package context."""
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest


def test_package_import_without_test_runner_path_mutation():
    root = Path(__file__).resolve().parents[3]
    environment = dict(os.environ, PYTHONPATH=str(root / 'tools'))
    completed = subprocess.run(
        [sys.executable, '-B', '-c',
         'from plimsoll import sps_compat; '
         'assert sps_compat._import("sps_hull", [], "$").METHOD_VERSION == "sps-3b3-hull-v1"'],
        cwd=root, env=environment, text=True, capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_complete_source_design_does_not_require_physical_geometry_or_cg():
    from plimsoll import sps_compat
    design = json.loads((Path(__file__).parent / 'fixtures/sps3b3-synthetic.json').read_text(encoding='utf-8-sig'))
    result = sps_compat.compute(design)
    assert result['status'] == 'available', result['diagnostics']
    assert result['hull']['draughtDeep'] == result['performance']['draughtDeep']
    expected = {'draughtDeep': 28.74623, 'blockDeep': .5605253,
                'concentration': .9457416, 'strengthComp': 1.48599,
                'flotation': 28596.51, 'damageTorp': 3.37437558}
    for key, value in expected.items():
        assert result['performance'][key] == pytest.approx(value, rel=1e-5)


def test_edit_commands_receive_the_complete_current_context_and_keep_shell_lock():
    from plimsoll import sps_compat
    design = json.loads((Path(__file__).parent / 'fixtures/sps3b3-synthetic.json').read_text(encoding='utf-8-sig'))
    locked = sps_compat.apply_edit(design, {'kind':'set_power_lock', 'value':True})
    assert locked['design']['editing']['power_hp'] == pytest.approx(72098.87, rel=1e-5)
    assert locked['design']['editing']['locked_bunker_lt'] == pytest.approx(3017.63428, rel=1e-5)
    fixed = sps_compat.apply_edit(design, {'kind':'lock_shells', 'groups':[1]})
    heavier = sps_compat.apply_edit(fixed['design'], {'kind':'set_parameter', 'name':'gun1_calibre', 'value':8})
    assert heavier['design']['parameters']['gun1_calibre'] == 8
    assert heavier['preview']['guns']['groups'][0]['shellWeight'] == pytest.approx(100.001678, rel=1e-5)
    assert heavier['design']['editing']['locked_shell_groups'] == [1]


def test_source_edit_refreshes_belts_and_preserves_deep_draught_callback_context():
    from plimsoll import sps_compat
    design=json.loads((Path(__file__).parent/'fixtures/sps3b3-synthetic.json').read_text(encoding='utf-8-sig'))
    edited=sps_compat.apply_edit(design,dict(kind='set_parameter',name='beam_moulded',value=27))
    # Controlled original full event graph, metric hull / imperial armour.
    assert edited['preview']['armour']['weightBeltMain']==pytest.approx(940.2576,rel=1e-5)
    assert edited['preview']['performance']['blockDeep']==pytest.approx(.481555551,rel=1e-5)
    assert sps_compat.compute(edited['design'])==edited['preview']
    invalid=sps_compat.apply_edit(design,dict(kind='set_parameter',name='gun1_barrels',value=True))
    assert invalid['status']=='partial'
    assert invalid['design']['parameters']['gun1_barrels']==12


def test_displacement_driver_and_freeboard_presets_preserve_source_callback_order():
    from plimsoll import sps_compat
    design=json.loads((Path(__file__).parent/'fixtures/sps3b3-synthetic.json').read_text(encoding='utf-8-sig'))
    changed=sps_compat.apply_edit(design,dict(kind='set_displacement_driver',value='displacement'))
    changed=sps_compat.apply_edit(changed['design'],dict(kind='set_parameter',name='normal_displacement_lt',value=22000))
    assert changed['preview']['armour']['weightBeltMain']==pytest.approx(928.368469,rel=1e-5)
    for preset,height in [('flush',49.74555),('raised',51.2283478)]:
        changed=sps_compat.apply_edit(design,dict(kind='freeboard_preset',value=preset))
        assert changed['preview']['armour']['maxBeltHeight']==pytest.approx(height,rel=1e-5)
        assert sps_compat.compute(changed['design'])==changed['preview']


def test_non_json_or_deep_input_produces_bounded_diagnostics_instead_of_recursion():
    from plimsoll import sps_compat
    cyclic={};cyclic['parameters']=cyclic
    assert sps_compat.compute(cyclic)['status']!='available'
    design=json.loads((Path(__file__).parent/'fixtures/sps3b3-synthetic.json').read_text(encoding='utf-8-sig'))
    design['parameters']['trim']=None
    result=sps_compat.compute(design)
    assert result['performance']['steadinessAdj'] is None
    design['parameters']['beam_moulded']=10**10000
    assert sps_compat.compute(design)['status']!='available'
