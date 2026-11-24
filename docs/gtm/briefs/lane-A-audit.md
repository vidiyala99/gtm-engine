# Lane A, round 2: the Audit tab (first screen of the GTM workspace)

Read `docs/gtm/briefs/COMMON.md` first. Start with `git fetch && git merge origin/main`. Hard stop: push a working tab within 30 minutes; the hackathon submits soon after.

**Goal:** the GTM workspace opens on an **Audit** tab that matches the approved direction in `docs/gtm/mockups/audit.html` (open it in the lane's Chromium first): verdict headline, four ranked findings (Keep / Cut / Fix) with receipt sidenotes naming the exact records and the tool's logo, a spend vs booked-calls dumbbell chart, and a "Build the target list" button that switches to the existing Intake/ICP view.

**You own:** new files `sellbird/web/gtm/audit.js`, `sellbird/web/gtm/audit.css`, `gtm/fixtures/audit.json` (the sample workspace "Halden Freight", labeled sample), and exactly one change in `sellbird/web/gtm/gtm.js`: add `['audit', 'Audit']` first in the views list and route it to your render function. Lane C is editing `gtm.js` in parallel: keep your change to those lines so the merge is trivial.

## Design process (owner rule, mandatory, before code)
Design skills are in `~/.claude/skills`. Run them, do not just read the names:
1. impeccable: run `~/.claude/skills/impeccable/scripts/impeccable context` if present (scripts may be missing; then say so), read `reference/operate.md` and `reference/craft-floor.md` before the first edit.
2. ui-ux-pro-max: run its search for "dumbbell chart comparison" (`--domain chart`) and "data table dashboard density" (`--domain ux`) and apply what matches.
3. taste-redesign, frontend-design, emil-design-eng: extend Sellbird's own tokens (`sellbird/web/app.css`), no new fonts, one memorable element (the receipt sidenotes), motion only as feedback.
Write in your status file one line per skill: what it told you and what it changed.

## Rules
- Logos: copy the inline SVG paths from the mockup (real Simple Icons, CC0). No monogram fake logos, no colored rail on cards, no pills on everything.
- The chart is inline SVG drawn to one scale; its labels stay at least 12px at 390px wide (draw labels in HTML or use a non-scaling layout on mobile).
- Verify in the lane's Chromium at 1440 and 390 px (use the existing web test harness in `gtm/tests/web/`), look at the screenshots, add a test that the Audit tab renders 4 findings, 7 receipts and the button switches view.
- Keep `python -m pytest -q gtm/tests` green. Commit and push to `lane-a`, update `docs/gtm/briefs/lane-a-status.md` with screenshot paths.
