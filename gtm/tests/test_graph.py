"""Lane B graph: what the UI and the demo rely on."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gtm.contract import Citation, Company, Person, Signal
from gtm.fixture_routes import load_fixture
from gtm.graph import build, kuzu_store, paths, runs

ENGINES = ["python"] + (["kuzu"] if kuzu_store.available() else [])
NOW = datetime(2026, 11, 24, tzinfo=timezone.utc)


def cite(url: str, quote: str = "") -> Citation:
    return Citation(url=url, quote=quote, retrieved_at=NOW)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(kuzu_store, "ROOT", tmp_path / "graph")
    monkeypatch.setattr(runs, "OVERLAY", tmp_path / "runs")


def ids(path) -> list[str]:
    return [n.id for n in path.nodes]


def test_build_is_idempotent():
    run = load_fixture()
    assert build(run).model_dump_json() == build(run).model_dump_json()
    assert build(run).model_dump_json() == build(load_fixture()).model_dump_json()


def test_ontology_covers_spec_edges():
    g = build(load_fixture())
    labels = {n.label for n in g.nodes}
    assert {"Company", "Person", "Product", "Competitor", "Signal"} <= labels
    types = {e.type for e in g.edges}
    assert {"works_at", "previously_employed_at", "competes_with", "matched_to", "contacted_via"} <= types


def test_rejected_company_is_not_matched():
    g = build(load_fixture())
    assert not g.out("company:co_umbrella", "matched_to")
    assert g.out("company:co_acme", "matched_to")


@pytest.mark.parametrize("engine", ENGINES)
def test_warm_intro_p3_to_p1_via_globex(engine):
    found = paths(build(load_fixture()), "warm_intro", engine=engine, target="p_3")
    assert len(found) == 1
    path = found[0]
    assert ids(path)[:3] == ["person:p_3", "company:co_globex", "person:p_1"]
    assert "Globex Pay" in path.summary
    first, second, last = (e.type for e in path.edges)
    assert first in ("works_at", "previously_employed_at")  # the fixture gives p_3 both edges to Globex
    assert (second, last) == ("previously_employed_at", "contacted_via")


@pytest.mark.parametrize("engine", ENGINES)
def test_warm_intro_never_targets_someone_already_contacted(engine):
    assert paths(build(load_fixture()), "warm_intro", engine=engine, target="p_1") == []


@pytest.mark.parametrize("engine", ENGINES)
def test_warm_intro_via_school(engine):
    run = load_fixture()
    run.people[0].schools = ["Example State University"]  # p_1, contacted
    run.people[2].schools = ["Example State University"]  # p_3
    run.people[2].past_employers = []
    found = paths(build(run), "warm_intro", engine=engine, target="p_3")
    assert [e.type for e in found[0].edges][:2] == ["attended", "attended"]


@pytest.mark.parametrize("engine", ENGINES)
def test_buying_cycle_ties_job_post_to_matched_company_and_persona(engine):
    found = paths(build(load_fixture()), "buying_cycle", engine=engine)
    assert len(found) == 1
    path = ids(found[0])
    assert path[:2] == ["signal:sig_1", "company:co_acme"] and path[2].startswith("product:")
    assert "person:p_1" in path


def displacement_run():
    run = load_fixture()
    initech = next(c for c in run.companies if c.id == "co_initech")
    initech.signals.append(Signal(id="sig_9", kind="review_complaint",
                                  summary="Reviews complain QueryCo dashboards are slow; renewal due in Q1",
                                  citation=cite("https://reviews.example.com/initech", "QueryCo is slow")))
    # A rejected company with the same story still shows (it uses the competitor), but a
    # company with no churn signal does not.
    acme = next(c for c in run.companies if c.id == "co_acme")
    acme.signals.append(Signal(id="sig_8", kind="tech_change", summary="Adopted QueryCo in 2025",
                               citation=cite("https://acme.example.com/stack")))
    return run


@pytest.mark.parametrize("engine", ENGINES)
def test_competitor_displacement_needs_competitor_and_churn(engine):
    found = paths(build(displacement_run()), "competitor_displacement", engine=engine)
    assert [ids(p)[0] for p in found] == ["company:co_initech"]
    assert ids(found[0])[1] == "competitor:queryco"
    assert ids(found[0])[-1] == "signal:sig_9"


@pytest.mark.skipif("kuzu" not in ENGINES, reason="kuzu not installed")
@pytest.mark.parametrize("make", [load_fixture, displacement_run])
def test_engines_agree(make):
    g = build(make())
    for kind in ("warm_intro", "buying_cycle", "competitor_displacement"):
        a = [p.model_copy(update={"engine": "x"}) for p in paths(g, kind, engine="python")]
        b = [p.model_copy(update={"engine": "x"}) for p in paths(g, kind, engine="kuzu")]
        assert a == b, kind


@pytest.mark.skipif("kuzu" not in ENGINES, reason="kuzu not installed")
def test_kuzu_store_rebuilds_when_run_changes():
    run = load_fixture()
    assert len(paths(build(run), "warm_intro", engine="kuzu")) == 2
    run.people[0].past_employers = []  # p_1 no longer shares Globex Pay
    assert paths(build(run), "warm_intro", engine="kuzu") == []


def test_unmatched_past_employer_becomes_external_company():
    run = load_fixture()
    run.people.append(Person(id="p_9", company_id="co_initech", name="Alex Example", title="CTO",
                             confidence=0.5, past_employers=["Hooli, Inc."],
                             citations=[cite("https://initech.example.com/team")]))
    g = build(run)
    ext = g.node("company:ext-hooli")
    assert ext.props["external"] is True


def client() -> TestClient:
    from gtm.graph.routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_routes_serve_graph_and_paths():
    c = client()
    g = c.get("/api/gtm/runs/fixture/graph").json()
    assert g["run_id"] == "fixture" and g["nodes"] and g["edges"]
    body = c.get("/api/gtm/runs/fixture/paths/warm_intro", params={"target": "p_3"}).json()
    path = body["paths"][0]
    assert [n["name"] for n in path["nodes"][:3]] == ["Riley Example", "Globex Pay", "Dana Example"]
    edge_ends = {(e["source"], e["target"]) for e in path["edges"]}
    node_ids = {n["id"] for n in path["nodes"]}
    assert all(s in node_ids and t in node_ids for s, t in edge_ends)  # drawable as-is


def test_routes_reject_unknown_kind_and_run():
    c = client()
    assert c.get("/api/gtm/runs/fixture/paths/astrology").status_code == 404
    assert c.get("/api/gtm/runs/nope/graph").status_code == 404


@pytest.mark.parametrize("engine", ENGINES)
def test_displacement_alias_serves_competitor_displacement(monkeypatch, engine):
    """Lane C asks for /paths/displacement; it gets the same paths as competitor_displacement."""
    import gtm.graph.routes as routes
    monkeypatch.setattr(routes, "load_run", lambda run_id: displacement_run())
    c = client()
    short = c.get("/api/gtm/runs/fixture/paths/displacement", params={"engine": engine}).json()
    full = c.get("/api/gtm/runs/fixture/paths/competitor_displacement", params={"engine": engine}).json()
    assert short == full and short["kind"] == "competitor_displacement"
    assert [n["id"] for n in short["paths"][0]["nodes"]][:2] == ["company:co_initech", "competitor:queryco"]
