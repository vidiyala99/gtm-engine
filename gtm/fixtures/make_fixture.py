"""Writes gtm/fixtures/run.json: a fictional run (example.com data only; the repo is public).

    python -m gtm.fixtures.make_fixture
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from gtm.contract import (ICP, AuditEvent, Citation, Company, Competitor, Draft, Expansion, Industry,
                          Intake, Lead, Persona, Person, Run, Scored, Signal)

T0 = datetime(2026, 11, 24, 18, 0, tzinfo=timezone.utc)


def cite(slug: str, title: str, quote: str, provider: str = "web", cost: float = 0.0) -> Citation:
    return Citation(url=f"https://{slug}.example.com/source", title=title, quote=quote,
                    provider=provider, retrieved_at=T0, cost_usd=cost)


def build() -> Run:
    intake = Intake(
        product="Northwind Query",
        description="A natural-language query layer over a company's databases with verifiable plans.",
        features=["NL to SQL with a reviewable plan", "row-level permissions", "Postgres, Snowflake, BigQuery"],
        constraints=["no on-prem before Q3"],
        customers=["a mid-market logistics firm"],
        pricing="usage-based, contracts from $30k/yr",
    )
    icp = ICP(
        industries=[Industry(value="Logistics software", naics="541511", confidence=0.82, why="2 of 3 wins"),
                    Industry(value="Fintech data teams", naics="522320", confidence=0.64, why="pricing fits")],
        headcount_bands=[Scored(value="200-2000", confidence=0.77)],
        revenue_bands=[Scored(value="$50M-$500M", confidence=0.58)],
        personas=[Persona(title="Head of Data", seniority="director", confidence=0.8),
                  Persona(title="VP Engineering", seniority="vp", confidence=0.66)],
        triggers=[Scored(value="hiring analytics engineers", confidence=0.74),
                  Scored(value="new CDO/Head of Data", confidence=0.7)],
        expansions=[Expansion(segment="Healthcare ops analytics", rationale="reviews cite ad-hoc SQL backlog",
                              evidence=[cite("reviews-a", "Review: SQL backlog", "we wait a week for a report",
                                             "glasser:/g2.reviews", 0.02)])],
    )
    companies = [
        Company(id="co_acme", name="Acme Freight", domain="acmefreight.example.com", hq="Chicago, US",
                industry="Logistics software", headcount="640", fit_score=88, intent_score=81, tier="A",
                signals=[Signal(id="sig_1", kind="job_post", summary="Hiring 3 analytics engineers",
                                observed_on="2026-11-10",
                                citation=cite("acme-jobs", "Careers", "Analytics Engineer (3 openings)"))],
                citations=[cite("acme", "About", "Freight visibility platform for 4,000 shippers")]),
        Company(id="co_globex", name="Globex Pay", domain="globexpay.example.com", hq="New York, US",
                industry="Fintech", headcount="1,200", fit_score=74, intent_score=69, tier="B",
                signals=[Signal(id="sig_2", kind="exec_hire", summary="New Head of Data in October",
                                observed_on="2026-10-02",
                                citation=cite("globex-news", "Press", "appoints Head of Data"))],
                citations=[cite("globex", "Home", "Payments infrastructure for marketplaces")]),
        Company(id="co_initech", name="Initech Health", domain="initech.example.com", hq="Austin, US",
                industry="Healthcare software", headcount="410", fit_score=61, intent_score=52, tier="C",
                signals=[], citations=[cite("initech", "About", "Scheduling for 900 clinics")]),
        Company(id="co_umbrella", name="Umbrella Logistics", domain="umbrella.example.com", hq="Leeds, UK",
                industry="Logistics", headcount="300", fit_score=70, intent_score=10, tier="C",
                signals=[Signal(id="sig_3", kind="hiring_freeze", negative=True, summary="Hiring freeze announced",
                                observed_on="2026-11-01",
                                citation=cite("umbrella-news", "Blog", "pausing all hiring until 2027"))],
                citations=[cite("umbrella", "Home", "Regional freight forwarding")],
                rejected_reason="hiring freeze (negative signal sig_3)"),
    ]
    people = [
        Person(id="p_1", company_id="co_acme", name="Dana Example", title="Head of Data", seniority="director",
               email="dana@acmefreight.example.com", email_status="verified", mx_ok=True, confidence=0.9,
               past_employers=["Globex Pay"], linkedin_url="https://www.linkedin.com/in/example-dana",
               citations=[cite("acme-team", "Team", "Dana Example, Head of Data")]),
        Person(id="p_2", company_id="co_globex", name="Sam Example", title="Head of Data", seniority="director",
               email="sam@globexpay.example.com", email_status="catch_all", mx_ok=True, confidence=0.7,
               citations=[cite("globex-news", "Press", "appoints Sam Example as Head of Data")]),
        Person(id="p_3", company_id="co_globex", name="Riley Example", title="VP Engineering", seniority="vp",
               email="", email_status="unknown", confidence=0.55, past_employers=["Globex Pay"],
               citations=[cite("globex-team", "Leadership", "Riley Example, VP Engineering")]),
    ]
    competitors = [
        Competitor(name="QueryCo", domain="queryco.example.com", kind="direct", positioning="BI-first NL query",
                   pricing_tiers=["Team $500/mo", "Enterprise custom"], differentiators=["dashboards"],
                   citations=[cite("queryco", "Pricing", "Team $500/mo")]),
        Competitor(name="In-house dbt + analysts", domain="dbt.example.com", kind="alternative",
                   positioning="hire analysts", citations=[cite("alt", "Survey", "62% build in-house")]),
    ]
    drafts = [
        Draft(id="d_1", person_id="p_1", channel="email", variant="A", subject="3 analytics engineer openings",
              body="Dana, saw Acme is hiring three analytics engineers. Teams at that stage often ...",
              signal_ids=["sig_1"], status="pending"),
        Draft(id="d_2", person_id="p_1", channel="linkedin", variant="A",
              body="Dana, congrats on the data team growth at Acme ...", signal_ids=["sig_1"], status="approved"),
        Draft(id="d_3", person_id="p_2", channel="email", variant="B", subject="first 90 days as Head of Data",
              body="Sam, new data leaders usually inherit a report backlog ...", signal_ids=["sig_2"],
              status="rejected", review_notes=["reviewer: 'usually inherit' is an unsupported claim"]),
    ]
    leads = [Lead(company_id="co_acme", person_id="p_1", stage="contacted", owner="ai"),
             Lead(company_id="co_globex", person_id="p_2", stage="matched", owner="ai"),
             Lead(company_id="co_initech", stage="matched", owner="rep")]
    steps = [("ai", "pipeline", "icp.inferred", "", 4100, 0.0),
             ("ai", "pipeline", "discovery.search", "glasser:/zoominfo.search", 0, 0.05),
             ("ai", "pipeline", "company.rejected", "co_umbrella", 0, 0.0),
             ("ai", "pipeline", "enrich.email", "p_1", 0, 0.01),
             ("ai", "reviewer", "draft.rejected", "d_3", 2200, 0.0),
             ("rep", "", "draft.approved", "d_2", 0, 0.0)]
    audit = [AuditEvent(at=T0 + timedelta(minutes=i), actor=a, agent=g, action=act, target=tgt,
                        tokens=tok, cost_usd=c) for i, (a, g, act, tgt, tok, c) in enumerate(steps)]
    return Run(id="fixture", created_at=T0, status="done", intake=intake, icp=icp, companies=companies, people=people,
               competitors=competitors, drafts=drafts, leads=leads, audit=audit)


if __name__ == "__main__":
    out = Path(__file__).parent / "run.json"
    out.write_text(build().model_dump_json(indent=2), encoding="utf-8")
    print(out)
