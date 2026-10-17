"""Source-format behaviour, independent from any physical ship calculation."""
import copy
import pytest
from plimsoll import sps_file_io, sship_fields


def test_original_fresh_window_defaults_and_new_design_do_not_alias():
    first = sps_file_io.default_design()
    assert first['parameters']['hull_year'] == 1950
    assert first['parameters']['stern'] == -1
    assert first['parameters']['gun1_layout_group1'] == 18
    first['parameters']['ship_name'] = 'Edited'
    assert sps_file_io.default_design()['parameters']['ship_name'] == 'Enter ship name'


def test_roundtrip_authority_units_notes_and_archive_unchanged():
    design = sps_file_io.default_design()
    parameters = design['parameters']
    parameters.update(ship_name='试验 {A} \\ 名称', hull_scale=1, armour_scale=0,
                      gun1_super_mounts_group1=3, gun1_super_mounts_group1_early=999)
    design['notes'] = '用户注释\n下一行，标点。'
    original = copy.deepcopy(design)
    data = sps_file_io.dumps(design)
    loaded = sps_file_io.loads(data)
    assert loaded['parameters']['gun1_super_mounts_group1'] == 3
    assert loaded['parameters']['gun1_super_mounts_group1_early'] == 3
    assert loaded['parameters']['hull_scale'] == 1
    assert loaded['parameters']['armour_scale'] == 0
    assert loaded['parameters']['ship_name'] == parameters['ship_name']
    assert loaded['notes'] == design['notes']
    assert design == original


def test_original_rejects_style_1x_instead_of_guessing_a_30_mapping():
    with pytest.raises(sps_file_io.FileIOError) as error:
        sps_file_io.loads(b'SpringStyle Version 1.1\n')
    assert 'supported' in str(error.value).lower()


def test_legacy_20_bulkhead_dimension_uses_internal_feet_before_text_assignment():
    records = list(sps_file_io.DEFAULT_RECORDS[:136])
    records[3], records[10], records[14], records[16] = '1', '0', '25', 'True'
    design = sps_file_io.loads(('SpringSharp Version 2.0\n' + '\n'.join(records) + '\n').encode())
    # MainForm.openFileCalc initializes bow=0 before the legacy branch, then
    # writes (25m / 0.3048 - 20ft).ToString("n2") into the armour page.
    assert design['parameters']['bow'] == 0
    assert design['parameters']['armour_bulkhead_beam'] == 62.02


def test_unknown_numeric_export_is_refused_because_original_reuses_previous_parse_value():
    design=sps_file_io.default_design();design['parameters']['beam_moulded']=None
    with pytest.raises(sps_file_io.FileIOError) as error:sps_file_io.dumps(design)
    assert any('beam_moulded' in d.get('path','') for d in error.value.diagnostics)
