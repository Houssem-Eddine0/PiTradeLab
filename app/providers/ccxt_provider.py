"""Fournisseur crypto via ccxt (Binance par défaut). Données temps réel.

L'exchange est lu depuis les settings (modifiable à chaud depuis la page de
configuration) ; l'instance ccxt est recréée si l'exchange change. Aucune clé
n'est nécessaire : seules les données publiques OHLCV sont consommées ici.
"""
import ccxt

from app import settings
from app.config import EXCHANGE

_exchange = None
_exchange_id = None


def _get():
    global _exchange, _exchange_id
    ex_id = settings.get("exchange") or EXCHANGE
    if _exchange is None or ex_id != _exchange_id:
        klass = getattr(ccxt, ex_id)
        _exchange = klass({"enableRateLimit": True})
        _exchange_id = ex_id
    return _exchange


def fetch_ohlcv(symbol: str, timeframe: str, limit: int):
    # ccxt renvoie déjà [[ts_ms, o, h, l, c, v], ...]
    return _get().fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
