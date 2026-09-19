"""
VETTING (the automated DYOR)
"""

import requests
import config


def check_github_activity(project_name):
    try:
        resp = requests.get(
            "https://api.github.com/search/repositories",
            params={"q": project_name, "sort": "updated"},
            timeout=15,
        )
        if resp.status_code != 200:
            return {"found": False, "stars": 0}
        items = resp.json().get("items", [])
        if not items:
            return {"found": False, "stars": 0}
        top = items[0]
        return {"found": True, "stars": top.get("stargazers_count", 0), "url": top.get("html_url")}
    except Exception as e:
        print(f"[vet] GitHub check failed for {project_name}: {e}")
        return {"found": False, "stars": 0}


def vet_coingecko(candidate):
    reasons = ["Listed on CoinGecko (passed their listing review)"]
    status = "pending"
    chains = []

    try:
        resp = requests.get(
            f"https://api.coingecko.com/api/v3/coins/{candidate['id']}",
            params={"localization": "false", "tickers": "false", "community_data": "false", "developer_data": "false"},
            timeout=20,
        )
        if resp.status_code == 200:
            data = resp.json()
            platforms = data.get("platforms", {})
            chains = [c for c in platforms.keys() if c]
            market_cap = (data.get("market_data") or {}).get("market_cap", {}).get("usd")
            if market_cap:
                status = "live"
                reasons.append(f"Has real trading market cap (~${market_cap:,.0f})")
    except Exception as e:
        print(f"[vet] CoinGecko detail check failed: {e}")

    return {
        "passed": True,
        "status": status,
        "chains": chains or ["unknown"],
        "reasons": reasons,
    }


def vet_defillama_raise(candidate):
    reasons = []
    passed = True

    amount = candidate.get("amount_usd") or 0
    if amount and amount >= config.MIN_FUNDING_USD:
        reasons.append(f"Raised ~${amount:,.0f} in funding")
    investors = candidate.get("investors") or []
    if investors:
        reasons.append(f"Backed by: {', '.join(investors[:3])}")

    gh = check_github_activity(candidate["name"])
    if gh["found"] and gh["stars"] >= config.MIN_GITHUB_STARS:
        reasons.append(f"Active GitHub repo ({gh['stars']} stars)")
    elif config.REQUIRE_GITHUB_ACTIVITY:
        passed = False
        reasons.append("No qualifying GitHub activity found")

    if not reasons:
        passed = False
        reasons.append("No funding or GitHub signal found")

    return {
        "passed": passed,
        "status": "pending",
        "chains": candidate.get("chains") or ["unknown"],
        "reasons": reasons,
    }


def vet_candidate(candidate):
    if candidate["source"] == "coingecko":
        return vet_coingecko(candidate)
    elif candidate["source"] == "defillama_raise":
        return vet_defillama_raise(candidate)
    return {"passed": False, "status": "pending", "chains": [], "reasons": ["Unknown source"]}


def recheck_live_status(entry):
    if entry["source"] != "coingecko":
        try:
            resp = requests.get(
                "https://api.coingecko.com/api/v3/search",
                params={"query": entry["name"]},
                timeout=15,
            )
            if resp.status_code == 200:
                coins = resp.json().get("coins", [])
                if coins:
                    return {"status": "live", "chains": entry.get("chains", []), "matched_id": coins[0]["id"]}
        except Exception as e:
            print(f"[vet] Live re-check failed for {entry['name']}: {e}")
        return {"status": entry.get("status", "pending"), "chains": entry.get("chains", [])}
    else:
        result = vet_coingecko(entry)
        return {"status": result["status"], "chains": result["chains"]}
