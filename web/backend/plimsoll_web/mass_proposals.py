"""Apply a reviewed proposal batch from one saved run, as exactly one revision.

The client never says *which* calculation its proposals came from: it names a
saved run, and this module reads the normalized request **out of that run row**.
The submitted ``current_options`` are normalized again here, against the saved
document of the base revision, and the two normalized requests must be equal.
That comparison is the whole point: a browser assembling a request from GUI
choices sends something structurally different from the normalized, default-rich
options the server stored, so raw structural equality would refuse every real
client. Normalizing both sides first compares *meaning*, and a request that
genuinely differs — another stage list, another environment density — is refused.

Everything after that is the core's decision. ``apply_mass_proposals``
recomputes every proposal from one unchanged snapshot of the saved revision and
writes the batch atomically or not at all, so a stale, forged, foreign,
duplicated or empty batch never reaches the ledger.
"""

from __future__ import annotations

import copy
from typing import Any, TypedDict
import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from plimsoll import _analysis_request, analysis

from .models import ProjectRevision
from .projects import RevisionConflict, owned_project, save_project
from .runs import owned_run

# The same two statuses the worker writes a payload for.
RESULT_RUN_STATUSES = frozenset({"completed", "partial"})


class MassProposalView(TypedDict):
    """The saved project after the batch, with the accepted changes."""

    project_id: str
    revision: int
    project: dict
    changes: list[dict]


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=409, detail=detail)


def _saved_run_request(db: Session, owner_id: uuid.UUID, project_id: uuid.UUID,
                       base_revision: int, current_revision: int, run_id: uuid.UUID,
                       condition_id: str):
    """The run this apply is allowed to use, checked against every identity.

    Ownership is enforced by :func:`owned_run`, which also refuses a run this
    account does not own *and* a row that is not an analysis request at all, so a
    damage-laboratory run is simply not found here. Everything else is checked
    against the project being written: the run's project, its revision and its
    loading condition must all be the ones the reader is applying against.
    """
    run = owned_run(db, owner_id, run_id)
    if str(run.project_id) != str(project_id):
        raise _conflict("that run belongs to another project")
    if run.revision != base_revision:
        # The reader is naming a run of an older revision. Report the revision
        # that actually holds the project, so the reload they need is the one
        # the conflict names.
        raise RevisionConflict(current_revision)
    if run.condition_id != condition_id:
        raise _conflict("that run used another loading condition")
    if run.status not in RESULT_RUN_STATUSES or run.result is None:
        raise _conflict("that run has no stored analysis result")
    return copy.deepcopy(run.request)


def _normalized_request(document: dict, condition_id: str, options: dict) -> dict:
    """Normalize the client's options on the server, against the saved document."""
    try:
        _, request, _ = _analysis_request.normalize(document, condition_id, options)
    except _analysis_request.AnalysisInputError as error:
        raise HTTPException(status_code=422, detail=error.diagnostics) from error
    return request


def apply_selected(
    owner_id: uuid.UUID, project_id: uuid.UUID, base_revision: int, run_id: uuid.UUID,
    condition_id: str, current_options: dict, proposals: list[dict], db: Session,
) -> MassProposalView:
    """Apply one explicit batch and save exactly one new revision."""
    project = owned_project(db, owner_id, project_id)
    if project.current_revision != base_revision:
        raise RevisionConflict(project.current_revision)
    saved = db.get(ProjectRevision, (project_id, base_revision))
    if saved is None:
        raise HTTPException(status_code=422, detail="that revision is not stored")
    request = _saved_run_request(db, owner_id, project_id, base_revision,
                                 project.current_revision, run_id, condition_id)
    submitted = _normalized_request(saved.document, condition_id, current_options)
    if submitted != request:
        raise _conflict("these calculation options are not the ones that run used")
    try:
        applied: dict[str, Any] = analysis.apply_mass_proposals(
            saved.document, condition_id, proposals, current_request=request)
    except _analysis_request.AnalysisInputError as error:
        # Stale, forged, foreign, duplicated, ambiguous or empty: the core refused
        # before anything was written, and nothing here has touched the database.
        raise HTTPException(status_code=422, detail=error.diagnostics) from error
    # The batch is already validated against the unchanged snapshot; saving it is
    # the ordinary optimistic save, so a second writer still cannot be overwritten.
    view = save_project(owner_id, project_id, base_revision, applied["project"], db)
    return {**view, "changes": applied["changes"]}