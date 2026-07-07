"""
Étape 5 — orchestration ML, optimisée Raspberry Pi.

Deux modes (selon config) :
  - ENTRAÎNEMENT (PC, scikit-learn) : entraîne un modèle par actif, l'exporte en
    JSON portable (poids + scaler) dans data/models/<actif>.json, et journalise le run.
  - INFÉRENCE (Pi, numpy pur) : recharge le JSON portable et calcule la proba de
    hausse SANS scikit-learn. Active si ML_TRAIN_ENABLED=false.

Statut thread-safe par actif = « fenêtre de progression ». Tout est défensif.
"""
import json
import logging
import os
import threading
import time

import pandas as pd

from app import adventures, config, settings
from app.database import get_conn
from app.ml import features, model, predictor

log = logging.getLogger("ml")

_lock = threading.RLock()
_status = {}   # iid -> dict


def training_available() -> bool:
    return bool(config.ML_ENABLED and config.ML_TRAIN_ENABLED and model.available())


def available() -> bool:
    """L'inférence ML est-elle exploitable ? (numpy pur — toujours possible si activé)"""
    return bool(config.ML_ENABLED)


def _set(iid, **kw):
    with _lock:
        s = _status.setdefault(iid, {})
        s.update(kw)
        s["ts"] = int(time.time() * 1000)


def get_proba(iid):
    """Dernière probabilité de hausse (mémoire, repli sur ml_runs). None si rien."""
    with _lock:
        s = _status.get(iid)
        if s and s.get("state") == "done" and s.get("proba_up") is not None:
            return float(s["proba_up"])
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT proba_up FROM ml_runs WHERE instrument=? AND proba_up IS NOT NULL ORDER BY id DESC LIMIT 1",
            (iid,)).fetchone()
    finally:
        conn.close()
    return float(row["proba_up"]) if row and row["proba_up"] is not None else None


def get_status():
    with _lock:
        per = {iid: dict(s) for iid, s in _status.items()}
    return {"available": available(), "training": training_available(),
            "enabled": config.ML_ENABLED, "model": config.ML_MODEL,
            "min_samples": config.ML_MIN_SAMPLES, "horizon": config.ML_HORIZON,
            "instruments": per}


def _instruments():
    seen, out = set(), []
    for inst in list(settings.get_instruments()) + adventures.tracked_instruments():
        if inst.id not in seen:
            seen.add(inst.id)
            out.append(inst)
    return out


def _read_prices(iid, limit=5000):
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT timestamp, open, high, low, close, volume FROM "
            "(SELECT timestamp, open, high, low, close, volume FROM prices "
            " WHERE instrument=? ORDER BY timestamp DESC LIMIT ?) ORDER BY timestamp ASC",
            (iid, limit)).fetchall()
    finally:
        conn.close()
    return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()


def _path(iid):
    os.makedirs(config.ML_DIR, exist_ok=True)
    return os.path.join(config.ML_DIR, f"{iid}.json")


def _save_model(iid, portable, metrics):
    with open(_path(iid), "w", encoding="utf-8") as f:
        json.dump({"portable": portable, "metrics": metrics, "ts": int(time.time() * 1000)}, f)


def _load_model(iid):
    p = _path(iid)
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _predict_latest(iid, portable):
    raw = _read_prices(iid)
    if raw.empty:
        return None
    infer = features.build(raw, with_label=False)
    if not len(infer):
        return None
    row = infer[portable["features"]].astype(float).iloc[-1].values
    return round(predictor.proba_up(portable, row), 4)


def _record_run(iid, m, proba):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO ml_runs (instrument, timestamp, model_type, n_samples, accuracy, baseline, proba_up, loss_curve, note) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (iid, int(time.time() * 1000), m.get("model_type"), m.get("n_samples"),
             m.get("accuracy"), m.get("baseline"), proba, json.dumps(m.get("loss_curve", [])), None))
        conn.commit()
    finally:
        conn.close()


def train_instrument(iid, name=None):
    name = name or iid
    if not training_available():
        return predict_instrument(iid, name)  # pas d'entraînement ici → inférence
    _set(iid, name=name, state="training", message="entraînement en cours…")
    try:
        raw = _read_prices(iid)
        if raw.empty:
            _set(iid, state="insufficient", message="aucune donnée")
            return
        feat = features.build(raw, with_label=True)
        if len(feat) < config.ML_MIN_SAMPLES:
            _set(iid, state="insufficient",
                 message=f"{len(feat)}/{config.ML_MIN_SAMPLES} échantillons — collecte en cours")
            return
        portable, m = model.train(feat)
        _save_model(iid, portable, m)
        proba = _predict_latest(iid, portable)
        _record_run(iid, m, proba)
        _set(iid, name=name, state="done", message=f"modèle {m['model_type']} à jour",
             accuracy=m["accuracy"], baseline=m["baseline"], n_samples=m["n_samples"],
             loss_curve=m["loss_curve"], proba_up=proba)
        log.info("%s : ML %s accuracy=%.3f baseline=%.3f proba_up=%s",
                 iid, m["model_type"], m["accuracy"], m["baseline"], proba)
    except Exception as e:
        _set(iid, state="error", message=str(e))
        log.warning("%s : erreur entraînement -> %s", iid, e)


def predict_instrument(iid, name=None):
    name = name or iid
    data = _load_model(iid)
    if not data:
        _set(iid, name=name, state="no_model", message="aucun modèle (à entraîner sur PC)")
        return
    try:
        portable = data["portable"]
        m = data.get("metrics", {})
        proba = _predict_latest(iid, portable)
        _set(iid, name=name, state="done", message="inférence (modèle entraîné sur PC)",
             accuracy=m.get("accuracy"), baseline=m.get("baseline"),
             n_samples=m.get("n_samples"), loss_curve=m.get("loss_curve", []), proba_up=proba)
    except Exception as e:
        _set(iid, state="error", message=str(e))
        log.warning("%s : erreur inférence -> %s", iid, e)


def train_all():
    for inst in _instruments():
        train_instrument(inst.id, inst.name)


def predict_all():
    for inst in _instruments():
        predict_instrument(inst.id, inst.name)


def run():
    log.info("ML démarré (entraînement=%s, inférence=%s)", training_available(), available())
    while True:
        if not config.ML_ENABLED:
            time.sleep(120)
            continue
        if training_available():
            train_all()
        else:
            predict_all()
        time.sleep(config.ML_INTERVAL)
