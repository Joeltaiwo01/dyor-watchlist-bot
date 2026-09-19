"""
NOTIFY
Sends a push notification straight to your phone via ntfy.
"""

import requests
import config


def send(title, message, priority="default", tags=None):
    try:
        requests.post(
            config.NTFY_URL,
            data=message.encode("utf-8"),
            headers={
                "Title": title,
                "Priority": priority,
                "Tags": ",".join(tags or []),
            },
            timeout=15,
        )
    except Exception as e:
        print(f"[notify] Failed to send notification: {e}")


def notify_new_watchlist_candidate(entry):
    chains = ", ".join(entry["chains"]) if entry["chains"] else "unknown chain"
    reasons = " • ".join(entry["reasons"])
    send(
        title=f"🔎 New project passed DYOR: {entry['name']}",
        message=f"Chain: {chains}\nWhy it passed: {reasons}\nStatus: {entry['status']} — added to watchlist.",
        tags=["mag", "eyes"],
    )


def notify_went_live(entry):
    chains = ", ".join(entry["chains"]) if entry["chains"] else "unknown chain"
    send(
        title=f"🚀 LIVE now: {entry['name']}",
        message=f"It's gone live on: {chains}\nWas tracked since: {entry['first_seen']}",
        priority="high",
        tags=["rocket", "tada"],
    )
