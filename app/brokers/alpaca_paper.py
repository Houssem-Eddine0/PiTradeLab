"""Connecteur Alpaca « paper trading » — actions US + crypto.

Argent FICTIF (compte paper Alpaca), mais ordres RÉELS envoyés à l'API.
Auth : APCA-API-KEY-ID + APCA-API-SECRET-KEY. Base : https://paper-api.alpaca.markets
  - test : GET /v2/account (solde, statut)
  - BUY  : POST /v2/orders (ordre MARKET en `notional` = montant en $, fractionnel)
  - SELL : DELETE /v2/positions/{symbol} (clôture toute la position)
"""
import logging
from urllib.parse import quote

import requests

log = logging.getLogger("alpaca")

NAME = "Alpaca (paper)"
NEEDS_KEYS = True
BASE = "https://paper-api.alpaca.markets"

STOCKS = {"AAPL", "TSLA", "MSFT", "NVDA", "AMZN", "GOOGL"}
CRYPTO = {"BTC": "BTC/USD", "ETH": "ETH/USD", "SOL": "SOL/USD", "BNB": "BNB/USD", "XRP": "XRP/USD"}


def _hdr(adv):
    return {"APCA-API-KEY-ID": adv.get("broker_key", ""),
            "APCA-API-SECRET-KEY": adv.get("broker_secret", ""),
            "Content-Type": "application/json"}


def _symbol(instrument):
    """(symbole Alpaca, time_in_force) ou (None, None) si non supporté."""
    if instrument.id in STOCKS:
        return instrument.id, "day"
    if instrument.id in CRYPTO:
        return CRYPTO[instrument.id], "gtc"
    return None, None


def test_connection(adv: dict) -> dict:
    if not adv.get("broker_key") or not adv.get("broker_secret"):
        return {"ok": False, "error": "Clé et secret Alpaca requis."}
    try:
        r = requests.get(f"{BASE}/v2/account", headers=_hdr(adv), timeout=15)
        r.raise_for_status()
        a = r.json()
        return {"ok": True, "balance": a.get("cash"), "currency": a.get("currency", "USD"),
                "message": f"Alpaca paper OK — statut {a.get('status')} ({a.get('cash')} {a.get('currency', 'USD')})."}
    except requests.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.response.status_code} — clés invalides ?"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def account_state(adv: dict) -> dict:
    if not adv.get("broker_key") or not adv.get("broker_secret"):
        return {"ok": False, "error": "Clé + secret requis."}
    try:
        r = requests.get(f"{BASE}/v2/account", headers=_hdr(adv), timeout=12)
        r.raise_for_status()
        a = r.json()
        positions = []
        rp = requests.get(f"{BASE}/v2/positions", headers=_hdr(adv), timeout=12)
        if rp.ok:
            for p in rp.json():
                positions.append({"symbol": p.get("symbol"), "units": float(p.get("qty", 0) or 0),
                                  "pl": float(p.get("unrealized_pl", 0) or 0)})
        return {"ok": True, "balance": float(a.get("cash", 0) or 0),
                "equity": float(a.get("portfolio_value", a.get("equity", 0)) or 0),
                "currency": a.get("currency", "USD"), "positions": positions}
    except requests.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.response.status_code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def execute(adv: dict, instrument, action: str, price: float, cash: float, position: float) -> dict:
    sym, tif = _symbol(instrument)
    if not sym:
        return {"ok": False, "error": f"{instrument.id} non négociable sur Alpaca."}
    if not adv.get("broker_key") or not adv.get("broker_secret"):
        return {"ok": False, "error": "Identifiants Alpaca incomplets."}
    try:
        if action == "SELL":
            r = requests.delete(f"{BASE}/v2/positions/{quote(sym, safe='')}", headers=_hdr(adv), timeout=20)
            r.raise_for_status()
            return {"ok": True, "closed": True}
        if cash <= 0:
            return {"ok": False, "error": "aucune liquidité allouée."}
        body = {"symbol": sym, "notional": round(cash, 2), "side": "buy",
                "type": "market", "time_in_force": tif}
        r = requests.post(f"{BASE}/v2/orders", headers=_hdr(adv), json=body, timeout=20)
        r.raise_for_status()
        return {"ok": True, "notional": round(cash, 2)}
    except requests.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.response.status_code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
