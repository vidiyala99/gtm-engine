# Research (what we read, what we take from it)

Cloned repos live in `ref/`, which is gitignored and read-only. Never run their code from inside them without `python -I` / review.

## Sellbird, formerly Harvey (base we fork)
- **Source:** github.com/ethanplusai/sellbird (`ethanplusai/harvey` redirects). Cloned at `ref/sellbird`, commit b212385 (2026-11-18).
- **License: AGPL-3.0.** Our fork stays public and AGPL, with credit in the README.
- **Size:** Python 3.11+, FastAPI, SQLite (aiosqlite), about 39k lines, 242 tests. No-build web dashboard in `sellbird/web`.
- **Pipeline:** `train <url>` → confirm signals (23-signal catalog, `signals.py`) → `discover` → profile (free HTTP, no model) → enrich (decision maker) → verify email (verified/risky/guess/invalid) → write → Outbox approval → send → handle replies.
- **Discovery providers** (`collectors/discover.py`): OpenStreetMap (free), Serper, TinyFish, DataForSEO, Scavio. Tuned for local SMBs.
- **HITL:** the Outbox is a decisions desk (A approve, R reject). There's a pre-send gate (`gate.py`), and drafts with foreign links are held.
- **Model runtime:** the isolated Claude Code CLI (`--safe-mode`, on the owner's Claude plan) or Codex on a ChatGPT plan. No API key.
- **Integrations:** Gmail, Microsoft 365, SMTP, Instantly, LinkedIn, calendar, email_finder, tech_detect.
- **Unknown:** whether it runs on Windows. Check first thing, with Docker (`Dockerfile`, `docker-compose.yml`) as the fallback.

## HumanLayer (`ref/humanlayer_humanlayer`, Apache-2.0)
- Now a platform for steering coding agents (riptide desktop/web/daemon, Bun + Docker + Postgres + Electric).
- **Not adopted:** too heavy to set up on event day.
- **Borrow:** the Research-Plan-Implement skills (`apps/riptide-rpi-claude-plugin/skills/`) and the "show me" visual-alignment reference.

## Factory ESLint plugin (`ref/Factory-AI_eslint-plugin`, Apache-2.0)
- Agent-steering lint rules covering file organization, test colocation, structured logging and route middleware. Meant to be adapted, not imported. Unmaintained.
- Applies only to the JS we add.

## anti-slop (`ref/dmmulroy_anti-slop`, MIT)
- About 100 Oxlint rules against agent TS/JS patterns. The author points to `cloudflare/oxlint-config` as its maintained successor.
- Applies only to the JS we add.

## No AI Slop manifesto (slopmanifesto.com) and Dex Horthy's "12 Rules for a Software Factory" talk (AIE Code Summit 2026)
- The talk was read via its sum.video transcript, because the YouTube captions returned HTTP 429.
- Takeaways are encoded in `../PLAYBOOK.md` (Anti-slop section):
  - plan in proportion to expected pain
  - align visually
  - agents test with real browsers
  - lint and checks as back-pressure
  - outcomes over the number of agents
  - disclose agent-written text
- Slop Code Bench publishes Python code-quality rules. Look them up to use with ruff.

## marketingskills (`ref/marketingskills`, MIT, commit 8fd2fca 2026-11-23)
- github.com/coreyhaines31/marketingskills: about 55 marketing skills (SKILL.md + references) for Claude Code. Prompts and playbooks only; no runtime.
- **Use as the agents' playbooks** (MIT, so we can vendor the text into our agent prompts with credit):
  - `product-marketing`: the intake doc (product, ICP, positioning) that every other skill reads. This is our Module 1 intake → ICP output format.
  - `prospecting`: the "SaaS" and "demand-signal" branches. Demand-signal requires a cited public source per lead, which matches the spec's citation rule. `references/signal-plays.md`, `enrichment-playbook.md`, `compliance.md`.
  - `cold-email`: writing rules plus `personalization.md`, `follow-up-sequences.md`, `reply-handling.md`, `linkedin-outreach.md` (the queued LinkedIn drafts item).
  - `competitor-profiling`: dated competitor profiles (Module 2). `reverse-engineer-marketing` `Landscape` mode for 3 to 5 competitors.
  - `revops`: lead scoring and stage definitions for the graph's lead states.
- **Not adopted:** the paid-data tool integrations in `tools/` (we use Sellbird's providers plus Hunter/Apollo).

## REA (installed as MCP + `reverse-engineer-anything` skill; no clone needed)
- No marketing section. Useful web tools for Module 2: `inspect_web_page` / `capture_browser_scenario` (cited page captures), `analyze_web_bundle` (tech-stack signal from shipped JS), `compare_web_captures` (what changed on a site). Stretch only.

## To verify at kickoff
- Flexprice API: events ingest, customers, credit grants, wallet balance check.
- Kùzu project status (embedded graph DB), or use Neo4j Aura Free.
- BAND SDK: reuse the patterns from `MultiplayerAI/agents` (band-sdk, room pool, approve/block).
- Organizer rules: is open-source base code allowed, must the demo be deployed, what is the deadline.
