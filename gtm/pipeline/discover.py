"""Step 4: ICP -> cited, scored companies, with negative signals kept as rejections.

Sources, cheapest first:
- Prospeo company search through Glasser ($0.0245 a page of 25): one query for companies
  in the ICP's industries and size that are hiring data roles, one ICP lookalike query
  with no region filter (so out-of-region companies show up and get rejected visibly).
- The company's own homepage (free): the citation every row needs.
- Its job board (free, Sellbird's ATS collector): open data roles, each with its URL.
- Akta news through Glasser (about $0.01 a company): funding, exec hires, layoffs.
- Prospeo's own funding events, each with its Crunchbase link.

Scores are rules, not model guesses, so the "why" signal can say exactly what counted.
"""

from __future__ import annotations

import asyncio
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import httpx

from gtm.contract import ICP, Citation, Company, Intake, Run, Signal
from gtm.pipeline import glasser, store, web
from gtm.pipeline.runner import event, log_event

PROSPEO = ("prospeo", "/search-company")
AKTA_NEWS = ("akta", "/v1/news")
MAX_COMPANIES = 16

DATA_ROLES = ["analytics engineer", "data engineer", "data analyst", "business intelligence", "bi analyst",
              "bi engineer", "bi developer", "analytics", "data platform", "head of data", "data scientist",
              "data architect", "data governance"]
PROSPEO_HIRING = ["Analytics Engineer", "Data Engineer", "Business Intelligence", "Data Analyst", "Head of Data"]
DATA_STACK = ["snowflake", "databricks", "bigquery", "redshift", "looker", "tableau", "power bi", "dbt", "fivetran",
              "metabase", "sigma", "mode", "segment", "amplitude", "hasura", "postgres", "graphql"]
# A company whose pitch leads with analytics, BI or text-to-SQL is a competitor, not a buyer.
VENDOR_TERMS = re.compile(r"\b(analytics|business intelligence|data science|explore data|text[- ]to[- ]sql|"
                          r"semantic layer|bi platform)\b", re.I)
# Services firms resell data work; they are not the team that buys PromptQL.
SERVICES_INDUSTRIES = {"IT Services and IT Consulting", "Business Consulting and Services", "Staffing and Recruiting",
                       "Outsourcing and Offshoring Consulting"}

INDUSTRY_MAP = [  # ICP wording -> Prospeo industry names
    (r"software|saas|tech", ["Software Development"]),
    (r"financ|fintech|bank|insur", ["Financial Services", "Banking", "Insurance"]),
    (r"health|medic|clinic|pharma", ["Hospitals and Health Care"]),
    (r"logistic|supply chain|freight|transport", ["Transportation, Logistics, Supply Chain and Storage"]),
    (r"retail|e-?commerce", ["Retail"]),
]

NORTH_AMERICA = {"US", "CA", "MX"}
EUROPE = {"GB", "IE", "FR", "DE", "NL", "BE", "LU", "ES", "PT", "IT", "CH", "AT", "DK", "SE", "NO", "FI", "IS", "PL",
          "CZ", "SK", "HU", "RO", "BG", "GR", "EE", "LV", "LT", "SI", "HR", "CY", "MT"}

NEWS_KINDS = [  # Akta tag name or headline -> (kind, negative)
    (r"layoff|lays off|workforce reduction|job cuts|cuts \d+ jobs|redundanc", ("layoffs", True)),
    (r"hiring freeze", ("hiring_freeze", True)),
    (r"funding|venture|investment round|capital rais", ("funding", False)),
    (r"executive|leadership|appointment|management change", ("exec_hire", False)),
    (r"product launch|technology|partnership", ("tech_change", False)),
]


def now() -> datetime:
    return datetime.now(timezone.utc)


# ── queries ──

def target_regions(intake: Intake) -> tuple[set[str], str]:
    text = " ".join(intake.constraints + [intake.description]).lower()
    regions, names = set(), []
    if "north america" in text or re.search(r"\b(us|usa|united states)\b", text):
        regions |= NORTH_AMERICA
        names.append("North America")
    if "europe" in text or re.search(r"\b(eu|uk)\b", text):
        regions |= EUROPE
        names.append("Europe")
    return regions, " and ".join(names)


def headcount_range(icp: ICP) -> tuple[int, int]:
    lo, hi = None, None
    bands = [b for b in icp.headcount_bands if b.confidence >= 0.6] or icp.headcount_bands  # search the sure ones
    for band in bands:
        nums = [int(n.replace(",", "")) for n in re.findall(r"\d[\d,]*", band.value)]
        if not nums:
            continue
        lo = nums[0] if lo is None else min(lo, nums[0])
        top = nums[1] if len(nums) > 1 else nums[0] * 10  # "5000+"
        hi = top if hi is None else max(hi, top)
    return (lo or 200), (hi or 5000)


def prospeo_industries(icp: ICP) -> list[str]:
    out = []
    for ind in sorted(icp.industries, key=lambda i: -i.confidence):
        for rx, names in INDUSTRY_MAP:
            if re.search(rx, ind.value, re.I):
                out += [n for n in names if n not in out]
    return out or ["Software Development"]


def queries(icp: ICP, intake: Intake) -> list[tuple[str, dict]]:
    """Companies in the ICP's industries and size that are hiring data roles. The top
    industry is searched in the home market; the next ones worldwide, so companies
    outside the target regions surface and are shown rejected rather than silently missing."""
    lo, hi = headcount_range(icp)
    regions, _ = target_regions(intake)
    industries = prospeo_industries(icp)

    def q(names: list[str], home_only: bool) -> dict:
        f = {"company_industry": {"include": names},
             "company_headcount_custom": {"min": lo, "max": hi},
             "company_job_posting_hiring_for": {"include": PROSPEO_HIRING, "match_type": "contains"}}
        if home_only and regions & NORTH_AMERICA:
            f["company_location_search"] = {"include": ["United States"]}
        return {"page": 1, "filters": f}

    out = [(f"{industries[0]}, hiring data roles, US", q(industries[:1], True))]
    if industries[1:]:
        out.append((f"{', '.join(industries[1:4])}, hiring data roles, any region", q(industries[1:5], False)))
    return out


def prospeo_rows(result: glasser.Result) -> list[dict]:
    out = result.output
    rows = out.get("results") or (out.get("output") or {}).get("results") or []
    return [r.get("company", r) for r in rows if isinstance(r, dict)]


def _domain(row: dict) -> str:
    d = (row.get("domain") or row.get("website") or "").lower()
    d = re.sub(r"^https?://", "", d).split("/")[0]
    return d.removeprefix("www.")


# ── per-company evidence ──

def company_citation(row: dict, when: datetime) -> Citation | None:
    domain = _domain(row)
    if domain:
        final, html = web.fetch(f"https://{domain}/")
        quote = web.self_description(html)
        if final and quote:
            return Citation(url=final, title=f"{row.get('name', domain)} homepage", quote=quote, provider="web",
                            retrieved_at=when)
    desc = (row.get("description") or "").strip()
    url = row.get("crunchbase_url") or row.get("linkedin_url") or row.get("website")
    if url and desc:
        return Citation(url=url, title=f"{row.get('name', '')} company profile", quote=desc[:300],
                        provider="glasser:prospeo/search-company", retrieved_at=when)
    return None


def _board_postings(domain: str):
    from sellbird.collectors import ats

    for path in ("", "careers", "jobs", "company/careers"):
        final, html = web.fetch(f"https://{domain}/{path}")
        board = ats.detect_board(html, domain) if html else None
        if board:
            break
    else:
        return None, []

    async def read():
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers={"User-Agent": web.UA}) as c:
            return await ats.read_board(c, board)
    postings = asyncio.run(read()) or []
    return board, ats.matching_roles(postings, DATA_ROLES)


def job_signals(cid: str, row: dict, when: datetime) -> list[Signal]:
    domain = _domain(row)
    board, roles = _board_postings(domain) if domain else (None, [])
    if roles:
        shown = roles[:3]
        summary = f"{len(roles)} open data role{'s' if len(roles) != 1 else ''} on its {board.label} board: " + \
                  "; ".join(p.title for p in shown)
        return [Signal(id=f"{cid}_jobs", kind="job_post", summary=summary[:300], observed_on=shown[0].posted,
                       citation=Citation(url=shown[0].url or board.page_url, title=f"{board.label} job board",
                                         quote=shown[0].summary(), provider="web", retrieved_at=when))]
    titles = [t for t in ((row.get("job_postings") or {}).get("active_titles") or [])
              if any(all(w in t.lower() for w in k.split()) for k in DATA_ROLES)]
    url = row.get("linkedin_url")
    if titles and url:
        return [Signal(id=f"{cid}_jobs", kind="job_post",
                       summary=f"Hiring for data roles: {'; '.join(titles[:3])}"[:300],
                       citation=Citation(url=url.rstrip("/") + "/jobs/", title="Open roles (Prospeo job index)",
                                         quote="; ".join(titles[:3]), provider="glasser:prospeo/search-company",
                                         retrieved_at=when, cost_usd=0.0))]
    return []


def funding_signals(cid: str, row: dict, when: datetime) -> list[Signal]:
    events = [e for e in ((row.get("funding") or {}).get("funding_events") or []) if e.get("link")]
    events.sort(key=lambda e: e.get("raised_at") or "", reverse=True)
    if not events:
        return []
    e = events[0]
    day = (e.get("raised_at") or "")[:10]
    amount = e.get("amount_printed") or "undisclosed amount"
    return [Signal(id=f"{cid}_funding", kind="funding", summary=f"{e.get('stage') or 'Funding'} ({amount}) on {day}",
                   observed_on=day,
                   citation=Citation(url=e["link"], title="Funding round", quote=f"{e.get('stage')} {amount} {day}",
                                     provider="glasser:prospeo/search-company", retrieved_at=when))]


def _names_company(title: str, name: str) -> bool:
    """The headline is about this company, not one that merely mentions it."""
    key = re.sub(r"[^a-z0-9 ]", "", (name or "").lower()).split()
    return bool(key) and re.search(rf"\b{re.escape(key[0])}\b", title.lower()) is not None


def news_signals(cid: str, domain: str, spend: glasser.Spend, run_id: str, lock: threading.Lock,
                 name: str = "") -> list[Signal]:
    try:
        res = glasser.run(*AKTA_NEWS, {"company": domain, "limit": 10}, spend=spend)
    except glasser.OverBudget:
        return []
    except glasser.GlasserError as e:
        log_event(run_id, event("news_miss", agent="discover", target=domain, detail=str(e)[:300]))
        return []
    rows = glasser.items(res) or (res.output.get("data") if isinstance(res.output.get("data"), list) else [])
    with lock:
        log_event(run_id, glasser.audit(res, "discover", f"Akta news for {domain}: {len(rows)} articles"))
    per_article = (res.cost_usd / len(rows)) if rows else 0.0
    out, seen = [], set()
    for r in rows:
        if name and not _names_company(r.get("title", ""), name):
            continue
        tags = " ".join(t.get("name", "") for t in r.get("tags") or [])
        text = f"{tags} {r.get('title', '')}"
        for rx, (kind, negative) in NEWS_KINDS:
            if kind in seen or not re.search(rx, text, re.I) or not r.get("url"):
                continue
            seen.add(kind)
            day = (r.get("published_date") or "")[:10]
            out.append(Signal(id=f"{cid}_{kind}", kind=kind, negative=negative, observed_on=day,
                              summary=f"{r.get('title', '')[:200]}" + (f" ({day})" if day else ""),
                              citation=Citation(url=r["url"], title=r.get("title", "")[:200],
                                                quote=(r.get("ai_summary") or r.get("title") or "")[:300],
                                                provider="glasser:akta/v1/news", retrieved_at=now(),
                                                cost_usd=round(per_article, 6))))
            break
    return out


# ── scoring ──

def _recent(day: str, days: int) -> bool:
    try:
        return datetime.fromisoformat(day[:10]).replace(tzinfo=timezone.utc) >= now() - timedelta(days=days)
    except ValueError:
        return False


def score(row: dict, icp: ICP, intake: Intake, signals: list[Signal]) -> tuple[int, int, list[str], list[str]]:
    fit, intent, fit_why, intent_why = 0, 10, [], []
    lo, hi = headcount_range(icp)
    staff = int(row.get("employee_count") or 0)
    if prospeo_industries(icp) and row.get("industry") in prospeo_industries(icp):
        fit += 30
        fit_why.append(f"industry {row['industry']}")
    elif row.get("industry"):
        fit += 10
        fit_why.append(f"adjacent industry {row['industry']}")
    if lo <= staff <= hi:
        fit += 30
        fit_why.append(f"{staff:,} staff in the {lo}-{hi} band")
    elif staff and lo / 2 <= staff <= hi * 2:
        fit += 15
        fit_why.append(f"{staff:,} staff, near the {lo}-{hi} band")
    regions, _ = target_regions(intake)
    country = ((row.get("location") or {}).get("country_code") or "").upper()
    if not regions or country in regions:
        fit += 20
        fit_why.append(f"HQ {country or 'unknown'}")
    tech = " ".join(t.get("name", "") for t in ((row.get("technology") or {}).get("technology_list") or [])).lower()
    stack = [s for s in DATA_STACK if s in tech]
    if stack:
        fit += 20
        fit_why.append("uses " + ", ".join(stack[:3]))
    for s in signals:
        if s.negative:
            continue
        if s.kind == "job_post":
            intent += 35 if s.citation.provider == "web" else 25
            intent_why.append("open data roles")
        elif s.kind == "funding" and _recent(s.observed_on, 548):
            intent += 25
            intent_why.append(f"funded {s.observed_on}")
        elif s.kind == "exec_hire":
            intent += 20
            intent_why.append("leadership change in the news")
        elif s.kind == "tech_change":
            intent += 10
            intent_why.append("product or tech news")
    return min(fit, 100), min(intent, 100), fit_why, intent_why


def tier(fit: int, intent: int, rejected: bool) -> str:
    if rejected:
        return "C"
    if fit >= 70 and intent >= 45:
        return "A"
    return "B" if fit >= 50 else "C"


def company_id(domain: str) -> str:
    return "co_" + re.sub(r"[^a-z0-9]+", "_", domain.lower()).strip("_")[:40]


def build_company(row: dict, icp: ICP, intake: Intake, spend: glasser.Spend, run_id: str,
                  lock: threading.Lock) -> Company | None:
    when = now()
    domain = _domain(row)
    cite = company_citation(row, when)
    if not domain or cite is None:  # no source, no row (the contract refuses it anyway)
        return None
    cid = company_id(domain)
    signals = (job_signals(cid, row, when) + funding_signals(cid, row, when) +
               news_signals(cid, domain, spend, run_id, lock, name=row.get("name") or ""))
    rejected = ""
    regions, region_names = target_regions(intake)
    loc = row.get("location") or {}
    country = (loc.get("country_code") or "").upper()
    if regions and country and country not in regions:
        signals.append(Signal(id=f"{cid}_region", kind="non_target_region", negative=True,
                              summary=f"HQ in {loc.get('country') or country}, outside {region_names}",
                              citation=cite.model_copy(update={"quote": loc.get("raw_address") or cite.quote}) if
                              loc.get("raw_address") and cite.provider != "web" else cite))
        rejected = f"Non-target region: HQ in {loc.get('country') or country}, outside {region_names}"
    for s in signals:
        if s.negative and not rejected and s.kind in ("layoffs", "hiring_freeze"):
            rejected = f"{s.kind.replace('_', ' ').capitalize()}: {s.summary}"[:300]
    fit, intent, fit_why, intent_why = score(row, icp, intake, signals)
    if rejected:
        intent = min(intent, 20)
    why = f"Fit {fit}: {', '.join(fit_why) or 'little ICP overlap'}. Intent {intent}: " + \
          (", ".join(intent_why) or "no buying signal found") + (f". Rejected: {rejected}" if rejected else "")
    signals.append(Signal(id=f"{cid}_score", kind="other", summary=why[:500], citation=cite))
    return Company(id=cid, name=row.get("name") or domain, domain=domain,
                   hq=", ".join(x for x in (loc.get("city"), loc.get("country")) if x),
                   industry=row.get("industry") or "", headcount=str(row.get("employee_count") or ""),
                   fit_score=fit, intent_score=intent, tier=tier(fit, intent, bool(rejected)), signals=signals,
                   citations=[cite], rejected_reason=rejected)


def candidates(icp: ICP, intake: Intake, run_id: str, spend: glasser.Spend, exclude: set[str]) -> list[dict]:
    lists = []
    for label, payload in queries(icp, intake):
        try:
            res = glasser.run(*PROSPEO, payload, spend=spend)
        except glasser.GlasserError as e:
            log_event(run_id, event("query_failed", agent="discover", detail=f"{label}: {e}"[:300]))
            continue
        rows = prospeo_rows(res)
        log_event(run_id, glasser.audit(res, "discover", f"Prospeo '{label}': {len(rows)} companies"))
        lists.append(rows)
    picked, seen = [], set(exclude)
    for i in range(max((len(x) for x in lists), default=0)):  # interleave the queries
        for rows in lists:
            if i >= len(rows):
                continue
            row, d = rows[i], _domain(rows[i])
            if not d or d in seen:
                continue
            seen.add(d)
            if row.get("industry") in SERVICES_INDUSTRIES:
                log_event(run_id, event("skipped", agent="discover", target=d,
                                        detail=f"{row.get('name')}: {row['industry']} firm, not a buyer"))
                continue
            if VENDOR_TERMS.search((row.get("description") or "")[:250]):
                log_event(run_id, event("skipped", agent="discover", target=d,
                                        detail=f"{row.get('name')}: sells analytics/BI, a competitor not a buyer"))
                continue
            picked.append(row)
    return picked[:MAX_COMPANIES]


def run_step(run_id: str) -> None:
    run = store.load(run_id)
    if run.icp is None:
        raise RuntimeError("discover needs an ICP")
    spend = glasser.Spend()
    exclude = {c.domain for c in run.competitors} | {c.domain for c in run.companies}
    rows = candidates(run.icp, run.intake, run_id, spend, exclude)
    lock = threading.Lock()

    def one(row):
        try:
            co = build_company(row, run.icp, run.intake, spend, run_id, lock)
        except Exception as e:  # one bad site never sinks the run
            log_event(run_id, event("company_failed", agent="discover", target=_domain(row),
                                    detail=f"{type(e).__name__}: {e}"[:300]))
            return
        if co is None:
            log_event(run_id, event("dropped_uncited", agent="discover", target=_domain(row),
                                    detail="no source page or profile to cite"))
            return

        def add(r: Run):
            if all(c.id != co.id for c in r.companies):
                r.companies.append(co)
        with lock:
            store.update(run_id, add)

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(one, rows))
    run = store.load(run_id)
    kept = [c for c in run.companies if not c.rejected_reason]
    log_event(run_id, event("discovered", agent="discover", target=run_id,
                            detail=f"{len(run.companies)} companies, {len(run.companies) - len(kept)} rejected, "
                                   f"tiers A/B/C = {sum(c.tier == 'A' for c in kept)}/"
                                   f"{sum(c.tier == 'B' for c in kept)}/{sum(c.tier == 'C' for c in kept)}, "
                                   f"data spend ${spend.spent_usd:.4f}"))
