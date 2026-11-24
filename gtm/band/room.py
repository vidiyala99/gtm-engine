"""The review room: planner -> builder -> reviewer -> security -> rep, one draft at a time.

Every agent message is a model decision posted to BAND with @mentions, appended
to the live feed (with tokens and cumulative cost) and written to the run as an
AuditEvent. A draft becomes `approved` only when the rep's own message says so,
and only after the reviewer and security both passed it.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from gtm.band import agents
from gtm.band.model import Model, Reply
from gtm.band.transport import make_pool, make_transport, parse_verdict
from gtm.contract import AuditEvent
from gtm.graph.runs import load_run, save_run

CAST = {"planner": "agent", "builder": "agent", "reviewer": "agent", "security": "agent", "rep": "human"}
STATE_DIR = Path(__file__).resolve().parents[2] / "data" / "gtm" / "band"


@dataclass
class FeedItem:
    seq: int
    at: str
    run_id: str
    draft_id: str
    sender: str
    to: list[str]
    text: str
    kind: str  # message | decision | approval_request | verdict | status
    tokens: int = 0
    cost_usd: float = 0.0
    model: str = ""


@dataclass
class Outcome:
    run_id: str
    draft_id: str
    state: str  # rejected | blocked | awaiting_rep | approved | stalled
    reason: str = ""
    details: list[str] = field(default_factory=list)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ReviewRoom:
    def __init__(self, model: Model, band=None, state_dir: Path | None = None):
        self.model = model
        self.band = band or make_transport(CAST)
        self.pool = make_pool(self.band)
        self.state_dir = state_dir or STATE_DIR
        self.feed: list[FeedItem] = []
        self.awaiting: dict[str, dict] = {}  # "run/draft" -> {"room", "asked_at"}
        self.seen_rep: set[str] = set()
        self._locks: dict[str, asyncio.Lock] = {}
        self._room: str | None = None
        self._last_sent_t = 0.0
        self._load()

    # --- persistence --------------------------------------------------------------
    @property
    def _feed_file(self) -> Path:
        return self.state_dir / "feed.jsonl"

    @property
    def _state_file(self) -> Path:
        return self.state_dir / "state.json"

    def _load(self) -> None:
        if self._feed_file.exists():
            for line in self._feed_file.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self.feed.append(FeedItem(**json.loads(line)))
        if self._state_file.exists():
            st = json.loads(self._state_file.read_text(encoding="utf-8"))
            self.awaiting = st.get("awaiting", {})
            self.seen_rep = set(st.get("seen_rep", []))

    def _save_state(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(json.dumps({"awaiting": self.awaiting, "seen_rep": sorted(self.seen_rep)}))

    def totals(self) -> dict:
        return {"messages": len(self.feed), "tokens": sum(i.tokens for i in self.feed),
                "cost_usd": round(sum(i.cost_usd for i in self.feed), 6)}

    def feed_since(self, since: int = 0) -> dict:
        items = [asdict(i) for i in self.feed if i.seq > since]
        running_tokens, running_cost = 0, 0.0
        cumulative = {}
        for i in self.feed:
            running_tokens += i.tokens
            running_cost += i.cost_usd
            cumulative[i.seq] = (running_tokens, round(running_cost, 6))
        for it in items:
            it["cumulative_tokens"], it["cumulative_cost_usd"] = cumulative[it["seq"]]
        return {"mode": self.band.mode, "items": items, "totals": self.totals(),
                "awaiting_rep": sorted(self.awaiting)}

    # --- room plumbing --------------------------------------------------------------
    async def room(self) -> str:
        if self._room is None:
            rid = await asyncio.to_thread(self.pool.get, "review", "planner")
            for member in ("builder", "reviewer", "security", "rep"):
                await asyncio.to_thread(self.band.add_participant, rid, "planner", member)
            self._room = rid
        return self._room

    async def _post(self, run_id: str, draft_id: str, sender: str, to: list[str], text: str, kind: str,
                    reply: Reply | None = None, action: str = "", target_status: str | None = None,
                    note: str | None = None) -> FeedItem:
        rid = await self.room()
        tag = f"[{run_id}/{draft_id}] "
        sent = await asyncio.to_thread(self.band.send, rid, sender, tag + text, to)
        self._last_sent_t = sent.t  # BAND's clock in live mode, so rep replies compare on one clock
        item = FeedItem(seq=(self.feed[-1].seq + 1) if self.feed else 1, at=_now().isoformat(), run_id=run_id,
                        draft_id=draft_id, sender=sender, to=list(to), text=text, kind=kind,
                        tokens=reply.tokens if reply else 0, cost_usd=reply.cost_usd if reply else 0.0,
                        model=reply.model if reply else "")
        self.feed.append(item)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with self._feed_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(item)) + "\n")
        self._audit(run_id, draft_id, sender, action or f"band.{sender}.{kind}", text, item, target_status, note)
        return item

    def _audit(self, run_id: str, draft_id: str, sender: str, action: str, text: str, item: FeedItem,
               target_status: str | None, note: str | None) -> None:
        run = load_run(run_id)
        run.audit.append(AuditEvent(at=_now(), actor="rep" if sender == "rep" else "ai", agent=sender,
                                    action=action, target=draft_id, detail=text[:1000],
                                    tokens=item.tokens, cost_usd=item.cost_usd))
        if target_status or note:
            for d in run.drafts:
                if d.id == draft_id:
                    if target_status:
                        d.status = target_status
                    if note:
                        d.review_notes.append(note)
        save_run(run)

    async def _think(self, agent: str, prompt: str) -> Reply:
        return await self.model(agent, prompt)

    # --- the flow -------------------------------------------------------------------
    async def review(self, run_id: str, draft_id: str) -> Outcome:
        key = f"{run_id}/{draft_id}"
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            lead = agents.lead_for(load_run(run_id), draft_id)
            if lead.draft.status != "pending":
                return Outcome(run_id, draft_id, lead.draft.status, f"draft is already {lead.draft.status}")
            if key in self.awaiting:
                return Outcome(run_id, draft_id, "awaiting_rep", "already waiting for the rep")

            plan = await self._think("planner", agents.planner_prompt(lead))
            if not plan.data or not plan.data.get("handoff"):
                return await self._stall(run_id, draft_id, "planner")
            await self._post(run_id, draft_id, "planner", ["builder"], plan.data["handoff"], "message", plan,
                             action="band.planner.handoff")

            build = await self._think("builder", agents.builder_prompt(lead, plan.data["handoff"]))
            if not build.data or not isinstance(build.data.get("claims"), list):
                return await self._stall(run_id, draft_id, "builder")
            claims = [c for c in build.data["claims"] if isinstance(c, dict)]
            subject = f"Subject: {lead.draft.subject}\n" if lead.draft.subject else ""
            claim_lines = "\n".join(f"- {c.get('text', '')} [{c.get('signal_id') or 'no signal'}]" for c in claims)
            await self._post(run_id, draft_id, "builder", ["reviewer"],
                             f"{build.data.get('note') or 'Draft for review.'}\n{lead.draft.channel} to {lead.who()}\n"
                             f"{subject}{lead.draft.body}\nClaims:\n{claim_lines}", "message", build,
                             action="band.builder.posted")

            rev = await self._think("reviewer", agents.reviewer_prompt(lead, claims))
            if not rev.text:
                return await self._stall(run_id, draft_id, "reviewer")
            verdict = agents.review_guard(lead, rev.data, claims)
            if not verdict.ok:
                why = "; ".join(verdict.details)
                await self._post(run_id, draft_id, "reviewer", ["builder", "planner"], f"REJECT: {why}", "decision",
                                 rev, action="band.reviewer.reject", target_status="rejected",
                                 note=f"reviewer: {why}")
                return Outcome(run_id, draft_id, "rejected", verdict.reason, verdict.details)
            await self._post(run_id, draft_id, "reviewer", ["security"], f"PASS: {verdict.reason}", "decision", rev,
                             action="band.reviewer.pass")

            findings = agents.security_scan(lead)
            sec = await self._think("security", agents.security_prompt(lead, findings))
            if not sec.text:
                return await self._stall(run_id, draft_id, "security")
            sv = agents.security_guard(findings, sec.data)
            if not sv.ok:
                why = "; ".join(sv.details)
                await self._post(run_id, draft_id, "security", ["builder", "planner"], f"BLOCK: {why}", "decision",
                                 sec, action="band.security.block", target_status="rejected",
                                 note=f"security: {why}")
                return Outcome(run_id, draft_id, "blocked", sv.reason, sv.details)
            item = await self._post(
                run_id, draft_id, "security", ["rep", "planner"],
                f"PASS: {sv.reason}. Approval needed: {lead.draft.channel} draft {draft_id} to {lead.who()}. "
                f"Reply 'approve {draft_id}' or 'reject {draft_id}' (mention @planner).",
                "approval_request", sec, action="band.security.pass")
            self.awaiting[key] = {"room": await self.room(), "asked_at": self._last_sent_t, "seq": item.seq}
            self._save_state()
            return Outcome(run_id, draft_id, "awaiting_rep", "waiting for the rep's reply in BAND")

    async def _stall(self, run_id: str, draft_id: str, agent: str) -> Outcome:
        await self._post(run_id, draft_id, "planner", ["rep"],
                         f"{agent} model call returned nothing; review stopped, draft stays pending.", "status",
                         action=f"band.{agent}.unavailable")
        return Outcome(run_id, draft_id, "stalled", f"{agent} model unavailable")

    # --- the human ----------------------------------------------------------------
    async def rep_says(self, run_id: str, draft_id: str, text: str) -> Outcome:
        """Mock mode: the rep types into the room. Live mode reads the app instead (poll_rep)."""
        if self.band.mode != "mock":
            raise RuntimeError("live BAND: the rep replies in the Band app; call poll_rep")
        rid = await self.room()
        msg = await asyncio.to_thread(self.band.send, rid, "rep", f"[{run_id}/{draft_id}] {text}", ["planner"])
        return await self._apply_rep(run_id, draft_id, text, msg.id)

    async def poll_rep(self) -> list[Outcome]:
        """Read the rep's messages to the planner and apply any verdicts on drafts we are waiting on."""
        if not self.awaiting:
            return []
        rid = await self.room()
        msgs = await asyncio.to_thread(self.band.verdicts, rid, "rep", "planner")
        out = []
        for m in msgs:
            if m.id in self.seen_rep:
                continue
            key = self._match(m.text, m.t)
            if key:
                run_id, draft_id = key.split("/", 1)
                out.append(await self._apply_rep(run_id, draft_id, m.text, m.id))
        return out

    def _match(self, text: str, t: float) -> str | None:
        live = {k: v for k, v in self.awaiting.items() if t >= v["asked_at"] - 1}
        named = [k for k in live if k in text or k.split("/", 1)[1] in text.split()]
        if len(named) == 1:
            return named[0]
        return next(iter(live)) if len(live) == 1 and not named else None

    async def _apply_rep(self, run_id: str, draft_id: str, text: str, msg_id: str) -> Outcome:
        key = f"{run_id}/{draft_id}"
        self.seen_rep.add(msg_id)
        verdict = parse_verdict(text)
        if key not in self.awaiting:
            self._save_state()
            return Outcome(run_id, draft_id, "ignored", "no approval was requested for this draft")
        if verdict is None:
            self._save_state()
            return Outcome(run_id, draft_id, "awaiting_rep", "rep message had no approve/reject")
        self.awaiting.pop(key)
        self._save_state()
        status = "approved" if verdict == "approve" else "rejected"
        await self._post(run_id, draft_id, "rep", ["planner"], text, "verdict", action=f"band.rep.{status}",
                         target_status=status, note=f"rep: {text}" if status == "rejected" else None)
        ack = ("approved by the rep; it may now be sent (test inbox only)." if status == "approved"
               else "rejected by the rep; it will not be sent.")
        await self._post(run_id, draft_id, "planner", ["rep", "builder"], f"{draft_id} {ack}", "status",
                         action=f"band.planner.ack_{status}")
        return Outcome(run_id, draft_id, status, f"rep replied: {text}")
