"""Runs the pipeline steps for one run in a background thread.

Each step reads the run from the store, does its work, and writes back through
`store.update`, so the UI polling GET /api/gtm/runs/{id} watches the run fill.
Progress is told through the audit log: run_started, step_started/step_done per
step, step_failed with the error, run_finished.
"""

from __future__ import annotations

import importlib
import logging
import threading
import traceback
from datetime import datetime, timezone
from typing import Callable

from gtm.contract import AuditEvent
from gtm.pipeline import store

log = logging.getLogger(__name__)

# (name, "module:function"); each function takes run_id. Resolved at run time so a
# step that has not landed yet is skipped, not fatal.
STEPS: list[tuple[str, str]] = [
    ("icp", "gtm.pipeline.icp:run_step"),
    ("discover", "gtm.pipeline.discover:run_step"),
    ("competitors", "gtm.pipeline.competitors:run_step"),
    ("enrich", "gtm.pipeline.enrich:run_step"),
    ("draft", "gtm.pipeline.draft:run_step"),
]


def event(action: str, agent: str = "pipeline", target: str = "", detail: str = "",
          tokens: int = 0, cost_usd: float = 0.0) -> AuditEvent:
    return AuditEvent(at=datetime.now(timezone.utc), actor="ai", agent=agent, action=action, target=target,
                      detail=detail, tokens=tokens, cost_usd=round(cost_usd, 6))


def log_event(run_id: str, ev: AuditEvent) -> None:
    store.update(run_id, lambda run: run.audit.append(ev))


def _resolve(spec: str) -> Callable[[str], None] | None:
    mod_name, fn = spec.split(":")
    try:
        mod = importlib.import_module(mod_name)
    except ModuleNotFoundError as e:
        if e.name == mod_name:
            return None
        raise
    return getattr(mod, fn)


def run_all(run_id: str, steps: list[tuple[str, str]] | None = None) -> None:
    log_event(run_id, event("run_started", target=run_id))
    for name, spec in steps or STEPS:
        fn = _resolve(spec)
        if fn is None:
            continue
        log_event(run_id, event("step_started", agent=name, target=run_id))
        try:
            fn(run_id)
        except Exception as e:  # one failing step stops the run but leaves what it found
            log.exception("gtm step %s failed for %s", name, run_id)
            detail = f"{type(e).__name__}: {e}"[:500]
            log_event(run_id, event("step_failed", agent=name, target=run_id, detail=detail))
            log.debug("%s", traceback.format_exc())
            return
        log_event(run_id, event("step_done", agent=name, target=run_id))
    log_event(run_id, event("run_finished", target=run_id))


def start(run_id: str) -> threading.Thread:
    t = threading.Thread(target=run_all, args=(run_id,), name=f"gtm-{run_id}", daemon=True)
    t.start()
    return t
