"""
DISCOVERY
Finds new project candidates from legit, free, no-card-needed sources.
"""

import requests

COINGECKO_NEW = "https://api.coingecko.com/api/v3/coins/list/new"
DEFILLAMA_RAISES = "https://api.llama.fi/raises"


def get_coingecko_candidates():
    candidates = []
    try:
        resp = requests.get(COINGECKO_NEW, timeout=20)
        resp.raise_for_status()
        for coin in resp.json():
            candidates.append({
                "source": "coingecko",
                "id": coin.get("id"),
                "name": coin.get("name"),
                "symbol": coin.get("symbol"),
                "activated_at": coin.get("activated_at"),
            })
    except Exception as e:
        print(f"[discover] CoinGecko fetch failed: {e}")
    return candidates


def get_defillama_raise_candidates():
    candidates = []
    try:
        resp = requests.get(DEFILLAMA_RAISES, timeout=20)
        resp.raise_for_status()
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
        print(f"[discover] DefiLlama fetch failed: {e}")
    return candidates


def discover_all():
    candidates = []
    candidates.extend(get_coingecko_candidates())
    candidates.extend(get_defillama_raise_candidates())
    return candidates
