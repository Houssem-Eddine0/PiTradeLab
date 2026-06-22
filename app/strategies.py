"""
Registre de stratégies techniques.

Chaque stratégie : compute(df) -> (score: float dans [-1, 1], details: dict).
Le trader applique ensuite les seuils (settings) pour décider BUY / SELL / HOLD,
et fusionne éventuellement avec le score IA.
"""
import pandas as pd
from ta.momentum import RSIIndicator

from app.config import MA_LONG, MA_SHORT, RSI_PERIOD


def _clamp(x):
    return round(max(-1.0, min(1.0, x)), 3)


def ma_rsi_volume(df: pd.DataFrame):
    """Tendance (MA) + momentum (RSI) + confirmation par le volume."""
    score = 0.0
    details = {}
    close = df["close"].astype(float)
    volume = df["volume"].astype(float)

    ma_short = close.rolling(MA_SHORT).mean().iloc[-1]
    ma_long = close.rolling(MA_LONG).mean().iloc[-1]
    if pd.isna(ma_short) or pd.isna(ma_long):
        return 0.0, {"error": f"pas assez de données ({MA_LONG} bougies requises)"}

    details["ma_short"] = round(ma_short, 4)
    details["ma_long"] = round(ma_long, 4)
    if ma_short > ma_long:
        score += 0.40
        details["trend"] = "bullish"
    else:
        score -= 0.40
        details["trend"] = "bearish"

    rsi = RSIIndicator(close, window=RSI_PERIOD).rsi().iloc[-1]
    if pd.isna(rsi):
        rsi = 50.0
    details["rsi"] = round(rsi, 2)
    if rsi < 30:
        score += 0.40
    elif rsi > 70:
        score -= 0.40
    elif rsi > 55:
        score += 0.10
    elif rsi < 45:
        score -= 0.10

    vol_ma = volume.rolling(MA_SHORT).mean().iloc[-1]
    vol_now = volume.iloc[-1]
    vol_ratio = (vol_now / vol_ma) if vol_ma and vol_ma > 0 else 1.0
    details["volume_ratio"] = round(vol_ratio, 2)
    if vol_ratio >= 1.5:
        score *= 1.2
    elif vol_ratio <= 0.5:
        score *= 0.7

    return _clamp(score), details


def rsi_reversion(df: pd.DataFrame):
    """Retour à la moyenne : achète survendu (RSI bas), vend suracheté (RSI haut)."""
    close = df["close"].astype(float)
    rsi = RSIIndicator(close, window=RSI_PERIOD).rsi().iloc[-1]
    if pd.isna(rsi):
        rsi = 50.0
    # rsi 30 -> +1 (achat), rsi 70 -> -1 (vente), rsi 50 -> 0
    score = (50.0 - rsi) / 20.0
    return _clamp(score), {"rsi": round(rsi, 2), "strategy": "rsi_reversion"}


def ma_crossover(df: pd.DataFrame):
    """Suivi de tendance pur : écart relatif entre MA courte et MA longue."""
    close = df["close"].astype(float)
    ma_short = close.rolling(MA_SHORT).mean().iloc[-1]
    ma_long = close.rolling(MA_LONG).mean().iloc[-1]
    if pd.isna(ma_short) or pd.isna(ma_long) or ma_long == 0:
        return 0.0, {"error": f"pas assez de données ({MA_LONG} bougies requises)"}
    diff = (ma_short - ma_long) / ma_long
    score = diff * 50.0  # ~2 % d'écart sature le score
    return _clamp(score), {
        "ma_short": round(ma_short, 4), "ma_long": round(ma_long, 4),
        "trend": "bullish" if diff > 0 else "bearish",
    }


def momentum(df: pd.DataFrame, window: int = 10):
    """Momentum : variation de prix sur les `window` dernières bougies."""
    close = df["close"].astype(float)
    if len(close) <= window or close.iloc[-window - 1] == 0:
        return 0.0, {"error": "pas assez de données"}
    roc = close.iloc[-1] / close.iloc[-window - 1] - 1.0
    score = roc * 25.0  # ~4 % de variation sature le score
    return _clamp(score), {"roc_pct": round(roc * 100, 3), "trend": "bullish" if roc > 0 else "bearish"}


STRATEGIES = {
    "ma_rsi_volume": ("MA + RSI + Volume", ma_rsi_volume),
    "rsi_reversion": ("RSI retour à la moyenne", rsi_reversion),
    "ma_crossover":  ("Croisement de moyennes", ma_crossover),
    "momentum":      ("Momentum", momentum),
}


def get(name):
    return STRATEGIES.get(name, STRATEGIES["ma_rsi_volume"])[1]


def list_strategies():
    return [{"id": k, "name": v[0]} for k, v in STRATEGIES.items()]
