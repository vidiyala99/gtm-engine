"""Lane B BAND room: the review flow's rules, with a scripted model standing in for Claude."""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gtm.band import agents, routes
from gtm.band.model import Reply
from gtm.band.room import CAST, ReviewRoom
from gtm.band.transport import MockBand, parse_verdict
from gtm.contract import can_send
from gtm.graph import runs
from gtm.graph.runs import load_run, save_run

UNSUPPORTED = "Teams at that stage usually inherit a report backlog nobody owns."


class Scripted:
    """A model whose decisions the test chooses. Records every call."""

    def __init__(self, reviewer="approve", security="pass", builder_claims=None, unsupported=(), silent=()):
        self.reviewer, self.security = reviewer, security
        self.builder_claims = builder_claims
        self.unsupported = list(unsupported)
        self.silent = set(silent)
        self.calls: list[str] = []

    async def __call__(self, agent: str, prompt: str) -> Reply:
        self.calls.append(agent)
        if agent in self.silent:
            return Reply(text="", data=None)
        data = {
            "planner": {"handoff": "Acme is hiring 3 analytics engineers (sig_1); lead with that.",
                        "focus_signal_ids": ["sig_1"]},
            "builder": {"note": "Posting d_1 as written.", "claims": self.builder_claims if self.builder_claims
                        is not None else [{"text": "Acme is hiring three analytics engineers", "signal_id": "sig_1"}]},
            "reviewer": {"verdict": self.reviewer, "reason": "checked against sig_1",
                         "claims": [{"claim": "Acme is hiring three analytics engineers", "signal_id": "sig_1",
                                     "supported": True, "reason": "careers page"}]
                         + [{"claim": c, "signal_id": None, "supported": False, "reason": "no signal says this"}
                            for c in self.unsupported]},
            "security": {"verdict": self.security, "issues": [] if self.security == "pass" else ["bad link"],
                         "reason": "clean" if self.security == "pass" else "unsafe link"},
        }[agent]
        return Reply(text=json.dumps(data), data=data, tokens=1000, cost_usd=0.01, model="scripted")


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(runs, "OVERLAY", tmp_path / "runs")
    monkeypatch.delenv("GTM_LINK_DOMAINS", raising=False)


def make_room(tmp_path, model) -> ReviewRoom:
    return ReviewRoom(model, band=MockBand(CAST), state_dir=tmp_path / "band")


def set_body(body: str, draft_id: str = "d_1") -> None:
    run = load_run("fixture")
    next(d for d in run.drafts if d.id == draft_id).body = body
    save_run(run)


def draft(draft_id: str = "d_1"):
    return next(d for d in load_run("fixture").drafts if d.id == draft_id)


def run_(coro):
    return asyncio.run(coro)


def test_reviewer_rejects_claim_without_signal(tmp_path):
    set_body(f"Dana, saw Acme is hiring three analytics engineers. {UNSUPPORTED}")
    model = Scripted(reviewer="reject", unsupported=[UNSUPPORTED])
    room = make_room(tmp_path, model)
    out = run_(room.review("fixture", "d_1"))
    assert out.state == "rejected"
    assert any("inherit a report backlog" in d for d in out.details)
    d = draft()
    assert d.status == "rejected" and not can_send(d)
    assert any(n.startswith("reviewer:") and "backlog" in n for n in d.review_notes)
    assert "security" not in model.calls  # rejected drafts stop at the reviewer
    assert not any("rep" in i.to for i in room.feed)  # the rep is never asked


def test_reviewer_approve_cannot_pass_a_claim_the_builder_left_unsourced(tmp_path):
    set_body(f"Dana, saw Acme is hiring three analytics engineers. {UNSUPPORTED}")
    model = Scripted(reviewer="approve", builder_claims=[
        {"text": "Acme is hiring three analytics engineers", "signal_id": "sig_1"},
        {"text": UNSUPPORTED, "signal_id": None}])
    out = run_(make_room(tmp_path, model).review("fixture", "d_1"))
    assert out.state == "rejected"
    assert draft().status == "rejected"


def test_draft_citing_another_companys_signal_is_rejected(tmp_path):
    run = load_run("fixture")
    next(d for d in run.drafts if d.id == "d_1").signal_ids = ["sig_2"]  # Globex's signal on an Acme draft
    save_run(run)
    out = run_(make_room(tmp_path, Scripted()).review("fixture", "d_1"))
    assert out.state == "rejected" and "sig_2" in " ".join(out.details)


def test_no_draft_reaches_approved_without_a_rep_message(tmp_path):
    room = make_room(tmp_path, Scripted())
    out = run_(room.review("fixture", "d_1"))
    assert out.state == "awaiting_rep"
    assert draft().status == "pending" and not can_send(draft())
    assert run_(room.poll_rep()) == []  # nobody replied: nothing changes
    assert draft().status == "pending"
    request = room.feed[-1]
    assert request.kind == "approval_request" and "rep" in request.to

    out = run_(room.rep_says("fixture", "d_1", "approve d_1"))
    assert out.state == "approved"
    assert draft().status == "approved" and can_send(draft())
    rep_events = [e for e in load_run("fixture").audit if e.actor == "rep" and e.target == "d_1"]
    assert [e.action for e in rep_events] == ["band.rep.approved"]


def test_rep_can_reject_and_rep_cannot_approve_a_reviewer_rejected_draft(tmp_path):
    room = make_room(tmp_path, Scripted())
    run_(room.review("fixture", "d_1"))
    assert run_(room.rep_says("fixture", "d_1", "reject d_1, too generic")).state == "rejected"
    assert draft().status == "rejected"

    set_body(f"Dana, saw Acme is hiring. {UNSUPPORTED}", "d_1")
    run = load_run("fixture")
    next(d for d in run.drafts if d.id == "d_1").status = "pending"
    save_run(run)
    room2 = make_room(tmp_path / "2", Scripted(reviewer="reject", unsupported=[UNSUPPORTED]))
    run_(room2.review("fixture", "d_1"))
    assert run_(room2.rep_says("fixture", "d_1", "approve d_1")).state == "ignored"
    assert draft().status == "rejected"


def test_security_blocks_private_data_and_unsafe_links_even_if_model_passes(tmp_path):
    set_body("Dana, saw Acme is hiring three analytics engineers. Call me on +1 415 555 0100 "
             "or see http://bit.ly/x")
    out = run_(make_room(tmp_path, Scripted(security="pass")).review("fixture", "d_1"))
    assert out.state == "blocked"
    text = " ".join(out.details)
    assert "phone number" in text and "non-https" in text and "shortener" in text
    assert draft().status == "rejected"


def test_every_agent_message_is_audited_with_tokens_and_cost(tmp_path):
    room = make_room(tmp_path, Scripted())
    run_(room.review("fixture", "d_1"))
    band = [e for e in load_run("fixture").audit if e.action.startswith("band.")]
    assert [e.agent for e in band] == ["planner", "builder", "reviewer", "security"]
    assert all(e.tokens == 1000 and e.cost_usd == 0.01 for e in band)
    feed = room.feed_since(0)
    assert feed["totals"] == {"messages": 4, "tokens": 4000, "cost_usd": 0.04}
    assert [i["cumulative_cost_usd"] for i in feed["items"]] == [0.01, 0.02, 0.03, 0.04]
    assert len(room.feed_since(2)["items"]) == 2


def test_handoffs_are_mentions_and_agents_only_see_what_mentions_them(tmp_path):
    room = make_room(tmp_path, Scripted())
    run_(room.review("fixture", "d_1"))
    band = room.band
    assert [i.to for i in room.feed] == [["builder"], ["reviewer"], ["security"], ["rep", "planner"]]
    def received(agent):
        return [m.sender for m in band.inbox(agent) if m.sender != agent]
    assert received("reviewer") == ["builder"]
    assert received("security") == ["reviewer"]
    assert len(band.inbox("rep")) == 4  # the human sees the whole room


def test_model_outage_stops_the_review_and_leaves_the_draft_pending(tmp_path):
    room = make_room(tmp_path, Scripted(silent={"reviewer"}))
    out = run_(room.review("fixture", "d_1"))
    assert out.state == "stalled"
    assert draft().status == "pending"


def test_feed_and_waiting_state_survive_a_restart(tmp_path):
    room = make_room(tmp_path, Scripted())
    run_(room.review("fixture", "d_1"))
    again = make_room(tmp_path, Scripted())
    assert len(again.feed) == 4 and "fixture/d_1" in again.awaiting


def test_rep_verdict_words():
    assert parse_verdict("approve d_1") == "approve"
    assert parse_verdict("Approved, ship it") == "approve"
    assert parse_verdict("reject d_1") == "block"
    assert parse_verdict("looks fine?") is None


def test_security_scan_allows_recipient_email_and_listed_domains(monkeypatch):
    monkeypatch.setenv("GTM_LINK_DOMAINS", "promptql.io")
    lead = agents.lead_for(load_run("fixture"), "d_1")
    lead.draft.body = "Reply to dana@acmefreight.example.com or read https://promptql.io/docs"
    assert agents.security_scan(lead) == []
    lead.draft.body = "see https://evil.example.net/x"
    assert agents.security_scan(lead) == ["link outside GTM_LINK_DOMAINS: evil.example.net"]


def test_routes_run_review_feed_and_rep(tmp_path):
    routes.set_room(make_room(tmp_path, Scripted()))
    app = FastAPI()
    app.include_router(routes.router)
    c = TestClient(app)
    try:
        assert c.post("/api/gtm/band/review/fixture/nope").status_code == 404
        out = c.post("/api/gtm/band/review/fixture/d_1", params={"wait": True}).json()
        assert out["state"] == "awaiting_rep"
        feed = c.get("/api/gtm/band/feed").json()
        assert feed["mode"] == "mock" and feed["awaiting_rep"] == ["fixture/d_1"]
        assert feed["totals"]["tokens"] == 4000
        assert c.post("/api/gtm/band/rep/fixture/d_1", json={"text": "approve d_1"}).json()["state"] == "approved"
        assert draft().status == "approved"
    finally:
        routes.set_room(None)
