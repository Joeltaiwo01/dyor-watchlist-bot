"""
WATCHLIST STORAGE
This is the bot's memory.
"""

import json
import os
import config


def load():
    if not os.path.exists(config.WATCHLIST_FILE):
        return {}
    with open(config.WATCHLIST_FILE, "r") as f:
        return json.load(f)


def save(watchlist):
    os.makedirs(os.path.dirname(config.WATCHLIST_FILE), exist_ok=True)
    with open(config.WATCHLIST_FILE, "w") as f:
        json.dump(watchlist, f, indent=2)


def add(watchlist, candidate, vet_result, first_seen):
    watchlist[candidate["id"]] = {
        "name": candidate["name"],
        "source": candidate["source"],
        "status": vet_result["status"],
        "chains": vet_result["chains"],
        "reasons": vet_result["reasons"],
        "first_seen": first_seen,
        "last_checked": first_seen,
        "notified_live": False,
    }
    return watchlist
