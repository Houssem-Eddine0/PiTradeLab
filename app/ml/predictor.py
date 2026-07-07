"""
Inférence ML SANS scikit-learn — numpy pur.

Le modèle entraîné sur PC (scikit-learn) est exporté en JSON portable (poids +
normalisation). Sur Raspberry Pi, on recharge ce JSON et on calcule la probabilité
de hausse avec numpy uniquement → pas besoin d'installer scikit-learn sur le Pi.

Format portable :
  {"type": "mlp"|"logreg", "features": [...],
   "mean": [...], "scale": [...],                # StandardScaler
   "coefs": [W1, W2, ...], "intercepts": [b1, ...]}  # couches (relu entre, sigmoïde finale)
"""
import numpy as np


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def proba_up(portable: dict, x_row) -> float:
    """Probabilité de hausse pour une ligne de features (ordre = portable['features'])."""
    x = np.asarray(x_row, dtype=float)
    mean = np.asarray(portable["mean"], dtype=float)
    scale = np.asarray(portable["scale"], dtype=float)
    scale = np.where(scale == 0, 1.0, scale)
    a = (x - mean) / scale

    coefs = portable["coefs"]
    intercepts = portable["intercepts"]
    last = len(coefs) - 1
    for i, (W, b) in enumerate(zip(coefs, intercepts)):
        a = a @ np.asarray(W, dtype=float) + np.asarray(b, dtype=float)
        if i < last:
            a = np.maximum(a, 0.0)  # ReLU entre couches cachées

    out = a if np.ndim(a) == 0 else a.reshape(-1)[0]
    return float(_sigmoid(out))
