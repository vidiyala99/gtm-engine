# Lane C status (web)

## Requests to the owner / other lanes
- **Owner, `pyproject.toml`:** add `"web/gtm/*"` to `[tool.setuptools.package-data] sellbird`. Editable installs work today; a built wheel would drop the GTM tab.
- Resolved: lane A's `{id}` route already serves `fixture`; lane A's POST bodies and lane B's `/paths` and `/band/feed` shapes are what the UI now sends and reads (checked against `origin/lane-a` 487463a and `origin/lane-b` 6574896).
- Nice to have from lane A: product names in `GET /api/gtm/runs` (today `{"ids": [...]}`), so the picker can say "PromptQL (run_…)" instead of the id.

## What works (fixture, in Chromium)
- GTM engine tab in the sidebar (Pipeline group). Files: `sellbird/web/gtm/gtm.{js,css}`; hook = 4 lines in `index.html`, 1 in `app.js`.
- Run picker + reload; facts line (companies, rejected, contacts, verified, drafts waiting, tokens, spend). Real runs poll every 3 s while the tab is open (paused while editing).
- Intake: form + "one box" chat-style; inline validation; POSTs to lane A.
- ICP: every field with a 0.00–1.00 confidence badge (number + colour) and its why; expansion segments with evidence links, accept / adjust (inline note) / dismiss.
- Leads: dense sheet, tier, fit and intent 0–100, signals (negative in red) each with a citation, source link under every company, rejected company stays with its reason. Filters All / A / B / C / Rejected. Contacts sheet: email status badge (verified, catch-all, risky, guess, invalid, unknown), MX, confidence, LinkedIn, source; emails masked by default on real runs (toggle).
- Competitors: direct / indirect / alternative columns, pricing tiers, differentiators, sources.
- Graph: SVG path from lane B's `/paths/{kind}` (warm intro, buying cycle, competitor displacement), three nodes a row with an elbow for longer paths, pager when there are several, each node's source linked; falls back to a browser walk when the API is missing (fixture: p_3 → Globex Pay → p_1). Mobile shows a step list.
- Drafts (HITL): approve / edit (stays waiting) / reject with a reason; the cited signal and its quote beside the copy; review notes on rejected drafts; rejected drafts have no approve button. Approve is the only send path (test inbox only, stated in the UI). On real runs an "Agent review" button starts lane B's BAND review; a draft the agents passed shows "your approval is asked in BAND too".
- Run status (`Run.status`): Running / Run done / Run failed badge; polls every 3 s while running, 12 s after.
- ICP adjust sends the reworded segment (lane A's `segment` field).
- Pipeline: Kanban Matched → Contacted → Replied → Meeting → Closed (won/lost) with a stage select per card; AI vs rep attribution; conversion by tier; A/B variant stats; audit log with timestamps, filter by actor.
- Agent thinking: collapsible feed (state remembered) from the audit log + BAND feed, tokens and cumulative cost per entry.
- Fixture actions apply in this tab only and say so; every rep action adds a rep audit event.

## Verification
- `python -m pytest -q gtm/tests` on lane-c → 9 passed (incl. `gtm/tests/web/test_gtm_web.py` at 1440 and 390 px: clicks every control, fails on console/page errors).
- `gtm/tests/web/test_gtm_web_live.py`: live-run path against an in-memory stand-in for lane A's routes. Intake → run starts and the picker switches; companies added server-side appear by polling within one tick; emails masked on real runs; approve posts `{"action":"approve"}`; a server refusal (409) shows as an error toast; stage move posts `{"stage":...}`.
- Core web tests (dashboard, packaging, signals…): 602 passed, 1 skipped.
- Chromium: the lane's Chromium lacked system libs; the test links the .deb libs in `~/chromelibs` by soname in a temp dir. No browser downloaded.
- Screenshots (looked at, fixed what they showed): `data/gtm/shots/{intake,icp,leads,competitors,graph,drafts,pipeline}-{1440,390}.png`.
- **Integrated with lanes A and B** (no merge pushed): `/tmp/gtm_integrate.py` assembles lane B's `gtm/` + lane A's `pipeline/` + these web tests and runs `gtm/tests` → 49 passed, 3 skipped. The browser check there hits lane B's real `/paths` (kuzu or python engine): warm intro shows both paths (p_2 and p_3 to p_1 via Globex Pay, then the product), with node sources and a path pager.
- Not yet run on real PromptQL data: lane A has no run yet (blocked on the model login, see lane-a-status).

## Design skills (all six present in `~/.claude/skills`)
- impeccable: Operate mode, so restraint and familiar patterns; no modals (edit, reject reason and adjust are inline); theme selection colour; empty, loading (skeleton) and error states.
- taste-core: says dashboards are out of its scope; kept its zero em-dash rule and "no decorative dots" (dots only on real status badges).
- taste-redesign: work inside the existing stack and tokens; no new fonts or libraries; tabular figures.
- frontend-design: one memorable element (the graph path), everything else quiet; sentence-case action labels that name the action; no all-caps eyebrows; dropped monospace for times and codes after the first screenshot (it read as costume).
- emil-design-eng: motion only as feedback (existing press scale, 160 ms chevron rotate); nothing animates on view switch; skeleton pulse off under reduced motion.
- ui-ux-pro-max: colour never alone (confidence shows its number, email status its word, tier its letter); 36 px touch targets on mobile; labels on every input; icon buttons have aria-labels.

## Next
- Switch the default run to the real PromptQL run when lane A lands; rerun the browser check on it and paste counts here.
- Verify the graph against lane B's real `/paths` payload.
