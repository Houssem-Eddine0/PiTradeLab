"""
Configuration centrale — tout est pilotable par variables d'environnement
(donc configurable dans Docker sans rebuild). Valeurs par défaut raisonnables.
"""
import os

# Charge un éventuel fichier .env (pratique pour les lancements locaux ;
# dans Docker les variables viennent de docker-compose).
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _f(name: str, default: float) -> float:
    return float(os.getenv(name, default))


def _i(name: str, default: int) -> int:
    return int(os.getenv(name, default))


# --- Marché ---
# Exchange ccxt par défaut pour la collecte des cryptos. Surchargeable à chaud
# depuis la page de configuration (settings.exchange), cette valeur n'est que le
# point de départ. Les actifs/timeframes sont définis par instrument (app/instruments.py),
# plus par SYMBOL/TIMEFRAME globaux.
EXCHANGE = os.getenv("EXCHANGE", "binance")      # n'importe quel exchange ccxt (binance, kraken, binanceus...)

# --- Base de données ---
DB_PATH = os.getenv("DB_PATH", "data/market.db")

# --- Paper trading ---
INITIAL_BALANCE = _f("INITIAL_BALANCE", 1000.0)  # capital virtuel de départ (devise de quote, ex: USDT)
FEE_RATE = _f("FEE_RATE", 0.001)                 # frais simulés par ordre (0.1%)

# --- Cadence (secondes) ---
COLLECTION_INTERVAL = _i("COLLECTION_INTERVAL", 60)
TRADING_INTERVAL = _i("TRADING_INTERVAL", 60)

# --- Paramètres de stratégie ---
RSI_PERIOD = _i("RSI_PERIOD", 14)
MA_SHORT = _i("MA_SHORT", 20)
MA_LONG = _i("MA_LONG", 50)
BUY_THRESHOLD = _f("BUY_THRESHOLD", 0.35)        # score >= seuil -> BUY
SELL_THRESHOLD = _f("SELL_THRESHOLD", -0.35)     # score <= seuil -> SELL

MIN_ROWS_REQUIRED = _i("MIN_ROWS_REQUIRED", 100)  # bougies min. avant de trader (MA_LONG + marge)
CANDLE_FETCH_LIMIT = _i("CANDLE_FETCH_LIMIT", 100)  # bougies récupérées à chaque collecte (auto-backfill)

# --- Clés API exchange (OPTIONNELLES) ---
# Inutiles pour le paper trading et les données publiques.
# À renseigner uniquement pour du trading réel.
API_KEY = os.getenv("EXCHANGE_API_KEY", "")
API_SECRET = os.getenv("EXCHANGE_SECRET", "")

# --- Intelligence artificielle (Gemini) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
AI_INTERVAL = _i("AI_INTERVAL", 1800)            # fréquence d'analyse IA par actif (s) — 30 min (quota-friendly multi-actifs)
AI_WEIGHT = _f("AI_WEIGHT", 0.5)                 # poids de l'avis IA dans le score final [0..1]

# --- News ---
NEWS_ENABLED = os.getenv("NEWS_ENABLED", "true").lower() == "true"
NEWS_RSS_URL = os.getenv("NEWS_RSS_URL", "https://cointelegraph.com/rss")

# --- Machine Learning (Phase 4) ---
ML_ENABLED = os.getenv("ML_ENABLED", "true").lower() == "true"
# Entraînement = scikit-learn (lourd) → à faire sur PC. Sur Pi Zero, laisser FALSE :
# le bot charge alors le modèle portable (JSON) entraîné sur PC et fait l'INFÉRENCE
# en numpy pur (sans scikit-learn).
ML_TRAIN_ENABLED = os.getenv("ML_TRAIN_ENABLED", "true").lower() == "true"
ML_MODEL = os.getenv("ML_MODEL", "mlp")      # "mlp" (réseau de neurones) | "logreg" (léger)
ML_INTERVAL = _i("ML_INTERVAL", 1800)        # ré-entraînement / ré-inférence périodique (s)
ML_MIN_SAMPLES = _i("ML_MIN_SAMPLES", 200)   # échantillons min. avant d'entraîner
ML_HORIZON = _i("ML_HORIZON", 10)            # horizon du label : hausse/baisse dans N bougies
ML_WEIGHT = _f("ML_WEIGHT", 0.0)             # poids de la proba ML dans le score final [0..1] (0 = désactivé)
ML_DIR = os.getenv("ML_DIR", os.path.join(os.path.dirname(DB_PATH) or ".", "models"))
