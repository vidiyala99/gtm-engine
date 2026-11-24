"""ICP step: per-field confidence, and expansions only with real review evidence."""

from datetime import datetime, timezone

import pytest

from gtm.contract import Intake, Run
from gtm.pipeline import glasser, icp, llm, store

REVIEWS = [
    {"id": "101", "url": "https://reviews.example.com/r/101", "productName": "Tool A", "title": "slow reports",
     "dislikes": "Our hospital ops team waits a week for every ad-hoc SQL report from the data team.",
     "problemsSolved": "dashboards for leadership", "author": "Verified User in Hospital & Health Care"},
    {"id": "102", "url": "https://reviews.example.com/r/102", "productName": "Tool A", "title": "ok",
     "dislikes": "Insurance claims analysts cannot ask questions without writing SQL themselves.",
     "problemsSolved": "", "author": "Verified User in Insurance"},
]

DRAFT = {
    "industries": [{"value": "Software", "naics": "513210", "confidence": 1.7, "why": "intake says SaaS"}],
    "headcount_bands": [{"value": "200-2000", "confidence": 0.7, "why": "enterprise pricing"}],
    "revenue_bands": [{"value": "$50M-$500M", "confidence": 0.5}],
    "personas": [{"title": "Head of Data", "seniority": "director", "confidence": 0.8},
                 {"title": "CTO", "seniority": "boss", "confidence": 0.6}],
    "triggers": [{"value": "hiring analytics engineers", "confidence": 0.7, "why": ""}],
    "g2_slugs": ["tool-a"],
}

EXPANSIONS = {"expansions": [
    {"segment": "Hospital operations", "rationale": "ops teams wait on SQL",
     "evidence": [{"review_id": "101", "quote": "waits a week for every ad-hoc SQL report"}]},
    {"segment": "Insurance claims", "rationale": "analysts blocked on SQL",
     "evidence": [{"review_id": "102", "quote": "a sentence the reviewer never wrote"}]},
    {"segment": "Invented vertical", "rationale": "no evidence", "evidence": [{"review_id": "999", "quote": "x"}]},
]}


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("GTM_DATA_DIR", str(tmp_path))
    replies = {"draft": DRAFT, "expansions": EXPANSIONS}
    monkeypatch.setattr(llm, "ask_json", lambda prompt, agent, task, **k: (replies[task], llm.Usage(tokens=1234)))
    monkeypatch.setattr(glasser, "run", lambda p, e, payload, **k: glasser.Result(
        p, e, {"output": {"data": {"items": REVIEWS}}}, 0.002, "https://glasser.example.com/run/1", cached=False))
    run = Run(id="r1", created_at=datetime.now(timezone.utc), intake=Intake(product="P", description="NL over data"))
    store.save(run)


def test_icp_has_per_field_confidence_in_range():
    icp.run_step("r1")
    got = store.load("r1").icp
    assert got.industries[0].confidence == 1.0  # clipped, never out of range
    assert got.industries[0].why and got.industries[0].naics == "513210"
    assert {p.seniority for p in got.personas} <= {"c_level", "vp", "director", "manager", "ic"}


def test_expansions_cite_real_reviews_only():
    icp.run_step("r1")
    exps = store.load("r1").icp.expansions
    assert [e.segment for e in exps] == ["Hospital operations", "Insurance claims"]  # invented id dropped
    assert str(exps[0].evidence[0].url) == "https://reviews.example.com/r/101"
    assert exps[0].evidence[0].quote == "waits a week for every ad-hoc SQL report"
    # a quote the review does not contain is replaced by the review's own words
    assert exps[1].evidence[0].quote.startswith("Insurance claims analysts cannot ask")
    assert all(e.status == "proposed" for e in exps)


def test_model_and_data_calls_are_audited_with_tokens_and_cost():
    icp.run_step("r1")
    audit = store.load("r1").audit
    model = [e for e in audit if e.action.startswith("model:")]
    calls = [e for e in audit if e.action.startswith("call:glasser")]
    assert len(model) == 2 and all(e.tokens == 1234 and e.actor == "ai" for e in model)
    assert calls and calls[0].cost_usd == 0.002
