"""Serves the fictional fixture run so the web lane can build before the pipeline lands.

GET /api/gtm/runs/fixture -> Run JSON. Lane A's real routes live at /api/gtm/runs/{id}.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from gtm.contract import Run

FIXTURE = Path(__file__).parent / "fixtures" / "run.json"
router = APIRouter()


def load_fixture() -> Run:
    return Run.model_validate_json(FIXTURE.read_text(encoding="utf-8"))


@router.get("/api/gtm/runs/fixture")
async def fixture_run():
    return load_fixture().model_dump(mode="json")
