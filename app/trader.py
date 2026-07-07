"""
Moteur de paper trading — thread de fond, pour chaque instrument sélectionné.

Décision = fusion de deux cerveaux :
  - score TECHNIQUE (stratégie choisie dans les settings)
  - score IA       (analyste Gemini + news), si disponible
  final = (1 - ai_weight) * technique + ai_weight * ia
Seuils d'achat/vente et stratégie sont lus dans les settings (modifiables à chaud).
"""
import json
import logging
import time

import pandas as pd

from app import ml, settings, strategies
from app.config import MIN_ROWS_REQUIRED, TRADING_INTERVAL
from app.database import get_conn
from app.state import controller

log = logging.getLogger("trader")


def _decide(final_score: float):
    bt = settings.get("buy_threshold")
    st = settings.get("sell_threshold")
    if final_score >= bt:
        return "BUY"
    if final_score <= st:
        return "SELL"
    return "HOLD"


def _process(inst, last_ts: dict):
    # Lecture des bougies : connexion fermée AVANT tout calcul (pas de fuite si
    # la stratégie lève).
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT timestamp, open, high, low, close, volume FROM "
            "(SELECT timestamp, open, high, low, close, volume FROM prices "
            " WHERE instrument=? ORDER BY timestamp DESC LIMIT ?) ORDER BY timestamp ASC",
            (inst.id, MIN_ROWS_REQUIRED),
        ).fetchall()
    finally:
        conn.close()

    if len(rows) < MIN_ROWS_REQUIRED:
        return

    df = pd.DataFrame([dict(r) for r in rows])
    ts = int(df["timestamp"].iloc[-1])
    price = float(df["close"].iloc[-1])
    if ts == last_ts.get(inst.id):
        return

    strat = strategies.get(settings.get("strategy"))
    tech_score, details = strat(df)

    snap = controller.snapshot(inst.id)  # lecture d'état sous verrou
    ai_score = (snap["ai"] or {}).get("score")
    aw = settings.get("ai_weight")
    final_score = tech_score if ai_score is None else (1 - aw) * tech_score + aw * ai_score

    # Fusion ML : la proba de hausse [0..1] devient un score [-1..1], pondéré par ml_weight.
    ml_w = settings.get("ml_weight") or 0.0
    ml_score = None
    if ml_w > 0:
        proba = ml.get_proba(inst.id)
        if proba is not None:
            ml_score = 2.0 * proba - 1.0
            final_score = (1 - ml_w) * final_score + ml_w * ml_score

    final_score = round(max(-1.0, min(1.0, final_score)), 3)

    signal = _decide(final_score)
    details["tech_score"] = tech_score
    details["ai_score"] = ai_score
    details["ml_score"] = round(ml_score, 3) if ml_score is not None else None
    details["final_score"] = final_score
    details["strategy"] = settings.get("strategy")

    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO signals (instrument, timestamp, signal, price, score, details) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (inst.id, ts, signal, price, final_score, json.dumps(details)),
        )
        conn.commit()
    finally:
        conn.close()

    if not snap["paused"] and signal in ("BUY", "SELL"):
        ok, msg = controller.execute(inst.id, signal, price, "auto")
        if ok:
            log.info(">> %s", msg)

    last_ts[inst.id] = ts
    log.info("%s : signal=%s score=%+.3f (tech=%+.2f ia=%s) prix=%.4f",
             inst.id, signal, final_score, tech_score,
             f"{ai_score:+.2f}" if ai_score is not None else "—", price)


def run():
    last_ts = {}
    log.info("démarré")
    while True:
        for inst in settings.get_instruments():
            try:
                _process(inst, last_ts)
            except Exception as e:
                log.warning("%s : erreur -> %s", inst.id, e)
        time.sleep(TRADING_INTERVAL)
