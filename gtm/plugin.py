"""Sellbird extension entry point (pyproject: [project.entry-points."sellbird.extensions"]).

Each lane adds its own `routes.py` exposing `router`; this mounts whichever exist,
so a lane that has not landed yet costs nothing.
"""

from __future__ import annotations

import importlib

LANE_ROUTERS = ("gtm.pipeline.routes", "gtm.graph.routes", "gtm.band.routes", "gtm.fixture_routes")


def install(registry) -> None:
    for name in LANE_ROUTERS:
        try:
            module = importlib.import_module(name)
        except ModuleNotFoundError as e:
            if e.name and (name == e.name or name.startswith(e.name + ".")):  # lane not built yet
                continue
            raise
        registry.add_router(module.router)
