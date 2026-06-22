"""
Abstraction des fournisseurs de données de marché.

Chaque fournisseur expose la même fonction :
    fetch_ohlcv(symbol, timeframe, limit) -> list[[ts_ms, open, high, low, close, volume]]

Cela permet de mélanger les classes d'actifs :
- ccxt      → cryptomonnaies (temps réel)
- yfinance  → or, actions, forex, indices (Yahoo Finance, sans clé API)
"""
from app.providers import ccxt_provider, yfinance_provider

_REGISTRY = {
    "ccxt": ccxt_provider,
    "yfinance": yfinance_provider,
}


def fetch_ohlcv(provider: str, symbol: str, timeframe: str, limit: int):
    if provider not in _REGISTRY:
        raise ValueError(f"fournisseur inconnu : {provider}")
    return _REGISTRY[provider].fetch_ohlcv(symbol, timeframe, limit)
