import pytest
from pydantic import ValidationError

from gtm.contract import Company, Draft, can_send
from gtm.fixture_routes import load_fixture
from gtm.fixtures.make_fixture import build


def test_fixture_file_matches_generator():
    assert load_fixture() == build()


def test_company_without_citation_is_refused():
    with pytest.raises(ValidationError):
        Company(id="x", name="X", domain="x.example.com", fit_score=50, intent_score=50, tier="B", citations=[])


def test_draft_must_cite_a_signal():
    with pytest.raises(ValidationError):
        Draft(id="d", person_id="p", channel="email", body="hi", signal_ids=[])


def test_only_approved_drafts_can_send():
    run = load_fixture()
    assert [d.id for d in run.drafts if can_send(d)] == ["d_2"]


def test_fixture_has_a_rejected_company():
    assert any(c.rejected_reason for c in load_fixture().companies)


def test_plugin_mounts_fixture_route():
    from sellbird import extensions
    from gtm.plugin import install

    reg = extensions.Registry()
    install(reg)
    paths = {r.path for router in reg.routers for r in router.routes}
    assert "/api/gtm/runs/fixture" in paths
