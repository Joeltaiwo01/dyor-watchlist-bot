"""
MAIN
This is the one script GitHub Actions runs on a timer.
"""

import sys
import os
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import watchlist as wl
from discover import discover_all
from vet import vet_candidate, recheck_live_status
import notify


def run():
    now = datetime.now(timezone.utc).isoformat()
    wlist = wl.load()

    candidates = discover_all()
    print(f"[main] Discovered {len(candidates)} raw candidates")

    new_count = 0
    for candidate in candidates:
        cid = candidate.get("id")
        if not cid or cid in wlist:
            continue

        result = vet_candidate(candidate)
        if not result["passed"]:
            continue

        wlist = wl.add(wlist, candidate, result, first_seen=now)
        notify.notify_new_watchlist_candidate(wlist[cid])
        new_count += 1

    print(f"[main] Added {new_count} new projects to watchlist")

    live_count = 0
    for cid, entry in wlist.items():
        if entry.get("status") == "live" and entry.get("notified_live"):
            continue

        check = recheck_live_status({**entry, "id": cid, "name": entry["name"], "source": entry["source"]})
        entry["last_checked"] = now
        if check["status"] == "live" and entry["status"] != "live":
            entry["status"] = "live"
            entry["chains"] = check.get("chains") or entry["chains"]
            notify.notify_went_live(entry)
            entry["notified_live"] = True
            live_count += 1
        elif check.get("chains"):
            entry["chains"] = check["chains"]

    print(f"[main] {live_count} projects flipped to LIVE this run")

    wl.save(wlist)
    print(f"[main] Watchlist saved: {len(wlist)} total projects tracked")


if __name__ == "__main__":
    run()
