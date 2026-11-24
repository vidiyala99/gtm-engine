# Lane C status (web)

## Requests to the owner / other lanes
- **Lane A, `Run.status`:** the runner logs `run_finished` / `step_failed` but leaves `status` at `"running"`. The UI now reads the audit log when status says running, so the badge is right either way; setting `status` in `runner.run_all` would make it right for every client.
- **Lane A, nice to have:** product names in `GET /api/gtm/runs` (today `{"ids": [...]}`). The picker now names a run's product once that run loads; the others show their id until picked.
- **Owner, `pyproject.toml`:** done on main (`web/gtm/*` in package data).

## Round 2: done
- **Toasts:** one at a time; a new toast replaces the one showing (`gToast` in gtm.js, core `showToast` untouched). Test: edit then approve leaves exactly one toast, "Approved".
- **Contacts clip:** Profile sits under the person, MX under the email status (6 columns, not 8). Long citations, chips, signal text and audit actions wrap. Kanban is `position: relative` (its sr-only labels were escaping the scroller and widening the page on phones). Filter bars wrap on phones. Test: no table, view, filter bar or page scrolls sideways in any view at 1440 and 390 (fixture); same check run on the real run.
- **Agent thinking cost:** each row shows its own cost (blank when 0, `<$0.001` for tiny charges); the cumulative total is in the header only. Test: header $0.060, rows $0.050 and $0.010, no row shows $0.060.
- **Run picker** opens the newest real run when the tab has no choice yet (ids sort by start time), else the fixture. Test against a stand-in list of two runs. Real runs open with emails masked.
- **Graph** opens on the first path kind that has a path until the rep picks one (the real run has no warm intro; buying cycle has 10).

## Real PromptQL run (this lane, started through the UI intake)
- `run_20261124223453_692498`, intake = `gtm/pipeline/intake_promptql.json`, filled into the Intake form in Chromium and submitted. Data in `data/gtm/runs/` (gitignored).
- Finished (`run_finished`), every step done: **16 companies, 2 rejected, 9 contacts, 4 verified (3 catch-all), 45 drafts waiting, 7 competitors**, 67,436 tokens, **$0.718 spent** (enrich $0.52 of it). Over the brief's $0.20 guess (no cache on this lane), each step far under $3.
- Graph (lane B, python engine): warm intro 0 paths, buying cycle 10, competitor displacement 0.
- Browser check on the real run (`data/gtm/lanec/realcheck.py`), 1440 and 390, every view: picker defaults to the run, badge "Run done", emails masked, no sideways overflow, 0 console or page errors. Screenshots looked at: `data/gtm/shots/real/{view}-{1440,390}[-top].png`.

## Verification
- `python -m pytest -q gtm/tests` on lane-c → 67 passed, 3 skipped.
- Chromium: system libs from `~/chromelibs`, linked by soname in a temp dir. No browser downloaded.

## Known, not fixed
- CJK characters in one cited title render as boxes on this machine (no CJK font installed). Data is correct.
- Leads sheet keeps `max-height: 70vh` with inner scroll, so about two real companies show per screen at 1440 (signals are long). A deliberate choice for the dense sheet; could switch to page scroll if the owner prefers.

## Next
- Merge to main when the owner asks; rerun the real-run check after lane A/B round 2 lands.
