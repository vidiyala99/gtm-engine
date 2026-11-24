"""Enrichment: buyers only, status straight from the verifier, every person cited."""

from datetime import datetime, timezone

import pytest

from gtm.contract import Citation, Company, Intake, Run
from gtm.pipeline import enrich, glasser, store, web

NOW = datetime.now(timezone.utc)
CITE = Citation(url="https://a.example.com/", quote="A does things", retrieved_at=NOW)


def co(cid, tier="A", rejected=""):
    return Company(id=cid, name=cid.upper(), domain=f"{cid}.example.com", fit_score=80, intent_score=60, tier=tier,
                   citations=[CITE], rejected_reason=rejected)


EMAILS = {"a.example.com": [
    {"value": "dana@a.example.com", "first_name": "Dana", "last_name": "Doe", "position": "VP of Data",
     "confidence": 90, "seniority": "executive", "sources": [{"uri": "https://blog.example.com/post"}]},
    {"value": "tim@a.example.com", "first_name": "Tim", "last_name": "Tax", "position": "Chief Tax Officer",
     "confidence": 95, "sources": [{"uri": "https://x.example.com/"}]},
    {"value": "cto@a.example.com", "first_name": "Cy", "last_name": "Toe", "position": "CTO", "confidence": 80,
     "sources": [{"uri": "https://www.google.com/search?q=x"}]},  # only a search link: nothing to cite
]}
VERDICT = {"dana@a.example.com": {"status": "accept_all", "mx_records": True}}


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("GTM_DATA_DIR", str(tmp_path))

    def fake_run(provider, endpoint, payload, **k):
        if endpoint == "/v2/domain-search":
            out = {"data": {"emails": EMAILS.get(payload["domain"], [])}}
        else:
            out = {"data": VERDICT.get(payload.get("email"), {"status": "valid", "mx_records": True})}
        return glasser.Result(provider, endpoint, out, 0.01, "https://glasser.example.com/run", cached=False)

    monkeypatch.setattr(glasser, "run", fake_run)
    monkeypatch.setattr(web, "fetch", lambda url, timeout=10: ("", ""))
    run = Run(id="r1", created_at=NOW, intake=Intake(product="P", description="d"),
              companies=[co("a"), co("b", tier="B"), co("z", tier="C", rejected="Layoffs: x")])
    store.save(run)
    enrich.run_step("r1")
    return store.load("r1")


def test_only_buyer_titles_with_a_citation_are_kept(env):
    assert [p.title for p in env.people] == ["VP of Data"]
    assert str(env.people[0].citations[0].url) == "https://blog.example.com/post"


def test_email_status_and_mx_come_from_the_verifier(env):
    p = env.people[0]
    assert p.email_status == "catch_all" and p.mx_ok is True  # never upgraded to verified
    assert any(e.action == "call:glasser:hunter/v2/email-verifier" for e in env.audit)


def test_live_companies_get_leads_and_rejected_do_not(env):
    leads = {l.company_id: l for l in env.leads}
    assert set(leads) == {"a", "b"}
    assert leads["a"].person_id == env.people[0].id and leads["a"].stage == "matched"


def test_seniority_mapping():
    assert enrich.seniority("Chief Data Officer") == "c_level"
    assert enrich.seniority("VP, Analytics") == "vp"
    assert enrich.seniority("Head of Data Platform") == "director"
    assert enrich.seniority("Vice President of Engineering") == "vp"


def test_title_matching_uses_whole_words():
    assert enrich.title_points("Director of Government Affairs") == 0
    assert enrich.title_points("Managing Director") == 0
    assert enrich.title_points("Chief Information Security Officer") == 0
    assert enrich.title_points("VP, Data & Analytics") >= 5
