# Lane C, round 2: the real PromptQL run, and three fixes

Read `docs/gtm/briefs/COMMON.md` and your status file first. Your round 1 work is merged into `main` (9be9979), together with lane B (graph + BAND) and, by the time you start, lane A's pipeline routes. Start with `git fetch && git merge origin/main`.

**Goal:** the GTM tab shows the real PromptQL run (`data/gtm/runs/promptql.json`, made by lane A) end to end, and the three defects below are gone. Finish-line items 2 to 7 on real data.

## What changed since round 1
- `.venv/bin/python` now loads the Claude token itself, so model calls work. Always run Python through it.
- Lane B serves `/paths/displacement` as an alias of `competitor_displacement` (round 2 in progress on lane B).
- `web/gtm/*` is in package data; the fixture route is mounted before `/api/gtm/runs/{id}`.

## Fixes (seen by the owner session in your 1440 screenshots)
1. **Toasts overlap:** two toasts render on top of each other (drafts-1440: "Segme..." over "Edit saved..."). Stack them or replace the old one.
2. **Contacts table clips** its last column (Profile / LinkedIn) at 1440 px. No horizontal clipping at 1440 or 390.
3. **Agent Thinking cost:** each row shows the running total, which reads as that event's cost. Show the event's own cost (blank when 0) and keep the cumulative only in the header.

## Real run
- Get the run onto this lane: lane A's run lives on lane 1. Copy is not possible between lanes, so start one here through the UI intake with `gtm/pipeline/intake_promptql.json` (data calls are cached only on lane 1; expect about $0.20 of Glasser spend, stop if a step passes $3). If the run fails, record why and use the fixture.
- Default the run picker to the newest real run. Real runs mask emails by default (keep).
- Rerun your Playwright check on the real run at 1440 and 390, look at every screenshot, paste the counts (companies, rejected, contacts, verified, drafts) into your status file.

Keep `python -m pytest -q gtm/tests` green, commit and push to `lane-c`.
