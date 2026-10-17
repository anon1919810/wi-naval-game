import base64
import json
from pathlib import Path
from plimsoll import analysis, sps_file_io

def declaration():
    root=Path(__file__).resolve().parents[3]
    return json.loads((root/'tools/plimsoll/tests/fixtures/sps3b3-synthetic.json').read_text(encoding='utf-8-sig'))


def test_preview_auth_csrf_catalog_and_source_import_are_pure(client,alice,project_id):
    assert client.get('/api/sps3b3/catalog').status_code==401
    catalog=alice.get('/api/sps3b3/catalog')
    assert catalog.status_code==200 and len(catalog.json()['fields'])==222
    before=alice.get(f'/api/projects/{project_id}').json()
    design=declaration()
    response=alice.post('/api/sps3b3/preview',json={'design':design,'command':{'kind':'set_parameter','name':'ship_name','value':'修改的设计'}})
    assert response.status_code==200,response.text
    assert response.json()['design']['parameters']['ship_name']=='修改的设计'
    native=sps_file_io.dumps(design)
    imported=alice.post('/api/sps3b3/import-preview',json={'filename':'test.sship','content_base64':base64.b64encode(native).decode()})
    assert imported.status_code==200,imported.text
    assert imported.json()['design']['parameters']['length_waterline']==180
    token=alice.headers.pop('X-CSRF-Token')
    try:assert alice.post('/api/sps3b3/preview',json={'design':design}).status_code==403
    finally:alice.headers['X-CSRF-Token']=token
    assert alice.get(f'/api/projects/{project_id}').json()==before


def test_saved_run_exports_are_owned_and_do_not_recompute_newer_project(alice,bob,project_id,worker_once,monkeypatch):
    project=alice.get(f'/api/projects/{project_id}').json()['project']
    project['sps_3b3_design']=declaration()
    saved=alice.put(f'/api/projects/{project_id}',json={'base_revision':1,'project':project})
    assert saved.status_code==200,saved.text
    queued=alice.post(f'/api/projects/{project_id}/runs',json={'revision':2,'condition_id':'loaded','options':{}})
    assert queued.status_code==202,queued.text
    run_id=queued.json()['id'];assert worker_once()
    result=alice.get(f'/api/runs/{run_id}').json()
    assert result['status']=='completed',result
    project['sps_3b3_design']['parameters']['ship_name']='New revision only'
    assert alice.put(f'/api/projects/{project_id}',json={'base_revision':2,'project':project}).status_code==200
    monkeypatch.setattr(analysis,'compute_project',lambda *a,**k:(_ for _ in ()).throw(AssertionError('export recomputed')))
    for format in ('txt','rtf','ssr','sship'):
        assert bob.get(f'/api/runs/{run_id}/export?format={format}').status_code==404
        response=alice.get(f'/api/runs/{run_id}/export?format={format}')
        assert response.status_code==200,response.text
        assert 'New revision only' not in response.text
        if format in ('ssr','rtf'):assert response.text.startswith('{\\rtf1')
        if format=='sship':assert sps_file_io.loads(response.content)['parameters']['length_waterline']==180
