"""Step 3: intake -> ICP with per-field confidence, plus expansions backed by G2 reviews.

1. The model drafts the ICP from the intake and names G2 product slugs worth mining
   (the product itself and the tools its buyers use today).
2. Glasser pulls G2 reviews for those slugs (anyapi /g2.reviews, about $0.002 each).
3. The model proposes 2-3 expansion segments and cites review ids. Code turns those ids
   into Citations from the review rows; an id the model invents matches nothing and
   an expansion left with no real evidence is dropped.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from gtm.contract import ICP, Citation, Expansion, Industry, Intake, Persona, Run, Scored
from gtm.pipeline import glasser, llm, store
from gtm.pipeline.runner import log_event

G2 = ("anyapi", "/g2.reviews")
MAX_SLUGS = 4
SENIORITIES = {"c_level", "vp", "director", "manager", "ic"}


def _intake_text(intake: Intake) -> str:
    return json.dumps(intake.model_dump(), indent=2)


def draft_prompt(intake: Intake) -> str:
    return f"""You are a B2B go-to-market analyst. From this product intake, infer the ideal customer profile.

INTAKE:
{_intake_text(intake)}

Return JSON:
{{
  "industries": [{{"value": str, "naics": "6-digit NAICS", "confidence": 0-1, "why": str}}],   // 2-4
  "headcount_bands": [{{"value": "e.g. 200-2000", "confidence": 0-1, "why": str}}],            // 1-2
  "revenue_bands": [{{"value": "e.g. $50M-$500M", "confidence": 0-1, "why": str}}],            // 1-2
  "personas": [{{"title": str, "seniority": "c_level|vp|director|manager|ic", "confidence": 0-1}}], // 2-4 buyers
  "triggers": [{{"value": str, "confidence": 0-1, "why": str}}],  // 3-5 observable buying events (exec hire, job posts, funding, tech change)
  "g2_slugs": [str]   // up to {MAX_SLUGS} G2 product slugs (as in g2.com/products/<slug>) whose reviews show this buyer's pain: the product itself if listed, and the BI / analytics / text-to-SQL tools buyers use today
}}
Confidence means how sure the intake makes you: 0.8+ only when the intake states it, 0.4-0.6 when inferred.
"why" is one short sentence pointing at the intake fact it rests on."""


def expansion_prompt(intake: Intake, icp: dict, reviews: list[dict]) -> str:
    rows = [{"id": r["id"], "product": r.get("productName", ""), "segment": r.get("marketSegment", ""),
             "reviewer": r.get("author", ""), "dislikes": (r.get("dislikes") or "")[:400],
             "problems_solved": (r.get("problemsSolved") or "")[:300]} for r in reviews]
    core = [i["value"] for i in icp.get("industries", [])]
    return f"""You are a B2B go-to-market analyst looking for ICP expansion segments: adjacent industries,
emerging verticals or non-obvious uses NOT already in the core ICP ({core}).

PRODUCT: {intake.product}: {intake.description}

G2 REVIEWS (real, from the tools these buyers use today; reviewer often names their industry):
{json.dumps(rows, indent=1)}

Propose 2-3 expansion segments. Each must rest on reviews above: cite their ids, and quote the exact
words (copied verbatim from "dislikes" or "problems_solved") that show the pain the product solves.
Return JSON:
{{"expansions": [{{"segment": str, "rationale": "one sentence linking the reviews to the product",
   "evidence": [{{"review_id": str, "quote": "verbatim substring of that review"}}]}}]}}"""


def _clip(x, lo=0.0, hi=1.0) -> float:
    try:
        return max(lo, min(hi, float(x)))
    except (TypeError, ValueError):
        return 0.5


def parse_icp(data: dict) -> ICP:
    def scored(rows, cls=Scored):
        out = []
        for r in rows or []:
            if not isinstance(r, dict) or not str(r.get("value", "")).strip():
                continue
            kw = {"value": str(r["value"]).strip(), "confidence": _clip(r.get("confidence")), "why": str(r.get("why", ""))}
            if cls is Industry:
                kw["naics"] = str(r.get("naics", ""))
            out.append(cls(**kw))
        return out

    personas = []
    for p in data.get("personas") or []:
        if isinstance(p, dict) and p.get("title"):
            sen = p.get("seniority") if p.get("seniority") in SENIORITIES else "director"
            personas.append(Persona(title=str(p["title"]), seniority=sen, confidence=_clip(p.get("confidence"))))
    return ICP(industries=scored(data.get("industries"), Industry), headcount_bands=scored(data.get("headcount_bands")),
               revenue_bands=scored(data.get("revenue_bands")), personas=personas,
               triggers=scored(data.get("triggers")))


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def review_citation(review: dict, quote: str, cost_usd: float, when: datetime) -> Citation | None:
    """A citation only if the quote is really in the review (else fall back to the review's own words)."""
    text = " ".join(review.get(k) or "" for k in ("dislikes", "problemsSolved", "likes", "title"))
    if not review.get("url"):
        return None
    if not quote or _norm(quote) not in _norm(text):
        quote = (review.get("dislikes") or review.get("problemsSolved") or "")[:240]
    if not quote:
        return None
    return Citation(url=review["url"], title=f"G2 review of {review.get('productName', '')}: {review.get('title', '')}"[:200],
                    quote=quote[:300], provider="glasser:anyapi/g2.reviews", retrieved_at=when, cost_usd=cost_usd)


def parse_expansions(data: dict, reviews: dict[str, dict], cost_per_review: float, when: datetime) -> list[Expansion]:
    out = []
    for e in (data or {}).get("expansions") or []:
        if not isinstance(e, dict) or not e.get("segment"):
            continue
        cites = []
        for ev in e.get("evidence") or []:
            r = reviews.get(str((ev or {}).get("review_id", "")))
            c = r and review_citation(r, str(ev.get("quote", "")), cost_per_review, when)
            if c and all(c.url != x.url for x in cites):
                cites.append(c)
        if cites:  # no real review behind it: the segment is not shown
            out.append(Expansion(segment=str(e["segment"]), rationale=str(e.get("rationale", "")), evidence=cites))
    return out[:3]


def fetch_reviews(slugs: list[str], run_id: str, spend: glasser.Spend) -> tuple[dict[str, dict], float]:
    reviews: dict[str, dict] = {}
    costs = []
    for slug in slugs[:MAX_SLUGS]:
        slug = slug.strip().lower().rsplit("/", 1)[-1]
        if len(slug) < 2:
            continue
        try:
            res = glasser.run(*G2, {"product": slug, "limit": 50, "sortBy": "helpful"}, spend=spend)
        except glasser.OverBudget:
            raise
        except glasser.GlasserError as e:
            log_event(run_id, _event("g2_miss", f"{slug}: {e}"[:300]))
            continue
        rows = [r for r in glasser.items(res) if isinstance(r, dict) and r.get("id") and r.get("url")]
        log_event(run_id, glasser.audit(res, "icp", f"G2 reviews for {slug}: {len(rows)} rows"))
        for r in rows:
            reviews[str(r["id"])] = r
        if rows:
            costs.append(res.cost_usd / len(rows))
    return reviews, (sum(costs) / len(costs) if costs else 0.0)


def _event(action: str, detail: str):
    from gtm.pipeline.runner import event
    return event(action, agent="icp", detail=detail)


def _pick_reviews(reviews: dict[str, dict], n: int = 60) -> list[dict]:
    """Reviews with something to say about pain, spread across products."""
    rows = [r for r in reviews.values() if len((r.get("dislikes") or "") + (r.get("problemsSolved") or "")) > 60]
    by_product: dict[str, list[dict]] = {}
    for r in rows:
        by_product.setdefault(r.get("productName", ""), []).append(r)
    picked = []
    while len(picked) < n and any(by_product.values()):
        for lst in by_product.values():
            if lst and len(picked) < n:
                picked.append(lst.pop(0))
    return picked


def build_icp(run: Run) -> ICP:
    """Network and model calls happen here; each one is logged to the run as it lands."""
    data, usage = llm.ask_json(draft_prompt(run.intake), agent="icp", task="draft")
    log_event(run.id, llm.model_event("icp", "draft", usage, target=run.id, detail="ICP draft from intake"))
    data = data if isinstance(data, dict) else {}
    icp = parse_icp(data)
    store.update(run.id, lambda r: setattr(r, "icp", icp))  # the UI shows the ICP before the reviews land
    slugs = [s for s in (data.get("g2_slugs") or []) if isinstance(s, str)]
    reviews, per_review = fetch_reviews(slugs, run.id, glasser.Spend())
    if reviews:
        exp_data, usage2 = llm.ask_json(expansion_prompt(run.intake, data, _pick_reviews(reviews)), agent="icp",
                                        task="expansions")
        log_event(run.id, llm.model_event("icp", "expansions", usage2, target=run.id,
                                          detail=f"expansions from {len(reviews)} G2 reviews"))
        icp.expansions = parse_expansions(exp_data if isinstance(exp_data, dict) else {}, reviews,
                                          round(per_review, 6), datetime.now(timezone.utc))
    return icp


def run_step(run_id: str) -> None:
    icp = build_icp(store.load(run_id))
    store.update(run_id, lambda r: setattr(r, "icp", icp))
