# Decision log (newest last; owner decisions marked "owner")

| When | Decision | Who | Why |
|---|---|---|---|
| 2026-11-23 23:35 | Both bonuses (Band +20, Flexprice +20) are must-haves; Snyk is last | Claude | Each bonus weighs as much as the largest base criterion; Snyk isn't scored |
| 2026-11-23 23:35 | No code before kickoff, only research and setup | Claude | Pre-built code may break the event rules |
| 2026-11-23 23:37 | Fork Sellbird (formerly Harvey); don't rebuild | owner | "Don't reinvent the wheel" |
| 2026-11-23 23:37 | Don't use Actintro as the demo product | owner | |
| 2026-11-23 23:40 | Demo product is PromptQL (Hasura) | owner | Owner wants a reply from Rajoshi |
| 2026-11-23 23:41 | The email to Rajoshi goes through Shipyard (checks + "ship it"); the engine never sends it; it leads with useful output | Claude (owner invited corrections) | Shipyard hard rules; a bot-on-your-product email reads as spam |
| 2026-11-23 23:41 | Real prospects' emails and LinkedIn URLs are masked in the public repo and video; demo sends go only to a test inbox | Claude | AGPL repo is public; privacy |
| 2026-11-23 23:45 | Extend Sellbird's no-build dashboard rather than Next.js | Claude | It already has the Outbox approval desk |
| 2026-11-23 23:55 | HumanLayer not adopted; lint repos used for ideas only (JS side); spec rules encoded as Python checks | Claude | Too heavy for the day; Sellbird is Python |
| 2026-11-24 00:00 | All state lives in these markdown files; no scratchpad, no auto-memory | owner | "Never use scratchpads" |
| 2026-11-24 13:37 | No sponsor details: build from SPEC.md alone | owner | "we play with whatever's in the doc" |
| 2026-11-24 13:13 | Heavy work (tests, servers, browsers) runs on Agent37 lanes, not the laptop; owner talks to lanes via T3 Code | owner | Laptop memory; "open the claude code sessions in agent37" |
| 2026-11-24 13:26 | Old project folders on lane 1 deleted to free disk | owner | "delete, we must've already everything on github" |
| 2026-11-24 09:50 | Glasser CLI is the candidate data layer (discovery, enrichment, cost per call) | Claude | Already logged in, one tool for many providers, pay per call fits Flexprice |
| 2026-11-24 13:44 | Flexprice dropped; BAND uses yesterday's keys; Glasser installed on lanes 1-3 | owner | "ignore flexprice we don't have a business"; "I thought you had band key"; "install glasser on those machines" |
