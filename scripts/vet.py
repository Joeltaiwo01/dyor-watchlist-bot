"""
VETTING (the automated DYOR)
"""

import requests


def vet_cmc_new(candidate):
    reasons = ["Listed on CoinMarketCap (recently added, real market data)"]
    status = "pending"
    chains = [candidate.get("platform")] if candidate.get("platform") else ["unknown"]
    contract_address = candidate.get("contract_address")

    market_cap = candidate.get("market_cap")
    if market_cap:
        status = "live"
        reasons.append(f"Has real trading market cap (~${market_cap:,.0f})")

    if contract_address:
        reasons.append(f"Contract: {contract_address}")
    else:
        reasons.append("No contract address available (may be a native/L1 coin, not a token)")

    return {"passed": True, "status": status, "chains": chains, "reasons": reasons, "contract_address": contract_address}


def vet_defillama_protocol(candidate):
    reasons = []
    passed = True
    tvl = candidate.get("tvl") or 0
    if tvl and tvl > 0:
        reasons.append(f"Real on-chain TVL (~${tvl:,.0f}) on DefiLlama — an operating product, not just a claim")
    else:
        passed = False
        reasons.append("No measurable TVL — likely not yet operating")

    return {"passed": passed, "status": "live", "chains": candidate.get("chains") or ["unknown"], "reasons": reasons, "contract_address": None}


def vet_candidate(candidate):
    if candidate["source"] == "cmc_new":
        return vet_cmc_new(candidate)
    elif candidate["source"] == "defillama_protocol":
        return vet_defillama_protocol(candidate)
    return {"passed": False, "status": "pending", "chains": [], "reasons": ["Unknown source"]}


def recheck_live_status(entry):
    return {"status": entry.get("status", "pending"), "chains": entry.get("chains", [])}
