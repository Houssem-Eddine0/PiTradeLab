"""Connecteur OANDA « practice » (fxTrade Practice) — forex, or/argent, indices.

Argent FICTIF (compte de démo OANDA), mais ordres RÉELS envoyés à l'API.
Auth : token API (Bearer) + account id. Base : https://api-fxpractice.oanda.com
  - test : GET /v3/accounts (token) puis /v3/accounts/{id}/summary (solde)
  - BUY  : POST /v3/accounts/{id}/orders (ordre MARKET, units entiers, base)
  - SELL : PUT  /v3/accounts/{id}/positions/{inst}/close (clôture la position longue)
"""
import logging

import requests

log = logging.getLogger("oanda")

NAME = "OANDA (practice)"
NEEDS_KEYS = True
BASE = "https://api-fxpractice.oanda.com"

# id catalogue -> instrument OANDA
SYMBOLS = {
    "EURUSD": "EUR_USD", "GBPUSD": "GBP_USD", "USDJPY": "USD_JPY",
    "GOLD": "XAU_USD", "SILVER": "XAG_USD", "OIL": "WTICO_USD",
    "SP500": "SPX500_USD", "NASDAQ": "NAS100_USD", "CAC40": "FR40_EUR",
}


def _hdr(adv):
    return {"Authorization": f"Bearer {adv.get('broker_key', '')}", "Content-Type": "application/json"}


def test_connection(adv: dict) -> dict:
    token = adv.get("broker_key")
    account = adv.get("broker_account")
    if not token:
        return {"ok": False, "error": "Token OANDA manquant."}
    try:
        if not account:
            r = requests.get(f"{BASE}/v3/accounts", headers=_hdr(adv), timeout=15)
            r.raise_for_status()
            accs = r.json().get("accounts", [])
            if not accs:
                return {"ok": False, "error": "Aucun compte associé à ce token."}
            account = accs[0]["id"]
        r = requests.get(f"{BASE}/v3/accounts/{account}/summary", headers=_hdr(adv), timeout=15)
        r.raise_for_status()
        a = r.json().get("account", {})
        return {"ok": True, "account": account, "balance": a.get("balance"), "currency": a.get("currency"),
                "message": f"OANDA practice OK — compte {account} ({a.get('balance')} {a.get('currency')})."}
    except requests.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.response.status_code} — token/compte invalide ?"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def account_state(adv: dict) -> dict:
    token = adv.get("broker_key")
    account = adv.get("broker_account")
    if not token or not account:
        return {"ok": False, "error": "Token + account id requis."}
    try:
        r = requests.get(f"{BASE}/v3/accounts/{account}/summary", headers=_hdr(adv), timeout=12)
        r.raise_for_status()
        a = r.json().get("account", {})
        positions = []
        rp = requests.get(f"{BASE}/v3/accounts/{account}/openPositions", headers=_hdr(adv), timeout=12)
        if rp.ok:
            for p in rp.json().get("positions", []):
                units = float(p.get("long", {}).get("units", 0) or 0) + float(p.get("short", {}).get("units", 0) or 0)
                positions.append({"symbol": p.get("instrument"), "units": units,
                                  "pl": float(p.get("unrealizedPL", 0) or 0)})
        return {"ok": True, "balance": float(a.get("balance", 0) or 0),
                "equity": float(a.get("NAV", a.get("balance", 0)) or 0),
                "currency": a.get("currency"), "positions": positions}
    except requests.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.response.status_code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def execute(adv: dict, instrument, action: str, price: float, cash: float, position: float) -> dict:
    token = adv.get("broker_key")
    account = adv.get("broker_account")
    sym = SYMBOLS.get(instrument.id)
    if not sym:
        return {"ok": False, "error": f"{instrument.id} non négociable sur OANDA."}
    if not token or not account:
        return {"ok": False, "error": "Identifiants OANDA incomplets (token + account id requis)."}
    try:
        if action == "SELL":
            r = requests.put(f"{BASE}/v3/accounts/{account}/positions/{sym}/close",
                             headers=_hdr(adv), json={"longUnits": "ALL"}, timeout=20)
            r.raise_for_status()
            return {"ok": True, "closed": True}
        units = int(cash / price) if price and price > 0 else 0
        if units < 1:
            return {"ok": False, "error": f"capital {cash:.2f} insuffisant pour 1 unité de {sym} (~{price:.2f})."}
        body = {"order": {"type": "MARKET", "instrument": sym, "units": str(units)}}
        r = requests.post(f"{BASE}/v3/accounts/{account}/orders", headers=_hdr(adv), json=body, timeout=20)
        r.raise_for_status()
        return {"ok": True, "units": units}
    except requests.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.response.status_code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
