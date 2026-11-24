# Lane B: the knowledge graph and the BAND agent room

Read `docs/gtm/briefs/COMMON.md` first.

**Goal:** finish-line items 4 and 8 in `docs/gtm/PLAN.md`: a graph built from a `Run` with one multi-hop query shown on screen, and four agents in a BAND room that review drafts, reject an unsupported claim, and wait for a human approval before any send.

**You own:** `gtm/graph/`, `gtm/band/` and `gtm/tests/test_graph*.py`, `gtm/tests/test_band*.py`.

## Graph (`gtm/graph/`)
1. **Engine:** first check, in under 10 minutes, whether `kuzu` installs and runs on the lane (pip wheel, embedded, no server). Its upstream was archived in 2025, so if it fails, use a plain Python graph (dicts of nodes and typed edges) behind the same functions. Record the choice in your status file.
2. **Ontology from SPEC.md Module 3:** nodes Company, Person, Product, Competitor, Signal. Edges works_at, competes_with, matched_to, contacted_via, replied_to, previously_employed_at. Add `attended` (school) and `has_signal` if needed, and say so in the status file.
3. `build(run) -> Graph` is idempotent: building twice from the same run gives the same graph.
4. Queries, each returning the path as a list of nodes and edges so the UI can draw it:
   - warm intro: from a target person to anyone we already contacted, via a shared past employer or school;
   - buying cycle: a job post signal tied to a matched company and its persona;
   - competitor displacement: a company that uses a competitor and has a churn or complaint signal.
5. `routes.py` exposes `router`: `GET /api/gtm/runs/{id}/graph` (nodes and edges) and `GET /api/gtm/runs/{id}/paths/{kind}`. Read runs with lane A's store (`gtm.pipeline.store`) when it lands; until then read `gtm/fixtures/run.json`.

## BAND room (`gtm/band/`)
- `gtm/band/transport.py` is working code copied from the owner's earlier project. It has a mock mode with BAND's delivery rules and a live mode through `band-sdk`. Rename its `HEEL_BAND_*` env names to `GTM_BAND_*`; keep its room pool (BAND allows 250 rooms per account).
- Cast: `planner`, `builder`, `reviewer`, `security` (agents) and `rep` (the human). Live keys arrive on the lane's `.env` as `GTM_BAND_<ROLE>_ID` and `GTM_BAND_<ROLE>_KEY`.
- **Flow for one draft:** planner @mentions builder with the lead and its signals. Builder posts the draft. Reviewer checks every claim against the cited signals and rejects any claim without one, with the reason. Security checks for private data and unsafe links. Only then does the rep get an approval request; the draft's status changes only on the rep's reply.
- Every agent decision is a model call, not a script. Each message becomes an `AuditEvent` with agent, tokens and cost.
- `routes.py`: `GET /api/gtm/band/feed` (messages, tokens and cumulative cost, for the UI's live feed) and `POST /api/gtm/band/review/{run_id}/{draft_id}` to start the flow.
- Build and test in mock mode first. Switch to live only when mock passes.

## Test command
`python -m pytest -q gtm/tests`

Tests to have: graph build is idempotent; the warm-intro query finds the path in the fixture (p_3 to p_1 via Globex Pay); the reviewer rejects a draft whose claim has no signal; no draft reaches `approved` without a rep message.
