"""
Étape 5 — entraînement du modèle ML (côté PC).

scikit-learn est importé PARESSEUSEMENT (seulement au moment d'entraîner) pour ne
PAS le charger en mémoire au démarrage — crucial sur Raspberry Pi où l'on ne fait
que de l'inférence (numpy pur, voir predictor.py). `available()` détecte la présence
de scikit-learn SANS l'importer.

Modèles : "mlp" (réseau de neurones, courbe de perte) ou "logreg" (léger).
L'entraînement renvoie aussi un dict PORTABLE (poids + scaler) sérialisable en JSON,
utilisable pour l'inférence sans scikit-learn.
"""
import importlib.util
import logging

from app.config import ML_MODEL
from app.ml.features import FEATURE_COLS

log = logging.getLogger("ml")


def available() -> bool:
    """scikit-learn est-il installable/présent ? (sans l'importer)"""
    return importlib.util.find_spec("sklearn") is not None


def _build_estimator(kind: str):
    from sklearn.linear_model import LogisticRegression
    from sklearn.neural_network import MLPClassifier
    if kind == "logreg":
        return ("logreg", LogisticRegression(max_iter=1000))
    return ("mlp", MLPClassifier(hidden_layer_sizes=(32, 16), activation="relu",
                                 max_iter=400, early_stopping=False, random_state=0))


def _portable(kind, scaler, est) -> dict:
    """Sérialise scaler + poids en structures JSON (listes), pour predictor.py."""
    if kind == "logreg":
        coefs = [est.coef_.T.tolist()]          # (n,1)
        intercepts = [est.intercept_.tolist()]  # (1,)
    else:
        coefs = [w.tolist() for w in est.coefs_]
        intercepts = [b.tolist() for b in est.intercepts_]
    return {"type": kind, "features": list(FEATURE_COLS),
            "mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist(),
            "coefs": coefs, "intercepts": intercepts}


def train(feat_df):
    """Entraîne sur features+label. Renvoie (portable_dict, metrics)."""
    if not available():
        raise RuntimeError("scikit-learn indisponible (entraînement à faire sur PC)")
    from sklearn.metrics import accuracy_score
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler

    X = feat_df[FEATURE_COLS].astype(float).values
    y = feat_df["label"].astype(int).values
    n = len(y)
    if len(set(y.tolist())) < 2:
        raise RuntimeError("une seule classe présente — données insuffisantes")

    baseline = max((y == 0).mean(), (y == 1).mean())
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, shuffle=False)

    scaler = StandardScaler().fit(X_tr)
    kind, est = _build_estimator(ML_MODEL)
    est.fit(scaler.transform(X_tr), y_tr)
    acc = float(accuracy_score(y_te, est.predict(scaler.transform(X_te))))
    loss_curve = [float(v) for v in getattr(est, "loss_curve_", [])]

    return _portable(kind, scaler, est), {
        "model_type": kind, "n_samples": int(n), "accuracy": round(acc, 4),
        "baseline": round(float(baseline), 4), "loss_curve": loss_curve}
