"""Reading and writing runs for lane B, through lane A's store once it lands.

`gtm.pipeline.store` owns data/gtm/runs/<id>.json. Until it exists (or for the
fixture id), runs come from gtm/fixtures/run.json, and lane B's own changes to
the fixture (draft verdicts, audit events) are kept in data/gtm/band/runs/.
"""

from __future__ import annotations

import importlib
import os
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path

from gtm.contract import Run
from gtm.fixture_routes import load_fixture

OVERLAY = Path(__file__).resolve().parents[2] / "data" / "gtm" / "band" / "runs"


class RunNotFound(KeyError):
    pass


def _store():
    try:
        return importlib.import_module("gtm.pipeline.store")
    except ModuleNotFoundError:
        return None


def _call(module, names: tuple[str, ...], *args):
    for name in names:
        fn = getattr(module, name, None)
        if callable(fn):
            return fn(*args)
    raise AttributeError(f"gtm.pipeline.store has none of {names}")


def _overlay(run_id: str) -> Path:
    return OVERLAY / f"{run_id}.json"


def load_run(run_id: str) -> Run:
    store = _store()
    if run_id != "fixture" and store is not None:
        try:
            run = _call(store, ("load_run", "load", "get_run", "get"), run_id)
        except (FileNotFoundError, KeyError) as e:
            raise RunNotFound(run_id) from e
        if run is None:
            raise RunNotFound(run_id)
        return run if isinstance(run, Run) else Run.model_validate(run)
    path = _overlay(run_id)
    if path.exists():
        return Run.model_validate_json(path.read_text(encoding="utf-8"))
    if run_id == "fixture":
        return load_fixture()
    raise RunNotFound(run_id)


_overlay_lock = threading.RLock()


def update_run(run_id: str, change: Callable[[Run], object]) -> Run:
    """Load, change in place, save, under the store's per-run lock, so a BAND event
    never overwrites a pipeline write made in between."""
    store = _store()
    if run_id != "fixture" and store is not None and callable(getattr(store, "update", None)):
        try:
            return store.update(run_id, change)
        except (FileNotFoundError, KeyError) as e:
            raise RunNotFound(run_id) from e
    with _overlay_lock:
        run = load_run(run_id)
        change(run)
        save_run(run)
        return run


def save_run(run: Run) -> None:
    store = _store()
    if run.id != "fixture" and store is not None:
        _call(store, ("save_run", "save", "put"), run)
        return
    path = _overlay(run.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(run.model_dump_json(indent=1))
    os.replace(tmp, path)
