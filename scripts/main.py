"""
MAIN
Runs on a schedule via GitHub Actions.
"""

import sys
import os
import json
from datetime import datetime, timezone

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import watchlist as wl
from discover import discover_all
from vet import vet_candidate, recheck_live_status
import notify

KNOWN_PROTOCOLS_FILE = "data/known_protocols.json"


def load_known_protocol_ids():
    if os.path.exists(KNOWN_PROTOCOLS_FILE):
        with open(KNOWN_PROTOCOLS_FILE, "r") as f:
            return json.load(f)
    return []


def save_known_protocol_ids(ids):
    os.makedirs(os.path.dirname(KNOWN_PROTOCOLS_FILE), exist_ok=True)
    with open(KNOWN_PROTOCOLS_FILE, "w") as f:
        json.dump(ids, f)


def write_status_report(now, discovered_count, discover_errors, new_count, live_count, total_tracked):
    lines = [
        f"# DYOR Bot Status",
        f"",
        f"Last run: {now}",
        f"",
        f"- Candidates discovered this run: {discovered_count}",
        f"- New projects added to watchlist: {new_count}",
        f"- Projects that flipped to LIVE: {live_count}",
        f"- Total projects being tracked: {total_tracked}",
        f"",
    ]
    if discover_errors:
        lines.append("## Errors while discovering (this is likely why nothing is found)")
        for err in discover_errors:
            lines.append(f"- {err}")
    else:
        lines.append("No errors — discovery ran cleanly. Zero results just means nothing new passed the filter this run.")

    with open("status.md", "w") as f:
        f.write("\n".join(lines))


def run():
    now = datetime.now(timezone.utc).isoformat()
    wlist = wl.load()
    known_protocol_ids = load_known_protocol_ids()

    candidates, discover_errors, updated_known_ids = discover_all(known_protocol_ids)
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
    save_known_protocol_ids(updated_known_ids)
    write_status_report(now, len(candidates), discover_errors, new_count, live_count, len(wlist))
    print(f"[main] Watchlist saved: {len(wlist)} total projects tracked")


if __name__ == "__main__":
    run()
