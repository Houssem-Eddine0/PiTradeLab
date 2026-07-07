"""
Serveur web FastAPI (multi-actifs + config runtime).
- Threads de fond : collector + trader + analyste IA.
- Pages : dashboard (/) et configuration (/config).
- API : état, vue d'ensemble, flux de trades, chat, commandes, settings, catalogue, exchange.
"""
import json
import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from app import (adventure_engine, adventures, analyst, brokers, collector,
                 exchange_client, learning, ml, settings, strategies, trader)
from app.ai import ai_available, ask, lang_instruction
from app.catalog import CATALOG_BY_ID, as_dicts as catalog_dicts
from app.config import INITIAL_BALANCE
from app.database import get_conn, init_db
from app.llm import providers_info, verify as llm_verify
from app.state import controller

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(name)s] %(levelname)s %(message)s", datefmt="%H:%M:%S")

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    controller.load()
    adventures.book.load()
    threading.Thread(target=collector.run, daemon=True, name="collector").start()
    threading.Thread(target=trader.run, daemon=True, name="trader").start()
    threading.Thread(target=analyst.run, daemon=True, name="analyst").start()
    threading.Thread(target=adventure_engine.trader_run, daemon=True, name="adv-trader").start()
    threading.Thread(target=adventure_engine.analyst_run, daemon=True, name="adv-analyst").start()
    threading.Thread(target=ml.run, daemon=True, name="ml").start()
    logging.getLogger("app").info("threads démarrés")
    yield


app = FastAPI(title="PiTradeLab", lifespan=lifespan)


# ----------------------------- Helpers -----------------------------

def _dump(model) -> dict:
    """Sérialise un modèle Pydantic — compatible v2 (model_dump) ET v1 (dict).
    Le Pi Zero tourne en pydantic v1 (pas de pydantic-core Rust)."""
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


def _instruments():
    return settings.get_instruments()


def _resolve(iid: str = None):
    insts = _instruments()
    if iid is None:
        return insts[0] if insts else None  # défaut : premier actif sélectionné
    for i in insts:
        if i.id == iid:
            return i
    return None  # actif demandé introuvable (désélectionné ?) → l'appelant gère


def _name(iid: str):
    inst = _resolve(iid)
    if inst and inst.id == iid:
        return inst.name, inst.asset_class, inst.quote
    cat = CATALOG_BY_ID.get(iid)
    if cat:
        return cat.name, cat.asset_class, cat.quote
    return iid, "", ""


def _last_price(iid: str):
    conn = get_conn()
    try:
        row = conn.execute("SELECT close FROM prices WHERE instrument=? ORDER BY timestamp DESC LIMIT 1", (iid,)).fetchone()
    finally:
        conn.close()
    return float(row["close"]) if row else None


def _overview(inst):
    snap = controller.snapshot(inst.id)
    conn = get_conn()
    try:
        price_row = conn.execute("SELECT close FROM prices WHERE instrument=? ORDER BY timestamp DESC LIMIT 1", (inst.id,)).fetchone()
        sig = conn.execute("SELECT signal FROM signals WHERE instrument=? ORDER BY id DESC LIMIT 1", (inst.id,)).fetchone()
    finally:
        conn.close()
    price = float(price_row["close"]) if price_row else None
    p = snap["portfolio"]
    total = p["balance"] + (p["position"] * price if price else 0.0)
    pnl = (total / INITIAL_BALANCE - 1.0) * 100.0
    return {"id": inst.id, "name": inst.name, "asset_class": inst.asset_class, "quote": inst.quote,
            "price": price, "signal": sig["signal"] if sig else None,
            "pnl": pnl, "total": total, "initial": INITIAL_BALANCE, "paused": snap["paused"]}


def _status_text(inst) -> str:
    o = _overview(inst)
    etat = "EN PAUSE" if o["paused"] else "ACTIF"
    return (f"{inst.name} [{etat}] | Prix : {o['price']} {inst.quote} | "
            f"Valeur : {o['total']:.2f} ({o['pnl']:+.2f} %) | Signal : {o['signal']}")


def _context_for_ai(inst) -> str:
    conn = get_conn()
    try:
        sig = conn.execute("SELECT signal, details FROM signals WHERE instrument=? ORDER BY id DESC LIMIT 1", (inst.id,)).fetchone()
    finally:
        conn.close()
    snap = controller.snapshot(inst.id)
    ctx = {"actif": inst.name, "classe": inst.asset_class, "prix": _last_price(inst.id),
           "portefeuille": {"liquidites": round(snap["portfolio"]["balance"], 2), "position": snap["portfolio"]["position"]},
           "auto_trading": "en pause" if snap["paused"] else "actif"}
    if sig:
        ctx["dernier_signal"] = sig["signal"]
        try:
            ctx["indicateurs"] = json.loads(sig["details"]) if sig["details"] else {}
        except (ValueError, TypeError):
            pass
    if snap["ai"]:
        ctx["analyse_ia"] = {"sentiment": snap["ai"].get("sentiment"), "score": snap["ai"].get("score")}
    return json.dumps(ctx, ensure_ascii=False)


def _run_command(iid: str, text: str) -> dict:
    inst = _resolve(iid)
    if not inst:
        return {"reply": "Aucun actif sélectionné."}
    a = text.strip().lower().lstrip("/")
    price = _last_price(inst.id)
    if a in ("buy", "acheter", "achat"):
        if price is None:
            return {"reply": f"⏳ Pas encore de prix pour {inst.name}."}
        ok, msg = controller.execute(inst.id, "BUY", price, "manuel")
        return {"reply": ("✅ " if ok else "⚠️ ") + msg}
    if a in ("sell", "vendre", "vente"):
        if price is None:
            return {"reply": f"⏳ Pas encore de prix pour {inst.name}."}
        ok, msg = controller.execute(inst.id, "SELL", price, "manuel")
        return {"reply": ("✅ " if ok else "⚠️ ") + msg}
    if a in ("pause", "stop"):
        controller.set_paused(inst.id, True)
        return {"reply": f"⏸️ {inst.name} : trading automatique en pause."}
    if a in ("resume", "reprendre", "start", "play"):
        controller.set_paused(inst.id, False)
        return {"reply": f"▶️ {inst.name} : trading automatique réactivé."}
    if a in ("status", "etat", "état"):
        return {"reply": _status_text(inst)}
    return {"reply": f"Commande inconnue : « {text} ». Essaie : buy, sell, pause, resume, status."}


# ----------------------------- Modèles -----------------------------

class ChatIn(BaseModel):
    message: str
    instrument: str = None


class CommandIn(BaseModel):
    action: str
    instrument: str = None


class SettingsIn(BaseModel):
    language: str = None
    strategy: str = None
    buy_threshold: float = None
    sell_threshold: float = None
    ai_weight: float = None
    ml_weight: float = None
    ai_interval: int = None
    ai_provider: str = None
    gemini_api_key: str = None
    gemini_model: str = None
    mistral_api_key: str = None
    mistral_model: str = None
    exchange: str = None
    exchange_api_key: str = None
    exchange_secret: str = None
    trading_mode: str = None
    instruments: list = None


class ExTest(BaseModel):
    exchange: str = None
    api_key: str = None
    secret: str = None


class AdventureIn(BaseModel):
    name: str = None
    enabled: bool = None
    broker: str = None
    max_capital: float = None
    instruments: list = None
    strategy: str = None
    buy_threshold: float = None
    sell_threshold: float = None
    ai_weight: float = None
    ml_weight: float = None
    ai_provider: str = None
    ai_api_key: str = None
    ai_model: str = None
    ai_prompt: str = None
    broker_key: str = None
    broker_secret: str = None
    broker_account: str = None


class AiTest(BaseModel):
    provider: str = "gemini"
    api_key: str = None
    model: str = None


class BrokerTest(BaseModel):
    broker: str = "sim"
    broker_key: str = None
    broker_secret: str = None
    broker_account: str = None


# ----------------------------- Pages -----------------------------

@app.get("/", response_class=HTMLResponse)
def dashboard():
    return (WEB_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/config", response_class=HTMLResponse)
def config_page():
    return (WEB_DIR / "config.html").read_text(encoding="utf-8")


@app.get("/adventures", response_class=HTMLResponse)
def adventures_page():
    return (WEB_DIR / "adventures.html").read_text(encoding="utf-8")


@app.get("/learning", response_class=HTMLResponse)
def learning_page():
    return (WEB_DIR / "learning.html").read_text(encoding="utf-8")


@app.get("/i18n.js")
def i18n_js():
    return Response((WEB_DIR / "i18n.js").read_text(encoding="utf-8"), media_type="application/javascript")


# ----------------------------- API marché -----------------------------

@app.get("/api/instruments")
def instruments():
    ov = [_overview(i) for i in _instruments()]
    total = sum(o["total"] for o in ov)
    initial = sum(o["initial"] for o in ov)
    global_pnl = (total / initial - 1.0) * 100.0 if initial else 0.0
    return {"instruments": [{"id": i.id, "name": i.name, "asset_class": i.asset_class} for i in _instruments()],
            "overview": ov, "global": {"total": total, "initial": initial, "pnl": global_pnl,
                                       "profit": total - initial, "language": settings.get("language")}}


@app.get("/api/state")
def state(instrument: str = None):
    inst = _resolve(instrument)
    if not inst:
        return {"error": "aucun actif"}
    conn = get_conn()
    try:
        chart_rows = conn.execute(
            "SELECT timestamp, close FROM (SELECT timestamp, close FROM prices WHERE instrument=? "
            "ORDER BY timestamp DESC LIMIT 120) ORDER BY timestamp ASC", (inst.id,)).fetchall()
        last_signal = conn.execute("SELECT * FROM signals WHERE instrument=? ORDER BY id DESC LIMIT 1", (inst.id,)).fetchone()
        trades = conn.execute("SELECT * FROM paper_trades WHERE instrument=? ORDER BY id DESC LIMIT 20", (inst.id,)).fetchall()
        signals = conn.execute("SELECT * FROM signals WHERE instrument=? ORDER BY id DESC LIMIT 20", (inst.id,)).fetchall()
        price_row = conn.execute("SELECT close FROM prices WHERE instrument=? ORDER BY timestamp DESC LIMIT 1", (inst.id,)).fetchone()
        n_candles = conn.execute("SELECT COUNT(*) AS n FROM prices WHERE instrument=?", (inst.id,)).fetchone()["n"]
    finally:
        conn.close()

    price = float(price_row["close"]) if price_row else None
    snap = controller.snapshot(inst.id)
    balance, position = snap["portfolio"]["balance"], snap["portfolio"]["position"]
    total = balance + (position * price if price else 0.0)
    pnl = (total / INITIAL_BALANCE - 1.0) * 100.0

    details = {}
    if last_signal and last_signal["details"]:
        try:
            details = json.loads(last_signal["details"])
        except (ValueError, TypeError):
            details = {}

    return {
        "instrument": {"id": inst.id, "name": inst.name, "asset_class": inst.asset_class,
                       "symbol": inst.symbol, "timeframe": inst.timeframe, "quote": inst.quote, "provider": inst.provider},
        "candles": n_candles, "price": price,
        "signal": last_signal["signal"] if last_signal else None,
        "score": last_signal["score"] if last_signal else None,
        "details": details, "paused": snap["paused"],
        "ai_enabled": ai_available(), "ai": snap["ai"],
        "trading_mode": settings.get("trading_mode"), "language": settings.get("language"),
        "portfolio": {"balance": balance, "position": position, "total": total,
                      "pnl": pnl, "profit": total - INITIAL_BALANCE, "initial": INITIAL_BALANCE},
        "chart": [{"t": r["timestamp"], "c": r["close"]} for r in chart_rows],
        "trades": [dict(r) for r in trades], "signals": [dict(r) for r in signals],
    }


@app.get("/api/trades")
def trades_feed(limit: int = 30):
    conn = get_conn()
    try:
        rows = conn.execute("SELECT instrument, timestamp, action, price, source FROM paper_trades "
                            "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    finally:
        conn.close()
    out = []
    for r in rows:
        name, cls, quote = _name(r["instrument"])
        out.append({"instrument": r["instrument"], "name": name, "asset_class": cls, "quote": quote,
                    "timestamp": r["timestamp"], "action": r["action"], "price": r["price"],
                    "source": r["source"] or "auto"})
    return {"trades": out}


@app.post("/api/command")
def command(inp: CommandIn):
    return _run_command(inp.instrument, inp.action)


@app.post("/api/chat")
def chat(inp: ChatIn):
    inst = _resolve(inp.instrument)
    msg = (inp.message or "").strip()
    if not msg:
        return {"reply": "Dis-moi quelque chose 🙂"}
    if msg.startswith("/"):
        return _run_command(inst.id if inst else None, msg)
    if not inst:
        return {"reply": "Aucun actif sélectionné."}
    if not ai_available():
        return {"reply": "🤖 IA non configurée. Commandes : /buy, /sell, /pause, /resume, /status."}
    system = ("Tu es l'assistant de trading multi-actifs de PiTradeLab. Concis et prudent. "
              "Tu conseilles mais n'exécutes PAS d'ordres (boutons ou /buy /sell). " + lang_instruction())
    try:
        reply = ask(f"Actif : {inst.name}\nContexte :\n{_context_for_ai(inst)}\n\nQuestion : {msg}", system=system)
    except Exception as e:
        reply = f"⚠️ Erreur IA : {e}"
    return {"reply": reply}


# ----------------------------- API configuration -----------------------------

@app.get("/api/catalog")
def catalog():
    return {"catalog": catalog_dicts()}


@app.get("/api/settings")
def get_settings():
    s = settings.all_settings()
    return {
        "language": s["language"], "strategy": s["strategy"],
        "buy_threshold": s["buy_threshold"], "sell_threshold": s["sell_threshold"],
        "ai_weight": s["ai_weight"], "ml_weight": s["ml_weight"], "ai_interval": s["ai_interval"],
        "ai_provider": s["ai_provider"],
        "gemini_model": s["gemini_model"], "gemini_key_set": bool(s["gemini_api_key"]),
        "mistral_model": s["mistral_model"], "mistral_key_set": bool(s["mistral_api_key"]),
        "exchange": s["exchange"], "exchange_keys_set": bool(s["exchange_api_key"] and s["exchange_secret"]),
        "trading_mode": s["trading_mode"], "instruments": s["instruments"],
        "strategies": strategies.list_strategies(), "languages": ["fr", "en", "es"],
        "ai_providers": providers_info(),
    }


@app.post("/api/settings")
def post_settings(inp: SettingsIn):
    changes = {k: v for k, v in _dump(inp).items() if v is not None}
    settings.update(changes)
    controller.sync_instruments()
    return {"ok": True}


@app.post("/api/exchange/test")
def exchange_test(inp: ExTest):
    ex = inp.exchange or settings.get("exchange")
    key = inp.api_key or settings.get("exchange_api_key")
    sec = inp.secret or settings.get("exchange_secret")
    return exchange_client.test_connection(ex, key, sec)


# ----------------------------- API aventures -----------------------------

def _adventure_overview(adv: dict) -> dict:
    insts = adventures.instruments_of(adv)
    legs, total = [], 0.0
    for inst in insts:
        snap = adventures.book.snapshot(adv["id"], inst.id)
        price = _last_price(inst.id)
        p = snap["portfolio"]
        value = p["balance"] + (p["position"] * price if price else 0.0)
        total += value
        legs.append({"id": inst.id, "name": inst.name, "asset_class": inst.asset_class,
                     "quote": inst.quote, "price": price, "value": value,
                     "balance": p["balance"], "position": p["position"],
                     "ai": {"sentiment": (snap["ai"] or {}).get("sentiment"),
                            "score": (snap["ai"] or {}).get("score")}})
    initial = adv.get("max_capital", 0.0)
    pnl = (total / initial - 1.0) * 100.0 if initial else 0.0
    pub = adventures.public(adv)
    pub.update({"total": total, "initial": initial, "profit": total - initial, "pnl": pnl, "legs": legs})
    real = adventures.real_account(adv)  # None si simulation, sinon état réel du compte courtier
    if real is not None:
        pub["real"] = real
    return pub


@app.get("/api/adventures")
def list_adventures():
    return {"adventures": [_adventure_overview(a) for a in adventures.list_raw()],
            "brokers": adventures.BROKERS, "providers": providers_info(),
            "strategies": strategies.list_strategies(), "catalog": catalog_dicts(),
            "language": settings.get("language")}


@app.post("/api/adventures")
def create_adventure(inp: AdventureIn):
    changes = {k: v for k, v in _dump(inp).items() if v is not None}
    adv = adventures.create(changes)
    adventures.book.load()
    return {"ok": True, "adventure": adv}


@app.post("/api/adventures/{adv_id}")
def update_adventure(adv_id: str, inp: AdventureIn):
    changes = {k: v for k, v in _dump(inp).items() if v is not None}
    adv = adventures.update(adv_id, changes)
    if not adv:
        return {"ok": False, "error": "Aventure introuvable."}
    adventures.book.load()
    return {"ok": True, "adventure": adv}


@app.delete("/api/adventures/{adv_id}")
def delete_adventure(adv_id: str):
    return {"ok": adventures.delete(adv_id)}


@app.post("/api/adventures/{adv_id}/test-broker")
def test_broker(adv_id: str):
    adv = adventures.get(adv_id)
    if not adv:
        return {"ok": False, "error": "Aventure introuvable."}
    return brokers.test_connection(adv)


@app.post("/api/ai/test")
def test_ai(inp: AiTest):
    return llm_verify(inp.provider, inp.api_key, inp.model)


@app.post("/api/broker/test")
def test_broker_creds(inp: BrokerTest):
    """Teste des identifiants courtier saisis (avant enregistrement)."""
    adv = {"broker": inp.broker, "broker_key": inp.broker_key or "",
           "broker_secret": inp.broker_secret or "", "broker_account": inp.broker_account or ""}
    return brokers.test_connection(adv)


# ----------------------------- API apprentissage / ML -----------------------------

@app.get("/api/learning")
def learning_summary():
    return learning.summary()


@app.get("/api/ml/status")
def ml_status():
    return ml.get_status()


@app.post("/api/ml/train")
def ml_train(instrument: str = None):
    if not ml.available():
        return {"ok": False, "error": ml.get_status().get("error") or "ML indisponible."}
    if instrument:
        inst = _resolve(instrument)
        threading.Thread(target=ml.train_instrument, args=(instrument, inst.name if inst else instrument),
                         daemon=True, name="ml-train-one").start()
    else:
        threading.Thread(target=ml.train_all, daemon=True, name="ml-train-all").start()
    return {"ok": True, "message": "Entraînement lancé."}


@app.get("/health")
def health():
    return {"status": "ok"}
