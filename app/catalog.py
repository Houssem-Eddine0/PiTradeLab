"""
Catalogue des instruments sélectionnables depuis la page de configuration.
L'utilisateur en choisit jusqu'à 5. Sert aussi à résoudre le nom d'un actif
historique (déjà tradé mais plus sélectionné).
"""
from dataclasses import asdict

from app.instruments import Instrument

CATALOG = [
    # Crypto (ccxt / Binance, temps réel)
    Instrument("BTC",    "Bitcoin",     "crypto",    "ccxt",     "BTC/USDT",  "1m", "USDT"),
    Instrument("ETH",    "Ethereum",    "crypto",    "ccxt",     "ETH/USDT",  "1m", "USDT"),
    Instrument("SOL",    "Solana",      "crypto",    "ccxt",     "SOL/USDT",  "1m", "USDT"),
    Instrument("BNB",    "BNB",         "crypto",    "ccxt",     "BNB/USDT",  "1m", "USDT"),
    Instrument("XRP",    "XRP",         "crypto",    "ccxt",     "XRP/USDT",  "1m", "USDT"),
    # Matières premières (yfinance)
    Instrument("GOLD",   "Or",          "commodity", "yfinance", "GC=F",      "5m", "USD"),
    Instrument("SILVER", "Argent",      "commodity", "yfinance", "SI=F",      "5m", "USD"),
    Instrument("OIL",    "Pétrole WTI", "commodity", "yfinance", "CL=F",      "5m", "USD"),
    # Actions (yfinance)
    Instrument("AAPL",   "Apple",       "stock",     "yfinance", "AAPL",      "5m", "USD"),
    Instrument("TSLA",   "Tesla",       "stock",     "yfinance", "TSLA",      "5m", "USD"),
    Instrument("MSFT",   "Microsoft",   "stock",     "yfinance", "MSFT",      "5m", "USD"),
    Instrument("NVDA",   "Nvidia",      "stock",     "yfinance", "NVDA",      "5m", "USD"),
    Instrument("AMZN",   "Amazon",      "stock",     "yfinance", "AMZN",      "5m", "USD"),
    Instrument("GOOGL",  "Google",      "stock",     "yfinance", "GOOGL",     "5m", "USD"),
    # Devises (yfinance)
    Instrument("EURUSD", "EUR/USD",     "forex",     "yfinance", "EURUSD=X",  "5m", "USD"),
    Instrument("GBPUSD", "GBP/USD",     "forex",     "yfinance", "GBPUSD=X",  "5m", "USD"),
    Instrument("USDJPY", "USD/JPY",     "forex",     "yfinance", "USDJPY=X",  "5m", "JPY"),
    # Indices (yfinance)
    Instrument("SP500",  "S&P 500",     "index",     "yfinance", "^GSPC",     "5m", "USD"),
    Instrument("NASDAQ", "Nasdaq 100",  "index",     "yfinance", "^NDX",      "5m", "USD"),
]

CATALOG_BY_ID = {i.id: i for i in CATALOG}


def as_dicts():
    return [asdict(i) for i in CATALOG]
