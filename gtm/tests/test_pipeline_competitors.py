"""Competitors: every one cited, and no price shown that the pricing page does not state."""

from datetime import datetime, timezone

import pytest

from gtm.contract import Intake, Run
from gtm.pipeline import competitors, llm, store, web

PAGES = {
    "https://alpha.example.com/": '<meta name="description" content="Alpha answers data questions in plain English.">',
    "https://alpha.example.com/pricing": "<p>Starter $20 / month</p><p>Team $200 / month</p>",
    "https://beta.example.com/": '<meta name="description" content="Beta is a BI tool for analysts and teams.">',
}

REPLIES = {
    "list": {"competitors": [{"name": "Alpha", "domain": "alpha.example.com", "kind": "direct"},
                             {"name": "Beta", "domain": "https://www.beta.example.com/", "kind": "weird"},
                             {"name": "Gone", "domain": "gone.example.com", "kind": "alternative"}]},
    "detail": {"alpha.example.com": {"positioning": "NL answers", "pricing_tiers":
                                     ["Starter: $20 / month", "Team: $200 / month", "Scale: $999 / month"],
                                     "differentiators": ["fast"]},
               "beta.example.com": {"positioning": "", "pricing_tiers": ["Pro: $50 / month"]}},
}


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("GTM_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(llm, "ask_json", lambda prompt, agent, task, **k: (REPLIES[task], llm.Usage(tokens=10)))
    monkeypatch.setattr(web, "fetch", lambda url, timeout=10: (url, PAGES[url]) if url in PAGES else ("", ""))
    store.save(Run(id="r1", created_at=datetime.now(timezone.utc), intake=Intake(product="P", description="d")))
    competitors.run_step("r1")
    return {c.name: c for c in store.load("r1").competitors}


def test_unreadable_competitor_is_dropped_and_rest_are_cited(env):
    assert set(env) == {"Alpha", "Beta"}
    assert all(c.citations for c in env.values())


def test_only_prices_on_the_page_survive(env):
    assert env["Alpha"].pricing_tiers == ["Starter: $20 / month", "Team: $200 / month"]
    assert str(env["Alpha"].citations[-1].url) == "https://alpha.example.com/pricing"
    assert env["Beta"].pricing_tiers == []  # no pricing page, so no price


def test_kind_and_positioning_fall_back_safely(env):
    assert env["Beta"].kind == "indirect" and env["Beta"].domain == "beta.example.com"
    assert env["Beta"].positioning == "Beta is a BI tool for analysts and teams."
