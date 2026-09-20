"""
DISCOVERY
Finds new project candidates from legit, free, no-card-needed sources.
"""

import requests

COINGECKO_NEW = "https://api.coingecko.com/api/v3/coins/list/new"
DEFILLAMA_RAISES = "https://api.llama.fi/raises"


def get_coingecko_candidates(errors):
    candidates = []
    try:
        resp = requests.get(COINGECKO_NEW, timeout=20)
        if resp.status_code != 200:
            errors.append(f"CoinGecko returned status {resp.status_code}: {resp.text[:200]}")
            return candidates
        for coin in resp.json():
            candidates.append({
                "source": "coingecko",
                "id": coin.get("id"),
                "name": coin.get("name"),
                "symbol": coin.get("symbol"),
                "activated_at": coin.get("activated_at"),
            })
    except Exception as e:
        errors.append(f"CoinGecko fetch failed: {e}")
        print(f"[discover] CoinGecko fetch failed: {e}")
    return candidates


def get_defillama_raise_candidates(errors):
    candidates = []
    try:
        resp = requests.get(DEFILLAMA_RAISES, timeout=20)
        if resp.status_code != 200:
            errors.append(f"DefiLlama returned status {resp.status_code}: {resp.text[:200]}")
            return candidates
        data = resp.json().get("raises", [])
        for raise_ in data:
            candidates.append({
                "source": "defillama_raise",
                "id": f"defillama-{raise_.get('name')}".lower().replace(" ", "-"),
                "name": raise_.get("name"),
                "amount_usd": raise_.get("amount"),
                "date": raise_.get("date"),
                "chains": raise_.get("chains", []),
                "investors": raise_.get("leadInvestors", []) + raise_.get("otherInvestors", []),
            })
    except Exception as e:
        errors.append(f"DefiLlama fetch failed: {e}")
        print(f"[discover] DefiLlama fetch failed: {e}")
    return candidates


def discover_all():
    errors = []
    candidates = []
    candidates.extend(get_coingecko_candidates(errors))
    candidates.extend(get_defillama_raise_candidates(errors))
    return candidates, errors
