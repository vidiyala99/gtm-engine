"""Drive the BAND room from a terminal.

python -m gtm.band.cli smoke                 open the pooled room, add the cast, post one hello to the rep
python -m gtm.band.cli review RUN DRAFT      run the four-agent review on one draft
python -m gtm.band.cli wait RUN DRAFT [SEC]  poll BAND for the rep's verdict (live mode)
python -m gtm.band.cli feed                  print the feed with tokens and cumulative cost

GTM_BAND_MODE in .env picks mock or live.
"""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from gtm.band.model import SellbirdModel  # noqa: E402
from gtm.band.room import ReviewRoom  # noqa: E402


async def main(argv: list[str]) -> int:
    room = ReviewRoom(SellbirdModel())
    cmd = argv[0] if argv else "feed"
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
