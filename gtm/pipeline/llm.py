"""Model calls through Sellbird's own Brain (Claude Code CLI on the Claude plan, isolated).

`ask_json` returns the parsed JSON plus the call's tokens so each step can write an
AuditEvent. Brain wants a StateManager only to log usage rows; `_UsageTap` stands in
for it and keeps those rows in memory instead of a SQLite file.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from gtm.contract import AuditEvent


class ModelUnavailable(RuntimeError):
    pass


@dataclass
class Usage:
    tokens: int = 0
    notional_usd: float = 0.0  # what the call would cost on the API; the Claude plan does not bill it
    rows: list[dict] = field(default_factory=list)
    cached: bool = False


class _UsageTap:
    def __init__(self) -> None:
        self.usage = Usage()

    async def record_usage_event(self, **row) -> None:
        self.usage.rows.append(row)
        self.usage.tokens += sum(int(row.get(k) or 0) for k in
                                 ("input_tokens", "output_tokens", "cache_read_tokens", "cache_creation_tokens"))
        self.usage.notional_usd += float(row.get("cost_usd") or 0.0)

    def __getattr__(self, name):  # any other StateManager call Brain makes is a no-op here
        async def _noop(*a, **k):
            return None
        return _noop


async def _ask(prompt: str, agent: str, task: str, timeout: float):
    from dotenv import load_dotenv
    from sellbird.brain import Brain

    load_dotenv(override=False)  # CLAUDE_CODE_OAUTH_TOKEN may live in .env on a lane machine
    tap = _UsageTap()
    brain = Brain(tap)
    text = await brain.think(prompt + "\n\nRespond ONLY with valid JSON. No markdown, no explanation.",
                             agent=agent, task=task, timeout=timeout, max_retries=1)
    if not text:
        raise ModelUnavailable(f"no reply from the model for {agent}/{task}")
    data = Brain._extract_json(text)
    if data is None:
        raise ModelUnavailable(f"model reply for {agent}/{task} was not JSON: {text[:200]}")
    return data, tap.usage


def cache_path(prompt: str, agent: str, task: str) -> Path:
    from gtm.pipeline.store import data_dir
    key = hashlib.sha256(f"{agent}\n{task}\n{prompt}".encode()).hexdigest()[:24]
    return data_dir() / "cache" / "llm" / f"{agent}-{task}-{key}.json"


def ask_json(prompt: str, *, agent: str, task: str, timeout: float = 300) -> tuple[dict | list, Usage]:
    """Blocking call (the pipeline runs in its own thread). Replies are cached by prompt
    hash, so a re-run of the same input replays without another model call. The prompt
    is saved beside the reply so every cached answer can be read against its question."""
    path = cache_path(prompt, agent, task)
    if path.exists():
        saved = json.loads(path.read_text(encoding="utf-8"))
        return saved["reply"], Usage(tokens=0, cached=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        data, usage = asyncio.run(_ask(prompt, agent, task, timeout))
    except ModelUnavailable:
        # Leave the question where a person (or another session) can answer it:
        # write {"reply": ...} into this file, rename it to drop ".pending", re-run.
        path.with_suffix(".pending.json").write_text(
            json.dumps({"agent": agent, "task": task, "prompt": prompt, "reply": None}, indent=2), encoding="utf-8")
        raise
    path.write_text(json.dumps({"agent": agent, "task": task, "prompt": prompt, "reply": data,
                                "tokens": usage.tokens}, indent=2), encoding="utf-8")
    return data, usage


def model_event(agent: str, task: str, usage: Usage, target: str = "", detail: str = "") -> AuditEvent:
    from gtm.pipeline.runner import event
    if usage.cached:
        note = f"{detail} (replayed from cache, no call)".strip()
    else:
        note = f"{detail} (plan call; API-equivalent ${usage.notional_usd:.4f})".strip()
    return event(f"model:{task}", agent=agent, target=target, detail=note, tokens=usage.tokens, cost_usd=0.0)
