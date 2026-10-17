import json
from pathlib import Path
import pytest
from plimsoll import sps_compat, sps_engine


def reference():
    return json.loads((Path(__file__).parent/'fixtures/sps3b3-synthetic.json').read_text(encoding='utf-8-sig'))


def test_locked_source_power_solver_retains_power_and_recomputes_speed_and_range():
    design=reference()
    for command in [dict(kind='set_power_lock',value=True),dict(kind='set_parameter',name='length_waterline',value=190),dict(kind='recalculate_power')]:
        edited=sps_compat.apply_edit(design,command);design=edited['design']
    engine=edited['preview']['engine']
    assert engine['hpMax']==pytest.approx(72098.87,rel=1e-5)
    assert engine['speedMax']<27.5
    # The source's stepped range solver stops on its own increment boundary.
    assert engine['bunker']==pytest.approx(3017.456,rel=1e-5)
    assert edited['preview']['performance']['strengthComp']==pytest.approx(1.55843949,rel=1e-5)
    unlocked=sps_compat.apply_edit(design,dict(kind='set_power_lock',value=False))
    assert not unlocked['design']['editing']['power_locked']
    assert not any(d['code']=='power_lock_pending_recalc' for d in unlocked['diagnostics'])
