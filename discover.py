"""
DISCOVERY
Finds new project candidates from confirmed-free, no-card-needed sources.
"""

import os
import requests

CMC_LISTINGS = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
DEFILLAMA_PROTOCOLS = "https://api.llama.fi/protocols"


def get_cmc_new_candidates(errors):
    candidates = []
    api_key = os.environ.get("COINMARKETCAP_API_KEY")
    if not api_key:
        errors.append("COINMARKETCAP_API_KEY is not set — add it as a GitHub secret.")
        return candidates

    try:
        resp = requests.get(
            CMC_LISTINGS,
            headers={"X-CMC_PRO_API_KEY": api_key, "Accept": "application/json"},
            params={"sort": "date_added", "sort_dir": "desc", "limit": 50},
            timeout=20,
        )
        if resp.status_code != 200:
            errors.append(f"CoinMarketCap returned status {resp.status_code}: {resp.text[:200]}")
            return candidates
        data = resp.json().get("data", [])
        for coin in data:
            candidates.append({
                "source": "cmc_new",
                "id": f"cmc-{coin.get('id')}",
                "name": coin.get("name"),
                "symbol": coin.get("symbol"),
                "date_added": coin.get("date_added"),
                "market_cap": (coin.get("quote", {}).get("USD", {}) or {}).get("market_cap"),
                "platform": (coin.get("platform") or {}).get("name"),
                "contract_address": (coin.get("platform") or {}).get("token_address"),
            })
    except Exception as e:
        errors.append(f"CoinMarketCap fetch failed: {e}")
        print(f"[discover] CoinMarketCap fetch failed: {e}")
    return candidates


def get_defillama_new_protocol_candidates(errors, known_protocol_ids):
    candidates = []
    try:
        resp = requests.get(DEFILLAMA_PROTOCOLS, timeout=20)
        if resp.status_code != 200:
            errors.append(f"DefiLlama returned status {resp.status_code}: {resp.text[:200]}")
            return candidates, known_protocol_ids
        data = resp.json()
        current_ids = set()
        for protocol in data:
            pid = protocol.get("slug") or protocol.get("id")
            if not pid:
                continue
            current_ids.add(pid)
            if pid not in known_protocol_ids:
                candidates.append({
                    "source": "defillama_protocol",
                    "id": f"defillama-protocol-{pid}",
                    "name": protocol.get("name"),
                    "chains": protocol.get("chains", []),
                    "tvl": protocol.get("tvl"),
                    "url": protocol.get("url"),
                })
        return candidates, list(current_ids)
    except Exception as e:
        errors.append(f"DefiLlama fetch failed: {e}")
        print(f"[discover] DefiLlama fetch failed: {e}")
        return candidates, known_protocol_ids


def discover_all(known_protocol_ids=None):
    errors = []
    candidates = []
    candidates.extend(get_cmc_new_candidates(errors))
    defillama_candidates, updated_known_ids = get_defillama_new_protocol_candidates(
        errors, set(known_protocol_ids or [])
    )
    candidates.extend(defillama_candidates)
    return candidates, errors, updated_known_ids
