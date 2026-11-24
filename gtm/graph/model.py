"""The graph's own shapes: typed nodes, typed edges, and the paths queries return.

Node and edge ids are stable strings derived from the run, so building twice
from the same run gives byte-identical graphs.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

NodeLabel = Literal["Company", "Person", "Product", "Competitor", "Signal", "School"]
EdgeType = Literal[
    # SPEC.md Module 3
    "works_at", "competes_with", "matched_to", "contacted_via", "replied_to", "previously_employed_at",
    # added by lane B (see docs/gtm/briefs/lane-b-status.md)
    "attended", "has_signal", "uses",
]

# (edge type) -> (from label, to label): the ontology, also the kuzu schema.
ONTOLOGY: dict[str, tuple[str, str]] = {
    "works_at": ("Person", "Company"),
    "previously_employed_at": ("Person", "Company"),
    "attended": ("Person", "School"),
    "has_signal": ("Company", "Signal"),
    "matched_to": ("Company", "Product"),
    "competes_with": ("Competitor", "Product"),
    "contacted_via": ("Person", "Product"),
    "replied_to": ("Person", "Product"),
    "uses": ("Company", "Competitor"),
}


class Node(BaseModel):
    id: str
    label: NodeLabel
    name: str
    props: dict[str, str | int | float | bool | None] = {}


class Edge(BaseModel):
    id: str
    type: EdgeType
    source: str
    target: str
    props: dict[str, str | int | float | bool | None] = {}


class Graph(BaseModel):
    run_id: str
    nodes: list[Node] = []
    edges: list[Edge] = []

    def node(self, node_id: str) -> Node:
        return self._nodes()[node_id]

    def _nodes(self) -> dict[str, Node]:
        return {n.id: n for n in self.nodes}

    def out(self, node_id: str, *types: str) -> list[Edge]:
        return [e for e in self.edges if e.source == node_id and (not types or e.type in types)]

    def into(self, node_id: str, *types: str) -> list[Edge]:
        return [e for e in self.edges if e.target == node_id and (not types or e.type in types)]


PathKind = Literal["warm_intro", "buying_cycle", "competitor_displacement"]


class Path(BaseModel):
    """One answer to a multi-hop query: the nodes and edges to draw, plus a sentence."""
    kind: PathKind
    summary: str
    nodes: list[Node] = Field(min_length=2)
    edges: list[Edge] = Field(min_length=1)
    engine: Literal["kuzu", "python"] = "python"
