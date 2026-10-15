"""The reviewed batch workflow: one saved run in, exactly one new revision out."""

from __future__ import annotations

import copy
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from plimsoll_web.models import ProjectRevision
from plimsoll_web.projects import RevisionConflict, save_project

STAGES = ["loading", "systems", "design_balance"]


@pytest.fixture
def concept(alice, worker_once):
    """A real concept project with a real completed run behind it."""
    response = alice.post("/api/projects", json={"template": "concept_cruiser",
                                                 "name": "concept cruiser"})
    assert response.status_code == 201
    project_id = response.json()["project_id"]
    queued = alice.post(f"/api/projects/{project_id}/runs", json={
        "revision": 1, "condition_id": "normal", "options": {"stages": STAGES}})
    assert queued.status_code == 202
    worker_once()
    run = alice.get(f"/api/runs/{queued.json()['id']}").json()
    assert run["status"] == "completed"
    return project_id, run


def proposals_of(run, item_ids):
    """The stored proposals for these items, exactly as the result presented them."""
    rows = (run["result"]["stages"]["systems"]["data"] or {})["update_proposals"]
    return [row for row in rows if row["item_id"] in item_ids]


def apply(alice, project_id, run, proposals, **overrides):
    body = {"base_revision": run["revision"], "run_id": run["id"],
            "condition_id": run["condition_id"],
            "current_options": {"stages": STAGES}, "proposals": proposals}
    body.update(overrides)
    return alice.post(f"/api/projects/{project_id}/mass-proposals", json=body)


def revision_count(alice, project_id):
    return alice.get(f"/api/projects/{project_id}").json()["revision"]


# --- the happy path ----------------------------------------------------------

def test_applies_one_batch_and_saves_exactly_one_revision(alice, concept):
    project_id, run = concept
    chosen = proposals_of(run, ["weapons.guns", "weapons.mounts", "weapons.ammunition"])
    assert len(chosen) == 3
    response = apply(alice, project_id, run, chosen)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["revision"] == 2
    assert len(body["changes"]) == 3
    condition = next(c for c in body["project"]["loading_conditions"] if c["id"] == "normal")
    # One batch, three writes, one revision: nothing else moved.
    assert set(condition["overrides"]) == {"weapons.guns", "weapons.mounts", "weapons.ammunition"}
    assert revision_count(alice, project_id) == 2


def test_accepted_empirical_provenance_is_labelled_as_an_estimate(alice, concept):
    project_id, run = concept
    body = apply(alice, project_id, run, proposals_of(run, ["weapons.guns"])).json()
    change = body["changes"][0]
    assert change["source"]["method"] == "accepted_selected_condition_empirical_estimate"
    assert change["source"]["source_sha256"]
    provenance = next(c for c in body["project"]["loading_conditions"] if c["id"] == "normal")
    assert provenance["override_provenance"]["weapons.guns"]["mass_t"]["estimate"] is True


def test_real_worker_computes_applies_and_recomputes(alice, concept, worker_once):
    """The workflow the reader actually performs: compute, apply, recompute."""
    project_id, run = concept
    before = proposals_of(run, ["weapons.guns"])
    first_demand = (run["result"]["stages"]["design_balance"]["data"] or {})["values"][
        "structure_demand_long_tons"]
    assert apply(alice, project_id, run, before).status_code == 200
    queued = alice.post(f"/api/projects/{project_id}/runs", json={
        "revision": 2, "condition_id": "normal", "options": {"stages": STAGES}})
    assert queued.status_code == 202
    worker_once()
    after_run = alice.get(f"/api/runs/{queued.json()['id']}").json()
    assert after_run["status"] == "completed"
    assert after_run["revision"] == 2
    # The accepted estimate is now the ledger's own mass for that condition, so
    # the same item is no longer a pending change...
    assert proposals_of(after_run, ["weapons.guns"]) == []
    assert next(c for c in alice.get(f"/api/projects/{project_id}").json()["project"]["loading_conditions"]
                if c["id"] == "normal")["overrides"]["weapons.guns"]["mass_t"] == pytest.approx(
        before[0]["proposed_mass_t"])
    # ...and the recomputation is its own result, not a claim of convergence:
    # the structural screen still has a live demand and its own shortfall.
    balance = (after_run["result"]["stages"]["design_balance"]["data"] or {})
    assert balance["status"] in {"completed", "partial"}
    assert balance["values"]["structure_demand_long_tons"] is not None
    assert balance["values"]["structure_demand_long_tons"] != pytest.approx(first_demand) \
        or balance["design_warnings"]


# --- the normalized-options comparison ---------------------------------------

def test_gui_assembled_options_are_normalized_before_they_are_compared(alice, worker_once):
    """Raw GUI options are not the normalized request, and must still be accepted."""
    response = alice.post("/api/projects", json={"template": "concept_cruiser", "name": "c"})
    project_id = response.json()["project_id"]
    queued = alice.post(f"/api/projects/{project_id}/runs", json={
        "revision": 1, "condition_id": "normal", "options": {}})
    worker_once()
    run = alice.get(f"/api/runs/{queued.json()['id']}").json()
    # The stored request is default-rich; this is a differently written but
    # equivalent assembly of the very same request.
    equivalent = {"stages": ["propulsion", "deck", "hydrostatics", "equilibrium",
                             "geometry", "l0", "systems", "loading"],
                  "equilibrium": {"rho_t_m3": 1.025}}
    body = apply(alice, project_id, run, proposals_of(run, ["weapons.guns"]),
                 current_options=equivalent)
    assert body.status_code == 200, body.text


def test_options_that_mean_something_else_are_refused(alice, concept):
    project_id, run = concept
    body = apply(alice, project_id, run, proposals_of(run, ["weapons.guns"]),
                 current_options={"stages": ["loading", "systems"]})
    assert body.status_code == 409
    assert revision_count(alice, project_id) == 1


def test_invalid_options_are_refused_with_diagnostics(alice, concept):
    project_id, run = concept
    body = apply(alice, project_id, run, proposals_of(run, ["weapons.guns"]),
                 current_options={"stages": ["not_a_stage"]})
    assert body.status_code == 422
    assert body.json()["detail"][0]["path"] == "$.options.stages"
    assert revision_count(alice, project_id) == 1


# --- authorization ----------------------------------------------------------

def test_another_account_cannot_apply_to_this_project(alice, bob, concept):
    project_id, run = concept
    assert bob.post(f"/api/projects/{project_id}/mass-proposals", json={
        "base_revision": run["revision"], "run_id": run["id"],
        "condition_id": run["condition_id"], "current_options": {"stages": STAGES},
        "proposals": proposals_of(run, ["weapons.guns"])}).status_code == 404
    assert revision_count(alice, project_id) == 1


def test_a_write_without_the_csrf_token_is_refused(alice, concept, monkeypatch):
    project_id, run = concept
    monkeypatch.setitem(alice.headers, "x-csrf-token", "not-the-session-token")
    assert apply(alice, project_id, run, proposals_of(run, ["weapons.guns"])).status_code == 403
    assert revision_count(alice, project_id) == 1


def test_a_signed_out_reader_is_refused(alice, concept):
    project_id, run = concept
    alice.cookies.clear()
    assert apply(alice, project_id, run, proposals_of(run, ["weapons.guns"])).status_code == 401


# --- identity of the run ----------------------------------------------------

def test_a_run_from_another_condition_is_refused(alice, concept, worker_once):
    project_id, run = concept
    other = alice.post(f"/api/projects/{project_id}/runs", json={
        "revision": 1, "condition_id": "deep", "options": {"stages": STAGES}})
    worker_once()
    assert apply(alice, project_id, run, proposals_of(run, ["weapons.guns"]),
                 run_id=other.json()["id"]).status_code == 409
    assert revision_count(alice, project_id) == 1


def test_a_run_from_an_older_revision_is_refused(alice, concept, worker_once):
    project_id, run = concept
    chosen = proposals_of(run, ["weapons.guns"])
    first = apply(alice, project_id, run, chosen)
    assert first.status_code == 200, first.text
    # The saved run still describes revision 1, which is no longer the base.
    body = apply(alice, project_id, run, chosen, base_revision=2)
    assert body.status_code == 409
    assert body.json()["current_revision"] == 2


def test_a_stale_base_revision_is_refused(alice, concept, worker_once):
    project_id, run = concept
    worker_once()
    assert apply(alice, project_id, run, proposals_of(run, ["weapons.guns"]),
                 base_revision=7).status_code == 409


def test_an_unknown_run_is_not_found(alice, concept):
    project_id, run = concept
    assert apply(alice, project_id, run, proposals_of(run, ["weapons.guns"]),
                 run_id=str(uuid.uuid4())).status_code == 404


# --- the batch itself --------------------------------------------------------

def test_an_empty_batch_is_refused(alice, concept):
    project_id, run = concept
    body = apply(alice, project_id, run, [])
    assert body.status_code == 422
    assert body.json()["detail"][0]["code"] == "analysis.proposal_empty"
    assert revision_count(alice, project_id) == 1


def test_a_forged_proposed_mass_is_refused(alice, concept):
    project_id, run = concept
    forged = copy.deepcopy(proposals_of(run, ["weapons.guns"]))
    forged[0]["proposed_mass_t"] = 1.0
    body = apply(alice, project_id, run, forged)
    assert body.status_code == 422
    assert body.json()["detail"][0]["code"] == "analysis.proposal_forged"
    assert revision_count(alice, project_id) == 1


def test_a_foreign_source_model_is_refused(alice, concept):
    project_id, run = concept
    forged = copy.deepcopy(proposals_of(run, ["weapons.guns"]))
    forged[0]["source_model_id"] = "concept.machinery"
    body = apply(alice, project_id, run, forged)
    assert body.status_code == 422
    assert body.json()["detail"][0]["code"] == "analysis.proposal_forged"


def test_two_proposals_for_one_item_are_refused(alice, concept):
    project_id, run = concept
    one = proposals_of(run, ["weapons.guns"])[0]
    body = apply(alice, project_id, run, [one, copy.deepcopy(one)])
    assert body.status_code == 422
    assert body.json()["detail"][0]["code"] == "analysis.proposal_duplicate"
    assert revision_count(alice, project_id) == 1


def test_a_partly_valid_batch_writes_nothing(alice, concept):
    project_id, run = concept
    good = copy.deepcopy(proposals_of(run, ["weapons.guns"]))
    bad = copy.deepcopy(proposals_of(run, ["weapons.mounts"]))
    bad[0]["proposed_mass_t"] = 3.0
    body = apply(alice, project_id, run, good + bad)
    assert body.status_code == 422
    assert revision_count(alice, project_id) == 1
    conditions = alice.get(f"/api/projects/{project_id}").json()["project"]["loading_conditions"]
    # The other condition's own declaration is untouched, and the selected one
    # gained nothing at all: not even the entry that was valid on its own.
    normal = next(c for c in conditions if c["id"] == "normal")
    assert not normal.get("overrides") and not normal.get("override_provenance")


def test_an_item_that_is_not_proposed_at_all_is_refused(alice, concept):
    project_id, run = concept
    template = proposals_of(run, ["weapons.guns"])[0]
    invented = copy.deepcopy(template)
    invented["item_id"] = "armour.deck"
    assert apply(alice, project_id, run, [invented]).status_code == 422


# --- one writer at a time ---------------------------------------------------

def test_two_saves_from_one_base_revision_produce_one_revision(alice, concept):
    """Two independently loaded sessions, one base revision, exactly one winner.

    Both sessions read the project while it is still at revision 1 and both hold
    their own edit of it. The conditional write — not a lock, and not the order
    the two requests happen to arrive in — is what decides, and the loser must
    answer as a lost update with no revision written and no server fault.
    """
    project_id, _ = concept
    project_uuid = uuid.UUID(project_id)
    factory = alice.app.state.session_factory
    loaded = []
    for name in ("first tab", "second tab"):
        with factory() as db:
            owner = _owner_id(db, project_uuid)
            loaded.append((db, owner, _named(alice, project_id, name)))
    try:
        with loaded[0][0] as db:
            accepted = save_project(loaded[0][1], project_uuid, 1, loaded[0][2], db)
        assert accepted["revision"] == 2
        assert accepted["project"]["name"] == "first tab"
        with pytest.raises(RevisionConflict) as conflict:
            save_project(loaded[1][1], project_uuid, 1, loaded[1][2], loaded[1][0])
        assert conflict.value.current_revision == 2
    finally:
        for db, _, _ in loaded:
            db.close()
    with factory() as db:
        rows = db.scalars(select(ProjectRevision).where(
            ProjectRevision.project_id == project_uuid).order_by(ProjectRevision.revision)).all()
        # One immutable revision was added, and it is the winner's document.
        assert [row.revision for row in rows] == [1, 2]
        assert rows[-1].document["name"] == "first tab"
        assert _owner_id(db, project_uuid) is not None
    saved = alice.get(f"/api/projects/{project_id}").json()
    assert saved["revision"] == 2
    assert saved["project"]["name"] == "first tab"


def test_a_losing_apply_answers_a_conflict_and_keeps_the_winner_document(alice, concept):
    """The same race through HTTP: 409, and the accepted apply's revision stands."""
    project_id, run = concept
    chosen = proposals_of(run, ["weapons.guns"])
    accepted = apply(alice, project_id, run, chosen)
    assert accepted.status_code == 200
    winner = accepted.json()["project"]
    # Another browser now saves, so this one is behind by one revision.
    other = alice.post("/api/projects", json={"template": "analytic_box", "name": "b"}).json()
    assert alice.put(f"/api/projects/{other['project_id']}", json={
        "base_revision": other["revision"], "project": other["project"]}).status_code == 200
    # This browser still holds revision 1 and tries to apply against it.
    body = apply(alice, project_id, run, chosen, base_revision=1)
    assert body.status_code == 409
    assert body.json()["current_revision"] == 2
    saved = alice.get(f"/api/projects/{project_id}").json()
    assert saved["revision"] == 2
    assert saved["project"]["name"] == winner["name"]


def test_a_rejected_save_leaves_no_unreachable_revision(alice, concept):
    project_id, _ = concept
    factory = alice.app.state.session_factory
    project_uuid = uuid.UUID(project_id)
    with factory() as db:
        owner = _owner_id(db, project_uuid)
    with factory() as db:
        save_project(owner, project_uuid, 1, _named(alice, project_id, "first tab"), db)
    forged = _named(alice, project_id, "second tab")
    forged["schema"] = "not-plimsoll-project-1"
    with factory() as db:
        with pytest.raises(HTTPException) as refusal:
            save_project(owner, project_uuid, 2, forged, db)
    assert refusal.value.status_code == 422
    with factory() as db:
        rows = db.scalars(select(ProjectRevision).where(
            ProjectRevision.project_id == project_uuid)).all()
        assert [row.revision for row in rows] == [1, 2]


def _named(browser, project_id, name):
    document = copy.deepcopy(browser.get(f"/api/projects/{project_id}").json()["project"])
    document["name"] = name
    return document


def _owner_id(db, project_id):
    from plimsoll_web.models import Project

    return db.scalar(select(Project).where(Project.id == project_id)).owner_id