"""
MULTI-CHAIN INSTANT LISTENER
Only alerts on launches matching a real project already on your DYOR
watchlist. Everything else is checked and logged silently — never sent
as a notification.
"""

import asyncio
import json
import os
import time
import requests
import websockets
from web3 import Web3

NTFY_TOPIC = "Jay_dyor_alerts-8x2f"
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPIC}"

MAX_RUNTIME_SECONDS = 5 * 60 * 60 + 45 * 60

CHAINS = {
    "ethereum": {"ws": "wss://ethereum-rpc.publicnode.com", "http": "https://ethereum-rpc.publicnode.com", "factory": "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f", "explorer_api": "https://api.etherscan.io/api", "goplus_chain_id": "1", "explorer_tx": "https://etherscan.io/tx/"},
    "base": {"ws": "wss://base-rpc.publicnode.com", "http": "https://base-rpc.publicnode.com", "factory": "0x8909Dc15e40173Ff4699343b6eB8132c65e18eC6", "explorer_api": "https://api.basescan.org/api", "goplus_chain_id": "8453", "explorer_tx": "https://basescan.org/tx/"},
    "bsc": {"ws": "wss://bsc-rpc.publicnode.com", "http": "https://bsc-rpc.publicnode.com", "factory": "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73", "explorer_api": "https://api.bscscan.com/api", "goplus_chain_id": "56", "explorer_tx": "https://bscscan.com/tx/"},
}

ROBINHOOD_HTTP = "https://rpc.mainnet.chain.robinhood.com"
ROBINHOOD_PONS_FACTORY = "0x7eD598BcEf8bd9Edd8C97A195C6d13f40801EC7e"
ROBINHOOD_EXPLORER_TX = "https://robinhoodchain.blockscout.com/tx/"

PUMPPORTAL_WS = "wss://pumpportal.fun/api/data"
RUGCHECK_REPORT = "https://api.rugcheck.xyz/v1/tokens/{mint}/report"

WATCHLIST_FILE = "data/watchlist.json"
SEEN_SCAM_BYTECODE_FILE = "data/seen_scam_bytecode.json"
ALERT_LOG_FILE = "data/instant_alerts_log.json"

PAIR_CREATED_TOPIC = Web3.keccak(text="PairCreated(address,address,address,uint256)").hex()


def send_ntfy(title, message, priority="high", tags=None):
    try:
        requests.post(NTFY_URL, data=message.encode("utf-8"), headers={"Title": title, "Priority": priority, "Tags": ",".join(tags or [])}, timeout=15)
    except Exception as e:
        print(f"[notify] Failed: {e}")


def load_watchlist_names():
    if not os.path.exists(WATCHLIST_FILE):
        return set()
    try:
        with open(WATCHLIST_FILE, "r") as f:
            data = json.load(f)
        return {v.get("name", "").strip().lower() for v in data.values() if v.get("name")}
    except Exception:
        return set()


def load_seen_scam_bytecode():
    if os.path.exists(SEEN_SCAM_BYTECODE_FILE):
        with open(SEEN_SCAM_BYTECODE_FILE, "r") as f:
            return json.load(f)
    return []


def save_seen_scam_bytecode(hashes):
    os.makedirs(os.path.dirname(SEEN_SCAM_BYTECODE_FILE), exist_ok=True)
    with open(SEEN_SCAM_BYTECODE_FILE, "w") as f:
        json.dump(hashes, f)


def log_alert(entry):
    os.makedirs(os.path.dirname(ALERT_LOG_FILE), exist_ok=True)
    log = []
    if os.path.exists(ALERT_LOG_FILE):
        with open(ALERT_LOG_FILE, "r") as f:
            try:
                log = json.load(f)
            except json.JSONDecodeError:
                log = []
    log.append(entry)
    with open(ALERT_LOG_FILE, "w") as f:
        json.dump(log[-500:], f)


def check_goplus(chain_id, address):
    try:
        resp = requests.get(f"https://api.gopluslabs.io/api/v1/token_security/{chain_id}", params={"contract_addresses": address}, timeout=15)
        if resp.status_code != 200:
            return None
        result = resp.json().get("result", {}).get(address.lower(), {})
        if not result:
            return None
        if result.get("is_honeypot") == "1" or result.get("cannot_sell_all") == "1" or result.get("hidden_owner") == "1":
            return False
        return True
    except Exception:
        return None


def check_honeypot_is(chain_id, address):
    try:
        resp = requests.get("https://api.honeypot.is/v2/IsHoneypot", params={"address": address, "chainID": chain_id}, timeout=15)
        if resp.status_code != 200:
            return None
        return not resp.json().get("honeypotResult", {}).get("isHoneypot", False)
    except Exception:
        return None


def get_deployer_and_history(chain_key, token_address, explorer_api):
    api_key = os.environ.get(f"{chain_key.upper()}_EXPLORER_API_KEY", "")
    try:
        resp = requests.get(explorer_api, params={"module": "contract", "action": "getcontractcreation", "contractaddresses": token_address, "apikey": api_key}, timeout=15)
        result = resp.json().get("result")
        if not result or not isinstance(result, list) or not result[0].get("contractCreator"):
            return None, None, None
        deployer = result[0]["contractCreator"]
        tx_resp = requests.get(explorer_api, params={"module": "account", "action": "txlist", "address": deployer, "sort": "asc", "apikey": api_key}, timeout=15)
        txs = tx_resp.json().get("result", [])
        contract_creations = [t for t in txs if t.get("to") == "" or t.get("to") is None]
        first_funding_from = txs[0].get("from") if txs else None
        return deployer, len(contract_creations), first_funding_from
    except Exception as e:
        print(f"[history] Check failed for {token_address} on {chain_key}: {e}")
        return None, None, None


def get_bytecode_hash(chain_http, token_address):
    try:
        resp = requests.post(chain_http, json={"jsonrpc": "2.0", "id": 1, "method": "eth_getCode", "params": [token_address, "latest"]}, timeout=15)
        code = resp.json().get("result", "")
        if not code or code == "0x":
            return None
        return Web3.keccak(hexstr=code).hex()
    except Exception:
        return None


def get_token_name_symbol(chain_http, token_address):
    name, symbol = None, None
    try:
        for selector, label in [("0x06fdde03", "name"), ("0x95d89b41", "symbol")]:
            resp = requests.post(chain_http, json={"jsonrpc": "2.0", "id": 1, "method": "eth_call", "params": [{"to": token_address, "data": selector}, "latest"]}, timeout=10)
            raw = resp.json().get("result", "")
            if raw and raw != "0x":
                try:
                    hex_data = raw[2:]
                    length = int(hex_data[64:128], 16)
                    text_hex = hex_data[128:128 + length * 2]
                    decoded = bytes.fromhex(text_hex).decode("utf-8", errors="ignore").strip()
                except Exception:
                    decoded = None
                if label == "name":
                    name = decoded
                else:
                    symbol = decoded
    except Exception:
        pass
    return name, symbol


def build_alert_and_check(chain_key, chain_cfg, token_address, watchlist_names, seen_scam_hashes):
    reasons = []
    passed = True
    matched_watchlist = False

    token_name, token_symbol = get_token_name_symbol(chain_cfg["http"], token_address)
    if token_name and token_name.strip().lower() in watchlist_names:
        matched_watchlist = True
        reasons.append(f"✅ MATCHES your DYOR watchlist — this is a project you already vetted as real: \"{token_name}\"")

    goplus_ok = check_goplus(chain_cfg["goplus_chain_id"], token_address)
    honeypot_ok = check_honeypot_is(chain_cfg["goplus_chain_id"], token_address)
    if goplus_ok is False or honeypot_ok is False:
        return None

    if goplus_ok and honeypot_ok:
        reasons.append("Passed GoPlus + honeypot.is safety checks")
    else:
        reasons.append("Safety check inconclusive — verify manually")

    deployer, prior_count, funding_from = get_deployer_and_history(chain_key, token_address, chain_cfg["explorer_api"])
    if deployer:
        if prior_count and prior_count > 3:
            reasons.append(f"⚠️ Deployer wallet has created {prior_count} contracts before — check its history")
        else:
            reasons.append(f"Deployer: {deployer[:10]}... (limited prior contract history)")

    bytecode_hash = get_bytecode_hash(chain_cfg["http"], token_address)
    if bytecode_hash and bytecode_hash in seen_scam_hashes:
        reasons.append("🚨 Contract code matches a previously flagged scam template")
        passed = False

    return {"passed": passed, "reasons": reasons, "deployer": deployer, "matched_watchlist": matched_watchlist, "token_name": token_name}


async def listen_evm_chain(chain_key, chain_cfg, start_time, watchlist_names, seen_scam_hashes):
    print(f"[{chain_key}] Connecting...")
    try:
        async with websockets.connect(chain_cfg["ws"], ping_interval=20, ping_timeout=20) as ws:
            sub_request = {"jsonrpc": "2.0", "id": 1, "method": "eth_subscribe", "params": ["logs", {"address": chain_cfg["factory"], "topics": [PAIR_CREATED_TOPIC]}]}
            await ws.send(json.dumps(sub_request))
            print(f"[{chain_key}] Subscribed to PairCreated events.")

            while time.time() - start_time < MAX_RUNTIME_SECONDS:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=60)
                except asyncio.TimeoutError:
                    continue
                try:
                    msg = json.loads(raw)
                    log = msg.get("params", {}).get("result", {})
                    topics = log.get("topics", [])
                    tx_hash = log.get("transactionHash")
                    if len(topics) < 3:
                        continue
                    token0 = "0x" + topics[1][-40:]
                    token1 = "0x" + topics[2][-40:]
                except Exception:
                    continue

                for token_address in (token0, token1):
                    check = build_alert_and_check(chain_key, chain_cfg, token_address, watchlist_names, seen_scam_hashes)
                    if check is None or not check["passed"]:
                        continue

                    if not check["matched_watchlist"]:
                        log_alert({"chain": chain_key, "address": token_address, "time": time.time(), "reasons": check["reasons"], "matched_watchlist": False, "alerted": False})
                        continue

                    reasons_text = "\n".join(f"• {r}" for r in check["reasons"])
                    message = f"Contract: {token_address}\nChain: {chain_key.capitalize()}\n{reasons_text}\n{chain_cfg['explorer_tx']}{tx_hash}"
                    title = f"🎯 REAL PROJECT LAUNCHED: {check['token_name']}"
                    send_ntfy(title, message, tags=["star", "rotating_light"])
                    log_alert({"chain": chain_key, "address": token_address, "time": time.time(), "reasons": check["reasons"], "matched_watchlist": True, "alerted": True})
    except Exception as e:
        print(f"[{chain_key}] Connection error: {e}")


async def listen_solana(start_time, watchlist_names):
    print("[solana] Connecting to Pump.fun...")
    try:
        async with websockets.connect(PUMPPORTAL_WS, ping_interval=20, ping_timeout=20) as ws:
            await ws.send(json.dumps({"method": "subscribeNewToken"}))
            print("[solana] Subscribed.")

            while time.time() - start_time < MAX_RUNTIME_SECONDS:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=60)
                except asyncio.TimeoutError:
                    continue
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                mint = event.get("mint")
                name = event.get("name", "Unknown")
                symbol = event.get("symbol", "")
                if not mint:
                    continue

                if not name or name.strip().lower() not in watchlist_names:
                    log_alert({"chain": "solana", "address": mint, "time": time.time(), "matched_watchlist": False, "alerted": False})
                    continue

                try:
                    resp = requests.get(RUGCHECK_REPORT.format(mint=mint), timeout=10)
                    if resp.status_code == 200:
                        data = resp.json()
                        risks = data.get("risks", [])
                        high = [r.get("name") for r in risks if r.get("level") == "danger"]
                        if high:
                            continue
                        verdict = f"RugCheck score: {data.get('score')}"
                    else:
                        verdict = "Safety check unavailable — verify manually"
                except Exception:
                    verdict = "Safety check unavailable — verify manually"

                message = f"Contract: {mint}\nChain: Solana (Pump.fun)\n{verdict}\nhttps://pump.fun/{mint}"
                send_ntfy(f"🎯 REAL PROJECT LAUNCHED: {name} ({symbol})", message, tags=["star", "rotating_light"])
                log_alert({"chain": "solana", "address": mint, "time": time.time(), "reasons": [verdict], "matched_watchlist": True, "alerted": True})
    except Exception as e:
        print(f"[solana] Connection error: {e}")


async def listen_robinhood(start_time, watchlist_names, seen_scam_hashes):
    print("[robinhood] Starting polling loop...")
    last_block_checked = None

    while time.time() - start_time < MAX_RUNTIME_SECONDS:
        try:
            block_resp = requests.post(ROBINHOOD_HTTP, json={"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []}, timeout=15)
            latest_block = int(block_resp.json()["result"], 16)
            if last_block_checked is None:
                last_block_checked = latest_block - 5
            if latest_block > last_block_checked:
                logs_resp = requests.post(ROBINHOOD_HTTP, json={"jsonrpc": "2.0", "id": 1, "method": "eth_getLogs", "params": [{"fromBlock": hex(last_block_checked + 1), "toBlock": hex(latest_block), "address": ROBINHOOD_PONS_FACTORY}]}, timeout=20)
                logs = logs_resp.json().get("result", [])
                for log in logs:
                    tx_hash = log.get("transactionHash")
                    log_alert({"chain": "robinhood", "tx": tx_hash, "time": time.time(), "matched_watchlist": False, "alerted": False})
                last_block_checked = latest_block
        except Exception as e:
            print(f"[robinhood] Poll error: {e}")
        await asyncio.sleep(30)


async def main():
    start_time = time.time()
    watchlist_names = load_watchlist_names()
    seen_scam_hashes = load_seen_scam_bytecode()

    tasks = [listen_solana(start_time, watchlist_names), listen_robinhood(start_time, watchlist_names, seen_scam_hashes)]
    for chain_key, chain_cfg in CHAINS.items():
        tasks.append(listen_evm_chain(chain_key, chain_cfg, start_time, watchlist_names, seen_scam_hashes))

    await asyncio.gather(*tasks)
    save_seen_scam_bytecode(seen_scam_hashes)


if __name__ == "__main__":
    asyncio.run(main())
