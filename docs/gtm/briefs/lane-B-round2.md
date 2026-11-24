# Lane B, round 2: real model, then live BAND

Read `docs/gtm/briefs/COMMON.md` and your status file first. Your round 1 work is merged into `main` (0f7822f). Start with `git fetch && git merge origin/main`.

**Goal:** finish-line item 8 runs for real: four agents in a live BAND room review a draft with model decisions, the reviewer rejects an unsupported claim, and the rep's reply in the Band app sets the status.

## What changed since round 1
- **Model login is fixed.** `.venv/bin/python` now loads the Claude token itself (the lane agent's own shell drops it). Always run Python through `.venv/bin/python`. Smoke: `.venv/bin/python -m gtm.band.cli smoke` in mock mode should show real model replies.
- `kuzu==0.11.3` is in `pyproject.toml` on main.

## Steps
1. **Mock with the real model:** `GTM_BAND_MODE=mock` review of fixture `d_1` (should pass to the rep) and `d_3` (the reviewer should reject "usually inherit"). Paste the feed lines (sender, verdict, tokens, cost) into your status file.
2. **Live:** you are authorized to post in the pooled BAND rooms with the four GTM agent identities and to send the rep (the owner) an approval request. That is the feature, not an outward-facing send. Set `GTM_BAND_MODE=live` for the run only (env on the command, not `.env`), run `smoke`, then `review fixture d_1`. Do not wait more than 2 minutes for the rep; leave it awaiting and record the room so the owner can reply later with `wait`.
3. **Path name:** lane C calls `/paths/displacement`; you serve `competitor_displacement`. Accept both names (alias), with a test.
4. Keep `python -m pytest -q gtm/tests` green, commit and push to `lane-b`, update `docs/gtm/briefs/lane-b-status.md`.
