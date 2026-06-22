"""
Récupération des actualités via flux RSS, choisi selon la classe d'actif.
Parsing en bibliothèque standard — aucune dépendance supplémentaire.
"""
import logging
import xml.etree.ElementTree as ET

import requests

from app.config import NEWS_RSS_URL

log = logging.getLogger("news")

# Flux par classe d'actif (le crypto a sa propre source spécialisée).
FEEDS = {
    "crypto":    "https://cointelegraph.com/rss",
    "commodity": "https://www.investing.com/rss/commodities.rss",
    "stock":     "https://finance.yahoo.com/news/rssindex",
    "index":     "https://finance.yahoo.com/news/rssindex",
    "forex":     "https://www.investing.com/rss/forex.rss",
}


def fetch_headlines(asset_class: str = None, limit: int = 8):
    """Titres d'actualité récents pour la classe d'actif (vide si erreur)."""
    url = FEEDS.get(asset_class, NEWS_RSS_URL)
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "PiTradeLab/1.0"})
        r.raise_for_status()
        root = ET.fromstring(r.content)
        titles = []
        for item in root.findall(".//item")[:limit]:
            title = item.findtext("title")
            if title:
                titles.append(title.strip())
        return titles
    except Exception as e:
        log.warning("[%s] erreur récupération news -> %s", asset_class, e)
        return []
