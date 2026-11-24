"""Run -> Graph. Pure and deterministic: the same run always gives the same graph."""

from __future__ import annotations

import re

from gtm.contract import Run
from gtm.graph.model import Edge, Graph, Node

STAGE_ORDER = ["matched", "contacted", "replied", "meeting", "closed_won", "closed_lost"]
_SUFFIXES = re.compile(r"\b(inc|llc|ltd|limited|corp|corporation|co|gmbh|plc|sa|bv)\b\.?", re.I)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "x"


def norm_org(name: str) -> str:
    """Company names as people write them on a profile: case, punctuation and legal suffix don't matter."""
    return re.sub(r"[^a-z0-9]+", " ", _SUFFIXES.sub(" ", name.lower())).strip()


def _reached(stage: str, floor: str) -> bool:
    if stage == "closed_lost":  # a lost deal still got that far; count it as replied at least
        return STAGE_ORDER.index(floor) <= STAGE_ORDER.index("replied")
    return STAGE_ORDER.index(stage) >= STAGE_ORDER.index(floor)


def build(run: Run) -> Graph:
    nodes: dict[str, Node] = {}
    edges: dict[str, Edge] = {}

    def add_node(node: Node) -> str:
        nodes.setdefault(node.id, node)
        return node.id

    def add_edge(type_: str, source: str, target: str, **props) -> None:
        eid = f"{type_}:{source}->{target}"
        edges.setdefault(eid, Edge(id=eid, type=type_, source=source, target=target, props=props))

    product = add_node(Node(id=f"product:{slug(run.intake.product)}", label="Product", name=run.intake.product,
                            props={"description": run.intake.description[:280],
                                   "personas": "|".join(p.title for p in (run.icp.personas if run.icp else []))}))

    by_name: dict[str, str] = {}
    for c in run.companies:
        cid = add_node(Node(id=f"company:{c.id}", label="Company", name=c.name, props={
            "domain": c.domain, "tier": c.tier, "fit_score": c.fit_score, "intent_score": c.intent_score,
            "rejected_reason": c.rejected_reason, "external": False, "source_url": str(c.citations[0].url)}))
        by_name[norm_org(c.name)] = cid
        if not c.rejected_reason:
            add_edge("matched_to", cid, product, fit_score=c.fit_score, intent_score=c.intent_score, tier=c.tier)
        for s in c.signals:
            sid = add_node(Node(id=f"signal:{s.id}", label="Signal", name=s.summary, props={
                "kind": s.kind, "negative": s.negative, "observed_on": s.observed_on,
                "source_url": str(s.citation.url), "quote": s.citation.quote}))
            add_edge("has_signal", cid, sid)

    def org(name: str) -> str:
        key = norm_org(name)
        if key in by_name:
            return by_name[key]
        cid = add_node(Node(id=f"company:ext-{slug(key)}", label="Company", name=name.strip(),
                            props={"external": True}))
        by_name[key] = cid
        return cid

    for comp in run.competitors:
        kid = add_node(Node(id=f"competitor:{slug(comp.name)}", label="Competitor", name=comp.name, props={
            "kind": comp.kind, "domain": comp.domain, "positioning": comp.positioning,
            "source_url": str(comp.citations[0].url)}))
        add_edge("competes_with", kid, product, kind=comp.kind)
        pattern = re.compile(rf"\b{re.escape(comp.name)}\b|{re.escape(comp.domain)}", re.I) if comp.domain \
            else re.compile(rf"\b{re.escape(comp.name)}\b", re.I)
        for c in run.companies:
            for s in c.signals:
                if pattern.search(f"{s.summary} {s.citation.quote}"):
                    add_edge("uses", f"company:{c.id}", kid, signal_id=s.id, source_url=str(s.citation.url))

    drafts_by_person: dict[str, list] = {}
    for d in run.drafts:
        drafts_by_person.setdefault(d.person_id, []).append(d)
    stage_by_person = {lead.person_id: lead.stage for lead in run.leads if lead.person_id}

    for p in run.people:
        pid = add_node(Node(id=f"person:{p.id}", label="Person", name=p.name, props={
            "title": p.title, "seniority": p.seniority, "email_status": p.email_status,
            "source_url": str(p.citations[0].url)}))
        current = f"company:{p.company_id}"
        if current in nodes:
            add_edge("works_at", pid, current, title=p.title)
        for past in p.past_employers:
            add_edge("previously_employed_at", pid, org(past))
        for school in p.schools:
            sch = add_node(Node(id=f"school:{slug(school)}", label="School", name=school.strip()))
            add_edge("attended", pid, sch)

        drafts = drafts_by_person.get(p.id, [])
        sent = [d for d in drafts if d.status == "sent"]
        stage = stage_by_person.get(p.id, "matched")
        if sent or _reached(stage, "contacted"):
            channels = sorted({d.channel for d in (sent or drafts)}) or ["unknown"]
            add_edge("contacted_via", pid, product, channel=",".join(channels), stage=stage)
        if _reached(stage, "replied"):
            add_edge("replied_to", pid, product, stage=stage)

    return Graph(run_id=run.id, nodes=sorted(nodes.values(), key=lambda n: n.id),
                 edges=sorted(edges.values(), key=lambda e: e.id))
