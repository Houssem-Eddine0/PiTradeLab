"""
Définition des instruments suivis par le bot (multi-actifs).

Liste par défaut couvrant les 4 classes demandées. Personnalisable via la
variable d'environnement INSTRUMENTS (JSON), sinon valeurs par défaut.
"""
import json
import os
from dataclasses import asdict, dataclass


@dataclass
class Instrument:
    id: str           # identifiant court unique : "BTC", "GOLD"...
    name: str         # nom affiché : "Bitcoin", "Or"...
    asset_class: str  # crypto | commodity | stock | forex | index
    provider: str     # "ccxt" | "yfinance"
    symbol: str       # symbole propre au fournisseur
    timeframe: str    # "1m", "5m"...
    quote: str        # devise de cotation (affichage) : "USDT", "USD"


DEFAULT_INSTRUMENTS = [
    Instrument("BTC",    "Bitcoin",  "crypto",    "ccxt",     "BTC/USDT",  "1m", "USDT"),
    Instrument("GOLD",   "Or",       "commodity", "yfinance", "GC=F",      "5m", "USD"),
    Instrument("AAPL",   "Apple",    "stock",     "yfinance", "AAPL",      "5m", "USD"),
    Instrument("EURUSD", "EUR/USD",  "forex",     "yfinance", "EURUSD=X",  "5m", "USD"),
]


def _load():
    raw = os.getenv("INSTRUMENTS")
    if raw:
        try:
            return [Instrument(**d) for d in json.loads(raw)]
        except Exception:
            pass
    return DEFAULT_INSTRUMENTS


INSTRUMENTS = _load()
BY_ID = {inst.id: inst for inst in INSTRUMENTS}


def as_dicts():
    return [asdict(i) for i in INSTRUMENTS]
