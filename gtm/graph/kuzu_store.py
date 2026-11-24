"""The graph stored in kuzu (embedded, no server) and the three queries in Cypher.

One database file per run under data/gtm/graph/, rebuilt whenever the run's
graph changes, so the stored graph is always exactly `build(run)`. Cypher does
the traversal; Python only sorts and applies the fuzzy persona-title match.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import threading
from pathlib import Path as FsPath

from gtm.graph import queries as q
from gtm.graph.model import ONTOLOGY, Edge, Graph, Path

ROOT = FsPath(__file__).resolve().parents[2] / "data" / "gtm" / "graph"
BUFFER_POOL = 64 * 1024 * 1024  # the lane has 4 GB; kuzu's default takes most of it
_EXTRA = {"Person": {"title": "STRING"}, "Signal": {"kind": "STRING", "negative": "BOOLEAN", "quote": "STRING"},
          "Product": {"personas": "STRING"}}
_LABELS = ("Company", "Person", "Product", "Competitor", "Signal", "School")
_lock = threading.Lock()
_open: dict[str, tuple[str, object, object]] = {}  # run_id -> (fingerprint, Database, Connection)

CHURN_RE2 = q.CHURN_WORDS.pattern

WARM_INTRO = """
MATCH (t:Person)-[e1:works_at|previously_employed_at]->(o:Company)<-[e2:works_at|previously_employed_at]-(c:Person),
      (c)-[cv:contacted_via]->(p:Product)
WHERE t.id <> c.id AND (label(e1) = 'previously_employed_at' OR label(e2) = 'previously_employed_at')
  AND NOT EXISTS { MATCH (t)-[:contacted_via]->(:Product) } {target}
RETURN t.id AS t, label(e1) AS l1, o.id AS o, label(e2) AS l2, c.id AS c, p.id AS p
UNION ALL
MATCH (t:Person)-[e1:attended]->(o:School)<-[e2:attended]-(c:Person), (c)-[cv:contacted_via]->(p:Product)
WHERE t.id <> c.id AND NOT EXISTS { MATCH (t)-[:contacted_via]->(:Product) } {target}
RETURN t.id AS t, label(e1) AS l1, o.id AS o, label(e2) AS l2, c.id AS c, p.id AS p
"""

BUYING_CYCLE = """
MATCH (c:Company)-[:has_signal]->(s:Signal), (c)-[:matched_to]->(p:Product)
WHERE s.kind = 'job_post' AND NOT s.negative
OPTIONAL MATCH (x:Person)-[:works_at]->(c)
RETURN s.id, c.id, p.id, p.personas, x.id, x.title
"""

DISPLACEMENT = """
MATCH (c:Company)-[:uses]->(k:Competitor)-[:competes_with]->(p:Product), (c)-[:has_signal]->(s:Signal)
WHERE s.kind = 'review_complaint'
   OR (NOT s.negative AND regexp_matches(lower(concat(s.name, ' ', s.quote)), $churn))
RETURN c.id, k.id, p.id, s.id
"""


def available() -> bool:
    try:
        import kuzu  # noqa: F401
    except ImportError:
        return False
    return True


def fingerprint(graph: Graph) -> str:
    return hashlib.sha256(graph.model_dump_json().encode()).hexdigest()[:16]


def _schema(conn) -> None:
    for label in _LABELS:
        cols = "".join(f", {k} {t}" for k, t in _EXTRA.get(label, {}).items())
        conn.execute(f"CREATE NODE TABLE {label}(id STRING, name STRING, props STRING{cols}, PRIMARY KEY(id))")
    for rel, (src, dst) in ONTOLOGY.items():
        conn.execute(f"CREATE REL TABLE {rel}(FROM {src} TO {dst}, eid STRING, props STRING)")


def _load(conn, graph: Graph) -> None:
    labels = {}
    for n in graph.nodes:
        labels[n.id] = n.label
        extra = {k: n.props.get(k) for k in _EXTRA.get(n.label, {})}
        extra = {k: (bool(v) if _EXTRA[n.label][k] == "BOOLEAN" else str(v or "")) for k, v in extra.items()}
        sets = "".join(f", {k}: ${k}" for k in extra)
        conn.execute(f"CREATE (:{n.label} {{id: $id, name: $name, props: $props{sets}}})",
                     {"id": n.id, "name": n.name, "props": json.dumps(n.props, sort_keys=True), **extra})
    for e in graph.edges:
        src, dst = ONTOLOGY[e.type]
        conn.execute(f"MATCH (a:{src} {{id: $s}}), (b:{dst} {{id: $t}}) "
                     f"CREATE (a)-[:{e.type} {{eid: $eid, props: $props}}]->(b)",
                     {"s": e.source, "t": e.target, "eid": e.id, "props": json.dumps(e.props, sort_keys=True)})


def store(graph: Graph, root: FsPath | None = None):
    """Open (building if needed) the kuzu database for this graph and return a connection."""
    import kuzu

    fp = fingerprint(graph)
    with _lock:
        cached = _open.get(graph.run_id)
        if cached and cached[0] == fp:
            return cached[2]
        if cached:
            _open.pop(graph.run_id)
            cached[2].close()
            cached[1].close()
        base = root or ROOT
        base.mkdir(parents=True, exist_ok=True)
        path = base / f"{re.sub(r'[^A-Za-z0-9_-]', '_', graph.run_id)}.kuzu"
        for stale in (path, FsPath(f"{path}.wal")):
            if stale.is_dir():
                shutil.rmtree(stale)
            elif stale.exists():
                stale.unlink()
        db = kuzu.Database(str(path), buffer_pool_size=BUFFER_POOL)
        conn = kuzu.Connection(db)
        _schema(conn)
        _load(conn, graph)
        _open[graph.run_id] = (fp, db, conn)
        return conn


def _rows(conn, cypher: str, params: dict | None = None) -> list[list]:
    res = conn.execute(cypher, params or {})
    out = []
    while res.has_next():
        out.append(res.get_next())
    return out


def _edge(edges: dict[str, Edge], type_: str, s: str, t: str) -> Edge:
    return edges[f"{type_}:{s}->{t}"]


def paths(graph: Graph, kind: str, target: str | None = None, root: FsPath | None = None) -> list[Path]:
    conn = store(graph, root)
    edges = {e.id: e for e in graph.edges}
    with _lock:
        if kind == "warm_intro":
            clause = "AND t.id = $target" if target else ""
            params = {"target": q.person_id(target)} if target else {}
            rows = _rows(conn, WARM_INTRO.replace("{target}", clause), params)
        elif kind == "buying_cycle":
            rows = _rows(conn, BUYING_CYCLE)
        else:
            rows = _rows(conn, DISPLACEMENT, {"churn": CHURN_RE2.lower()})

    if kind == "warm_intro":
        best: dict[tuple[str, str], tuple] = {}
        for t, l1, o, l2, c, p in rows:
            e1, e2, cv = _edge(edges, l1, t, o), _edge(edges, l2, c, o), _edge(edges, "contacted_via", c, p)
            key = (e1.id, e2.id)
            if (t, c) not in best or key < best[(t, c)][0]:
                best[(t, c)] = (key, e1, o, e2, cv)
        return [q.warm_intro_path(graph, t, e1, o, e2, c, cv, "kuzu")
                for (t, c), (_, e1, o, e2, cv) in sorted(best.items())]

    if kind == "buying_cycle":
        groups: dict[tuple[str, str, str], list[tuple[str, str]]] = {}
        personas: dict[str, list[str]] = {}
        for s, c, p, pers, x, title in rows:
            groups.setdefault((s, c, p), [])
            personas[p] = [v for v in (pers or "").split("|") if v]
            if x:
                groups[(s, c, p)].append((x, title or ""))
        out = []
        for (s, c, p), staff in groups.items():
            fit = [x for x, title in staff if q.persona_match(title, personas[p])] if personas[p] else [x for x, _ in staff]
            works = sorted((_edge(edges, "works_at", x, c) for x in fit), key=lambda e: e.id)
            has = _edge(edges, "has_signal", c, s)
            out.append((has.id, q.buying_cycle_path(graph, s, c, has, _edge(edges, "matched_to", c, p), works, "kuzu")))
        return [path for _, path in sorted(out, key=lambda x: x[0])]

    found = []
    for c, k, p, s in rows:
        uses, has = _edge(edges, "uses", c, k), _edge(edges, "has_signal", c, s)
        found.append(((uses.id, has.id), q.displacement_path(graph, c, uses, k, _edge(edges, "competes_with", k, p),
                                                              has, "kuzu")))
    return [path for _, path in sorted(found, key=lambda x: x[0])]
