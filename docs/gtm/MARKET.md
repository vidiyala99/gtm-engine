# Market: why this hackathon exists, and our purpose (2026-11-24 09:50)

Data pulled with the Glasser CLI. Total spend about $0.39. Raw JSON is in `ref/glasser-runs/` (gitignored).
Endpoints used:
- G2 reviews: `anyapi /g2.reviews`, the 50 most recent per product
- headcount: `akta /v1/company/headcount-trends`

## 1. The market is booming, not struggling

Headcount from Akta (LinkedIn), 2026-11-01:

| Company | Employees | 12-month growth | 6-month growth |
|---|---|---|---|
| Clay | 1,580 | +45% | +15% |
| Apollo.io | 1,025 | +60% | +49% |
| 11x (AI SDR) | 110 | +83% | +47% |

**Correction.** Earlier I said from memory that 11x looked like it was struggling (high churn). The data says it is hiring fast. Buyers are paying for GTM tools, and the category is growing.

## 2. What users still complain about

Counts of themes in the "dislikes" text of the 50 most recent G2 reviews per product.

**Method caveat.** The first counts below are loose keyword hits; for example, "data" also matches "database". A stricter recount for data-quality complaints only (inaccurate, outdated, incorrect, bounce) gives:
- Apollo: 15 of 49 (the finding holds)
- Outreach: 2 of 50 (its loose "data (11)" was noise)
- 11x: 3 of 50
- Instantly: 1 of 42

Review dates:
- Apollo: 2026-08-27 to 2026-11-23
- Outreach: 2026-09-23 to 2026-10-28
- Instantly: 2026-06-22 to 2026-11-24
- 11x: 2025-11-06 to 2026-11-16

| Product | Avg rating (n) | Top complaints |
|---|---|---|
| Apollo.io (data) | 4.34 (49) | data (14), limits (14), credits (12), accuracy (12), outdated (10), integrations (5) |
| Outreach (sequencing) | 4.34 (50) | integrations (7), complexity and learning curve; data quality only 2 on the strict recount. One reviewer does not trust its AI: "not always clear what was AI vs. rules-based" |
| Instantly (cold email) | 3.82 (42) | credits (7), expensive (4), learning curve (4). Also: a domain lock-in surprise and a refund turned into credit |
| 11x (AI SDR) | 4.51 (50) | needs very tight targeting ("throwing darts blindly" otherwise), contact filtering too coarse, AI output must keep being reviewed, proving ROI |

G2 had no usable reviews for Clay or Artisan: Clay returned 1 review and Artisan returned 2.

Paraphrased receipts from the review text:
- Apollo: the platform "went off a cliff with its AI integration"; lists and sequences became a struggle.
- 11x: unless you are extremely targeted it "can feel like you're throwing darts blindly"; "it's still AI", so you keep reviewing it.

## 3. Why the hackathon exists

Synthesis of §1, §2 and SPEC §1:
- Spending on GTM tools is growing fast, but each tool covers one slice: data (Apollo), workflow (Clay), sequencing (Outreach, Instantly), autopilot (11x).
- The pains that remain sit between the slices:
  - data that is wrong or outdated
  - credit and limit surprises
  - learning curves
  - AI that only works with tight targeting and human review
- Hence the spec's closed loop: one memory (the graph), cited evidence, human approval, and cost per lead (Flexprice).

## 4. Our purpose (proposed; the owner decides)

**Evidence-first GTM.** You describe your product once. The engine:
- finds leads
- attaches a public source to every lead and every claim in the email
- verifies each contact before it counts
- shows the cost of each lead before spending credits
- sends nothing without a human's approval

How each part answers a pain in §2:
- **Cited, verified leads** answer Apollo's "inaccurate, outdated data".
- **Visible per-lead cost and a credit gate** answer the credit and limit surprises (Apollo, Instantly).
- **A sharp ICP with confidence scores and an approval step** answer 11x's "throwing darts" and "keep reviewing it".
- **One loop with a graph memory** answers the integration and handoff complaints (Outreach).
- **Showing what the AI did vs. what a human did** (the spec's attribution requirement) answers Outreach's "AI vs. rules-based" distrust.

The purpose is inferred from the complaints above: it is a synthesis, not a measured result.

Demo product: PromptQL (owner decision, see DECISIONS.md).

## Open
- Check this against the sponsors at the venue: their APIs may change which pains we can show.
- Glasser could be the data layer for discovery and enrichment, through the CLI with no key. If Glasser sponsors today, there may be a "best use" prize.
