# Organizer spec: AI GTM Engine (pasted by the owner 2026-11-23 23:32, kept verbatim in substance)

## 1. Overview
**Problem:** GTM runs in silos: ICP in slide decks, ad-hoc prospect search, isolated enrichment tools, inconsistent outreach, manual pipeline tracking. Context gets lost at every handoff.

**Vision:** an autonomous closed loop that:
- ingests plain-language product descriptions and commercial criteria
- infers and refines the buyer profile
- discovers validated accounts and decision-makers grounded in public evidence
- links entities, histories and buying signals in a Knowledge Graph
- writes multi-channel outreach through a human-in-the-loop (HITL) gateway
- tracks the full funnel and attribution in one dashboard

## 2. Functional requirements
### Module 1: Product intake & ICP engine
- **Intake:** chat and structured form capturing features, capabilities, constraints, existing customers and wins, pricing and contract values.
- **Structured ICP output:**
  - industries (NAICS/SIC)
  - company size (headcount and revenue bands)
  - personas, titles and seniority
  - trigger events (tech stack changes, exec hires, funding)
  - field-level confidence from 0.00 to 1.00
- **ICP expansion:** adjacent segments, emerging verticals and non-obvious uses, with evidence. The founder can accept, adjust or dismiss each.

### Module 2: Customer & competitor discovery
- **Buyer discovery:**
  - from company sites, regulatory filings, press and job postings
  - verifiable prospects, each with a **mandatory inline source citation**
  - filtered by negative signals (hiring freeze, non-target region)
- **Competitive landscape:** direct, indirect and alternative competitors, covering positioning, value props, public pricing tiers and differentiators.

### Module 3: Dynamic Knowledge Graph
- **Nodes:** Company, Person, Product, Competitor, Signal.
- **Edges:** works_at, competes_with, matched_to, contacted_via, replied_to, previously_employed_at.
- **Multi-hop reasoning:**
  - warm intro paths via shared employers or schools
  - job requisitions linked to active buying cycles
  - competitor displacement via renewal and churn signals
- **Continuous signal ingestion:** periodic updates to nodes and edges.

### Module 4: Enrichment & multi-channel outreach
- **Enrichment** via Hunter.io, Apollo, Clearbit or Prospeo: business email with deliverability and MX status, LinkedIn URL, domain and HQ.
- **Outreach:** multi-touch email and LinkedIn sequences that weave in trigger signals and value props, with persona-specific tone, length and CTA.
- **HITL gateway:** mandatory approval before queueing or sending. Reps approve, edit or reject in the queue.

### Module 5: Lead management & dashboard
- **Kanban:** Matched → Contacted → Replied → Meeting Booked → Closed/Lost.
- **Attribution:** AI-driven vs rep actions, plus timestamps and an audit log for every outbound action.
- **Analytics:** stage conversion by industry and company tier, and A/B results across templates, channels and value props.

## 3. Bonus integrations (+20 marks each)
- **Band Desktop (multi-agent):**
  - Planner/Architect, Builder, Reviewer (copy, fact and source checks) and Security agent
  - @mention handoffs, with HITL control over schema changes and outreach dispatch
  - live view of agent messages, session tokens and cumulative cost
- **Flexprice (usage billing):**
  - meters Leads Enriched, Outreach Sent and Graph Queries Evaluated
  - credit balances gate high-cost enrichment
  - per-lead cost in the billing ledger
- **Snyk:** vulnerability scanning of outbound services, with SAST and SCA in CI/CD.

## 4. Suggested architecture
| Tier | Options | Role |
|---|---|---|
| Graph DB | Neo4j / Kùzu | traversal, schema, path reasoning |
| Reasoning | LLM + RAG | ICP extraction, signal synthesis, copy |
| Discovery | Tavily / Serper / Playwright | live search, scraping, citations |
| Enrichment | Apollo / Hunter / Clearbit | firmographics, emails, social |
| Messaging | SendGrid / Gmail API / LinkedIn API | delivery, webhooks, rate limits |
| Frontend | Next.js / Tailwind / Radix | dense tables, Kanban, HITL terminal |

**UI requirements:**
- editorial look over a dense spreadsheet-style surface
- inline enrichment status and confidence badges
- collapsible "Agent Thinking" live feed (reasoning, graph traversals, validation)
- fit and intent score from 0 to 100, with Tier A/B/C

## 5. Judging
| Criterion | Weight | Expectation |
|---|---|---|
| ICP & discovery quality | 20% | sensible ICP, real cited leads, credible expansion |
| Enrichment & outreach | 20% | verified contacts, signal-personalized copy, strict HITL |
| Dashboard & lead mgmt | 15% | stage tracking, agent/rep attribution, conversion analytics |
| Startup viability | 15% | believable business, real pain, differentiation |
| Technical execution & demo | 10% | clean architecture, working end-to-end prototype |
| Band Desktop | +20% | multi-agent collaboration with a HITL decision demo |
| Flexprice | +20% | live metering and credit-gated execution |

**Deliverables:**
1. End-to-end deployed prototype (intake to dashboard).
2. Public repo with setup docs.
3. A 2–3 minute video: intake, graph matching, message composition, HITL review, dashboard sync.
4. System design doc: query logic, graph ontology, reasoning loops, bonus integrations.
