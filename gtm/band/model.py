"""One agent decision = one model call through Sellbird's Brain, with its tokens and cost.

`SellbirdModel` reuses `sellbird.brain.Brain` unchanged (isolated, tool-less
Claude CLI on the Claude plan, retries, timeouts) and reads the per-call usage
rows Brain writes, through a small ledger standing in for Sellbird's state.
Tests pass any async callable with the same signature instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Reply:
    text: str
    data: dict | None
    tokens: int = 0
    cost_usd: float = 0.0
    model: str = ""


class Model(Protocol):
    async def __call__(self, agent: str, prompt: str) -> Reply: ...


@dataclass
class _Ledger:
    """The parts of Sellbird's StateManager that Brain touches on a call."""
    rows: list[dict] = field(default_factory=list)

    async def increment_usage(self, **_kw) -> None:
        return None

    async def record_usage_event(self, **row) -> None:
        self.rows.append(row)

    async def get_setting(self, _key: str, default=None):
        return default

    async def set_setting(self, _key: str, _value) -> None:
        return None


class SellbirdModel:
    def __init__(self, model: str = "", timeout: float = 120.0):
        self.model = model
        self.timeout = timeout

    async def __call__(self, agent: str, prompt: str) -> Reply:
        from sellbird.brain import Brain
        from sellbird.config import BrainConfig

        ledger = _Ledger()
        brain = Brain(ledger, BrainConfig(model=self.model) if self.model else None)
        text = await brain.think(prompt + "\n\nRespond ONLY with valid JSON. No markdown, no explanation.",
                                 timeout=self.timeout, max_retries=1, agent=f"gtm-band-{agent}", task="review")
        data = Brain._extract_json(text) if text else None
        tokens = sum(int(r.get(k) or 0) for r in ledger.rows
                     for k in ("input_tokens", "output_tokens", "cache_read_tokens", "cache_creation_tokens"))
        cost = round(sum(float(r.get("cost_usd") or 0.0) for r in ledger.rows), 6)
        models = ",".join(sorted({str(r.get("model") or "") for r in ledger.rows} - {""}))
        return Reply(text=text, data=data if isinstance(data, dict) else None, tokens=tokens, cost_usd=cost,
                     model=models)
