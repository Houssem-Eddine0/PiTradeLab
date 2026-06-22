"""
État partagé thread-safe — un portefeuille INDÉPENDANT par instrument.

Portefeuilles créés dynamiquement (les actifs suivis peuvent changer depuis la
page de configuration). Source de vérité unique, manipulée sous verrou par le
thread `trader` (ordres auto) et par les endpoints web (ordres manuels).

En mode "live", un ordre ccxt déclenche AUSSI un ordre réel sur l'exchange
(la comptabilité affichée reste celle du paper trading, pour rester cohérente).
"""
import logging
import threading
import time

from app import config, settings
from app.database import get_conn

log = logging.getLogger("state")


class Controller:
    def __init__(self):
        self._lock = threading.RLock()
        self.portfolios = {}
        self.paused = {}
        self.ai = {}

    def _ensure(self, iid: str):
        if iid not in self.portfolios:
            self.portfolios[iid] = {"balance": config.INITIAL_BALANCE, "position": 0.0}
            self.paused.setdefault(iid, False)
            self.ai.setdefault(iid, {})

    def sync_instruments(self):
        with self._lock:
            for inst in settings.get_instruments():
                self._ensure(inst.id)

    def load(self):
        conn = get_conn()
        try:
            ids = {i.id for i in settings.get_instruments()}
            ids |= {r["instrument"] for r in conn.execute("SELECT DISTINCT instrument FROM paper_trades")}
            with self._lock:
                for iid in ids:
                    self._ensure(iid)
                    row = conn.execute(
                        "SELECT balance, position FROM paper_trades WHERE instrument=? ORDER BY id DESC LIMIT 1",
                        (iid,),
                    ).fetchone()
                    if row:
                        self.portfolios[iid] = {"balance": float(row["balance"]), "position": float(row["position"])}
        finally:
            conn.close()

    def _maybe_live(self, iid: str, action: str):
        """Passe un ordre réel si le mode live est actif et l'actif est sur ccxt.

        La taille de l'ordre est calculée à partir du SOLDE RÉEL du compte
        (tout-ou-rien, comme la compta papier) — jamais à partir du portefeuille
        virtuel, qui n'a aucun lien avec les fonds réels.
        """
        if settings.get("trading_mode") != "live":
            return
        inst = next((i for i in settings.get_instruments() if i.id == iid), None)
        if not inst or inst.provider != "ccxt":
            return
        key, secret = settings.get("exchange_api_key"), settings.get("exchange_secret")
        if not key or not secret:
            return
        from app import exchange_client
        ex = settings.get("exchange")
        amount = exchange_client.live_amount(ex, key, secret, inst.symbol, action.lower())
        if not amount or amount <= 0:
            log.warning("ordre live %s %s ignoré : solde réel insuffisant", action, iid)
            return
        exchange_client.place_order(ex, key, secret, inst.symbol, action.lower(), amount)

    def execute(self, iid: str, action: str, price: float, source: str = "auto"):
        with self._lock:
            self._ensure(iid)
            p = self.portfolios[iid]
            if action == "BUY":
                if p["balance"] <= 0:
                    return False, f"{iid} : déjà investi (aucune liquidité)."
                amount = (p["balance"] * (1 - config.FEE_RATE)) / price
                p["position"] = amount
                p["balance"] = 0.0
            elif action == "SELL":
                if p["position"] <= 0:
                    return False, f"{iid} : aucune position à vendre."
                amount = p["position"]
                p["balance"] = p["position"] * price * (1 - config.FEE_RATE)
                p["position"] = 0.0
            else:
                return False, f"Action inconnue : {action}"

            conn = get_conn()
            try:
                conn.execute(
                    "INSERT INTO paper_trades (instrument, timestamp, action, price, balance, position, source) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (iid, int(time.time() * 1000), action, price, p["balance"], p["position"], source),
                )
                conn.commit()
            finally:
                conn.close()

        # ordre réel éventuel (hors verrou)
        try:
            self._maybe_live(iid, action)
        except Exception as e:
            log.warning("ordre live %s %s -> %s", action, iid, e)

        mode = settings.get("trading_mode")
        return True, f"{action} {iid} exécuté à {price:.4f} ({source}, {mode})."

    def set_paused(self, iid: str, value: bool):
        with self._lock:
            self._ensure(iid)
            self.paused[iid] = bool(value)

    def set_ai(self, iid: str, data: dict):
        with self._lock:
            self._ensure(iid)
            self.ai[iid] = data

    def snapshot(self, iid: str) -> dict:
        with self._lock:
            self._ensure(iid)
            return {
                "portfolio": dict(self.portfolios[iid]),
                "paused": self.paused.get(iid, False),
                "ai": dict(self.ai.get(iid, {})),
            }


controller = Controller()
