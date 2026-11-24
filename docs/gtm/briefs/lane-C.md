# Lane C: the web (GTM workspace in Sellbird's dashboard)

Read `docs/gtm/briefs/COMMON.md` first.

**Goal:** finish-line items 2 to 7 visible and usable in the browser: intake, ICP, cited leads, graph path, enrichment badges, the HITL draft queue, and the dashboard (Kanban, attribution, audit log, conversion by tier, A/B stats), plus the collapsible "Agent Thinking" feed.

**You own:** a new `sellbird/web/gtm/` folder (HTML, CSS, JS for the GTM views) and the smallest possible hook in `sellbird/web/index.html` and `sellbird/web/app.js` to add a GTM tab. Nothing else in `sellbird/`.

## Build order
1. Read Sellbird's dashboard first (`sellbird/web/index.html`, `app.js`, `app.css`, and `sellbird dashboard` locally) and extend its look: its fonts, colors and spacing. No build step, no framework, no CDN; it must work offline like the rest of the dashboard.
2. Build every view against `GET /api/gtm/runs/fixture` from minute one. Switch to `GET /api/gtm/runs/{id}` with a run picker when lane A's routes land. Poll while a run is in progress so the user watches it fill.
3. Views, in this order:
   - **Intake:** a form (product, description, features, constraints, customers, pricing) and a one-box chat-style alternative.
   - **ICP card:** each field with its confidence badge (0.00 to 1.00) and its "why"; expansion segments with their evidence links and accept / adjust / dismiss.
   - **Leads table:** dense, spreadsheet-like. Company, tier, fit and intent (0 to 100), signals, and a citation link on every row. Rejected companies stay visible with their reason. Enrichment status badge per contact (verified, catch-all, risky, guess, invalid, unknown).
   - **Competitor map:** direct, indirect, alternative with pricing tiers.
   - **Graph path:** draw the multi-hop path from lane B's `/paths/{kind}` (fixture fallback: p_3 to p_1 via Globex Pay). Simple inline SVG is enough.
   - **Draft queue (HITL):** approve / edit / reject per draft, the cited signal shown beside the copy, reviewer notes shown on rejected drafts. Approve is the only path to send.
   - **Pipeline:** Kanban Matched, Contacted, Replied, Meeting, Closed (won/lost), AI vs rep attribution, audit log with timestamps, conversion by tier, A/B variant stats.
   - **Agent Thinking:** collapsible live feed from the audit log and `GET /api/gtm/band/feed`, with tokens and cumulative cost.
4. The spec asks for an editorial look over a dense spreadsheet surface. Density and legibility beat decoration.

## Design process (owner rule, every round)
- Before the first view, load these skills if they exist on the lane (`~/.claude/skills`, plugins): impeccable, taste-core, taste-redesign, ui-ux-pro-max, emil-design-eng, frontend-design. In your status file, name what each one said that changed a decision. If a skill is missing on the lane, say which.
- Verify every view in a real browser on the lane (Playwright with the Chromium already installed; never download another). Check 1440 px and 390 px wide, click every control, and save screenshots to `data/gtm/shots/` with their paths in your status file. A passing script is not done; a screenshot you looked at is.

## Test command
`python -m pytest -q gtm/tests` (keep it green; you add no Python unless a test needs it). Plus your Playwright check script under `gtm/tests/web/` that loads the fixture views and fails on console errors.
