"""Glasser CLI client with a response cache and a spend guard.

Every response is cached under data/gtm/cache/glasser/, keyed by provider, endpoint
and input, so a re-run costs nothing. `Spend` tallies real charges for a step and
refuses a call once the step passes its cap (COMMON.md: stop past $3 a step).
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass, field

from gtm.pipeline.store import data_dir

STEP_CAP_USD = 3.0


class GlasserError(RuntimeError):
    pass


class OverBudget(GlasserError):
    pass


@dataclass
class Result:
    provider: str
    endpoint: str
    output: dict
    cost_usd: float
    run_url: str
    cached: bool

    @property
    def label(self) -> str:
        return f"glasser:{self.provider}{self.endpoint}"


@dataclass
class Spend:
    cap_usd: float = STEP_CAP_USD
    spent_usd: float = 0.0
    calls: list[Result] = field(default_factory=list)


def _key(provider: str, endpoint: str, payload: dict) -> str:
    raw = json.dumps([provider, endpoint, payload], sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _cache_file(provider: str, endpoint: str, key: str):
    slug = re.sub(r"[^A-Za-z0-9]+", "_", f"{provider}{endpoint}").strip("_")[:60]
    d = data_dir() / "cache" / "glasser"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{slug}-{key}.json"


def cached(provider: str, endpoint: str, payload: dict) -> Result | None:
    path = _cache_file(provider, endpoint, _key(provider, endpoint, payload))
    if not path.exists():
        return None
    env = json.loads(path.read_text(encoding="utf-8"))
    return Result(provider, endpoint, env.get("output") or {}, float(env.get("charge_usd") or 0), env.get("run_url", ""),
                  cached=True)


def run(provider: str, endpoint: str, payload: dict, *, spend: Spend | None = None, task: str = "",
        timeout: int = 300) -> Result:
    hit = cached(provider, endpoint, payload)
    if hit:
        if spend is not None:
            spend.calls.append(hit)
        return hit
    if spend is not None and spend.spent_usd >= spend.cap_usd:
        raise OverBudget(f"step spend ${spend.spent_usd:.2f} reached its ${spend.cap_usd:.2f} cap")
    key = _key(provider, endpoint, payload)
    cmd = ["glasser", "run", "-p", provider, "-e", endpoint, "-i", json.dumps(payload),
           "--idempotency-key", f"gtm-{key}", "--wait", "--wait-timeout", str(timeout), "--json"]
    if task:
        cmd += ["--task", task]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 30)
    try:
        env = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise GlasserError(f"{provider}{endpoint}: unreadable reply: {(proc.stdout or proc.stderr)[:300]}")
    if "error" in env and "status" not in env:
        raise GlasserError(f"{provider}{endpoint}: {env['error']}")
    cost = float(env.get("charge_usd") or 0)
    if spend is not None:
        spend.spent_usd += cost
    if env.get("status") != "COMPLETED":
        raise GlasserError(f"{provider}{endpoint}: {env.get('status')} {env.get('failure')}")
    _cache_file(provider, endpoint, key).write_text(json.dumps(env, indent=2), encoding="utf-8")
    result = Result(provider, endpoint, env.get("output") or {}, cost, env.get("run_url", ""), cached=False)
    if spend is not None:
        spend.calls.append(result)
    return result


def items(result: Result) -> list[dict]:
    """The row list inside a Glasser envelope, wherever the provider put it."""
    out = result.output
    for path in (("output", "data", "items"), ("output", "data"), ("output", "items"), ("output",), ("data",),
                 ("items",)):
        cur = out
        for k in path:
            cur = cur.get(k) if isinstance(cur, dict) else None
        if isinstance(cur, list):
            return cur
    return []


def audit(result: Result, agent: str, detail: str = ""):
    from gtm.pipeline.runner import event
    note = detail + (" (cache hit, no charge)" if result.cached else "")
    return event(f"call:{result.label}", agent=agent, target=result.run_url, detail=note.strip(),
                 cost_usd=0.0 if result.cached else result.cost_usd)
