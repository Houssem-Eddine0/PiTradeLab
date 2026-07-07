"""
Étape 5 — extraction de features pour le modèle ML.

À partir des bougies OHLCV d'un actif, construit des features numériques et un
label binaire : le prix est-il PLUS HAUT dans `horizon` bougies (1) ou non (0) ?
Le modèle apprend donc une PROBABILITÉ de hausse — pas un ordre BUY/SELL direct.

Dépend de pandas + ta (déjà dans requirements).
"""
import math

import pandas as pd
from ta.momentum import RSIIndicator

from app.config import MA_LONG, MA_SHORT, ML_HORIZON, RSI_PERIOD

FEATURE_COLS = ["ret1", "ret5", "ma_ratio", "rsi", "vol_ratio", "volatility", "roc", "hour_sin", "hour_cos"]


def build(df: pd.DataFrame, horizon: int = ML_HORIZON, with_label: bool = True) -> pd.DataFrame:
    """df : colonnes timestamp(ms), open, high, low, close, volume (ordre ASC)."""
    df = df.copy()
    close = df["close"].astype(float)
    volume = df["volume"].astype(float)

    df["ret1"] = close.pct_change(1)
    df["ret5"] = close.pct_change(5)

    ma_s = close.rolling(MA_SHORT).mean()
    ma_l = close.rolling(MA_LONG).mean()
    df["ma_ratio"] = ma_s / ma_l - 1.0

    df["rsi"] = RSIIndicator(close, window=RSI_PERIOD).rsi() / 100.0

    vol_ma = volume.rolling(MA_SHORT).mean()
    df["vol_ratio"] = volume / vol_ma

    df["volatility"] = close.pct_change().rolling(MA_SHORT).std()
    df["roc"] = close / close.shift(10) - 1.0

    hours = pd.to_datetime(df["timestamp"], unit="ms", utc=True).dt.hour
    df["hour_sin"] = (2 * math.pi * hours / 24).apply(math.sin)
    df["hour_cos"] = (2 * math.pi * hours / 24).apply(math.cos)

    cols = list(FEATURE_COLS)
    if with_label:
        future = close.shift(-horizon)
        df["label"] = (future > close).astype("float")
        df.loc[future.isna(), "label"] = float("nan")  # pas de futur → pas de label
        cols = cols + ["label"]

    df = df.replace([float("inf"), float("-inf")], pd.NA)
    df = df.dropna(subset=cols)
    return df
