# AI GTM Engine: plan (drafted 2026-11-23 23:35 from the organizer spec; follow ../PLAYBOOK.md)

## Scoring math (what wins)
- **Base criteria total 80%:** ICP & discovery 20, enrichment & outreach 20, dashboard 15, viability 15, tech & demo 10.
- **Band +20** is a must-have. **Flexprice dropped 2026-11-24 13:44 (owner)**: no business to bill, so the +20 is given up.
- Snyk is in the spec but not in the scoring matrix, so it's last in the queue (a CI SAST/SCA run, about 20 minutes).

## Finish line (measurable)
One live run, recorded, with no edits:
1. **Intake:** type a real product description.
2. **ICP:** structured ICP with per-field confidence and 2 to 3 expansion segments to accept or dismiss.
3. **Discovery:** at least 10 real companies and buyers. Every row has a clickable source citation. At least 1 is rejected by a negative signal.
4. **Graph:** stored in the graph. One multi-hop query is shown on screen: a warm-intro path, or a job post tied to a buying cycle.
5. **Enrichment:** at least 5 contacts with verified email or MX status, plus a confidence badge.
6. **Outreach:** an email and LinkedIn draft citing a specific signal. It goes through the HITL queue (approve / edit / reject).
   - Approved mail is sent only to our own test inbox, never to real prospects.
7. **Dashboard:** Kanban with stages Matched → Contacted → Replied → Meeting → Closed. AI vs rep attribution, audit log, conversion by tier, A/B variant stats.
8. **Band:** Planner, Builder, Reviewer and Security agents in a BAND room, handing off via @mentions.
   - The Reviewer rejects a draft with an unsupported claim.
   - A human approves the send in BAND.
   - The token and cost stream is visible.
9. **Flexprice:** events are metered (leads enriched, outreach sent, graph queries). When the credit balance hits zero, enrichment is gated live in the demo. Cost per lead appears in the ledger.

## Scope cuts (decided up front)
- **Real data:** real search and enrichment on one product, not a generic multi-tenant app.
- **No real outreach:** LinkedIn is draft-only. The LinkedIn API isn't usable in a day, so we say so honestly.
- **"Continuous signal ingestion"** is a refresh button plus one scheduled re-run, not a streaming system.
- **Everything else goes to QUEUE.md.**

## Base: fork Sellbird (formerly Harvey), don't rebuild (owner 2026-11-23 23:37)
- **Repo:** github.com/ethanplusai/sellbird (old `ethanplusai/harvey` redirects). Cloned to `ref/sellbird`, last commit 2026-11-18, about 39k lines of Python, 242 tests.
- **License: AGPL-3.0.** Our fork must stay public and AGPL, with credit in the README. That's fine for a hackathon. Ask the organizers whether building on an open-source base is allowed. It usually is when disclosed.

| Spec module | Sellbird already has | We add |
|---|---|---|
| 1 Intake & ICP | `sellbird train <url>` learns the product; 23-signal catalog you confirm (`signals.py`) | Plain-language chat/form intake; ICP fields with 0–1 confidence; expansion segments to accept or dismiss |
| 2 Discovery | Provider adapters (`collectors/discover.py`: OSM, Serper, TinyFish, DataForSEO, Scavio); free site profiler; ATS/job-post collector | Inline source citations per row; competitor map. It's tuned for local SMBs, so add a B2B source (Serper/TinyFish queries) |
| 3 Knowledge graph | nothing (SQLite) | Neo4j/Kùzu graph built from its SQLite data; multi-hop queries (warm intro, job post tied to a buying cycle, competitor displacement) |
| 4 Enrichment & outreach | Decision-maker finder, email-pattern verification (verified/risky/guess/invalid), writer, LinkedIn module, **Outbox approval queue (A/R keys)**, pre-send gate | Hunter/Apollo as extra verifiers; per-signal personalization shown with its citation |
| 5 Dashboard | FastAPI JSON API + no-build web dashboard (Today, Outbox, conversations, contacts) | Kanban by stage, AI vs rep attribution, conversion by tier, A/B variant stats |
| Band +20 | 5 internal agents (scout, writer, sender, handler, analyst) | Run them as Planner/Builder/Reviewer/Security in a BAND room with @mentions; HITL approve in BAND; token/cost stream |
| Flexprice +20 | Its own budget and usage tracking (`usage.py`, quota) | Meter enrich/send/graph-query events to Flexprice; credit gate before enrichment |

- **Model runtime:** it thinks through the Claude Code CLI on your Claude plan, or Codex on a ChatGPT plan, so no API key is needed. Check it runs on Windows (or in its Docker image) first thing.

## Edge we already own
- **The owner's existing outreach workflow already is a GTM loop:**
  - scout → enrich → evidence with receipts → draft → checks → human "ship it" gate → status pipeline
  - the patterns for "claims follow receipts" and the HITL gate are proven there
- **BAND:** working code from HEEL TURN to reuse as a pattern: band-sdk, the room pool (250-room limit) and the commissioner approve/block flow.
- **Apollo:** Apollo MCP is connected in Claude Code, so enrichment can be tested immediately. The app still needs an API key.
- Building new code before kickoff may be against the rules. Tonight is research and setup only; the code gets written at the event.

## Stack (my recommendation; your call)
- **Frontend:** extend Sellbird's no-build dashboard (`sellbird/web`) with the Kanban, the citations column, the graph view and the "Agent Thinking" panel. Don't rewrite it in Next.js: it already has the Outbox approval desk.
- **API:** Sellbird's FastAPI (`dashboard.py`), with the graph, BAND and Flexprice added as modules.
- **Graph:** Neo4j Aura Free (hosted, so it uses none of your laptop's memory).
  - Kùzu is embedded and lighter, but its project status needs checking in the morning first.
- **Search:** Tavily or Exa, with Playwright for page fetches.
- **Enrichment:** Hunter (email verification and MX), plus Apollo.
- **Email:** SendGrid or the Gmail API, sending to a test inbox.
- **Billing:** Flexprice, with events and credit grants via its API (read the docs at kickoff).
- **Hosting:** deploy early (Vercel plus Render or Fly) so the demo link is never on localhost.

## Lanes (max 3, one owner per directory)
- **A** `api/pipeline/`: intake → ICP → discovery with citations → enrichment → drafts. Flexprice meter calls are added at each step.
- **B** `api/graph/` + `agents/`: graph schema and queries, plus the BAND room with 4 agents and the HITL approve flow.
- **C** `web/`: the UI, running on fixture JSON from minute one, then wired to the API. Design stack loaded in the first brief.

## Timeline
| Time | Milestone |
|---|---|
| Kickoff + 30 min | Keys in `.env`, Agent37 lanes proven, Flexprice and BAND docs read, repo scaffolded, deployed hello-world |
| +2.5 h | Intake → ICP → 10 cited leads, visible in the UI (core loop, played by hand) |
| +4 h | Graph + enrichment + drafts + HITL queue |
| +5 h | BAND agents and Flexprice gating live |
| Freeze (deadline minus 3 h) | Frozen deploy, then the video (2–3 min), the architecture doc and the README |
| Deadline minus 30 min | Submitted |

## Needed at kickoff
- **Keys:** OpenAI, Tavily or Exa, Hunter, Apollo, Flexprice, BAND, Neo4j Aura, SendGrid or Gmail.
- **From the organizers:** the deadline, whether pre-built code is allowed, and whether the demo must be deployed.
- **Demo product: PromptQL (Hasura),** chosen by the owner at 23:40. Not Actintro. A real B2B data/AI product makes the viability score credible.
  - The email leads with the useful output (cited accounts showing buying signals, plus the competitor map), not "I ran a bot on you".
  - In the public repo and video, emails and personal LinkedIn URLs of real prospects are masked. Only companies, titles and public sources are shown.
  - The demo's approved sends go only to our own test inbox.

## Tooling decided from the owner's links (2026-11-23 23:55)
- **HumanLayer** (Apache-2.0, Bun/Docker/Postgres monorepo for steering coding agents). Too heavy to adopt the day of the event; it would replace Agent37. We borrow only its Research-Plan-Implement skills and the "show me" visual-alignment pattern.
- **Factory ESLint plugin / dmmulroy anti-slop:** TS/JS lint rules. Sellbird is Python, so they only cover the small amount of JS we add to `sellbird/web`. For the Python side, use ruff plus a few custom checks that encode the spec as tests:
  - every prospect row has a source URL
  - no draft is sendable without approval
  - every metered action writes a Flexprice event
