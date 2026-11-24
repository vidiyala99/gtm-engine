"""Drive the BAND room from a terminal.

python -m gtm.band.cli smoke                 open the pooled room, add the cast, post one hello to the rep
python -m gtm.band.cli review RUN DRAFT      run the four-agent review on one draft
python -m gtm.band.cli wait RUN DRAFT [SEC]  poll BAND for the rep's verdict (live mode)
python -m gtm.band.cli feed                  print the feed with tokens and cumulative cost
python -m gtm.band.cli reset DRAFT...        fixture only: set drafts back to pending so they can be reviewed again

GTM_BAND_MODE in .env picks mock or live; `--mode live|mock` before the command overrides it for one run.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from gtm.band.model import SellbirdModel  # noqa: E402
from gtm.band.room import ReviewRoom  # noqa: E402


def reset_fixture(draft_ids: list[str]) -> list[str]:
    from gtm.graph.runs import update_run

    def change(run) -> None:
        for d in run.drafts:
            if d.id in draft_ids:
                d.status, d.review_notes = "pending", []

    run = update_run("fixture", change)
    from gtm.band.room import STATE_DIR
    state_file = STATE_DIR / "state.json"
    if state_file.exists():  # forget any approval request still open for these drafts
        st = json.loads(state_file.read_text(encoding="utf-8"))
        drop = {f"fixture/{d}" for d in draft_ids}
        st["awaiting"] = {k: v for k, v in st.get("awaiting", {}).items() if k not in drop}
        state_file.write_text(json.dumps(st))
    return [f"{d.id}={d.status}" for d in run.drafts]


async def main(argv: list[str]) -> int:
    if argv[:1] == ["--mode"] and len(argv) > 1:
        os.environ["GTM_BAND_MODE"] = argv[1]
        argv = argv[2:]
    cmd = argv[0] if argv else "feed"
    if cmd == "reset":
        print(" ".join(reset_fixture(argv[1:])))
        return 0
    room = ReviewRoom(SellbirdModel())
    if cmd == "smoke":
        rid = await room.room()
        msg = await asyncio.to_thread(room.band.send, rid, "planner",
                                      "GTM Engine review room is open. Drafts will come here for your approval.",
                                      ["rep"])
        print(f"mode={room.band.mode} room={rid} members={room.band.participants(rid)} sent={msg.id}")
    elif cmd == "review":
        print(json.dumps(asdict(await room.review(argv[1], argv[2])), indent=1))
    elif cmd == "wait":
        key, deadline = f"{argv[1]}/{argv[2]}", float(argv[3]) if len(argv) > 3 else 600
        waited = 0.0
        while key in room.awaiting and waited < deadline:
            for o in await room.poll_rep():
                print(json.dumps(asdict(o)))
            await asyncio.sleep(5)
            waited += 5
        print("still waiting" if key in room.awaiting else "done")
    elif cmd == "feed":
        for item in room.feed_since(0)["items"]:
            print(f"#{item['seq']} {item['sender']} -> @{','.join(item['to'])} [{item['kind']}] "
                  f"tok={item['tokens']} cum=${item['cumulative_cost_usd']:.4f}: {item['text'][:160]}")
        print(room.totals())
    else:
        print(__doc__)
        return 2
    for line in room.band.console:
        print("  band:", line[:160])
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
