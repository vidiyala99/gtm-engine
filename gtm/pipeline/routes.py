"""GTM run API (lane A). Mounted by gtm/plugin.py.

POST /api/gtm/runs                              Intake body -> {"id"}; the pipeline runs in the background
GET  /api/gtm/runs/{id}                         the run as it stands (poll it to watch it fill)
POST /api/gtm/runs/{id}/expansions/{i}          {"status": "accepted"|"adjusted"|"dismissed", "segment"?, "note"?}
POST /api/gtm/runs/{id}/drafts/{draft_id}       {"action": "approve"|"reject"|"edit", "body"?, "subject"?, "note"?}
POST /api/gtm/runs/{id}/leads/{company_id}      {"stage": Stage, "person_id"?}

Every change a person makes here is an AuditEvent with actor="rep".
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from gtm.contract import AuditEvent, Intake, Lead, Run, Stage
from gtm.pipeline import runner, store

router = APIRouter()


def now() -> datetime:
    return datetime.now(timezone.utc)


def rep_event(action: str, target: str, detail: str = "") -> AuditEvent:
    return AuditEvent(at=now(), actor="rep", agent="rep", action=action, target=target, detail=detail)


class ExpansionDecision(BaseModel):
    status: Literal["accepted", "adjusted", "dismissed"]
    segment: str = ""  # the rep's rewording, for "adjusted"
    note: str = ""


class DraftDecision(BaseModel):
    action: Literal["approve", "reject", "edit"]
    body: str = ""
    subject: str | None = None
    note: str = ""


class StageMove(BaseModel):
    stage: Stage
    person_id: str = ""


def _load_or_404(run_id: str) -> Run:
    try:
        return store.load(run_id)
    except store.RunNotFound:
        raise HTTPException(404, f"no run {run_id}")


def _update(run_id: str, change) -> Run:
    try:
        return store.update(run_id, change)
    except store.RunNotFound:
        raise HTTPException(404, f"no run {run_id}")


@router.post("/api/gtm/runs")
async def start_run(intake: Intake):
    run_id = "run_" + now().strftime("%Y%m%d%H%M%S") + "_" + secrets.token_hex(3)
    run = Run(id=run_id, created_at=now(), intake=intake,
              audit=[AuditEvent(at=now(), actor="rep", agent="rep", action="intake_submitted", target=run_id,
                                detail=intake.product)])
    store.save(run)
    runner.start(run_id)
    return {"id": run_id}


@router.get("/api/gtm/runs")
async def list_runs():
    return {"ids": [i for i in store.list_ids()]}


@router.get("/api/gtm/runs/{run_id}")
async def get_run(run_id: str):
    if run_id == "fixture":  # served by gtm.fixture_routes; keep this route from shadowing it
        from gtm.fixture_routes import load_fixture
        return load_fixture().model_dump(mode="json")
    return _load_or_404(run_id).model_dump(mode="json")


@router.post("/api/gtm/runs/{run_id}/expansions/{i}")
async def decide_expansion(run_id: str, i: int, decision: ExpansionDecision):
    def change(run: Run):
        if run.icp is None or not 0 <= i < len(run.icp.expansions):
            raise HTTPException(404, f"no expansion {i}")
        exp = run.icp.expansions[i]
        before = exp.segment
        exp.status = decision.status
        if decision.status == "adjusted" and decision.segment.strip():
            exp.segment = decision.segment.strip()
        detail = f"{before} -> {exp.segment}" if exp.segment != before else before
        if decision.note:
            detail += f" ({decision.note})"
        run.audit.append(rep_event(f"expansion_{decision.status}", f"expansion:{i}", detail))
    return _update(run_id, change).model_dump(mode="json")


@router.post("/api/gtm/runs/{run_id}/drafts/{draft_id}")
async def decide_draft(run_id: str, draft_id: str, decision: DraftDecision):
    def change(run: Run):
        draft = next((d for d in run.drafts if d.id == draft_id), None)
        if draft is None:
            raise HTTPException(404, f"no draft {draft_id}")
        if draft.status == "sent":
            raise HTTPException(409, "draft already sent")
        if decision.action == "edit":
            if not decision.body.strip():
                raise HTTPException(422, "an edit needs a body")
            draft.body = decision.body
            if decision.subject is not None:
                draft.subject = decision.subject
            draft.status = "pending"  # an edit never approves; it goes back to the queue
            action = "draft_edited"
        else:
            draft.status = "approved" if decision.action == "approve" else "rejected"
            action = f"draft_{draft.status}"
        if decision.note:
            draft.review_notes.append(f"rep: {decision.note}")
        run.audit.append(rep_event(action, f"draft:{draft_id}", decision.note))
    return _update(run_id, change).model_dump(mode="json")


@router.post("/api/gtm/runs/{run_id}/leads/{company_id}")
async def move_lead(run_id: str, company_id: str, move: StageMove):
    def change(run: Run):
        if not any(c.id == company_id for c in run.companies):
            raise HTTPException(404, f"no company {company_id}")
        lead = next((l for l in run.leads if l.company_id == company_id), None)
        if lead is None:
            lead = Lead(company_id=company_id)
            run.leads.append(lead)
        before = lead.stage
        lead.stage = move.stage
        if move.person_id:
            lead.person_id = move.person_id
        run.audit.append(rep_event("lead_moved", f"company:{company_id}", f"{before} -> {move.stage}"))
    return _update(run_id, change).model_dump(mode="json")
