# Lane B status

## Requests to the owner
- Add `kuzu==0.11.3` to `pyproject.toml` (installed on the lane with `uv pip`; the graph falls back to plain Python without it).
- Add `band-sdk` to `pyproject.toml` when BAND goes live.
- Fixture: no company has a competitor-use + churn signal, so `/paths/competitor_displacement` is empty on it. Tests build one in code.

## Round 2
### Step 1: mock BAND with the real model: done
- Model login works through `.venv/bin/python` (Sellbird Brain, Claude plan).
- First d_1 run was rejected wrongly: the Builder listed facts from the Planner's handoff (title, tier, scores) as draft claims, and the hard guard counted each one as unsupported. Fix: Builder and Reviewer prompts now count only the words in the draft's subject and body; a greeting name is not a claim; a fragment cut off with "..." counts only for what it states before the cut.
- CLI: `--mode live|mock` before the command (one run only, `.env` untouched); `reset DRAFT...` sets fixture drafts back to pending.
- Result (`cli --mode mock review fixture d_1`, then `d_3`):
  - d_1 → `awaiting_rep`. #4 planner→@builder tok=2600 · #5 builder→@reviewer tok=2884 · #6 reviewer→@security PASS ("all completed claims supported by sig_1; the truncated fragment states nothing") tok=3005 · #7 security→@rep,planner approval_request PASS tok=2383. Cost for d_1: $0.0218.
  - d_3 → `rejected`. #8 planner tok=2567 · #9 builder tok=3355 · #10 reviewer→@builder,planner REJECT: unsupported claim "New data leaders usually inherit a report backlog" (no signal) tok=3114. Cost for d_3: $0.0255.
  - Feed total, including the wrong first d_1 run (#1-#3): 10 messages, 29,018 tokens, $0.0738 (cost as reported by Sellbird's usage rows).

### Step 3: path alias: done
- `/paths/displacement` serves `competitor_displacement` (same body, `kind` is the canonical name). Test: `test_displacement_alias_serves_competitor_displacement` (both engines).

### Step 2: live BAND: done, waiting on the rep
- `cli --mode live smoke`: pooled room `318911c9-f605-463a-b626-71ecf02cdf74` ("GTM Engine review"), cast planner, builder, reviewer, security + rep (owner); hello posted to @rep.
- `cli --mode live review fixture d_1` → `awaiting_rep`, real model decisions posted in BAND: #11 planner→@builder tok=2601 · #12 builder→@reviewer tok=2885 · #13 reviewer→@security PASS ("the only claim, three openings, is supported by sig_1") tok=2966 · #14 security→@rep,planner approval request tok=2379. 10,831 tokens, $0.0198.
- `cli --mode live wait fixture d_1 115` → "still waiting" (no reply within 2 minutes). The request stays open in `data/gtm/band/state.json`.
- **Owner:** in the Band app, reply in that room to the planner with `@planner approve d_1` (or `reject d_1`), then run `.venv/bin/python -m gtm.band.cli --mode live wait fixture d_1 60`. It sets d_1's status and the planner acknowledges.
- Re-run from scratch: `.venv/bin/python -m gtm.band.cli reset d_1` (fixture status back to pending, open request dropped).

## Graph (`gtm/graph/`): done
- Engine: **kuzu 0.11.3** (21 MB wheel, embedded, works on the lane). Plain-Python traversal behind the same `paths()` is the fallback; tests hold both engines to identical output.
- One kuzu file per run in `data/gtm/graph/<run_id>.kuzu`, rebuilt when the run's graph changes; buffer pool capped at 64 MB.
- Ontology: Company, Person, Product, Competitor, Signal + **School** (added). Edges from SPEC + **attended**, **has_signal**, **uses** (Company→Competitor, derived when a signal names a competitor).
- Past employers not in the run become external Company nodes (`company:ext-<slug>`).
- Queries: `warm_intro` (shared past employer or school, to someone already contacted), `buying_cycle` (job post → matched company → persona from ICP), `competitor_displacement` (uses competitor + churn/complaint signal).
- Routes: `GET /api/gtm/runs/{id}/graph`, `GET /api/gtm/runs/{id}/paths/{kind}?target=p_3&engine=auto|kuzu|python`.
- Runs load from `gtm.pipeline.store` when it lands, else the fixture.
- Fixture result: 13 nodes, 14 edges; warm intro p_3 → Globex Pay → p_1 (plus p_2 → p_1); buying cycle sig_1 → Acme → Dana.

## BAND room (`gtm/band/`): mock mode done, live blocked (see Blocks)
- `transport.py`: `HEEL_BAND_*` → `GTM_BAND_*`; room pool kept, pool file now `data/gtm/band/rooms.json` (gitignored); `reject` now counts as a rep verdict.
- `room.py` flow per draft: planner @builder (handoff) → builder @reviewer (draft verbatim + claim list) → reviewer @security (pass) or @builder,@planner (REJECT with reasons) → security @rep,@planner (approval request) or BLOCK → rep replies @planner → status changes.
- Every agent step is one model call (`model.py` → Sellbird `Brain`, tokens and cost read from its usage rows). Hard checks only tighten: a claim with no signal, a cited signal the company lacks, a negative signal, phone/email/http/shortener/off-list links (`GTM_LINK_DOMAINS`).
- `approved` only from a rep message, only after reviewer and security pass. Model outage → `stalled`, draft untouched.
- Each message → feed item (tokens, cumulative cost) + `AuditEvent` on the run. Feed and waiting state persist in `data/gtm/band/`.
- Routes: `GET /api/gtm/band/feed?since=N`, `POST /api/gtm/band/review/{run}/{draft}?wait=true`, `POST /api/gtm/band/rep/{run}/{draft}` (mock only), `POST /api/gtm/band/poll` (live; also auto-polls every 5 s while waiting).

- Live transport: the rep's id is resolved from `GTM_BAND_REP_HANDLE` among the planner's peers (found: a User peer); rep replies read newest-first; "asked at" uses BAND's clock.
- Read-only live probe worked (identity + peers). Note: the four BAND agents are the reused HEEL TURN wrestler identities (display names like "Brutus Kane"); rename them in the Band app if that matters for the video.
- CLI: `python -m gtm.band.cli smoke | review RUN DRAFT | wait RUN DRAFT [sec] | feed`.
- Checked through Sellbird's real dashboard app (in-process, temp state): no token → 401; `/graph` 200 (13 nodes, 14 edges); `/paths/warm_intro?target=p_3` → kuzu: Riley → Globex Pay → Dana → product; `/band/review/fixture/d_1` → `stalled` (CLI logged out), draft stays `pending`.

## Next (owner)
1. Log the lane's Claude CLI in (below). Then mock run with the real model: `python -m gtm.band.cli review fixture d_1`.
2. Go live: set `GTM_BAND_MODE=live` in `.env`, run `python -m gtm.band.cli smoke` (creates 1 pooled room), then `review` and reply `approve d_1` to the planner in the Band app; `wait` picks it up. My live send needed an approval this session doesn't have, so it has not run yet.

## Blocks
- **Claude CLI on the lane is not logged in for headless calls**: `claude -p` returns "Not logged in · Please run /login" with or without Sellbird's isolation flags. No `~/.claude/.credentials.json`. Every BAND agent decision needs it. Owner: run `claude login` (or `claude setup-token` and put `CLAUDE_CODE_OAUTH_TOKEN` in the lane env). I did not work around auth.

## Tests
- `python -m pytest -q gtm/tests`: 41 passed (round 2).

## Lane A integration
- `gtm/graph/runs.py` reads with `gtm.pipeline.store.load` and writes BAND events with `store.update` (locked read-modify-write), matching lane A's store on `origin/lane-a`. Test holds it to that API with a stand-in module.
- Not yet run on real PromptQL data: no saved run on this lane (`data/gtm/runs/` empty) and lane A is blocked on the same model login. When a run exists: `curl .../api/gtm/runs/<id>/paths/warm_intro` and `python -m gtm.band.cli review <id> <draft>`.
