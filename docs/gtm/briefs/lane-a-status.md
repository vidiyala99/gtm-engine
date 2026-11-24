# Lane A status

## Requests to the owner (contract)
- `Run.status` ("running" | "done" | "failed") would save the UI from reading the audit log. Today: progress is the audit log (`run_started`, `step_started`/`step_done`/`step_failed` per step with `agent`=step name, `run_finished`).

## Works
- Step 1 store (`gtm/pipeline/store.py`): atomic JSON at `data/gtm/runs/<id>.json`, per-run lock, `GTM_DATA_DIR` override.
- Step 2 routes (`gtm/pipeline/routes.py`): POST/GET runs, expansions, drafts (approve/reject/edit), leads. Rep changes write `actor="rep"` audit events. Verified through Sellbird's dashboard app (token auth, localhost only).
- Runner (`gtm/pipeline/runner.py`): background thread, steps icp → discover → competitors → enrich → draft, missing steps skipped.
- Step 3 ICP (`icp.py`): model drafts ICP + G2 slugs; Glasser `anyapi /g2.reviews` pulls reviews; model proposes expansions citing review ids; code keeps only real ids and verbatim quotes.
- Step 4 discovery (`discover.py`): Prospeo search via Glasser (industry + headcount + "hiring data roles"; 2nd query worldwide so out-of-region companies show as rejected), homepage citation (free), Sellbird ATS job boards (free), Prospeo funding events (Crunchbase links), Akta news (exec hire, layoffs). Rule-based fit/intent scores, tier, a `<id>_score` signal that states the why. Skips analytics vendors (competitors) and IT-services/staffing firms, with an audit line.
- Clients: `glasser.py` (cache under `data/gtm/cache/glasser/`, $3/step cap), `llm.py` (Sellbird Brain, replies cached by prompt hash, a miss leaves a `.pending.json`), `web.py` (cached page fetch).

## Route bodies (for lane C)
- expansions: `{"status": "accepted"|"adjusted"|"dismissed", "segment"?: str, "note"?: str}`
- drafts: `{"action": "approve"|"reject"|"edit", "body"?: str, "subject"?: str, "note"?: str}`; edit keeps it pending; 409 once sent.
- leads: `{"stage": Stage, "person_id"?: str}`; creates the lead if missing.
- Every route returns the updated run.

## Run results (run id `promptql`, intake `gtm/pipeline/intake_promptql.json`)
- ICP: 4 industries, 2 headcount bands, 4 personas, 5 triggers, each with confidence + why. 3 expansions with 8 G2 review citations (176 reviews from 4 products, $0.0094).
- Discovery: 16 companies, all cited (14 homepage, 2 Prospeo profile). 3 rejected (1 layoffs news article, 2 HQ outside NA/EU). Tiers of the rest: A 6, B 7. Signals: 14 job_post, 11 funding, 2 exec_hire, 4 tech news. Data spend $0.16.
- Model replies for this run's ICP were written by the lane-A session into the reply cache, because the lane CLI can't log in (see Blocks). They're marked `author` in `data/gtm/cache/llm/*.json`; delete those files once the token works and re-run to get Brain replies.

## Next
- Competitors, then enrichment (5 contacts), then drafts.

## Blocks
- **Model calls from the lane session:** your smoke test at 22:09 worked (1,944 tokens), so your shell has a credential. My session (Claude Code child) still gets "Not logged in". Please put `CLAUDE_CODE_OAUTH_TOKEN=...` in `/home/node/gtm-engine/.env` (gitignored); `gtm/pipeline/llm.py` loads it. Until then a model miss writes `data/gtm/cache/llm/<agent>-<task>-<hash>.pending.json` and the step stops; the reply can be filled in and the step re-run for free (Glasser calls are cached).
