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

- Step 5 enrichment (`enrich.py`): Sellbird people finder on team/about pages + Hunter domain search, ranked against ICP personas (whole-word title match; security/finance/legal etc. excluded); Hunter verifier sets email status + MX (never upgraded); each person cited; a Lead per live company.
- Step 6 drafts (`draft.py`): per contact email 1A/1B/2/3 + LinkedIn via Brain under Sellbird's `email_style` rules; scraped text fenced (`sellbird.untrusted`); a draft citing no real positive signal is dropped; rule breaks go to `review_notes`; all `pending`.

## Run results (run id `promptql`, intake `gtm/pipeline/intake_promptql.json`), all steps real (Brain + Glasser), 2026-11-24 ~22:45
- ICP: 4 industries, 2 headcount bands, 4 personas, 5 triggers, confidence + why each. 3 expansions with 7 verbatim G2 review citations.
- Competitors: 6 (3 direct, 2 indirect, 1 alternative), all cited.
- Discovery: 16 companies, all cited. 2 rejected (HQ outside NA/EU). Live tiers: A 4, B 10. Signals: 12 job_post, 11 funding, 5 tech news, 1 exec_hire. (An earlier run also had 1 layoffs rejection; negative signals vary with the ICP the model writes.)
- Enrichment: 9 contacts at the top companies: 4 verified, 3 catch-all, 1 unknown, 1 guess (no address found). Buyer titles only (CIO/CTO/VP or Head of Engineering/Data).
- Drafts: 45 pending (9 contacts × 1A, 1B, 2, 3, LinkedIn), each citing ≥1 signal; 0 sendable until a rep approves.
- Cost: data $0.58 this run (about $1.10 Glasser total today incl. exploration); model 66,547 tokens on the Claude plan.
- Commands: `.venv/bin/python -m pytest -q gtm/tests` (38 pass). Through the API: `POST /api/gtm/runs` with the intake JSON runs all steps in the background.

## Next
- Owner/lane B/C: wire the UI to `GET /api/gtm/runs/promptql` (or a fresh POST). Possible lane-A follow-ups: graph export helper for lane B, a re-run/refresh route.

## Blocks
- none. (Model login was missing earlier in the session; it works now. A model miss still leaves `data/gtm/cache/llm/*.pending.json` and stops the step.)
