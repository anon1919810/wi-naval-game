"""Cross-account browser contract, immutable runs, restart and local test mail."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
import pytest

from plimsoll_web.config import Settings
from plimsoll_web.mailer import ConsoleMailer, MailUnavailable, mailer_from_settings
from plimsoll_web.main import create_app


def test_two_user_saved_queen_mary_run_survives_restart(alice, bob, engine, worker_once):
    created = alice.post('/api/projects', json={'template': 'queen_mary_1913', 'name': 'HMS Queen Mary'})
    assert created.status_code == 201
    project_id = created.json()['project_id']
    original = created.json()['project']
    assert bob.get(f'/api/projects/{project_id}').status_code == 404
    assert bob.put(f'/api/projects/{project_id}', json={'base_revision': 1, 'project': original}).status_code == 404

    edited = json.loads(json.dumps(original))
    edited['name'] = 'HMS Queen Mary — research copy'
    saved = alice.put(f'/api/projects/{project_id}', json={'base_revision': 1, 'project': edited})
    assert saved.status_code == 200
    assert saved.json()['revision'] == 2
    assert alice.put(f'/api/projects/{project_id}', json={'base_revision': 1, 'project': edited}).status_code == 409

    queued = alice.post(f'/api/projects/{project_id}/runs', json={
        'revision': 2, 'condition_id': 'normal-engineering', 'options': {'stages': ['loading']},
    })
    assert queued.status_code == 202
    run_id = queued.json()['id']
    assert bob.post(f'/api/projects/{project_id}/runs', json={
        'revision': 2, 'condition_id': 'normal-engineering', 'options': {'stages': ['loading']},
    }).status_code == 404
    assert worker_once() is True
    finished = alice.get(f'/api/runs/{run_id}').json()
    assert finished['result']['schema'] == 'plimsoll-analysis-1'
    assert finished['result']['input_snapshot']['revision'] == 2
    assert finished['result']['request_fingerprint'] == queued.json()['request_fingerprint']
    assert bob.get(f'/api/runs/{run_id}').status_code == 404
    assert bob.get(f'/api/runs/{run_id}/export?format=json').status_code == 404

    restarted = create_app(Settings(database_url=str(engine.url), secret_key='test-secret-only',
                                    allowed_origins=('http://testserver',), allow_insecure_cookies=True))
    with TestClient(restarted) as browser:
        browser.cookies.update(alice.cookies)
        after = browser.get(f'/api/runs/{run_id}')
        assert after.status_code == 200
        assert after.json()['result']['request_fingerprint'] == finished['result']['request_fingerprint']
        exported = browser.get(f'/api/runs/{run_id}/export?format=json')
        assert exported.status_code == 200
        assert exported.json()['request_fingerprint'] == after.json()['result']['request_fingerprint']
        assert after.json()['result']['input_snapshot']['name'] == 'HMS Queen Mary — research copy'


@pytest.mark.parametrize('template,condition', [
    ('analytic_box', 'loaded'), ('generic_steamer', 'coastal'),
])
def test_other_reference_cases_can_run_loading(alice, worker_once, template, condition):
    created = alice.post('/api/projects', json={'template': template, 'name': template})
    assert created.status_code == 201
    project_id = created.json()['project_id']
    queued = alice.post(f'/api/projects/{project_id}/runs', json={
        'revision': 1, 'condition_id': condition, 'options': {'stages': ['loading']},
    })
    assert queued.status_code == 202
    assert worker_once() is True
    result = alice.get(f"/api/runs/{queued.json()['id']}").json()['result']
    assert result['request_fingerprint'] == queued.json()['request_fingerprint']


def test_local_mail_requires_explicit_loopback_only_mode():
    base = dict(database_url='sqlite:///local.db', secret_key='local-secret',
                allowed_origins=('http://127.0.0.1:5173',), allow_insecure_cookies=True,
                local_mail_test=True)
    assert isinstance(mailer_from_settings(Settings(**base)), ConsoleMailer)
    with pytest.raises(MailUnavailable):
        mailer_from_settings(Settings(**{**base, 'allowed_origins': ('http://example.com',)}))
    with pytest.raises(MailUnavailable):
        mailer_from_settings(Settings(**{**base, 'allow_insecure_cookies': False}))
