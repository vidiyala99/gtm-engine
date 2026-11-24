# Lane C status (web)

## Requests to the owner / other lanes
- **Owner, `pyproject.toml`:** add `"web/gtm/*"` to `[tool.setuptools.package-data] sellbird`. Editable installs work today; a built wheel would drop the GTM tab.
- **Lane A, POST bodies the UI sends** (match these, or tell me yours):
  - `POST /api/gtm/runs` body = `Intake` JSON; reads `id` (or `run_id`) from the reply.
  - `POST /api/gtm/runs/{id}/drafts/{draft_id}` `{"action": "approve"|"reject"|"edit", "body"?: str, "note"?: str}`
  - `POST /api/gtm/runs/{id}/expansions/{i}` `{"status": "accepted"|"adjusted"|"dismissed", "note": str}`
  - `POST /api/gtm/runs/{id}/leads/{company_id}` `{"stage": <Stage>}`
  - Nice to have: `GET /api/gtm/runs` → list of `{id, intake.product}` for the run picker (falls back to runs started from this browser).
  - Errors: a JSON `{"detail"|"message": "..."}` is shown to the user as is.
- **Lane B:** `/paths/{kind}` with `kind` in `warm_intro | buying_cycle | displacement`; UI reads `{nodes:[{id,label|name,type}], edges:[{source,target,type}]}` (or a list of those). `/band/feed` → `{messages:[{sender,text,mentions,tokens,cost_usd,t|at}]}` or a bare list.

## What works (fixture, in Chromium)
- GTM engine tab in the sidebar (Pipeline group). Files: `sellbird/web/gtm/gtm.{js,css}`; hook = 4 lines in `index.html`, 1 in `app.js`.
- Run picker + reload; facts line (companies, rejected, contacts, verified, drafts waiting, tokens, spend). Real runs poll every 3 s while the tab is open (paused while editing).
- Intake: form + "one box" chat-style; inline validation; POSTs to lane A.
- ICP: every field with a 0.00–1.00 confidence badge (number + colour) and its why; expansion segments with evidence links, accept / adjust (inline note) / dismiss.
- Leads: dense sheet, tier, fit and intent 0–100, signals (negative in red) each with a citation, source link under every company, rejected company stays with its reason. Filters All / A / B / C / Rejected. Contacts sheet: email status badge (verified, catch-all, risky, guess, invalid, unknown), MX, confidence, LinkedIn, source; emails masked by default on real runs (toggle).
- Competitors: direct / indirect / alternative columns, pricing tiers, differentiators, sources.
- Graph: SVG path from lane B's `/paths/{kind}`; falls back to computing warm intro and buying cycle in the browser. Fixture shows p_3 → Globex Pay → p_1. Mobile shows a step list.
- Drafts (HITL): approve / edit (stays waiting) / reject with a reason; the cited signal and its quote beside the copy; review notes on rejected drafts; rejected drafts have no approve button. Approve is the only send path (test inbox only, stated in the UI).
- Pipeline: Kanban Matched → Contacted → Replied → Meeting → Closed (won/lost) with a stage select per card; AI vs rep attribution; conversion by tier; A/B variant stats; audit log with timestamps, filter by actor.
- Agent thinking: collapsible feed (state remembered) from the audit log + BAND feed, tokens and cumulative cost per entry.
- Fixture actions apply in this tab only and say so; every rep action adds a rep audit event.

## Verification
- `python -m pytest -q gtm/tests` → 8 passed (incl. `gtm/tests/web/test_gtm_web.py` at 1440 and 390 px: clicks every control, fails on console/page errors).
- Core web tests (dashboard, packaging, signals…): 602 passed, 1 skipped.
- Chromium: the lane's Chromium lacked system libs; the test links the .deb libs in `~/chromelibs` by soname in a temp dir. No browser downloaded.
- Screenshots (looked at, fixed what they showed): `data/gtm/shots/{intake,icp,leads,competitors,graph,drafts,pipeline}-{1440,390}.png`.
- Not yet run on real PromptQL data: lane A's routes are not on any branch yet (checked `origin`).

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
