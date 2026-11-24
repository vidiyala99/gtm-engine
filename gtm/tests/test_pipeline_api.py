"""The run store and the rep-facing routes (lane A, steps 1-2)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gtm.contract import can_send
from gtm.fixture_routes import load_fixture
from gtm.pipeline import routes, runner, store


@pytest.fixture(autouse=True)
def tmp_store(tmp_path, monkeypatch):
    monkeypatch.setenv("GTM_DATA_DIR", str(tmp_path))
    started = []
    monkeypatch.setattr(runner, "start", lambda run_id: started.append(run_id))
    return started


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


@pytest.fixture
def saved_run():
    run = load_fixture()
    run.id = "r1"
    store.save(run)
    return run


def test_save_then_load_round_trips(saved_run):
    assert store.load("r1") == saved_run


def test_crash_mid_write_keeps_the_last_good_run(saved_run, monkeypatch):
    def boom(*a, **k):
        raise OSError("disk gone")
    monkeypatch.setattr(store.os, "replace", boom)
    changed = saved_run.model_copy(deep=True)
    changed.companies = []
    with pytest.raises(OSError):
        store.save(changed)
    assert store.load("r1").companies == saved_run.companies
    assert not list(store.runs_dir().glob("*.tmp"))


def test_unknown_or_hostile_id_is_not_found():
    for bad in ("nope", "../../etc/passwd"):
        with pytest.raises(store.RunNotFound):
            store.load(bad)


def test_post_intake_creates_run_and_starts_pipeline(client, tmp_store):
    r = client.post("/api/gtm/runs", json={"product": "PromptQL", "description": "NL queries over data"})
    assert r.status_code == 200
    run_id = r.json()["id"]
    assert tmp_store == [run_id]
    got = client.get(f"/api/gtm/runs/{run_id}").json()
    assert got["intake"]["product"] == "PromptQL"
    assert got["audit"][0]["action"] == "intake_submitted"


def test_get_missing_run_is_404(client):
    assert client.get("/api/gtm/runs/missing").status_code == 404


def test_fixture_still_served(client):
    assert client.get("/api/gtm/runs/fixture").json()["id"] == "fixture"


def test_draft_approve_writes_rep_audit_event_and_becomes_sendable(client, saved_run):
    pending = next(d for d in saved_run.drafts if d.status == "pending")
    r = client.post(f"/api/gtm/runs/r1/drafts/{pending.id}", json={"action": "approve"})
    assert r.status_code == 200
    run = store.load("r1")
    d = next(d for d in run.drafts if d.id == pending.id)
    assert can_send(d)
    last = run.audit[-1]
    assert (last.actor, last.action, last.target) == ("rep", "draft_approved", f"draft:{pending.id}")


def test_rejected_draft_cannot_send(client, saved_run):
    d = saved_run.drafts[0]
    client.post(f"/api/gtm/runs/r1/drafts/{d.id}", json={"action": "reject", "note": "claim unsupported"})
    run = store.load("r1")
    got = next(x for x in run.drafts if x.id == d.id)
    assert got.status == "rejected" and not can_send(got)
    assert "rep: claim unsupported" in got.review_notes


def test_edit_changes_body_and_stays_pending(client, saved_run):
    approved = next(d for d in saved_run.drafts if d.status == "approved")
    client.post(f"/api/gtm/runs/r1/drafts/{approved.id}", json={"action": "edit", "body": "new words"})
    got = next(x for x in store.load("r1").drafts if x.id == approved.id)
    assert got.body == "new words" and got.status == "pending" and not can_send(got)
    assert store.load("r1").audit[-1].action == "draft_edited"


def test_expansion_decisions(client, saved_run):
    r = client.post("/api/gtm/runs/r1/expansions/0", json={"status": "adjusted", "segment": "Hospital ops"})
    exp = r.json()["icp"]["expansions"][0]
    assert exp["status"] == "adjusted" and exp["segment"] == "Hospital ops"
    assert store.load("r1").audit[-1].actor == "rep"
    assert client.post("/api/gtm/runs/r1/expansions/9", json={"status": "dismissed"}).status_code == 404


def test_lead_stage_move_is_rep_attributed(client, saved_run):
    co = saved_run.companies[0].id
    r = client.post(f"/api/gtm/runs/r1/leads/{co}", json={"stage": "contacted"})
    lead = next(l for l in r.json()["leads"] if l["company_id"] == co)
    assert lead["stage"] == "contacted"
    ev = store.load("r1").audit[-1]
    assert ev.actor == "rep" and ev.action == "lead_moved"
    assert client.post(f"/api/gtm/runs/r1/leads/{co}", json={"stage": "nowhere"}).status_code == 422


def test_runner_skips_missing_steps_and_logs_failures(saved_run):
    def bad(run_id):
        raise RuntimeError("provider down")
    import types, sys
    mod = types.ModuleType("gtm_fake_step")
    mod.run_step = bad
    sys.modules["gtm_fake_step"] = mod
    runner.run_all("r1", [("absent", "gtm.pipeline.not_built:run_step"), ("fake", "gtm_fake_step:run_step")])
    actions = [(e.agent, e.action) for e in store.load("r1").audit[-3:]]
    assert actions == [("pipeline", "run_started"), ("fake", "step_started"), ("fake", "step_failed")]
