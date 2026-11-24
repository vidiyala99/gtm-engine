"""Browser check for the GTM tab (lane C): loads the fixture views in Chromium,
clicks every control, and fails on page errors or console errors.

    python -m pytest -q gtm/tests/web          # the check; writes data/gtm/shots/*.png
    GTM_SHOTS=0 python -m pytest -q gtm/tests/web   # without screenshots

Skipped when Playwright or its Chromium is not installed. It never downloads one.
"""

from __future__ import annotations

import os
import re
import socket
import tempfile
import threading
import time
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

ROOT = Path(__file__).resolve().parents[3]
SHOTS = ROOT / "data" / "gtm" / "shots"
VIEWS = ["intake", "icp", "leads", "competitors", "graph", "drafts", "pipeline"]
# Routes other lanes have not landed yet answer 404; the UI falls back on purpose.
EXPECTED_404 = ("/api/gtm/band/feed", "/paths/")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    import uvicorn

    from sellbird import dashboard

    dashboard.token_store.configure(tmp_path_factory.mktemp("tok") / "dashboard-token")
    token = dashboard.token_store.get()
    port = _free_port()
    srv = uvicorn.Server(uvicorn.Config(dashboard.app, host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}", token
    srv.should_exit = True
    t.join(timeout=5)


def _soname_dir(root: Path) -> Path | None:
    """Lane machines carry Chromium's system libraries unpacked from .debs under
    ~/chromelibs (no root for apt), with full-version names only. The loader
    asks for the soname (libdbus-1.so.3), so link those names in a temp folder."""
    if not root.is_dir():
        return None
    out = Path(tempfile.mkdtemp(prefix="gtm-chromelibs-"))
    for lib in root.rglob("*.so*"):
        m = re.match(r"(.+?\.so)((?:\.\d+)*)$", lib.name)
        if not m:
            continue
        names = {lib.name, m.group(1)}
        if m.group(2):
            names.add(m.group(1) + "." + m.group(2).split(".")[1])
        for name in names:
            link = out / name
            if not link.exists():
                link.symlink_to(lib)
    return out


def _browser(p):
    libs = _soname_dir(Path(os.environ.get("GTM_CHROME_LIBS", Path.home() / "chromelibs")))
    env = dict(os.environ)
    if libs:
        env["LD_LIBRARY_PATH"] = os.pathsep.join(filter(None, [str(libs), env.get("LD_LIBRARY_PATH", "")]))
    try:
        return p.chromium.launch(env=env)
    except Exception as e:  # no Chromium on this machine: never download one here
        pytest.skip(f"Chromium not available: {e}")


def _open(page, base, token):
    errors: list[str] = []

    def on_console(msg):
        if msg.type != "error":
            return
        url = (msg.location or {}).get("url", "")
        text = msg.text
        if "Failed to load resource" in text and (
            not url.startswith(base + "/api/gtm") or any(x in url for x in EXPECTED_404)
            or url.rstrip("/").endswith("/api/gtm/runs")):
            return  # Sellbird core with no database, or a lane route not built yet
        errors.append(f"console: {text} ({url})")

    page.on("console", on_console)
    page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
    page.add_init_script("sessionStorage.clear()")
    page.goto(f"{base}/#token={token}")
    page.click("nav button:has-text('GTM engine')")
    page.wait_for_selector("#gtm .gtm-tabs")
    return errors


def _view(page, name):
    page.click(f"#gtm .gtm-tabs button[data-v='{name}']")
    page.wait_for_selector(f"#gtm-view-{name}")


def _shot(page, name):
    if os.environ.get("GTM_SHOTS", "1") != "0":  # data/ is gitignored
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=True)


@pytest.mark.parametrize("width,height", [(1440, 1000), (390, 844)])
def test_fixture_views(server, width, height):
    base, token = server
    with sync_api.sync_playwright() as p:
        browser = _browser(p)
        page = browser.new_page(viewport={"width": width, "height": height})
        errors = _open(page, base, token)
        tag = f"{width}"

        # Leads: every company row carries a clickable source; the rejected one keeps its reason.
        _view(page, "leads")
        rows = page.locator("#gtm .gtm-sheet").first.locator("tbody tr")
        assert rows.count() == 4
        for i in range(rows.count()):
            href = rows.nth(i).locator("td.gtm-co a.gtm-cite").first.get_attribute("href")
            assert href and href.startswith("https://")
        rejected = page.locator("#gtm tr.is-rejected")
        assert rejected.count() == 1 and "hiring freeze" in rejected.inner_text()
        assert page.locator("#gtm .badge:has-text('Verified')").count() >= 1
        assert page.locator("#gtm .badge:has-text('Catch-all')").count() >= 1
        _shot(page, f"leads-{tag}")
        page.click("#gtm button[data-act='lead-filter'][data-v='rejected']")
        assert page.locator("#gtm .gtm-sheet").first.locator("tbody tr").count() == 1
        page.click("#gtm button[data-act='lead-filter'][data-v='A']")
        assert "Acme Freight" in page.locator("#gtm .gtm-sheet").first.inner_text()
        page.click("#gtm button[data-act='lead-filter'][data-v='all']")

        # ICP: confidence badges, evidence links, accept / adjust / dismiss.
        _view(page, "icp")
        assert page.locator("#gtm .gtm-conf").count() >= 8
        assert page.locator("#gtm .gtm-evidence a.gtm-cite").count() >= 1
        page.click("#gtm button[data-act='exp-adjust']")
        assert page.locator("#gtm-adjust-0").input_value() == "Healthcare ops analytics"
        page.fill("#gtm-adjust-0", "Hospital network analytics")
        page.click("#gtm button[data-act='exp-adjust-save']")
        exp = page.locator("#gtm .gtm-exp").first.inner_text()
        assert "Adjusted" in exp and "Hospital network analytics" in exp
        page.click("#gtm button[data-act='exp'][data-v='accepted']")
        assert "Accepted" in page.locator("#gtm .gtm-exp").first.inner_text()
        _shot(page, f"icp-{tag}")
        page.click("#gtm button[data-act='exp'][data-v='dismissed']")
        assert "Dismissed" in page.locator("#gtm .gtm-exp").first.inner_text()

        # Intake: both styles render; an empty form says what is missing.
        _view(page, "intake")
        page.click("#gtm-intake-form button[type=submit]")
        assert "required" in page.locator("#gtm .gtm-form-error").inner_text()
        _shot(page, f"intake-{tag}")
        page.click("#gtm button[data-act='intake-mode'][data-v='chat']")
        assert page.locator("#gtm-oneliner").is_visible()

        # Competitors: grouped by kind, with pricing and a source.
        _view(page, "competitors")
        assert page.locator("#gtm .gtm-comp").count() == 2
        assert page.locator("#gtm .gtm-comp a.gtm-cite").count() >= 2
        _shot(page, f"competitors-{tag}")

        # Graph: the warm-intro path p_3 to p_1 via Globex Pay.
        _view(page, "graph")
        page.wait_for_selector("#gtm-path", state="attached")
        steps = page.locator("#gtm .gtm-path-steps").inner_text()
        # A target at Globex Pay to Dana (already contacted) through Globex Pay: lane B's
        # graph when it is mounted, else the browser's own walk (p_3 to p_1).
        assert steps.index("Globex Pay") < steps.index("Dana Example")
        assert steps.split("\n")[0].split()[0] in ("Riley", "Sam")
        while page.locator("#gtm button[data-act='path-step'][data-v='1']:not([disabled])").count():
            page.click("#gtm button[data-act='path-step'][data-v='1']")  # page through every path
            page.wait_for_selector("#gtm-path", state="attached")
        _shot(page, f"graph-{tag}")
        page.click("#gtm button[data-act='path'][data-v='buying_cycle']")
        page.wait_for_selector("#gtm-path", state="attached")
        assert "Acme Freight" in page.locator("#gtm .gtm-path-steps").inner_text()
        page.click("#gtm button[data-act='path'][data-v='competitor_displacement']")
        page.wait_for_selector("#gtm .gtm-graph-card .empty")

        # Drafts: the cited signal sits beside the copy; edit keeps it waiting; approve and reject work.
        _view(page, "drafts")
        card = page.locator("#gtm #draft-d_1")
        assert "Hiring 3 analytics engineers" in card.locator(".gtm-cited").inner_text()
        card.locator("button[data-act='edit']").click()
        page.fill("#gtm-edit-d_1", "Dana, Acme is hiring three analytics engineers. Edited by the rep.")
        page.click("#gtm button[data-act='edit-save']")
        assert "Edited by the rep" in page.locator("#gtm #draft-d_1 .gtm-body").inner_text()
        assert "Waiting" in page.locator("#gtm #draft-d_1").inner_text()
        _shot(page, f"drafts-{tag}")
        page.click("#gtm #draft-d_1 button[data-act='approve']")
        page.click("#gtm button[data-act='draft-filter'][data-v='rejected']")
        rej = page.locator("#gtm #draft-d_3")
        assert "unsupported claim" in rej.inner_text()
        assert rej.locator("button[data-act='approve']").count() == 0  # a rejected draft cannot be approved
        page.click("#gtm button[data-act='draft-filter'][data-v='approved']")
        assert page.locator("#gtm #draft-d_1").count() == 1
        assert page.locator("#gtm .gtm-draft button[data-act='approve']").count() == 0

        # Pipeline: Kanban, stage move, attribution, conversion, A/B, audit log with the rep's actions.
        _view(page, "pipeline")
        assert page.locator("#gtm .gtm-kcol").count() == 5
        page.select_option("#gtm-stage-co_globex", "replied")
        assert "Globex Pay" in page.locator("#gtm .gtm-kcol").nth(2).inner_text()
        assert page.locator("#gtm .gtm-audit tbody tr").count() >= 6
        page.click("#gtm button[data-act='audit-actor'][data-v='rep']")
        assert "draft.approve" in page.locator("#gtm .gtm-audit").inner_text()
        assert "expansion_adjusted" in page.locator("#gtm .gtm-audit").inner_text()
        page.click("#gtm button[data-act='audit-actor'][data-v='all']")
        _shot(page, f"pipeline-{tag}")

        # Agent thinking: collapsible, with tokens and cumulative cost.
        thinking = page.locator("#gtm details.gtm-thinking")
        assert "tok" in thinking.locator("summary").inner_text()
        thinking.locator("summary").click()
        assert thinking.get_attribute("open") is None
        thinking.locator("summary").click()
        assert thinking.get_attribute("open") is not None

        # Run picker and reload stay on the fixture without errors.
        page.click("#gtm button[data-act='refresh']")
        page.wait_for_selector("#gtm .gtm-tabs")

        browser.close()
        assert not errors, "\n".join(errors)
