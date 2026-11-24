"""Run storage: one JSON file per run at data/gtm/runs/<id>.json.

Writes go to a temp file in the same folder and are renamed into place, so a crash
never leaves half a run. `update` serialises read-modify-write per run, so the
background pipeline and a rep clicking approve never overwrite each other.
"""

from __future__ import annotations

import os
import re
import tempfile
import threading
from collections import defaultdict
from pathlib import Path
from typing import Callable

from gtm.contract import Run

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_locks: dict[str, threading.RLock] = defaultdict(threading.RLock)
_locks_guard = threading.Lock()


class RunNotFound(KeyError):
    pass


def data_dir() -> Path:
    return Path(os.environ.get("GTM_DATA_DIR", "data/gtm"))


def runs_dir() -> Path:
    d = data_dir() / "runs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(run_id: str) -> Path:
    if not _ID_RE.match(run_id):
        raise RunNotFound(run_id)
    return runs_dir() / f"{run_id}.json"


def _lock(run_id: str) -> threading.RLock:
    with _locks_guard:
        return _locks[run_id]


def save(run: Run) -> None:
    path = _path(run.id)
    with _lock(run.id):
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{run.id}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(run.model_dump_json(indent=2))
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise


def load(run_id: str) -> Run:
    path = _path(run_id)
    if not path.exists():
        raise RunNotFound(run_id)
    return Run.model_validate_json(path.read_text(encoding="utf-8"))


def update(run_id: str, change: Callable[[Run], object]) -> Run:
    """Load, apply `change` in place, save; all under the run's lock."""
    with _lock(run_id):
        run = load(run_id)
        change(run)
        save(run)
        return run


def list_ids() -> list[str]:
    return sorted(p.stem for p in runs_dir().glob("*.json"))
