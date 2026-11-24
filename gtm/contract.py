"""The shared data shape of one GTM run. Every lane reads and writes these types.

One `Run` is the whole story of one product: intake, ICP, companies, people,
competitors, drafts, stages and the audit log. The pipeline (lane A) produces it,
the graph and agents (lane B) read and annotate it, the web (lane C) renders it.
Change a field only through the owner session: all three lanes depend on it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

Confidence = float  # 0.00 to 1.00, validated per field below
Stage = Literal["matched", "contacted", "replied", "meeting", "closed_won", "closed_lost"]
Tier = Literal["A", "B", "C"]
EmailStatus = Literal["verified", "catch_all", "risky", "guess", "invalid", "unknown"]
DraftStatus = Literal["pending", "approved", "rejected", "sent"]  # a rep edit is an audit event; the draft stays pending
Actor = Literal["ai", "rep"]


class Citation(BaseModel):
    """Where a fact came from. A fact without one is not shown."""
    url: HttpUrl
    title: str = ""
    quote: str = ""  # the sentence or field that supports the claim
    provider: str = ""  # e.g. "glasser:/g2.reviews", "web"
    retrieved_at: datetime
    cost_usd: float = 0.0


class Scored(BaseModel):
    value: str
    confidence: Confidence = Field(ge=0, le=1)
    why: str = ""


class Industry(Scored):
    naics: str = ""


class Persona(BaseModel):
    title: str
    seniority: Literal["c_level", "vp", "director", "manager", "ic"]
    confidence: Confidence = Field(ge=0, le=1)


class Expansion(BaseModel):
    segment: str
    rationale: str
    evidence: list[Citation] = Field(min_length=1)
    status: Literal["proposed", "accepted", "adjusted", "dismissed"] = "proposed"


class Intake(BaseModel):
    product: str
    description: str
    features: list[str] = []
    constraints: list[str] = []
    customers: list[str] = []
    pricing: str = ""


class ICP(BaseModel):
    industries: list[Industry]
    headcount_bands: list[Scored]
    revenue_bands: list[Scored]
    personas: list[Persona]
    triggers: list[Scored]
    expansions: list[Expansion] = []


class Signal(BaseModel):
    id: str
    kind: Literal["funding", "exec_hire", "job_post", "tech_change", "review_complaint",
                  "hiring_freeze", "non_target_region", "layoffs", "other"]
    summary: str
    negative: bool = False
    observed_on: str = ""  # ISO date from the source, if it gives one
    citation: Citation


class Company(BaseModel):
    id: str
    name: str
    domain: str
    hq: str = ""
    industry: str = ""
    headcount: str = ""
    fit_score: int = Field(ge=0, le=100)
    intent_score: int = Field(ge=0, le=100)
    tier: Tier
    signals: list[Signal] = []
    citations: list[Citation] = Field(min_length=1)  # spec: mandatory inline citation
    rejected_reason: str = ""  # set when a negative signal filters it out


class Person(BaseModel):
    id: str
    company_id: str
    name: str
    title: str
    seniority: str = ""
    email: str = ""
    email_status: EmailStatus = "unknown"
    mx_ok: bool | None = None
    linkedin_url: str = ""
    confidence: Confidence = Field(ge=0, le=1)
    past_employers: list[str] = []
    schools: list[str] = []
    citations: list[Citation] = Field(min_length=1)


class Competitor(BaseModel):
    name: str
    domain: str
    kind: Literal["direct", "indirect", "alternative"]
    positioning: str
    pricing_tiers: list[str] = []
    differentiators: list[str] = []
    citations: list[Citation] = Field(min_length=1)


class Draft(BaseModel):
    id: str
    person_id: str
    channel: Literal["email", "linkedin"]
    step: int = 1
    variant: str = "A"
    subject: str = ""
    body: str
    signal_ids: list[str] = Field(min_length=1)  # the signal(s) the copy cites
    status: DraftStatus = "pending"
    review_notes: list[str] = []


class Lead(BaseModel):
    company_id: str
    person_id: str = ""
    stage: Stage = "matched"
    owner: Actor = "ai"


class AuditEvent(BaseModel):
    at: datetime
    actor: Actor
    agent: str = ""  # planner / builder / reviewer / security / pipeline step
    action: str
    target: str = ""
    detail: str = ""
    tokens: int = 0
    cost_usd: float = 0.0


class Run(BaseModel):
    id: str
    created_at: datetime
    intake: Intake
    icp: ICP | None = None
    companies: list[Company] = []
    people: list[Person] = []
    competitors: list[Competitor] = []
    drafts: list[Draft] = []
    leads: list[Lead] = []
    audit: list[AuditEvent] = []

    def cost_usd(self) -> float:
        return round(sum(e.cost_usd for e in self.audit), 4)


def can_send(draft: Draft) -> bool:
    """The HITL gate: nothing leaves without a human approval."""
    return draft.status == "approved"
