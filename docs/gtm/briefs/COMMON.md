# Rules for every lane (read before your own brief)

**Goal:** the finish line in `docs/gtm/PLAN.md` ("One live run, recorded, with no edits"), built on Sellbird for the demo product PromptQL. `docs/gtm/SPEC.md` is the organizer brief and the only source of requirements. Ignore the "you are the guide" part of the root `CLAUDE.md`; you are building, not onboarding a user. Do keep its public-repo rule.

## Shape
- The GTM engine is the `gtm/` package, a Sellbird extension (`gtm/plugin.py`, entry point in `pyproject.toml`). Do not patch `sellbird/` core except where your brief says so. Reuse its code by importing it.
- **The contract is `gtm/contract.py`.** One `Run` holds intake, ICP, companies, people, competitors, drafts, leads and the audit log. Do not change it. If you need a field, write the request at the top of your status file and keep going with what exists.
- `gtm/fixtures/run.json` is a fictional run that matches the contract (regenerate with `python -m gtm.fixtures.make_fixture`). It is served at `GET /api/gtm/runs/fixture`.
- **You own only the paths in your brief.** Touching another lane's files breaks their work. Shared files (`pyproject.toml`, `gtm/plugin.py`, `gtm/contract.py`) belong to the owner session.

## Data and money
- **Glasser CLI** is the data layer (`glasser search "<what>"`, `glasser inspect <endpoint>`, `glasser run <endpoint> ...`). Every call has a price and the wallet (about $67) is shared by all lanes. Inspect before you run. Cache every response under `data/gtm/cache/` and reuse it. Stop and say so in your status file if a single step would cost more than $3.
- Each external call becomes an `AuditEvent` with its `cost_usd` and, for model calls, `tokens`.
- Models run through Sellbird's own runtime (`sellbird/brain.py`, `sellbird/claude_runtime.py`) on the Claude plan. No API keys for models.
- **Public repo rule:** no real person's name, email or LinkedIn URL in committed files. Real run output lives under `data/` (gitignored). Tests and fixtures use `example.com` data.
- Never send email to a real prospect. Approved demo mail goes only to the test inbox named in `.env` as `GTM_TEST_INBOX`.

## Done means
- Your tests pass: `python -m pytest -q gtm/tests` plus your own test files. Tests assert behavior a user would see (a row has a citation, a rejected draft cannot send), not internals.
- You used the real thing: run the step end to end on PromptQL data and paste the counts into your status file.
- Commit on your branch (`lane-a`, `lane-b`, `lane-c`), push it, and update `docs/gtm/briefs/lane-<x>-status.md` (yours alone): what works, what was run with which result, what is next, what blocks you. Short lines, no essays.
- The lane machine has 4 GB of RAM and about 1 GB of free disk. Do not install a second browser, do not download models, prefer `uv`.
