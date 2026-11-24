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
- **Model calls:** the `claude` CLI on this lane says "Not logged in" (no `~/.claude` credentials, no `CLAUDE_CODE_OAUTH_TOKEN`). Sellbird's Brain therefore returns nothing. Fix on the lane: `claude login`, or `claude setup-token` and export `CLAUDE_CODE_OAUTH_TOKEN`. Smoke test: `.venv/bin/python -c "from gtm.pipeline import llm; print(llm.ask_json('Return {\"ok\": true}', agent='t', task='t'))"`.
