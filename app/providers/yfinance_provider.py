"""
Fournisseur multi-actifs via Yahoo Finance (yfinance) — sans clé API.
Couvre : or (GC=F), actions (AAPL...), forex (EURUSD=X), indices (^GSPC...).

Note : données Yahoo légèrement différées et limitées aux heures de marché
pour les actions. Le bot gère naturellement l'absence de nouvelle bougie.
"""
import logging
import math

import yfinance as yf

log = logging.getLogger("yfinance")

# Profondeur d'historique à demander selon la granularité (contraintes Yahoo).
_PERIOD = {
    "1m": "5d", "2m": "5d", "5m": "5d",
    "15m": "1mo", "30m": "1mo", "60m": "3mo", "1h": "3mo",
    "1d": "1y",
}


def fetch_ohlcv(symbol: str, timeframe: str, limit: int):
    period = _PERIOD.get(timeframe, "5d")
    df = yf.Ticker(symbol).history(period=period, interval=timeframe, auto_adjust=False)
    if df is None or df.empty:
        return []

    df = df.tail(limit + 60)
    out = []
    for idx, row in df.iterrows():
        o, h, l, c = row.get("Open"), row.get("High"), row.get("Low"), row.get("Close")
        if any(v is None or (isinstance(v, float) and math.isnan(v)) for v in (o, h, l, c)):
            continue
        vol = row.get("Volume", 0)
        if vol is None or (isinstance(vol, float) and math.isnan(vol)):
            vol = 0.0
        ts = int(idx.timestamp() * 1000)
        out.append([ts, float(o), float(h), float(l), float(c), float(vol)])
    return out
