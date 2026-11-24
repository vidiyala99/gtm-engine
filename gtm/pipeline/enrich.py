"""Step 5: decision makers at tier A/B companies, with verifier-backed email status.

Per company, best first, until MAX_COMPANIES are covered:
- Sellbird's people finder reads the company's own team/about pages (free); a match to
  an ICP persona gets its address from Hunter's email finder.
- Hunter domain search (executive/senior people in IT and management) through Glasser,
  ranked against the ICP personas; data and analytics leaders first.
- Every kept address goes through Hunter's verifier: its status and MX record are what
  the run shows. Nothing is marked verified unless the verifier said "valid".
Each person cites where they were found (a page Hunter saw the address on, or the team page).
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from gtm.contract import ICP, Citation, Company, Lead, Person, Run
from gtm.pipeline import glasser, store, web
from gtm.pipeline.runner import event, log_event

DOMAIN_SEARCH = ("hunter", "/v2/domain-search")
EMAIL_FINDER = ("hunter", "/v2/email-finder")
VERIFIER = ("hunter", "/v2/email-verifier")
MAX_COMPANIES = 8
PER_COMPANY = 2

STATUS = {"valid": "verified", "accept_all": "catch_all", "invalid": "invalid", "disposable": "invalid",
          "webmail": "risky", "unknown": "unknown"}
STATUS_WEIGHT = {"verified": 1.0, "catch_all": 0.7, "risky": 0.5, "unknown": 0.45, "guess": 0.3, "invalid": 0.1}

TITLE_POINTS = [  # what makes a title a PromptQL buyer
    (r"\bchief data\b|\bcdo\b|\bchief analytics\b", 6),
    (r"\b(head|vp|vice president|director|svp)\b.*\b(data|analytics|business intelligence|bi)\b", 5),
    (r"\b(data|analytics)\b.*\b(head|lead|director|vp)\b", 5),
    (r"\bdata (platform|engineering|science|infrastructure)\b", 4),
    (r"\bcto\b|\bchief technology\b|\bcio\b|\bchief information\b", 3),
    (r"\b(vp|vice president|head|svp)\b.*\bengineering\b", 3),
    (r"\banalytics\b|\bdata\b", 2),
]
NOT_BUYER = re.compile(r"\b(tax|legal|counsel|recruit|talent|hr|people|sales|marketing|account|finance|treasur|"
                       r"payroll|facilities|communications|investor|security|government|affairs)\b", re.I)


def title_points(title: str, icp: ICP | None = None) -> int:
    t = (title or "").lower()
    if not t or NOT_BUYER.search(t):
        return 0
    pts = max((p for rx, p in TITLE_POINTS if re.search(rx, t)), default=0)
    if pts and icp:  # a word-for-word persona match adds a point
        for persona in icp.personas:
            for alt in re.split(r"\s*/\s*", persona.title.lower()):
                if alt and re.search(rf"\b{re.escape(alt)}\b", t):
                    pts += 1
                    break
    return pts


def seniority(title: str, hunter_seniority: str = "") -> str:
    t = (title or "").lower()
    if re.search(r"\bvp\b|vice president|svp|evp", t):
        return "vp"
    if re.search(r"\bchief\b|\bc[a-z]o\b|founder|president", t):
        return "c_level"
    if re.search(r"director|head of", t) or hunter_seniority == "executive":
        return "director"
    if re.search(r"manager|lead", t) or hunter_seniority == "senior":
        return "manager"
    return "ic"


def _source_url(sources: list[dict]) -> str:
    for s in sources or []:
        uri = s.get("uri") or ""
        if uri.startswith("http") and "google.com/search" not in uri:
            return uri
    return ""


def person_id(email: str, name: str, company_id: str) -> str:
    return "p_" + hashlib.sha256(f"{company_id}|{email or name}".lower().encode()).hexdigest()[:10]


def verify(email: str, spend: glasser.Spend, run_id: str) -> tuple[str, bool | None, list[dict]]:
    try:
        res = glasser.run(*VERIFIER, {"email": email}, spend=spend)
    except glasser.OverBudget:
        return "guess", None, []
    except glasser.GlasserError as e:
        log_event(run_id, event("verify_failed", agent="enrich", detail=str(e)[:300]))
        return "unknown", None, []
    log_event(run_id, glasser.audit(res, "enrich", "email verifier"))
    d = res.output.get("data") or {}
    return STATUS.get(d.get("status") or "", "unknown"), d.get("mx_records"), d.get("sources") or []


def team_page_people(co: Company, icp: ICP | None) -> list[tuple[dict, str]]:
    """Sellbird's people finder over the company's own pages: (person, page_url) for buyer titles."""
    from sellbird.collectors import people as sb_people

    pages = []
    for path in ("", "about", "team", "leadership", "company", "about-us"):
        final, html = web.fetch(f"https://{co.domain}/{path}")
        if html:
            pages.append((final, html))
    found = []
    for p in sb_people.find_people(pages, co.domain, co.name) if pages else []:
        title = p.get("title") or ""
        if title_points(title, icp) >= 3:
            found.append((p, p.get("evidence_url") or (pages[0][0] if pages else "")))
    return found


def people_for(co: Company, icp: ICP | None, spend: glasser.Spend, run_id: str) -> list[Person]:
    when = datetime.now(timezone.utc)
    picks: list[dict] = []  # {first, last, title, email, hunter_conf, cite_url, cite_quote, provider, linkedin}
    for p, page in team_page_people(co, icp):
        first, last = p.get("first_name") or "", p.get("last_name") or ""
        if not (first and last and page):
            continue
        try:
            res = glasser.run(*EMAIL_FINDER, {"domain": co.domain, "first_name": first, "last_name": last}, spend=spend)
            log_event(run_id, glasser.audit(res, "enrich", f"email finder for a {p.get('title')} at {co.domain}"))
            d = res.output.get("data") or {}
        except glasser.GlasserError:
            d = {}
        picks.append({"first": first, "last": last, "title": p.get("title", ""), "email": d.get("email") or "",
                      "conf": (d.get("score") or 40) / 100, "cite_url": page, "provider": "web",
                      "cite_quote": (p.get("evidence") or f"{first} {last}, {p.get('title', '')}")[:300],
                      "linkedin": d.get("linkedin_url") or ""})
    try:
        res = glasser.run(*DOMAIN_SEARCH, {"domain": co.domain, "type": "personal", "limit": 10,
                                           "department": ["it", "management", "executive"],
                                           "seniority": ["executive", "senior"]}, spend=spend)
        emails = (res.output.get("data") or {}).get("emails") or []
        log_event(run_id, glasser.audit(res, "enrich", f"Hunter domain search {co.domain}: {len(emails)} people"))
    except glasser.OverBudget:
        emails = []
    except glasser.GlasserError as e:
        log_event(run_id, event("search_failed", agent="enrich", target=co.domain, detail=str(e)[:300]))
        emails = []
    for e in emails:
        url = _source_url(e.get("sources")) or e.get("linkedin") or ""
        if not (e.get("value") and e.get("position") and url):
            continue
        picks.append({"first": e.get("first_name") or "", "last": e.get("last_name") or "", "title": e["position"],
                      "email": e["value"], "conf": (e.get("confidence") or 50) / 100, "cite_url": url,
                      "provider": "glasser:hunter/v2/domain-search", "linkedin": e.get("linkedin") or "",
                      "cite_quote": f"{e['position']} at {co.name}; address seen on this page", "hs": e.get("seniority")})
    picks = [p for p in picks if title_points(p["title"], icp) > 0 and (p["first"] or p["last"])]
    picks.sort(key=lambda p: (-title_points(p["title"], icp), -p["conf"]))
    out, seen = [], set()
    for p in picks:
        key = (p["first"] + p["last"]).lower()
        if key in seen:
            continue
        seen.add(key)
        status, mx, sources = ("guess", None, [])
        if p["email"]:
            status, mx, sources = verify(p["email"], spend, run_id)
        cites = [Citation(url=p["cite_url"], title=f"Where {co.name}'s {p['title']} was found", quote=p["cite_quote"],
                          provider=p["provider"], retrieved_at=when)]
        extra = _source_url(sources)
        if extra and extra != p["cite_url"]:
            cites.append(Citation(url=extra, title="Address seen by the verifier", quote=p["email"],
                                  provider="glasser:hunter/v2/email-verifier", retrieved_at=when))
        out.append(Person(id=person_id(p["email"], key, co.id), company_id=co.id,
                          name=f"{p['first']} {p['last']}".strip(), title=p["title"][:120],
                          seniority=seniority(p["title"], p.get("hs", "")), email=p["email"], email_status=status,
                          mx_ok=mx, linkedin_url=p["linkedin"],
                          confidence=round(min(1.0, p["conf"] * STATUS_WEIGHT.get(status, 0.4) + 0.05 *
                                               min(title_points(p["title"], icp), 6) / 6), 2),
                          citations=cites))
        if len(out) >= PER_COMPANY:
            break
    return out


def targets(run: Run) -> list[Company]:
    live = [c for c in run.companies if not c.rejected_reason and c.tier in ("A", "B")]
    live.sort(key=lambda c: (c.tier, -(c.fit_score + c.intent_score)))
    return live


def run_step(run_id: str) -> None:
    run = store.load(run_id)
    spend = glasser.Spend()
    covered = 0
    for co in targets(run):
        if covered >= MAX_COMPANIES:
            break
        found = people_for(co, run.icp, spend, run_id)
        if not found:
            log_event(run_id, event("no_contact", agent="enrich", target=co.id, detail="no buyer-titled person found"))
            continue
        covered += 1

        def add(r: Run, co=co, found=found):
            have = {p.id for p in r.people}
            r.people.extend(p for p in found if p.id not in have)
            lead = next((l for l in r.leads if l.company_id == co.id), None)
            if lead is None:
                r.leads.append(Lead(company_id=co.id, person_id=found[0].id))
            elif not lead.person_id:
                lead.person_id = found[0].id
        store.update(run_id, add)

    def matched(r: Run):  # every live company sits on the board, contact or not
        have = {l.company_id for l in r.leads}
        r.leads.extend(Lead(company_id=c.id) for c in r.companies if not c.rejected_reason and c.id not in have)
    store.update(run_id, matched)
    run = store.load(run_id)
    log_event(run_id, event("enriched", agent="enrich", target=run_id,
                            detail=f"{len(run.people)} contacts at {covered} companies; "
                                   f"verified {sum(p.email_status == 'verified' for p in run.people)}, "
                                   f"catch-all {sum(p.email_status == 'catch_all' for p in run.people)}, "
                                   f"MX ok {sum(bool(p.mx_ok) for p in run.people)}; data spend ${spend.spent_usd:.4f}"))
