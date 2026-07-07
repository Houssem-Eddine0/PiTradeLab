"""
Store de configuration runtime, persisté dans data/settings.json.

- Valeurs par défaut issues de config.py (variables d'environnement) au 1er lancement.
- Modifiable à chaud depuis la page de configuration (les threads relisent les
  settings à chaque cycle).
- Thread-safe.
"""
import json
import os
import threading

from app import config
from app.instruments import Instrument, as_dicts as default_instrument_dicts

SETTINGS_PATH = os.path.join(os.path.dirname(config.DB_PATH) or ".", "settings.json")

# Clés autorisées + valeurs par défaut
DEFAULTS = {
    "language": "fr",
    "strategy": "ma_rsi_volume",
    "buy_threshold": config.BUY_THRESHOLD,
    "sell_threshold": config.SELL_THRESHOLD,
    "ai_weight": config.AI_WEIGHT,
    "ml_weight": config.ML_WEIGHT,
    "ai_interval": config.AI_INTERVAL,
    "ai_provider": "gemini",  # "gemini" | "mistral" (IA du bot de base)
    "gemini_api_key": config.GEMINI_API_KEY,
    "gemini_model": config.GEMINI_MODEL,
    "mistral_api_key": "",
    "mistral_model": "mistral-small-latest",
    "exchange": config.EXCHANGE,
    "exchange_api_key": config.API_KEY,
    "exchange_secret": config.API_SECRET,
    "trading_mode": "paper",  # "paper" | "live"
    "instruments": default_instrument_dicts(),
}

SECRET_KEYS = {"gemini_api_key", "mistral_api_key", "exchange_api_key", "exchange_secret"}

_lock = threading.RLock()
_data = {}
_version = 0                       # incrémenté à chaque modification
_inst_cache = {"version": -1, "list": []}  # mémoïsation de get_instruments()


def _load():
    global _data
    d = dict(DEFAULTS)
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                stored = json.load(f)
            for k, v in stored.items():
                if k in DEFAULTS:
                    d[k] = v
        except Exception:
            pass
    _data = d


def save():
    with _lock:
        os.makedirs(os.path.dirname(SETTINGS_PATH) or ".", exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(_data, f, ensure_ascii=False, indent=2)


def get(key, default=None):
    with _lock:
        return _data.get(key, default)


def all_settings():
    with _lock:
        return dict(_data)


def update(changes: dict):
    global _version
    with _lock:
        for k, v in changes.items():
            if k not in DEFAULTS:
                continue
            # Ne pas écraser un secret avec une valeur vide
            if k in SECRET_KEYS and (v is None or v == ""):
                continue
            if k == "instruments" and isinstance(v, list):
                v = v[:5]  # 5 actifs maximum
            _data[k] = v
        _version += 1
    save()


def get_instruments():
    """Liste d'objets Instrument (max 5), mémoïsée tant que les settings ne changent pas."""
    with _lock:
        if _inst_cache["version"] == _version:
            return list(_inst_cache["list"])
        out = []
        for d in get("instruments", [])[:5]:
            try:
                out.append(Instrument(**d))
            except (TypeError, ValueError):
                continue
        _inst_cache["version"] = _version
        _inst_cache["list"] = out
        return list(out)


_load()
_version = 1  # invalide le cache après le chargement initial
