"""Discovery: cited rows only, rejections kept with their reason, competitors not prospected."""

from datetime import datetime, timezone

import pytest

from gtm.contract import ICP, Industry, Intake, Persona, Run, Scored
from gtm.pipeline import discover, glasser, store, web


def row(name, domain, country="US", industry="Software Development", staff=900, desc="We make tools.", **extra):
    return {"name": name, "domain": domain, "industry": industry, "employee_count": staff, "description": desc,
            "location": {"city": "X", "country": {"US": "United States", "AU": "Australia"}.get(country, country),
                         "country_code": country, "raw_address": f"1 Main St, {country}"},
            "technology": {"technology_list": [{"name": "Snowflake"}]}, **extra}


ROWS = [
    row("Cited Co", "cited.example.com",
        funding={"funding_events": [{"link": "https://funding.example.com/r/1", "stage": "Series C",
                                     "amount_printed": "$50M", "raised_at": "2026-06-01T00:00:00"}]}),
    row("Ghost Co", "ghost.example.com", desc=""),  # no page and no profile text: nothing to cite
    row("Far Co", "far.example.com", country="AU"),
    row("Layoff Co", "layoff.example.com"),
    row("Rival BI", "rival.example.com", desc="Rival is the analytics platform for everyone."),
    row("Agency", "agency.example.com", industry="IT Services and IT Consulting"),
]

NEWS = {"layoff.example.com": [{"url": "https://news.example.com/a/1", "title": "Layoff Co lays off 10% of staff",
                                "tags": [{"name": "Layoffs"}], "published_date": "2026-11-01"}]}


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("GTM_DATA_DIR", str(tmp_path))

    def fake_run(provider, endpoint, payload, **k):
        if provider == "prospeo":
            out = {"results": [{"company": r} for r in ROWS]}
        else:
            out = {"data": NEWS.get(payload["company"], [])}
        return glasser.Result(provider, endpoint, out, 0.01, "https://glasser.example.com/run", cached=False)

    def fake_fetch(url, timeout=10):
        if "ghost" in url or "careers" in url or "jobs" in url:
            return "", ""
        host = url.split("/")[2]
        return url, f'<html><head><meta name="description" content="{host} homepage says what it does."></head></html>'

    monkeypatch.setattr(glasser, "run", fake_run)
    monkeypatch.setattr(web, "fetch", fake_fetch)
    icp = ICP(industries=[Industry(value="Software", confidence=0.8), Industry(value="Fintech", confidence=0.6)],
              headcount_bands=[Scored(value="200-5000", confidence=0.7)], revenue_bands=[],
              personas=[Persona(title="Head of Data", seniority="vp", confidence=0.8)], triggers=[])
    intake = Intake(product="P", description="NL over data", constraints=["North America and Europe first"])
    store.save(Run(id="r1", created_at=datetime.now(timezone.utc), intake=intake, icp=icp))
    discover.run_step("r1")
    return store.load("r1")


def by_name(run):
    return {c.name: c for c in run.companies}


def test_company_without_a_citation_never_reaches_the_run(env):
    assert "Ghost Co" not in by_name(env)
    assert any(e.action == "dropped_uncited" and e.target == "ghost.example.com" for e in env.audit)
    assert all(c.citations and c.citations[0].quote for c in env.companies)


def test_rejected_companies_stay_with_their_reason(env):
    cos = by_name(env)
    assert cos["Far Co"].rejected_reason.startswith("Non-target region: HQ in Australia")
    assert cos["Layoff Co"].rejected_reason.startswith("Layoffs:")
    lay = next(s for s in cos["Layoff Co"].signals if s.kind == "layoffs")
    assert lay.negative and str(lay.citation.url) == "https://news.example.com/a/1"
    assert cos["Far Co"].tier == "C" and cos["Cited Co"].rejected_reason == ""


def test_competitors_and_services_firms_are_not_prospects(env):
    assert "Rival BI" not in by_name(env) and "Agency" not in by_name(env)


def test_scores_explain_themselves(env):
    co = by_name(env)["Cited Co"]
    why = next(s for s in co.signals if s.id.endswith("_score"))
    assert f"Fit {co.fit_score}" in why.summary and "funded 2026-06-01" in why.summary
    assert 0 <= co.fit_score <= 100 and co.tier in "AB"
    funding = next(s for s in co.signals if s.kind == "funding")
    assert str(funding.citation.url) == "https://funding.example.com/r/1"
