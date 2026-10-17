import copy
import json
from pathlib import Path


def test_source_gun_rules_cover_threshold_and_shell_override_without_mutating_inputs():
    from plimsoll import sps_compat
    result = sps_compat.compute(json.loads((Path(__file__).parent / 'fixtures/sps3b3-synthetic.json').read_text(encoding='utf-8-sig')))
    try:
        from plimsoll import sps_gun_review
    except ImportError:
        assert False, 'The source rule and description formatter is missing'
    group = copy.deepcopy(result['guns']['groups'][0])
    group.update(gunType=4, mountType=4, dateGun=1919, calibre=6.5,
                 shellWeight=200, autoShellWeight=100)
    before = copy.deepcopy(group)
    rules = sps_gun_review.gun_rules(group)
    assert len(rules) == 32
    active = {item['code'] for item in rules if item['condition']}
    assert 'gun.era_dual_purpose' in active
    assert 'gun.calibre_qf_aa_dp' not in active
    assert 'gun.shell_heavy' in active
    group['calibre'] = 6.5001
    assert any(item['code']=='gun.calibre_qf_aa_dp' and item['condition'] for item in sps_gun_review.gun_rules(group))
    assert before['calibre'] == 6.5


def test_two_group_description_retains_both_mount_classes_and_auxiliary_units():
    from plimsoll import sps_compat, sps_gun_review
    result = sps_compat.compute(json.loads((Path(__file__).parent / 'fixtures/sps3b3-synthetic.json').read_text(encoding='utf-8-sig')))
    review = result['review']
    assert '3 x 2-gun mounts' in review['gun_descriptions'][0]
    assert '2 x Triple mounts' in review['gun_descriptions'][0]
    assert '21.0' in review['auxiliary_descriptions'][0]
    assert '533 mm' in review['auxiliary_descriptions'][0]
    assert 'reloads' in review['auxiliary_descriptions'][2]


def test_source_geometry_warnings_keep_zero_thickness_and_unknown_distinct():
    from plimsoll import sps_gun_review
    hull={'block':.25,'length':100,'draught':10}
    free={'lengthBow':90,'fcLength':.6,'fdLength':.4,'qdLength':.1,'adLength':-.1,'freeDistributed':5}
    armour=dict(beltMainLength=80,beltEndsLength=30,beltMain=1,beltEnds=0,beltUpper=0,
                beltMainHeight=16,beltEndsHeight=100,beltUpperHeight=100,maxBeltHeight=15,
                bulkheadHeight=16,bulgeHeight=None)
    rules=sps_gun_review.design_rules({},hull,free,armour)
    conditions={rule['code']:rule['condition'] for rule in rules}
    assert conditions['design.belt_length'] is True
    assert conditions['design.belt_height'] is True
    assert conditions['design.bulkhead_height'] is True
    assert conditions['design.bulge_height'] is None
    armour['beltMain']=0
    assert next(rule for rule in sps_gun_review.design_rules({},hull,free,armour) if rule['code']=='design.belt_height')['condition'] is False
