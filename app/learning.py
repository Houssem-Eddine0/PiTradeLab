"""
Étape 4 — Fenêtre d'apprentissage : que retient le système de ses trades ?

Calcule, à partir des trades enregistrés (bot de base + aventures) et des analyses
IA, des indicateurs de performance LISIBLES :
  - taux de réussite (win rate) et P&L réalisé par actif / par aventure,
  - courbe de P&L cumulé (la « courbe d'apprentissage » du bot),
  - évaluation de l'IA : ses avis (bullish/bearish) se sont-ils vérifiés ?

Aucune dépendance lourde : lecture SQL + calcul pur.
"""
from app import adventures, settings
from app.config import INITIAL_BALANCE
from app.database import get_conn


def _ms(ts):
    """Normalise un timestamp en millisecondes (anciennes lignes en secondes)."""
    ts = int(ts)
    return ts if ts > 1_000_000_000_000 else ts * 1000


def _round_trips(trades, baseline):
    """trades : lignes (timestamp, action, price, balance) triées par id ASC.
    Reconstruit les allers-retours (BUY→SELL) et leur P&L réalisé."""
    cash = baseline
    wins = n = 0
    realized = 0.0
    curve = []  # (ts, pnl_cumulé)
    for t in trades:
        if t["action"] == "SELL":
            pnl = float(t["balance"]) - cash
            realized += pnl
            n += 1
            if pnl > 0:
                wins += 1
            cash = float(t["balance"])
            curve.append({"t": _ms(t["timestamp"]), "cum": round(realized, 4)})
    return {"round_trips": n, "wins": wins,
            "win_rate": round(100.0 * wins / n, 1) if n else None,
            "realized_pnl": round(realized, 4)}, curve


def _last_price(conn, iid):
    row = conn.execute("SELECT close FROM prices WHERE instrument=? ORDER BY timestamp DESC LIMIT 1", (iid,)).fetchone()
    return float(row["close"]) if row else None


def base_performance():
    conn = get_conn()
    try:
        out, curve = [], []
        cum = 0.0
        insts = {i.id: i for i in settings.get_instruments()}
        ids = [r["instrument"] for r in conn.execute("SELECT DISTINCT instrument FROM paper_trades")]
        for iid in ids:
            trades = conn.execute(
                "SELECT timestamp, action, price, balance, position FROM paper_trades "
                "WHERE instrument=? ORDER BY id ASC", (iid,)).fetchall()
            stats, _ = _round_trips(trades, INITIAL_BALANCE)
            last = conn.execute(
                "SELECT balance, position FROM paper_trades WHERE instrument=? ORDER BY id DESC LIMIT 1",
                (iid,)).fetchone()
            price = _last_price(conn, iid)
            value = INITIAL_BALANCE
            if last:
                value = float(last["balance"]) + (float(last["position"]) * price if price else 0.0)
            name = insts[iid].name if iid in insts else iid
            stats.update({"id": iid, "name": name, "value": round(value, 2),
                          "pnl_pct": round((value / INITIAL_BALANCE - 1.0) * 100.0, 2)})
            out.append(stats)
        # courbe de P&L cumulé global : somme des P&L réalisés (par actif) dans l'ordre temporel
        per_inst_cash = {}
        rows = conn.execute(
            "SELECT instrument, timestamp, action, balance FROM paper_trades ORDER BY timestamp ASC").fetchall()
        for r in rows:
            iid = r["instrument"]
            if r["action"] == "SELL":
                prev = per_inst_cash.get(iid, INITIAL_BALANCE)
                cum += float(r["balance"]) - prev
                per_inst_cash[iid] = float(r["balance"])
                curve.append({"t": _ms(r["timestamp"]), "cum": round(cum, 4)})
        return out, curve
    finally:
        conn.close()


def adventure_performance():
    out = []
    conn = get_conn()
    try:
        for adv in adventures.list_raw():
            insts = adventures.instruments_of(adv)
            n_assets = max(1, len(insts))
            share = adv.get("max_capital", 0.0) / n_assets
            agg = {"round_trips": 0, "wins": 0, "realized_pnl": 0.0}
            value = 0.0
            for inst in insts:
                trades = conn.execute(
                    "SELECT timestamp, action, price, balance, position FROM adventure_trades "
                    "WHERE adventure_id=? AND instrument=? ORDER BY id ASC", (adv["id"], inst.id)).fetchall()
                stats, _ = _round_trips(trades, share)
                agg["round_trips"] += stats["round_trips"]
                agg["wins"] += stats["wins"]
                agg["realized_pnl"] += stats["realized_pnl"]
                last = conn.execute(
                    "SELECT balance, position FROM adventure_trades WHERE adventure_id=? AND instrument=? "
                    "ORDER BY id DESC LIMIT 1", (adv["id"], inst.id)).fetchone()
                price = _last_price(conn, inst.id)
                if last:
                    value += float(last["balance"]) + (float(last["position"]) * price if price else 0.0)
                else:
                    value += share
            n = agg["round_trips"]
            out.append({"id": adv["id"], "name": adv["name"], "enabled": adv.get("enabled"),
                        "round_trips": n, "wins": agg["wins"],
                        "win_rate": round(100.0 * agg["wins"] / n, 1) if n else None,
                        "realized_pnl": round(agg["realized_pnl"], 4),
                        "value": round(value, 2), "initial": adv.get("max_capital", 0.0),
                        "pnl_pct": round((value / adv["max_capital"] - 1.0) * 100.0, 2) if adv.get("max_capital") else 0.0})
        return out
    finally:
        conn.close()


def ai_evaluation(horizon_ms=3_600_000):
    """L'IA avait-elle raison ? Compare le signe du score IA au rendement réalisé
    sur l'heure qui suit l'analyse. (horizon par défaut : 1 h)"""
    conn = get_conn()
    try:
        by_inst = {}
        total = hits = 0
        rows = conn.execute(
            "SELECT instrument, timestamp, score FROM ai_analysis WHERE score IS NOT NULL ORDER BY id ASC").fetchall()
        for r in rows:
            if r["score"] is None or abs(r["score"]) < 0.05:
                continue  # avis neutre : non évaluable
            t0 = _ms(r["timestamp"])
            p0 = conn.execute(
                "SELECT close FROM prices WHERE instrument=? AND timestamp<=? ORDER BY timestamp DESC LIMIT 1",
                (r["instrument"], t0)).fetchone()
            p1 = conn.execute(
                "SELECT close FROM prices WHERE instrument=? AND timestamp>=? ORDER BY timestamp ASC LIMIT 1",
                (r["instrument"], t0 + horizon_ms)).fetchone()
            if not p0 or not p1 or not p0["close"]:
                continue
            ret = float(p1["close"]) / float(p0["close"]) - 1.0
            correct = (r["score"] > 0 and ret > 0) or (r["score"] < 0 and ret < 0)
            d = by_inst.setdefault(r["instrument"], {"n": 0, "hits": 0})
            d["n"] += 1
            d["hits"] += 1 if correct else 0
            total += 1
            hits += 1 if correct else 0
        for iid, d in by_inst.items():
            d["accuracy"] = round(100.0 * d["hits"] / d["n"], 1) if d["n"] else None
        return {"n": total, "accuracy": round(100.0 * hits / total, 1) if total else None,
                "by_instrument": by_inst, "horizon_min": horizon_ms // 60000}
    finally:
        conn.close()


def summary():
    base, curve = base_performance()
    return {"base": base, "adventures": adventure_performance(),
            "ai": ai_evaluation(), "curve": curve, "initial_per_asset": INITIAL_BALANCE}
