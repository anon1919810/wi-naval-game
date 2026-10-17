import copy
import json
from pathlib import Path
import subprocess
import sys
import os
import pytest
from plimsoll import analysis, loading, exports, sps_compat, sps_file_io

ROOT=Path(__file__).resolve().parents[3]

def project():
    data=json.loads((ROOT/'tools/plimsoll/cases/projects/analytic_box.project.json').read_text(encoding='utf-8-sig'))
    data['sps_3b3_design']=json.loads((Path(__file__).parent/'fixtures/sps3b3-synthetic.json').read_text(encoding='utf-8-sig'))
    return data


def test_sps_default_stage_is_independent_and_exports_the_frozen_report(monkeypatch):
    document=project();before=copy.deepcopy(document)
    monkeypatch.setattr(loading,'resolve_loading',lambda *a,**k:pytest.fail('SPS invoked physical loading'))
    result=analysis.compute_project(document,'loaded')
    assert result['status']=='completed',result['diagnostics']
    assert result['request']['options']['stages']==['sps_compat']
    assert result['stages']['loading']['status']=='not_requested'
    data=result['stages']['sps_compat']['data']
    assert data['report']['text']==exports.serialize_report(result,'txt')
    data['report']['text']='Frozen report 中文\n'
    data['design']['parameters']['ship_name']='A later name cannot change this report'
    assert exports.serialize_report(result,'txt')=='Frozen report 中文\n'
    assert exports.serialize_report(result,'ssr').startswith('{\\rtf1')
    assert sps_file_io.loads(exports.serialize_report(result,'sship').encode())['parameters']['ship_name']=='A later name cannot change this report'
    assert not any(d.get('message','').startswith("{'code':") for d in result['diagnostics'])
    assert document==before


def test_every_effective_source_field_has_a_working_typed_edit_route():
    from plimsoll import sps_field_catalog
    design=project()['sps_3b3_design']
    refused=[]
    for name in sps_field_catalog.catalog()['fields']:
        reply=sps_compat.apply_edit(design,dict(kind='set_parameter',name=name,value=design['parameters'][name]))
        errors=[d for d in reply['diagnostics'] if d.get('severity')=='error']
        if errors:refused.append((name,errors))
    assert not refused


def test_cli_can_export_sps_formats_and_refuses_input_alias(tmp_path):
    source=tmp_path/'source.project.json';source.write_text(json.dumps(project()),encoding='utf-8')
    output=tmp_path/'result.json';text=tmp_path/'report.txt';native=tmp_path/'design.sship'
    environment=dict(os.environ,PYTHONPATH=str(ROOT/'tools'))
    command=[sys.executable,'-B','-m','plimsoll','analyze',str(source),'--condition','loaded','--output',str(output),'--txt',str(text),'--sship',str(native)]
    completed=subprocess.run(command,cwd=ROOT,env=environment,capture_output=True,text=True)
    assert completed.returncode==0,completed.stderr
    assert 'Recoil' in text.read_text(encoding='utf-8')
    assert sps_file_io.loads(native.read_bytes())['parameters']['length_waterline']==180
    original=source.read_bytes()
    refused=subprocess.run(command[:-1]+[str(source)],cwd=ROOT,env=environment,capture_output=True,text=True)
    assert refused.returncode!=0 and 'cli.output_alias' in refused.stderr
    assert source.read_bytes()==original
