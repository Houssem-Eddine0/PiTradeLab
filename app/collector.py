"""
Collecteur de données — thread de fond.
Parcourt les instruments ACTUELLEMENT sélectionnés (relus à chaque cycle, donc
réactif aux changements depuis la page de configuration) et stocke leurs bougies.
"""
import logging
import time

from app import settings
from app.config import CANDLE_FETCH_LIMIT, COLLECTION_INTERVAL
from app.database import get_conn
from app.providers import fetch_ohlcv

log = logging.getLogger("collector")


def run():
    log.info("démarré")
    while True:
        for inst in settings.get_instruments():
            try:
                candles = fetch_ohlcv(inst.provider, inst.symbol, inst.timeframe, CANDLE_FETCH_LIMIT)
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
