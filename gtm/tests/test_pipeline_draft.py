"""Drafts: every one cites a real signal, A/B on email 1, all pending, rule breaks flagged."""

from datetime import datetime, timezone

import pytest

from gtm.contract import Citation, Company, Intake, Person, Run, Signal, can_send
from gtm.pipeline import draft, llm, store

NOW = datetime.now(timezone.utc)
CITE = Citation(url="https://a.example.com/jobs", quote="Analytics Engineer", retrieved_at=NOW)

COMPANY = Company(id="co_a", name="Acme", domain="a.example.com", fit_score=90, intent_score=70, tier="A",
                  citations=[CITE], signals=[
                      Signal(id="co_a_jobs", kind="job_post", summary="3 analytics engineer roles open", citation=CITE),
                      Signal(id="co_a_layoffs", kind="layoffs", negative=True, summary="old news", citation=CITE)])
PERSON = Person(id="p_1", company_id="co_a", name="Dana Doe", title="VP Data", email="dana@a.example.com",
                email_status="verified", confidence=0.9, citations=[CITE])

SEEN = {}


def reply_for(prompt, agent, task, **k):
    SEEN["prompt"] = prompt
    body = "Acme has three analytics engineer roles open. That usually means a long queue of data questions. " \
           "Worth a look at answers your team can check?"
    return {"p_1": {"email": [
        {"step": 1, "variant": "A", "subject": "analytics queue", "body": body, "signal_ids": ["co_a_jobs"]},
        {"step": 1, "variant": "B", "subject": "data questions", "body": "We think you will love this!",
         "signal_ids": ["co_a_jobs"]},
        {"step": 2, "variant": "A", "subject": "a thought", "body": "Another angle.", "signal_ids": ["made_up"]},
        {"step": 3, "variant": "A", "subject": "closing", "body": "Should I close this out?",
         "signal_ids": ["co_a_layoffs", "co_a_jobs"]},
    ], "linkedin": {"body": "Saw the analytics engineer roles at Acme.", "signal_ids": ["co_a_jobs"]}}}, \
        llm.Usage(tokens=500)


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("GTM_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(llm, "ask_json", reply_for)
    store.save(Run(id="r1", created_at=NOW, intake=Intake(product="P", description="d"), companies=[COMPANY],
                   people=[PERSON]))
    draft.run_step("r1")
    return store.load("r1")


def test_every_draft_cites_a_real_positive_signal(env):
    assert env.drafts and all(set(d.signal_ids) <= {"co_a_jobs"} for d in env.drafts)
    assert not any(d.step == 2 for d in env.drafts)  # cited an id that does not exist: dropped
    assert any(e.action == "draft_dropped" for e in env.audit)


def test_ab_variants_on_first_email_and_a_linkedin_note(env):
    assert {(d.channel, d.step, d.variant) for d in env.drafts} == {
        ("email", 1, "A"), ("email", 1, "B"), ("email", 3, "A"), ("linkedin", 1, "A")}


def test_all_drafts_start_pending_and_cannot_send(env):
    assert all(d.status == "pending" and not can_send(d) for d in env.drafts)


def test_rule_breaks_are_flagged_for_review(env):
    b = next(d for d in env.drafts if d.variant == "B")
    assert any("exclamation" in n for n in b.review_notes) and any('"I" or "we"' in n for n in b.review_notes)
    a = next(d for d in env.drafts if d.channel == "email" and d.variant == "A" and d.step == 1)
    assert a.review_notes == [] and a.body.endswith("Sam")


def test_scraped_text_is_fenced_and_negative_signals_withheld(env):
    assert SEEN["prompt"].count("<untrusted source=") >= 2  # company facts and each signal
    assert "</untrusted>" in SEEN["prompt"]
    assert "co_a_layoffs" not in SEEN["prompt"]
