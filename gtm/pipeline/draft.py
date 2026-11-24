"""Step 6: per contact, a 3-step email sequence (A/B on the first email) and a LinkedIn note.

Written by the model under Sellbird's writing rules (sellbird.email_style: word caps,
no dashes, no exclamation marks, no AI tells, one question). Each draft must cite at
least one real signal id of that contact's company; one that cites none is dropped
(the copy would make an unsupported claim). Rule breaks found by Sellbird's checker go
into review_notes for the reviewer. Every draft starts pending: only a rep approves.
Scraped text reaches the model inside <untrusted> fences (sellbird.untrusted).
"""

from __future__ import annotations

import json
import os

from gtm.contract import Company, Draft, Person, Run
from gtm.pipeline import llm, store
from gtm.pipeline.runner import event, log_event

BATCH = 4
EMAIL_STEPS = [(1, "A"), (1, "B"), (2, "A"), (3, "A")]


def sender_name() -> str:
    return os.environ.get("GTM_SENDER_NAME", "Sam")


def contact_block(person: Person, co: Company) -> dict:
    from sellbird.untrusted import fence

    usable = [s for s in co.signals if not s.negative and not s.id.endswith("_score")]
    return {
        "person_id": person.id,
        "first_name": person.name.split(" ")[0] if person.name else "",
        "title": person.title,
        "company": co.name,
        "company_facts": fence(f"{co.industry}; {co.headcount} staff; HQ {co.hq}. Site says: "
                               f"{co.citations[0].quote}", "company homepage"),
        "signals": [{"id": s.id, "kind": s.kind, "date": s.observed_on,
                     "fact": fence(f"{s.summary} | source quote: {s.citation.quote}", s.citation.provider or "web")}
                    for s in usable],
    }


def prompt(run: Run, contacts: list[dict]) -> str:
    from sellbird.email_style import BREAKUP_MAX_WORDS, FIRST_EMAIL_MAX_WORDS, FOLLOW_UP_MAX_WORDS
    from sellbird.untrusted import UNTRUSTED_RULE

    comp = [f"{c.name} ({c.kind}): {c.positioning}" for c in run.competitors[:5]]
    return f"""You write cold outreach for {run.intake.product}, sent by {sender_name()}.

PRODUCT: {run.intake.description}
WHY IT WINS: {run.intake.features}
COMPETITORS THE BUYER MAY USE: {comp}

{UNTRUSTED_RULE}

CONTACTS:
{json.dumps(contacts, indent=1, ensure_ascii=False)}

For EACH contact write:
- email step 1, variant A and variant B: two different openings, each built on one of THEIR signals
  (say the fact plainly, then what it likely costs a {{title}} like them, then one short question).
  Variant A leads with the strongest buying signal; variant B with a different signal or angle.
  At most {FIRST_EMAIL_MAX_WORDS} words.
- email step 2: a new angle (a competitor gap or a second signal). At most {FOLLOW_UP_MAX_WORDS} words.
- email step 3: a short breakup. At most {BREAKUP_MAX_WORDS} words.
- one LinkedIn connection note, under 300 characters, citing a signal.
Rules (Sellbird's): plain text, open with them (never "I" or "We"), no dash between words, no exclamation
marks, no lists, at most one question, subject 2-5 words, no sign-off (it is added), use only facts from
the signals, never invent numbers, customers or claims. Every draft lists the signal ids it relies on.
Return JSON: {{"<person_id>": {{"email": [{{"step": 1, "variant": "A", "subject": str, "body": str,
  "signal_ids": [str]}}, ...4 items for 1A, 1B, 2A, 3A], "linkedin": {{"body": str, "signal_ids": [str]}}}}}}"""


def build_drafts(person: Person, co: Company, reply: dict) -> tuple[list[Draft], list[str]]:
    from sellbird.email_style import style_problems, tidy, with_sign_off

    valid = {s.id for s in co.signals if not s.negative}
    names = [n for n in (person.name, *person.name.split(" "), co.name) if n]
    drafts, dropped = [], []
    items = [("email", e) for e in (reply.get("email") or []) if isinstance(e, dict)]
    if isinstance(reply.get("linkedin"), dict):
        items.append(("linkedin", {**reply["linkedin"], "step": 1, "variant": "A", "subject": ""}))
    for channel, d in items:
        step, variant = int(d.get("step") or 1), str(d.get("variant") or "A")[:2]
        ids = [i for i in (d.get("signal_ids") or []) if i in valid]
        body = tidy(str(d.get("body") or ""))
        did = f"d_{person.id}_{channel}_{step}{variant}"
        if not ids or not body:
            dropped.append(f"{did}: cites no real signal" if body else f"{did}: empty")
            continue
        subject = tidy(str(d.get("subject") or ""))
        notes = []
        if channel == "email":
            notes = [f"style: {p}" for p in style_problems(subject, body, kind="cold", step=step, names=names)]
            body = with_sign_off(body, sender_name())
        elif len(body) > 300:
            notes.append(f"style: LinkedIn note is {len(body)} characters; keep it under 300")
        drafts.append(Draft(id=did, person_id=person.id, channel=channel, step=step, variant=variant,
                            subject=subject, body=body, signal_ids=ids, review_notes=notes))
    return drafts, dropped


def targets(run: Run) -> list[tuple[Person, Company]]:
    cos = {c.id: c for c in run.companies if not c.rejected_reason}
    done = {d.person_id for d in run.drafts}
    return [(p, cos[p.company_id]) for p in run.people
            if p.company_id in cos and p.id not in done and p.email_status != "invalid"]


def run_step(run_id: str) -> None:
    run = store.load(run_id)
    todo = targets(run)
    made = dropped = 0
    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        reply, usage = llm.ask_json(prompt(run, [contact_block(p, c) for p, c in batch]), agent="draft",
                                    task=f"sequences-{i // BATCH}")
        log_event(run_id, llm.model_event("draft", "sequences", usage, target=run_id,
                                          detail=f"drafts for {len(batch)} contacts"))
        new = []
        for p, c in batch:
            drafts, lost = build_drafts(p, c, (reply or {}).get(p.id) or {})
            new += drafts
            dropped += len(lost)
            for why in lost:
                log_event(run_id, event("draft_dropped", agent="draft", target=p.id, detail=why))

        def add(r: Run, new=new):
            have = {d.id for d in r.drafts}
            r.drafts.extend(d for d in new if d.id not in have)
        store.update(run_id, add)
        made += len(new)
    log_event(run_id, event("drafted", agent="draft", target=run_id,
                            detail=f"{made} drafts pending review for {len(todo)} contacts; {dropped} dropped"))
