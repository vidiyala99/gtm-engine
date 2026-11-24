# Lane B, round 3: a deployable demo and the design doc

Read `docs/gtm/briefs/COMMON.md` first. Start with `git fetch && git merge origin/main`. Hard stop at 35 minutes.

**Goal:** (1) a static build of the GTM workspace that a judge can open from a URL with no server, and (2) the system design doc the organizers require.

## 1. Static demo (`scripts/gtm_static.py`, output `dist/gtm-demo/`, gitignored)
- A standalone page (`dist/gtm-demo/index.html`) that loads `sellbird/web/gtm/*` (and `audit.*` when lane A lands) without Sellbird's dashboard shell or token, with a small fetch shim that maps `/api/gtm/...` to JSON files written next to it.
- Snapshot JSON: the fixture run, the BAND feed, graph and paths for the fixture. Rep actions apply in the page only (as fixture mode already does).
- Check it with `python -m http.server` + the lane's Chromium at 1440 and 390: every tab renders, no console errors. Screenshots to `data/gtm/shots/static-*.png`.
- The owner session deploys `dist/gtm-demo/` to Vercel; you do not deploy.

## 2. Design doc (`docs/gtm/DESIGN.md`)
Short and true to the code, with file paths: architecture (Sellbird extension, lanes), the `Run` contract, graph ontology and the three multi-hop queries, reasoning loops (ICP, discovery with citations and negative signals, enrichment, drafts), the BAND four-agent review and HITL gate, and what is real vs sample (Audit uses a sample workspace; PromptQL run uses real public data). No real people's names or emails.

Keep `python -m pytest -q gtm/tests` green. Commit and push to `lane-b`, update `docs/gtm/briefs/lane-b-status.md`.
