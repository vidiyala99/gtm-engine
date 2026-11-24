"""Competitor map: direct, indirect and alternative, with public pricing where it exists.

1. The model names competitors from the intake and ICP (name, domain, kind).
2. Each one's homepage and pricing page are fetched (free) and reduced to text.
3. The model reads only that text and returns positioning, tiers and differentiators.
   A pricing tier is kept only if its price figure appears on the cited pricing page;
   positioning falls back to the homepage's own description.
Runs before discovery, so competitors are never prospected as buyers.
"""

from __future__ import annotations

import html as htmllib
import json
import re
from datetime import datetime, timezone

from gtm.contract import Citation, Competitor, Run
from gtm.pipeline import llm, store, web
from gtm.pipeline.runner import event, log_event

KINDS = {"direct", "indirect", "alternative"}
PAGE_CHARS = 3500


def list_prompt(run: Run) -> str:
    icp = run.icp.model_dump(include={"industries", "personas"}) if run.icp else {}
    return f"""You map the competitive landscape for a B2B product.

PRODUCT: {run.intake.product}: {run.intake.description}
FEATURES: {run.intake.features}
ICP: {json.dumps(icp)}

Name 6-8 competitors a buyer would compare it with:
- direct: same job, same buyer (AI / natural-language analytics on company data)
- indirect: different product the buyer uses for the same need (BI, semantic layers, notebooks)
- alternative: what they do instead (in-house text-to-SQL on an LLM, analyst ticket queue)
Use real companies with their real root domain. For "alternative", pick a real product that embodies it.
Return JSON: {{"competitors": [{{"name": str, "domain": "root domain", "kind": "direct|indirect|alternative"}}]}}"""


def detail_prompt(product: str, pages: dict[str, dict]) -> str:
    return f"""Below is text from competitors' own homepages and pricing pages. For each domain, using ONLY this
text, write how it positions itself and list its public pricing tiers and differentiators versus {product}.

{json.dumps(pages, indent=1)}

Return JSON: {{"<domain>": {{"positioning": "one sentence from their own words",
  "pricing_tiers": ["Tier name: price as written on the page"],   // [] when the page shows no prices
  "differentiators": ["2-3 short phrases"]}}}}
Copy prices exactly as written. Never guess a price."""


def page_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html or "")
    text = htmllib.unescape(re.sub(r"(?s)<[^>]+>", " ", html))
    return " ".join(text.split())


def _prices(text: str) -> set[str]:
    return set(re.findall(r"[$€£]\s?\d[\d,.]*", text or ""))


def verified_tiers(tiers: list, pricing_text: str) -> list[str]:
    """Keep a tier only if every price figure it quotes is on the pricing page."""
    found = {p.replace(" ", "") for p in _prices(pricing_text)}
    out = []
    for t in tiers or []:
        if not isinstance(t, str):
            continue
        quoted = {p.replace(" ", "") for p in _prices(t)}
        if quoted and quoted <= found or (not quoted and re.search(r"free|contact|custom", t, re.I)
                                          and pricing_text):
            out.append(t[:120])
    return out[:5]


def _domain(d: str) -> str:
    d = re.sub(r"^https?://", "", (d or "").strip().lower()).split("/")[0]
    return d.removeprefix("www.")


def run_step(run_id: str) -> None:
    run = store.load(run_id)
    data, usage = llm.ask_json(list_prompt(run), agent="competitors", task="list")
    log_event(run_id, llm.model_event("competitors", "list", usage, target=run_id, detail="competitor list"))
    named = [c for c in (data or {}).get("competitors", []) if isinstance(c, dict) and c.get("domain")]
    when = datetime.now(timezone.utc)
    pages, cites = {}, {}
    for c in named[:8]:
        d = _domain(c["domain"])
        home_url, home = web.fetch(f"https://{d}/")
        if not home_url:
            log_event(run_id, event("dropped_uncited", agent="competitors", target=d, detail="homepage unreadable"))
            continue
        price_url, price_html = web.fetch(f"https://{d}/pricing")
        pages[d] = {"name": c.get("name", d), "homepage": page_text(home)[:PAGE_CHARS],
                    "pricing_page": page_text(price_html)[:PAGE_CHARS] if price_url else ""}
        cites[d] = (home_url, web.self_description(home) or pages[d]["homepage"][:200], price_url,
                    page_text(price_html) if price_url else "")
    if not pages:
        raise RuntimeError("no competitor homepage could be read")
    details, usage2 = llm.ask_json(detail_prompt(run.intake.product, pages), agent="competitors", task="detail")
    log_event(run_id, llm.model_event("competitors", "detail", usage2, target=run_id,
                                      detail=f"positioning and pricing from {len(pages)} sites"))
    out = []
    for c in named:
        d = _domain(c["domain"])
        if d not in cites:
            continue
        home_url, home_quote, price_url, price_text = cites[d]
        info = (details or {}).get(d) or {}
        tiers = verified_tiers(info.get("pricing_tiers"), price_text)
        citations = [Citation(url=home_url, title=f"{c.get('name', d)} homepage", quote=home_quote[:300],
                              provider="web", retrieved_at=when)]
        if tiers and price_url:
            citations.append(Citation(url=price_url, title=f"{c.get('name', d)} pricing", quote="; ".join(tiers)[:300],
                                      provider="web", retrieved_at=when))
        out.append(Competitor(name=c.get("name") or d, domain=d,
                              kind=c.get("kind") if c.get("kind") in KINDS else "indirect",
                              positioning=str(info.get("positioning") or home_quote)[:300],
                              pricing_tiers=tiers,
                              differentiators=[str(x)[:120] for x in (info.get("differentiators") or [])][:3],
                              citations=citations))

    def change(r: Run):
        r.competitors = out
    store.update(run_id, change)
    log_event(run_id, event("competitors_mapped", agent="competitors", target=run_id,
                            detail=f"{len(out)} competitors, {sum(bool(c.pricing_tiers) for c in out)} with public "
                                   f"pricing"))
