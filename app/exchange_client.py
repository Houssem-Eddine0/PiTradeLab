"""
Connexion à un compte exchange réel (Binance ou autre via ccxt).

- test_connection : vérifie les clés en lecture seule (récupère le solde).
- place_order     : passe un ordre marché RÉEL (utilisé uniquement en mode "live").

⚠️ Le mode "live" engage de vrais fonds. Le mode "paper" (défaut) n'utilise jamais
ces fonctions. Les clés ne nécessitent que la permission "lecture" pour se connecter.
"""
import logging

import ccxt

log = logging.getLogger("exchange")


def _make(exchange_id: str, api_key: str, secret: str):
    klass = getattr(ccxt, exchange_id)
    return klass({"apiKey": api_key, "secret": secret, "enableRateLimit": True})


def test_connection(exchange_id: str, api_key: str, secret: str) -> dict:
    """Teste les clés et renvoie quelques soldes non nuls."""
    if not api_key or not secret:
        return {"ok": False, "error": "Clés manquantes."}
    try:
        ex = _make(exchange_id, api_key, secret)
        balance = ex.fetch_balance()
        totals = balance.get("total", {})
        non_zero = {k: v for k, v in totals.items() if v and v > 0}
        top = dict(sorted(non_zero.items(), key=lambda kv: -kv[1])[:8])
        return {"ok": True, "exchange": exchange_id, "balances": top,
                "message": f"Connecté à {exchange_id} ({len(non_zero)} actifs avec solde)."}
    except ccxt.AuthenticationError:
        return {"ok": False, "error": "Authentification refusée (clés invalides ou permissions insuffisantes)."}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def live_amount(exchange_id: str, api_key: str, secret: str, symbol: str, side: str) -> float:
    """Quantité d'un ordre tout-ou-rien calculée sur le SOLDE RÉEL du compte.

    - buy  : tout le cash disponible dans la devise de quote → quantité en base.
    - sell : toute la position disponible dans la devise de base.
    Renvoie 0.0 si rien à trader (ou en cas d'erreur) → l'appelant n'envoie pas d'ordre.
    """
    try:
        ex = _make(exchange_id, api_key, secret)
        base, quote = symbol.split("/")
        free = (ex.fetch_balance() or {}).get("free", {})
        if side == "buy":
            cash = float(free.get(quote, 0) or 0)
            price = float((ex.fetch_ticker(symbol) or {}).get("last") or 0)
            return cash / price if price > 0 else 0.0
        return float(free.get(base, 0) or 0)
    except Exception as e:
        log.warning("calcul taille ordre réel %s %s -> %s", side, symbol, e)
        return 0.0


def place_order(exchange_id: str, api_key: str, secret: str, symbol: str, side: str, amount: float) -> dict:
    """Passe un ordre marché réel. side = 'buy' | 'sell'. amount en unités de base."""
    try:
        ex = _make(exchange_id, api_key, secret)
        amount = float(ex.amount_to_precision(symbol, amount))
        order = ex.create_order(symbol, "market", side, amount)
        log.info("ordre RÉEL %s %s %s -> id=%s", side, amount, symbol, order.get("id"))
        return {"ok": True, "order_id": order.get("id")}
    except Exception as e:
        log.warning("échec ordre réel %s %s -> %s", side, symbol, e)
        return {"ok": False, "error": str(e)}
