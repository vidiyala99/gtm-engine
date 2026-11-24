"""The three multi-hop questions, answered as drawable paths.

`paths(graph, kind)` runs the query in kuzu when it is installed (Cypher in
`gtm/graph/kuzu_store.py`) and in plain Python otherwise. Both engines return
the same paths in the same order; the tests hold them to that.
"""

from __future__ import annotations

import re

from gtm.graph.model import Edge, Graph, Node, Path

ORG_EDGES = ("works_at", "previously_employed_at", "attended")
SHARED_PAST = ("previously_employed_at", "attended")  # a current coworker alone is not a warm intro
CHURN_WORDS = re.compile(r"churn|renewal|complain|frustrat|switch|migrat|cancel|replac|leaving|moving off", re.I)
_WORD = re.compile(r"[a-z0-9]+")


def person_id(value: str) -> str:
    return value if value.startswith("person:") else f"person:{value}"


def is_churn_signal(node: Node) -> bool:
    return node.props.get("kind") == "review_complaint" or (
        not node.props.get("negative") and bool(CHURN_WORDS.search(f"{node.name} {node.props.get('quote') or ''}")))


def persona_match(title: str, personas: list[str]) -> bool:
    words = set(_WORD.findall(title.lower()))
    return any(set(_WORD.findall(p.lower())) <= words for p in personas if p.strip())


def _personas(graph: Graph, product_id: str) -> list[str]:
    raw = graph.node(product_id).props.get("personas") or ""
    return [p for p in str(raw).split("|") if p]


def _contacted(graph: Graph, pid: str) -> Edge | None:
    found = graph.out(pid, "contacted_via")
    return found[0] if found else None


# --- the paths, assembled from ids so both engines share one shape --------------

def warm_intro_path(graph: Graph, t: str, e1: Edge, o: str, e2: Edge, c: str, cv: Edge, engine: str) -> Path:
    via = "school" if e1.type == "attended" else "employer"
    tn, on, cn = graph.node(t), graph.node(o), graph.node(c)
    return Path(kind="warm_intro", engine=engine,
                summary=f"{tn.name} and {cn.name} share {via} {on.name}; {cn.name} is already contacted "
                        f"({cv.props.get('channel')}), so ask for an intro.",
                nodes=[tn, on, cn, graph.node(cv.target)], edges=[e1, e2, cv])


def buying_cycle_path(graph: Graph, s: str, c: str, has: Edge, matched: Edge, staff: list[Edge],
                      engine: str) -> Path:
    sn, cn = graph.node(s), graph.node(c)
    people = [graph.node(e.source) for e in staff]
    who = ", ".join(f"{p.name} ({p.props.get('title')})" for p in people) or "no persona found yet"
    return Path(kind="buying_cycle", engine=engine,
                summary=f"{cn.name} posted '{sn.name}' and is matched to {graph.node(matched.target).name} "
                        f"(tier {matched.props.get('tier')}); buyer: {who}.",
                nodes=[sn, cn, graph.node(matched.target), *people], edges=[has, matched, *staff])


def displacement_path(graph: Graph, c: str, uses: Edge, k: str, comp: Edge, has: Edge, engine: str) -> Path:
    cn, kn, sn = graph.node(c), graph.node(k), graph.node(has.target)
    return Path(kind="competitor_displacement", engine=engine,
                summary=f"{cn.name} uses {kn.name}, which competes with {graph.node(comp.target).name}, "
                        f"and shows a churn signal: '{sn.name}'.",
                nodes=[cn, kn, graph.node(comp.target), sn], edges=[uses, comp, has])


# --- python engine --------------------------------------------------------------

def warm_intro(graph: Graph, target: str | None = None) -> list[Path]:
    people = [n.id for n in graph.nodes if n.label == "Person"]
    targets = [person_id(target)] if target else people
    best: dict[tuple[str, str], Path] = {}
    for t in targets:
        if t not in {n.id for n in graph.nodes} or _contacted(graph, t):
            continue
        for e1 in sorted(graph.out(t, *ORG_EDGES), key=lambda e: e.id):
            for e2 in sorted(graph.into(e1.target, *ORG_EDGES), key=lambda e: e.id):
                c = e2.source
                cv = _contacted(graph, c)
                if c == t or not cv:
                    continue
                if e1.type not in SHARED_PAST and e2.type not in SHARED_PAST:
                    continue
                best.setdefault((t, c), warm_intro_path(graph, t, e1, e1.target, e2, c, cv, "python"))
    return [best[k] for k in sorted(best)]


def buying_cycle(graph: Graph) -> list[Path]:
    out = []
    for has in sorted((e for e in graph.edges if e.type == "has_signal"), key=lambda e: e.id):
        sig = graph.node(has.target)
        if sig.props.get("kind") != "job_post" or sig.props.get("negative"):
            continue
        for matched in graph.out(has.source, "matched_to"):
            personas = _personas(graph, matched.target)
            staff = sorted(graph.into(has.source, "works_at"), key=lambda e: e.id)
            fit = [e for e in staff if persona_match(graph.node(e.source).props.get("title") or "", personas)]
            out.append(buying_cycle_path(graph, has.target, has.source, has, matched, fit if personas else staff,
                                         "python"))
    return out


def competitor_displacement(graph: Graph) -> list[Path]:
    out = []
    for uses in sorted((e for e in graph.edges if e.type == "uses"), key=lambda e: e.id):
        for comp in graph.out(uses.target, "competes_with"):
            for has in sorted(graph.out(uses.source, "has_signal"), key=lambda e: e.id):
                if is_churn_signal(graph.node(has.target)):
                    out.append(displacement_path(graph, uses.source, uses, uses.target, comp, has, "python"))
    return out


PYTHON = {"warm_intro": warm_intro, "buying_cycle": buying_cycle, "competitor_displacement": competitor_displacement}
KINDS = tuple(PYTHON)


def paths(graph: Graph, kind: str, engine: str = "auto", target: str | None = None) -> list[Path]:
    if kind not in PYTHON:
        raise KeyError(kind)
    if engine in ("auto", "kuzu"):
        from gtm.graph import kuzu_store
        if kuzu_store.available():
            return kuzu_store.paths(graph, kind, target=target)
        if engine == "kuzu":
            raise RuntimeError("kuzu is not installed")
    return PYTHON[kind](graph, target) if kind == "warm_intro" else PYTHON[kind](graph)
