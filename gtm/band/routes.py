"""BAND room API for the UI's live feed and the review trigger.

GET  /api/gtm/band/feed?since=N               messages after seq N, tokens, cumulative cost
POST /api/gtm/band/review/{run_id}/{draft_id}   start the four-agent review (?wait=true to block)
POST /api/gtm/band/rep/{run_id}/{draft_id}      mock mode only: the rep's reply, {"text": "approve d_1"}
POST /api/gtm/band/poll                         live mode: read the rep's replies from BAND now
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from gtm.graph.runs import RunNotFound, load_run

router = APIRouter()
logger = logging.getLogger(__name__)
_room = None
_tasks: set[asyncio.Task] = set()
_poller: asyncio.Task | None = None
POLL_SECONDS = 5.0


def get_room():
    global _room
    if _room is None:
        from dotenv import load_dotenv

        from gtm.band.model import SellbirdModel
        from gtm.band.room import ReviewRoom

        load_dotenv(Path(__file__).resolve().parents[2] / ".env")
        _room = ReviewRoom(SellbirdModel())
    return _room


def set_room(room) -> None:
    """Tests and scripts install their own room (a fake model, a temp state dir)."""
    global _room
    _room = room


def _check(run_id: str, draft_id: str) -> None:
    try:
        run = load_run(run_id)
    except RunNotFound:
        raise HTTPException(404, f"no run {run_id}") from None
    if not any(d.id == draft_id for d in run.drafts):
        raise HTTPException(404, f"no draft {draft_id} in run {run_id}")


async def _poll_forever(room) -> None:
    while room.awaiting:
        try:
            await room.poll_rep()
        except Exception as e:  # keep polling through a flaky network
            logger.warning(f"BAND poll failed: {e}")
        await asyncio.sleep(POLL_SECONDS)


def _ensure_poller(room) -> None:
    global _poller
    if room.band.mode == "live" and room.awaiting and (_poller is None or _poller.done()):
        _poller = asyncio.create_task(_poll_forever(room))


@router.get("/api/gtm/band/feed")
async def band_feed(since: int = 0):
    return get_room().feed_since(since)


@router.post("/api/gtm/band/review/{run_id}/{draft_id}")
async def band_review(run_id: str, draft_id: str, wait: bool = False):
    _check(run_id, draft_id)
    room = get_room()

    async def go():
        outcome = await room.review(run_id, draft_id)
        _ensure_poller(room)
        return outcome

    if wait:
        return asdict(await go())
    task = asyncio.create_task(go())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return {"started": True, "run_id": run_id, "draft_id": draft_id}


class RepReply(BaseModel):
    text: str


@router.post("/api/gtm/band/rep/{run_id}/{draft_id}")
async def band_rep(run_id: str, draft_id: str, body: RepReply):
    _check(run_id, draft_id)
    room = get_room()
    if room.band.mode != "mock":
        raise HTTPException(409, "live BAND: the rep replies in the Band app")
    return asdict(await room.rep_says(run_id, draft_id, body.text))


@router.post("/api/gtm/band/poll")
async def band_poll():
    room = get_room()
    if room.band.mode != "live":
        return {"applied": []}
    return {"applied": [asdict(o) for o in await room.poll_rep()]}
