"""
Analyste IA — thread de fond, pour chaque instrument sélectionné.

Boucle en continu : si une clé Gemini est configurée, analyse chaque actif
(marché + news) toutes les `ai_interval` secondes et met le score IA en cache.
Réagit à l'activation de la clé sans redémarrage (relit les settings à chaque tour).
"""
import json
import logging
import time

from app import config, settings
from app.ai import ai_available, ask, lang_instruction
from app.database import get_conn
from app.news import fetch_headlines
from app.state import controller

log = logging.getLogger("analyst")


def _system():
    return ("Tu es un analyste de marché quantitatif prudent. "
            "Tu réponds STRICTEMENT en JSON valide, sans texte autour. " + lang_instruction())


def _gather_context(inst) -> dict:
    conn = get_conn()
    price_row = conn.execute(
        "SELECT close FROM prices WHERE instrument=? ORDER BY timestamp DESC LIMIT 1", (inst.id,)
    ).fetchone()
    sig_row = conn.execute(
        "SELECT signal, details FROM signals WHERE instrument=? ORDER BY id DESC LIMIT 1", (inst.id,)
    ).fetchone()
    conn.close()
    ctx = {"actif": inst.name, "classe": inst.asset_class}
    if price_row:
        ctx["prix"] = round(float(price_row["close"]), 4)
    if sig_row:
        ctx["dernier_signal_technique"] = sig_row["signal"]
        try:
            ctx["indicateurs"] = json.loads(sig_row["details"]) if sig_row["details"] else {}
        except (ValueError, TypeError):
            pass
    return ctx


def _build_prompt(inst, ctx, headlines):
    news_block = "\n".join(f"- {h}" for h in headlines) if headlines else "(aucune)"
    return (
        f"Analyse les perspectives court terme de {inst.name} ({inst.asset_class}).\n\n"
        f"Données techniques :\n{json.dumps(ctx, ensure_ascii=False)}\n\n"
        f"Actualités récentes :\n{news_block}\n\n"
        'Renvoie un JSON STRICT : {"score": <-1 à 1>, '
        '"sentiment": "bullish|neutral|bearish", "reasoning": "<1-2 phrases>"}'
    )


def _analyze(inst):
    ctx = _gather_context(inst)
    headlines = fetch_headlines(inst.asset_class) if config.NEWS_ENABLED else []
    raw = ask(_build_prompt(inst, ctx, headlines), system=_system(), json_mode=True)
    data = json.loads(raw)
    data["score"] = max(-1.0, min(1.0, float(data.get("score", 0.0))))
    data["sentiment"] = data.get("sentiment", "neutral")
    data["reasoning"] = data.get("reasoning", "")
    data["headlines"] = headlines[:5]
    data["ts"] = int(time.time() * 1000)
    controller.set_ai(inst.id, data)
    conn = get_conn()
    conn.execute(
        "INSERT INTO ai_analysis (instrument, timestamp, score, sentiment, reasoning, headlines) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (inst.id, data["ts"], data["score"], data["sentiment"], data["reasoning"],
         json.dumps(data["headlines"], ensure_ascii=False)),
    )
    conn.commit()
    conn.close()
    log.info("%s : IA score=%+.2f sentiment=%s", inst.id, data["score"], data["sentiment"])


def run():
    log.info("démarré")
    while True:
        if not ai_available():
            time.sleep(20)  # pas de clé : on réessaie (la clé peut être ajoutée à chaud)
            continue
        for inst in settings.get_instruments():
            try:
                _analyze(inst)
            except Exception as e:
                log.warning("%s : erreur analyste -> %s", inst.id, e)
        time.sleep(settings.get("ai_interval") or 1800)
