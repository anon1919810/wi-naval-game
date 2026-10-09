"""Two real database transactions compete at their final UPDATE statement."""
from datetime import timedelta
import uuid

import pytest
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker

from plimsoll import analysis
from plimsoll_web import runs, worker
from plimsoll_web.models import CalculationRun


@pytest.mark.parametrize('entrypoint', ['api', 'worker'])
@pytest.mark.parametrize('first', ['recovery', 'worker'])
def test_terminal_winner_cannot_be_overwritten(alice, project_id, engine, monkeypatch, entrypoint, first):
    response = alice.post(f'/api/projects/{project_id}/runs', json={
        'revision': 1, 'condition_id': 'loaded', 'options': {'stages': ['loading']}})
    assert response.status_code == 202
    identity = uuid.UUID(response.json()['id'])
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as db:
        row = worker.claim_next_run(db)
        assert row.id == identity
        owner = row.owner_id
        lease = row.lease_expires_at
        payload = analysis.compute_project(row.input_snapshot, row.condition_id, row.request['options'])
    clock = {'now': lease-timedelta(seconds=1)}
    monkeypatch.setattr(worker, 'utc_now', lambda: clock['now'])
    monkeypatch.setattr(runs, 'utc_now', lambda: clock['now'])
    monkeypatch.setattr(worker, '_run_bounded', lambda *_: ('result', payload))
    gate = {'armed': True, 'hits': 0}

    def recover():
        if entrypoint == 'worker':
            worker.recover_expired_runs(factory)
        else:
            with factory.begin() as db:
                runs._expire_lost_runs(db, owner)

    def before_update(_conn, _cursor, sql, _params, _context, _many):
        if not gate['armed'] or not sql.lstrip().upper().startswith('UPDATE CALCULATION_RUNS '):
            return
        gate['armed'] = False
        gate['hits'] += 1
        if first == 'recovery':
            clock['now'] = lease+timedelta(seconds=1)
            recover()
        else:
            worker.execute_run(identity, factory)

    event.listen(engine, 'before_cursor_execute', before_update)
    try:
        if first == 'recovery':
            worker.execute_run(identity, factory)
        else:
            clock['now'] = lease+timedelta(seconds=1)
            recover()
    finally:
        event.remove(engine, 'before_cursor_execute', before_update)
    assert gate['hits'] == 1
    with factory() as db:
        row = db.get(CalculationRun, identity)
        assert row.lease_expires_at is None
        assert row.finished_at is not None
        if first == 'recovery':
            assert row.status == 'failed'
            assert row.result is None
            assert row.error['code'] == 'run.worker_lost'
        else:
            assert row.status == 'completed'
            assert row.result['status'] == 'completed'
            assert row.error is None
