# Lane A: the pipeline (intake to drafts)

Read `docs/gtm/briefs/COMMON.md` first.

**Goal:** a real PromptQL run that produces a `Run` with an ICP and at least 10 cited companies (at least 1 rejected by a negative signal), then 5 enriched contacts and signal-cited drafts. Finish-line items 1, 2, 3, 5, 6 in `docs/gtm/PLAN.md`. First milestone: items 1 to 3 through the API.

**You own:** `gtm/pipeline/` (new) and `gtm/tests/test_pipeline*.py`.

## Steps, each one verified before the next
1. **Store** (`gtm/pipeline/store.py`): save and load `Run` JSON at `data/gtm/runs/<id>.json`. Writes are atomic (temp file plus rename) so a crash never leaves half a run.
2. **Routes** (`gtm/pipeline/routes.py`, exposes `router`; `gtm/plugin.py` already mounts it):
   - `POST /api/gtm/runs` with an `Intake` body starts a run in the background and returns its id.
   - `GET /api/gtm/runs/{id}` returns the run as it stands, so the UI can poll and watch it fill.
   - `POST /api/gtm/runs/{id}/expansions/{i}` with `accepted|adjusted|dismissed`.
   - `POST /api/gtm/runs/{id}/drafts/{draft_id}` with `approve|reject|edit` (an edit changes the body and stays pending).
   - `POST /api/gtm/runs/{id}/leads/{company_id}` to move a stage.
   - Every state change by a person is an `AuditEvent` with `actor="rep"`.
3. **ICP** (`icp.py`): intake text to `ICP` with per-field confidence and a `why`. Expansions must carry real evidence (for example G2 review complaints via `glasser:/g2.reviews`).
4. **Discovery** (`discover.py`): ICP to companies.
   - Sources: Glasser company search and similar companies, Aviato funding, Akta headcount, and Sellbird's job-post collector (`sellbird/collectors/ats.py`).
   - Every company has at least one `Citation` with a real URL and a quote. The contract refuses one without.
   - Score fit and intent 0 to 100, tier A/B/C, and say why in the signal summaries.
   - Negative signals (hiring freeze, layoffs, non-target region) set `rejected_reason`; the company stays in the run so the UI can show the rejection.
   - Competitors (`competitors.py`): direct, indirect and alternative, with public pricing where it exists.
5. **Enrichment** (`enrich.py`): decision makers per tier A/B company via Sellbird's people finder (`sellbird/collectors/people.py`) plus Hunter through Glasser. Email status and MX come from the verifier, never a guess marked verified.
6. **Drafts** (`draft.py`): email (3 steps) and LinkedIn per contact through Sellbird's writer, each citing at least one signal id. Two variants (A/B) on the first email. All start `pending`.

## Test command
`python -m pytest -q gtm/tests`

Tests to have: a company row without a citation never reaches the run; a rejected company keeps its reason; a draft approve writes a rep audit event; only approved drafts are sendable (`gtm.contract.can_send`).
