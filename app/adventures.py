"""
Aventures — sessions de trading ISOLÉES, en parallèle du bot paper de base.

Chaque aventure a :
  - un nom (modifiable), un capital max à ne pas dépasser,
  - ses propres actifs, sa stratégie et ses seuils,
  - son propre fournisseur IA + clé (ou celui de base si vide) + un prompt de
    départ décrivant les préférences de trading,
  - un mode d'exécution (broker) : "sim" (prix réels, ordres simulés — défaut sûr)
    puis "alpaca_paper" / "oanda_paper" (à venir).

Le capital est réparti à parts égales entre les actifs de l'aventure ; chaque
sous-portefeuille fonctionne en tout-ou-rien (comme le bot de base). Tout est
persisté : la config dans data/adventures.json, les ordres dans la table
adventure_trades. Le bot de base continue de tourner en virtuel (pour le ML).
"""
import json
import os
import threading
import time
import uuid

from app import config, settings
from app.database import get_conn
from app.instruments import Instrument

ADV_PATH = os.path.join(os.path.dirname(config.DB_PATH) or ".", "adventures.json")

SECRET_KEYS = {"ai_api_key", "broker_key", "broker_secret"}
BROKERS = ["sim", "alpaca_paper", "oanda_paper"]

# Champs autorisés + valeurs par défaut d'une aventure
TEMPLATE = {
    "name": "Nouvelle aventure",
    "enabled": False,
    "broker": "sim",
    "max_capital": 30.0,
    "instruments": [],
    "strategy": "ma_rsi_volume",
    "buy_threshold": config.BUY_THRESHOLD,
    "sell_threshold": config.SELL_THRESHOLD,
    "ai_weight": 0.3,
    "ml_weight": 0.0,
    "ai_provider": "",   # "" => utilise l'IA de base ; sinon "gemini" | "mistral"
    "ai_api_key": "",    # "" => clé de base
    "ai_model": "",
    "ai_prompt": "",     # préférences de trading décrites à l'IA
    # Identifiants courtier (selon broker) : OANDA = token+account ; Alpaca = key+secret
    "broker_key": "",
    "broker_secret": "",
    "broker_account": "",
}

_lock = threading.RLock()
_data = {}  # id -> dict


def _load():
    global _data
    out = {}
    if os.path.exists(ADV_PATH):
        try:
            with open(ADV_PATH, encoding="utf-8") as f:
                for adv in json.load(f):
                    if isinstance(adv, dict) and adv.get("id"):
                        out[adv["id"]] = _normalize(adv)
        except Exception:
            pass
    _data = out


def _normalize(adv: dict) -> dict:
    merged = dict(TEMPLATE)
    merged.update({k: v for k, v in adv.items() if k in TEMPLATE or k in ("id", "created_ts")})
    merged["id"] = adv.get("id") or uuid.uuid4().hex[:12]
    merged.setdefault("created_ts", int(time.time() * 1000))
    try:
        merged["max_capital"] = max(0.0, float(merged["max_capital"]))
    except (TypeError, ValueError):
        merged["max_capital"] = 30.0
    if not isinstance(merged.get("instruments"), list):
        merged["instruments"] = []
    merged["instruments"] = merged["instruments"][:5]
    return merged


def _save():
    with _lock:
        os.makedirs(os.path.dirname(ADV_PATH) or ".", exist_ok=True)
        with open(ADV_PATH, "w", encoding="utf-8") as f:
            json.dump(list(_data.values()), f, ensure_ascii=False, indent=2)


def list_raw():
    with _lock:
        return [dict(a) for a in _data.values()]


def public(adv: dict) -> dict:
    """Copie sans les secrets (clés masquées en booléens)."""
    out = {k: v for k, v in adv.items() if k not in SECRET_KEYS}
    out["ai_key_set"] = bool(adv.get("ai_api_key"))
    out["broker_keys_set"] = bool(adv.get("broker_key"))
    return out


def list_public():
    return [public(a) for a in list_raw()]


def get(adv_id: str):
    with _lock:
        a = _data.get(adv_id)
        return dict(a) if a else None


def create(changes: dict) -> dict:
    adv = _normalize({**TEMPLATE, **(changes or {})})
    adv["id"] = uuid.uuid4().hex[:12]
    adv["created_ts"] = int(time.time() * 1000)
    with _lock:
        _data[adv["id"]] = adv
    _save()
    return public(adv)


def update(adv_id: str, changes: dict):
    with _lock:
        adv = _data.get(adv_id)
        if not adv:
            return None
        for k, v in (changes or {}).items():
            if k not in TEMPLATE:
                continue
            # ne pas écraser un secret par du vide (= « inchangé »)
            if k in SECRET_KEYS and (v is None or v == ""):
                continue
            adv[k] = v
        adv = _normalize(adv)
        _data[adv_id] = adv
    _save()
    return public(adv)


def delete(adv_id: str) -> bool:
    with _lock:
        existed = _data.pop(adv_id, None) is not None
    if existed:
        _save()
    return existed


def enabled_adventures():
    return [a for a in list_raw() if a.get("enabled")]


def instruments_of(adv: dict):
    out = []
    for d in (adv.get("instruments") or [])[:5]:
        try:
            out.append(Instrument(**d))
        except (TypeError, ValueError):
            continue
    return out


def tracked_instruments():
    """Instruments uniques (par id) de toutes les aventures activées —
    pour que le collecteur récupère aussi leurs bougies."""
    seen, out = set(), []
    for adv in enabled_adventures():
        for inst in instruments_of(adv):
            if inst.id not in seen:
                seen.add(inst.id)
                out.append(inst)
    return out


def resolve_ai(adv: dict):
    """(provider, api_key, model) effectifs : ceux de l'aventure si une clé y est
    définie, sinon ceux de l'IA de base."""
    if adv.get("ai_api_key") and adv.get("ai_provider"):
        return adv["ai_provider"], adv["ai_api_key"], (adv.get("ai_model") or None)
    provider = settings.get("ai_provider") or "gemini"
    if provider == "mistral":
        return "mistral", settings.get("mistral_api_key"), settings.get("mistral_model")
    return "gemini", settings.get("gemini_api_key"), settings.get("gemini_model")


# --------------------------------------------------------------------------
# Portefeuilles isolés (un sous-portefeuille par (aventure, actif))
# --------------------------------------------------------------------------

class AdventureBook:
    def __init__(self):
        self._lock = threading.RLock()
        self.portfolios = {}   # (adv_id, iid) -> {"balance", "position"}
        self.ai = {}           # (adv_id, iid) -> dict

    def _share(self, adv: dict) -> float:
        n = max(1, len(instruments_of(adv)))
        return adv.get("max_capital", 0.0) / n

    def _ensure(self, adv: dict, iid: str):
        key = (adv["id"], iid)
        if key not in self.portfolios:
            self.portfolios[key] = {"balance": self._share(adv), "position": 0.0}

    def load(self):
        conn = get_conn()
        try:
            for adv in list_raw():
                for inst in instruments_of(adv):
                    with self._lock:
                        self._ensure(adv, inst.id)
                        row = conn.execute(
                            "SELECT balance, position FROM adventure_trades "
                            "WHERE adventure_id=? AND instrument=? ORDER BY id DESC LIMIT 1",
                            (adv["id"], inst.id),
                        ).fetchone()
                        if row:
                            self.portfolios[(adv["id"], inst.id)] = {
                                "balance": float(row["balance"]), "position": float(row["position"])}
        finally:
            conn.close()

    def execute(self, adv: dict, iid: str, action: str, price: float, source: str = "auto"):
        with self._lock:
            self._ensure(adv, iid)
            p = self.portfolios[(adv["id"], iid)]
            if action == "BUY":
                if p["balance"] <= 0:
                    return False, "déjà investi (aucune liquidité)."
                amount = (p["balance"] * (1 - config.FEE_RATE)) / price
                p["position"] = amount
                p["balance"] = 0.0
            elif action == "SELL":
                if p["position"] <= 0:
                    return False, "aucune position à vendre."
                p["balance"] = p["position"] * price * (1 - config.FEE_RATE)
                p["position"] = 0.0
            else:
                return False, f"action inconnue : {action}"

            conn = get_conn()
            try:
                conn.execute(
                    "INSERT INTO adventure_trades (adventure_id, instrument, timestamp, action, price, balance, position, source) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (adv["id"], iid, int(time.time() * 1000), action, price, p["balance"], p["position"], source),
                )
                conn.commit()
            finally:
                conn.close()
        return True, f"{action} {iid} @ {price:.4f} ({source})."

    def set_ai(self, adv_id: str, iid: str, data: dict):
        with self._lock:
            self.ai[(adv_id, iid)] = data

    def snapshot(self, adv_id: str, iid: str) -> dict:
        with self._lock:
            p = self.portfolios.get((adv_id, iid)) or {"balance": 0.0, "position": 0.0}
            return {"portfolio": dict(p), "ai": dict(self.ai.get((adv_id, iid), {}))}


book = AdventureBook()

# --------------------------------------------------------------------------
# Réconciliation compte réel courtier (mise en cache pour ménager l'API)
# --------------------------------------------------------------------------

_acct_cache = {}  # adv_id -> (ts_monotonic, data)


def real_account(adv: dict, ttl: float = 30.0):
    """État réel du compte courtier (None si broker == sim). Mis en cache `ttl` s."""
    if adv.get("broker", "sim") == "sim":
        return None
    now = time.monotonic()
    cached = _acct_cache.get(adv["id"])
    if cached and (now - cached[0]) < ttl:
        return cached[1]
    from app import brokers
    try:
        data = brokers.account_state(adv)
    except Exception as e:
        data = {"ok": False, "error": str(e)}
    _acct_cache[adv["id"]] = (now, data)
    return data


_load()
