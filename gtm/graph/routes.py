"""GET /api/gtm/runs/{id}/graph and GET /api/gtm/runs/{id}/paths/{kind}."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from gtm.graph import build, paths
from gtm.graph.queries import KINDS, canonical_kind
from gtm.graph.runs import RunNotFound, load_run

router = APIRouter()


def _graph(run_id: str):
    try:
        return build(load_run(run_id))
    except RunNotFound:
        raise HTTPException(404, f"no run {run_id}") from None


@router.get("/api/gtm/runs/{run_id}/graph")
async def run_graph(run_id: str):
    g = await run_in_threadpool(_graph, run_id)
    return g.model_dump(mode="json")


@router.get("/api/gtm/runs/{run_id}/paths/{kind}")
async def run_paths(run_id: str, kind: str, target: str | None = None, engine: str = "auto"):
    kind = canonical_kind(kind)
    if kind not in KINDS:
        raise HTTPException(404, f"unknown path kind {kind}; one of {', '.join(KINDS)}")
    if engine not in ("auto", "kuzu", "python"):
        raise HTTPException(400, "engine is auto, kuzu or python")

    def go():
        found = paths(_graph(run_id), kind, engine=engine, target=target)
        return {"run_id": run_id, "kind": kind, "engine": found[0].engine if found else engine,
                "paths": [p.model_dump(mode="json") for p in found]}

    try:
        return await run_in_threadpool(go)
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from None
