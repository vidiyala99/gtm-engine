# Lane A status

## Requests to the owner (contract)
- `Run.status` ("running" | "done" | "failed") would save the UI from reading the audit log. Today: progress is the audit log (`run_started`, `step_started`/`step_done`/`step_failed` per step with `agent`=step name, `run_finished`).

## Works
- Step 1 store (`gtm/pipeline/store.py`): atomic JSON at `data/gtm/runs/<id>.json`, per-run lock, `GTM_DATA_DIR` override.
- Step 2 routes (`gtm/pipeline/routes.py`): POST/GET runs, expansions, drafts (approve/reject/edit), leads. Rep changes write `actor="rep"` audit events. Verified through Sellbird's dashboard app (token auth, localhost only).
- Runner (`gtm/pipeline/runner.py`): background thread, steps icp → discover → competitors → enrich → draft, missing steps skipped.

## Route bodies (for lane C)
- expansions: `{"status": "accepted"|"adjusted"|"dismissed", "segment"?: str, "note"?: str}`
- drafts: `{"action": "approve"|"reject"|"edit", "body"?: str, "subject"?: str, "note"?: str}`; edit keeps it pending; 409 once sent.
- leads: `{"stage": Stage, "person_id"?: str}`; creates the lead if missing.
- Every route returns the updated run.

## Run results
- (none yet on PromptQL data)

## Next
- Step 3 ICP with real expansion evidence.

## Blocks
- **Model calls from the lane session:** your smoke test at 22:09 worked (1,944 tokens), so your shell has a credential. My session (Claude Code child) still gets "Not logged in". Please put `CLAUDE_CODE_OAUTH_TOKEN=...` in `/home/node/gtm-engine/.env` (gitignored); `gtm/pipeline/llm.py` loads it. Until then a model miss writes `data/gtm/cache/llm/<agent>-<task>-<hash>.pending.json` and the step stops; the reply can be filled in and the step re-run for free (Glasser calls are cached).
