"""
Threads des aventures (en parallèle du bot de base, qui continue en virtuel) :
  - adv_trader : pour chaque aventure activée et chaque actif, calcule le signal
    (stratégie + seuils de l'aventure, fusionné avec son score IA) et exécute
    dans le portefeuille isolé de l'aventure (via le courtier choisi).
  - adv_analyst : score IA par aventure, en utilisant SON fournisseur/clé/prompt
    (ou ceux de base), mis en cache.

Les actifs des aventures sont aussi collectés (cf. collector qui unionne les
instruments du bot de base et ceux des aventures).
"""
import json
import logging
import time

import pandas as pd

from app import adventures, brokers, ml, settings, strategies
from app.config import MIN_ROWS_REQUIRED, TRADING_INTERVAL
from app.database import get_conn
from app.llm import ask as llm_ask
from app.news import fetch_headlines

log = logging.getLogger("adventure")


def _load_df(iid: str):
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT timestamp, open, high, low, close, volume FROM "
            "(SELECT timestamp, open, high, low, close, volume FROM prices "
            " WHERE instrument=? ORDER BY timestamp DESC LIMIT ?) ORDER BY timestamp ASC",
            (iid, MIN_ROWS_REQUIRED),
        ).fetchall()
    finally:
        conn.close()
    if len(rows) < MIN_ROWS_REQUIRED:
        return None
    return pd.DataFrame([dict(r) for r in rows])


def _decide(adv, score):
    if score >= adv.get("buy_threshold", 0.35):
        return "BUY"
    if score <= adv.get("sell_threshold", -0.35):
        return "SELL"
    return "HOLD"


def _process(adv, inst, last_ts: dict):
    df = _load_df(inst.id)
    if df is None:
        return
    ts = int(df["timestamp"].iloc[-1])
    price = float(df["close"].iloc[-1])
    key = (adv["id"], inst.id)
    if ts == last_ts.get(key):
        return

    strat = strategies.get(adv.get("strategy", "ma_rsi_volume"))
    tech_score, _ = strat(df)

    snap = adventures.book.snapshot(adv["id"], inst.id)
    ai_score = (snap["ai"] or {}).get("score")
    aw = adv.get("ai_weight", 0.3)
    score = tech_score if ai_score is None else (1 - aw) * tech_score + aw * ai_score

    ml_w = adv.get("ml_weight", 0.0) or 0.0
    if ml_w > 0:
        proba = ml.get_proba(inst.id)
        if proba is not None:
            score = (1 - ml_w) * score + ml_w * (2.0 * proba - 1.0)

    score = round(max(-1.0, min(1.0, score)), 3)

    signal = _decide(adv, score)
    if signal in ("BUY", "SELL"):
        pre = snap["portfolio"]  # liquidité/position AVANT l'exécution
        ok, msg = adventures.book.execute(adv, inst.id, signal, price, "auto")
        if ok:
            if adv.get("broker", "sim") != "sim":
                try:
                    res = brokers.execute(adv, inst, signal, price, pre["balance"], pre["position"])
                    if res.get("ok"):
                        log.info("[%s] ordre RÉEL %s %s OK (%s)", adv["name"], signal, inst.id, adv["broker"])
                    else:
                        log.info("[%s] %s %s : courtier -> %s (l'aventure reste simulée pour cet actif)",
                                 adv["name"], signal, inst.id, res.get("error"))
                except Exception as e:
                    log.warning("[%s] courtier %s %s -> %s", adv["name"], signal, inst.id, e)
            log.info("[%s] %s | score=%+.3f (tech=%+.2f ia=%s)", adv["name"], msg, score,
                     tech_score, f"{ai_score:+.2f}" if ai_score is not None else "—")

    last_ts[key] = ts


def trader_run():
    last_ts = {}
    log.info("trader aventures démarré")
    while True:
        for adv in adventures.enabled_adventures():
            for inst in adventures.instruments_of(adv):
                try:
                    _process(adv, inst, last_ts)
                except Exception as e:
                    log.warning("[%s] %s : erreur -> %s", adv.get("name"), inst.id, e)
        time.sleep(TRADING_INTERVAL)


# ------------------------------- IA par aventure -------------------------------

def _analyze(adv, inst):
    provider, key, model = adventures.resolve_ai(adv)
    if not key:
        return
    price = None
    df = _load_df(inst.id)
    if df is not None:
        price = round(float(df["close"].iloc[-1]), 4)
    headlines = fetch_headlines(inst.asset_class)
    news_block = "\n".join(f"- {h}" for h in headlines[:6]) if headlines else "(aucune)"

    lang = settings.get("language", "fr")
    prefs = adv.get("ai_prompt") or ""
    system = ("Tu es un analyste de marché quantitatif prudent. "
              "Tu réponds STRICTEMENT en JSON valide, sans texte autour. "
              + (f"Préférences de l'utilisateur : {prefs} " if prefs else "")
              + {"en": "Answer in English.", "es": "Responde en español."}.get(lang, "Réponds en français."))
    prompt = (
        f"Analyse les perspectives court terme de {inst.name} ({inst.asset_class}). "
        f"Prix actuel : {price}.\nActualités :\n{news_block}\n\n"
        'Renvoie un JSON STRICT : {"score": <-1 à 1>, '
        '"sentiment": "bullish|neutral|bearish", "reasoning": "<1-2 phrases>"}'
    )
    raw = llm_ask(prompt, system=system, json_mode=True, provider=provider, api_key=key, model=model)
    data = json.loads(raw)
    data["score"] = max(-1.0, min(1.0, float(data.get("score", 0.0))))
    data["sentiment"] = data.get("sentiment", "neutral")
    data["reasoning"] = data.get("reasoning", "")
    data["headlines"] = headlines[:5]
    data["ts"] = int(time.time() * 1000)
    adventures.book.set_ai(adv["id"], inst.id, data)
    log.info("[%s] IA %s score=%+.2f", adv["name"], inst.id, data["score"])


def analyst_run():
    log.info("analyste aventures démarré")
    while True:
        advs = adventures.enabled_adventures()
        any_ai = False
        for adv in advs:
            provider, key, _ = adventures.resolve_ai(adv)
            if not key:
                continue
            any_ai = True
            for inst in adventures.instruments_of(adv):
                try:
                    _analyze(adv, inst)
                except Exception as e:
                    log.warning("[%s] IA %s : erreur -> %s", adv.get("name"), inst.id, e)
        time.sleep(settings.get("ai_interval") or 1800 if any_ai else 30)
