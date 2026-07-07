"""
Collecteur de données — thread de fond.
Parcourt les instruments ACTUELLEMENT sélectionnés (relus à chaque cycle, donc
réactif aux changements depuis la page de configuration) et stocke leurs bougies.
"""
import logging
import time

from app import adventures, settings
from app.config import CANDLE_FETCH_LIMIT, COLLECTION_INTERVAL
from app.database import get_conn
from app.providers import fetch_ohlcv

log = logging.getLogger("collector")

# Durée d'une bougie (s) → inutile de re-télécharger un actif avant qu'une nouvelle
# bougie soit possible (gros gain réseau/CPU sur Pi, surtout pour yfinance en 5m).
_TF_SECONDS = {"1m": 60, "2m": 120, "5m": 300, "15m": 900, "30m": 1800,
               "60m": 3600, "1h": 3600, "1d": 86400}


def _instruments_to_collect():
    """Actifs du bot de base + ceux des aventures activées, dédupliqués par id."""
    seen, out = set(), []
    for inst in list(settings.get_instruments()) + adventures.tracked_instruments():
        if inst.id not in seen:
            seen.add(inst.id)
            out.append(inst)
    return out


def run():
    log.info("démarré")
    last_fetch = {}  # iid -> time.monotonic du dernier essai
    while True:
        now = time.monotonic()
        for inst in _instruments_to_collect():
            # Throttle : on saute si la dernière collecte est plus récente que la bougie.
            tf = _TF_SECONDS.get(inst.timeframe, 60)
            if now - last_fetch.get(inst.id, 0.0) < tf * 0.9:
                continue
            try:
                candles = fetch_ohlcv(inst.provider, inst.symbol, inst.timeframe, CANDLE_FETCH_LIMIT)
                last_fetch[inst.id] = now  # même si vide : évite de marteler un marché fermé
                if not candles:
                    log.info("%s : aucune donnée (marché fermé ?)", inst.id)
                    continue
                conn = get_conn()
                try:
                    conn.executemany(
                        "INSERT OR IGNORE INTO prices "
                        "(instrument, timestamp, open, high, low, close, volume) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        [[inst.id] + candle for candle in candles],
                    )
                    conn.commit()
                finally:
                    conn.close()
                log.info("%s : %d bougies, dernier close=%.4f", inst.id, len(candles), candles[-1][4])
            except Exception as e:
                log.warning("%s : erreur -> %s", inst.id, e)

        time.sleep(COLLECTION_INTERVAL)
