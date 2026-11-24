"""The GTM tab against a live run: start a run from Intake, watch it fill by
polling, and send real POSTs. Lane A's routes are stood in for by a small
in-memory router with the request shapes listed in lane-c-status.md, so this
checks the UI's half of that contract.
"""

from __future__ import annotations

import copy
import threading
import time

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

from gtm.tests.web.test_gtm_web import _browser, _free_port, _open  # noqa: E402

RUN_ID = "stub-live-1"
OLDER, NEWER = "run_20261101090000_aaaaaa", "run_20261124090000_bbbbbb"


def _stub_router(state):
    from fastapi import APIRouter, Body, HTTPException

    from gtm.fixture_routes import load_fixture

    r = APIRouter()

    @r.post("/api/gtm/runs")
    async def start(intake: dict = Body(...)):
        run = load_fixture().model_dump(mode="json")
        run.update(id=RUN_ID, status="running", intake={**run["intake"], **intake}, companies=run["companies"][:1])
        state["run"], state["posts"] = run, []
        return {"id": RUN_ID}

    @r.get("/api/gtm/runs")
    async def listing():
        return {"ids": [NEWER, OLDER] + ([RUN_ID] if "run" in state else [])}

    @r.get("/api/gtm/runs/{run_id}")
    async def get(run_id: str):
        if run_id == "fixture":  # a /{id} route shadows the fixture route mounted after it
            return load_fixture().model_dump(mode="json")
        if run_id in (OLDER, NEWER):
            run = load_fixture().model_dump(mode="json")
            run.update(id=run_id, status="done", intake={**run["intake"], "product": "Product " + run_id[-6:]})
            return run
        if run_id != RUN_ID or "run" not in state:
            raise HTTPException(404, "no such run")
        return state["run"]

    @r.post("/api/gtm/runs/{run_id}/drafts/{draft_id}")
    async def draft(run_id: str, draft_id: str, body: dict = Body(...)):
        state["posts"].append(("draft", draft_id, body))
        d = next(x for x in state["run"]["drafts"] if x["id"] == draft_id)
        if body.get("action") == "approve" and d["status"] == "rejected":
            raise HTTPException(409, "a rejected draft cannot be approved")
        d["status"] = {"approve": "approved", "reject": "rejected"}.get(body["action"], d["status"])
        state["run"]["audit"].append({"at": "2026-11-24T18:10:00Z", "actor": "rep", "agent": "dashboard",
                                      "action": "draft." + body["action"], "target": draft_id,
                                      "detail": "", "tokens": 0, "cost_usd": 0})
        return {"ok": True}

    @r.post("/api/gtm/runs/{run_id}/leads/{company_id}")
    async def lead(run_id: str, company_id: str, body: dict = Body(...)):
        state["posts"].append(("lead", company_id, body))
        for lead_ in state["run"]["leads"]:
            if lead_["company_id"] == company_id:
                lead_["stage"], lead_["owner"] = body["stage"], "rep"
        return {"ok": True}

    return r


@pytest.fixture(scope="module")
def live_server(tmp_path_factory):
    import uvicorn

    from sellbird import dashboard

    state: dict = {}
    dashboard.token_store.configure(tmp_path_factory.mktemp("tok") / "dashboard-token")
    token = dashboard.token_store.get()
    app = dashboard.build_app(routers=[_stub_router(state)])  # the stub wins over any real route
    port = _free_port()
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}", token, state
    srv.should_exit = True
    t.join(timeout=5)


def test_live_run_fills_and_posts(live_server):
    from gtm.fixture_routes import load_fixture

    base, token, state = live_server
    with sync_api.sync_playwright() as p:
        browser = _browser(p)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = _open(page, base, token)

        # Start a run from the one-box intake.
        page.click("#gtm .gtm-tabs button[data-v='intake']")
        page.click("#gtm button[data-act='intake-mode'][data-v='chat']")
        page.fill("#gtm-oneliner", "Northwind Query is a natural-language query layer for data teams. Usage-based, from $30k a year.")
        page.click("#gtm-intake-form button[type=submit]")
        page.wait_for_selector("#gtm-view-icp")
        assert page.locator("#gtm-run-picker").input_value() == RUN_ID
        assert state["run"]["intake"]["product"] == "Northwind Query"
        assert "$30k" in state["run"]["intake"]["pricing"]

        # The pipeline adds companies; the open tab picks them up by polling.
        page.click("#gtm .gtm-tabs button[data-v='leads']")
        assert page.locator("#gtm .gtm-leads tbody tr").count() == 1
        state["run"]["companies"] = copy.deepcopy(load_fixture().model_dump(mode="json")["companies"])
        page.wait_for_function("() => document.querySelectorAll('#gtm .gtm-leads tbody tr').length === 4", timeout=8000)
        assert "Running" in page.locator("#gtm-live").inner_text()
        state["run"]["status"] = "done"
        page.wait_for_function("() => document.getElementById('gtm-live').innerText.includes('Run done')", timeout=8000)

        # Real-run emails are masked until the rep asks to see them.
        assert "d•••@acmefreight.example.com" in page.locator("#gtm .gtm-email").first.inner_text()
        page.click("#gtm button[data-act='mask']")
        assert "dana@acmefreight.example.com" in page.locator("#gtm .gtm-email").first.inner_text()

        # Approve goes to the server with the agreed body, and the UI shows the server's answer.
        page.click("#gtm .gtm-tabs button[data-v='drafts']")
        page.click("#gtm #draft-d_1 button[data-act='approve']")
        page.wait_for_selector("#gtm .gtm-draft", state="detached", timeout=5000)
        assert ("draft", "d_1", {"action": "approve"}) in state["posts"]
        assert next(d for d in state["run"]["drafts"] if d["id"] == "d_1")["status"] == "approved"

        # A refusal from the server is shown, not swallowed.
        state["run"]["drafts"][0]["status"] = "rejected"
        state["run"]["drafts"].append({**state["run"]["drafts"][0], "id": "d_9", "status": "pending"})
        page.wait_for_selector("#gtm #draft-d_9", timeout=15000)  # a done run polls every 12 s
        state["run"]["drafts"][-1]["status"] = "rejected"  # changed under the rep's feet
        page.click("#gtm #draft-d_9 button[data-act='approve']")
        page.wait_for_selector(".toast.error", timeout=5000)
        assert "cannot be approved" in page.locator(".toast.error").inner_text()

        # Stage moves post the stage.
        page.click("#gtm .gtm-tabs button[data-v='pipeline']")
        page.select_option("#gtm-stage-co_initech", "meeting")
        page.wait_for_function("() => document.querySelectorAll('#gtm .gtm-kcol')[3].innerText.includes('Initech')", timeout=5000)
        assert ("lead", "co_initech", {"stage": "meeting"}) in state["posts"]

        browser.close()
        errors = [e for e in errors if "409 (Conflict)" not in e or "/drafts/d_9" not in e]  # provoked above
        assert not errors, "\n".join(errors)


def test_picker_defaults_to_newest_real_run(live_server):
    base, token, _ = live_server
    with sync_api.sync_playwright() as p:
        browser = _browser(p)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = _open(page, base, token)  # no run picked in this tab
        page.wait_for_function(f"() => document.getElementById('gtm-run-picker').value === '{NEWER}'", timeout=5000)
        assert page.locator("#gtm .gtm-title h2").inner_text() == "Product bbbbbb"
        assert "d•••@" in page.locator("#gtm .gtm-email").first.inner_text()  # real runs open masked
        page.select_option("#gtm-run-picker", "fixture")  # the fixture is still one pick away
        page.wait_for_function("() => (document.getElementById('gtm-live')?.innerText || '').includes('Fixture')", timeout=5000)
        browser.close()
        assert not errors, "\n".join(errors)
