import json
from pathlib import Path


def test_report_uses_the_same_full_section_model_and_escapes_rtf_notes():
    from plimsoll import sps_compat
    design = json.loads((Path(__file__).parent / 'fixtures/sps3b3-synthetic.json').read_text(encoding='utf-8-sig'))
    design['notes'] = '追加 {注释} \\ 路径 😀\n下一行'
    result = sps_compat.compute(design)
    try:
        from plimsoll import sps_report
    except ImportError:
        assert False, 'The compatible report is missing'
    model = sps_report.build(result)
    assert len(model['sections']) >= 11
    text = sps_report.serialize(result, format='txt')
    assert text == model['text']
    assert '17,244' in text and '20,777' in text
    assert 'Cross-sectional' in text and 'Recoil' in text
    assert '53,786' in text
    assert 'laid down 1910 (Engine 1905)' in text
    assert design['notes'] in text
    rtf = sps_report.serialize(result, format='ssr')
    assert rtf.startswith('{\\rtf1')
    assert '\\{' in rtf and '\\\\' in rtf and '\\u' in rtf
    assert rtf == sps_report.serialize(result, format='rtf')
