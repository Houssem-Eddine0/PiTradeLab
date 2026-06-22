# ⚡ PiTradeLab

Laboratoire de trading algorithmique **multi-actifs** — bot de **paper trading**
dockerisé avec **dashboard web temps réel** et **couche IA (Gemini)**. Tourne sur
n'importe quelle machine (PC, serveur, Raspberry Pi) via Docker.

> Objectif : apprendre Python, l'architecture logicielle, la finance quantitative
> et le machine learning appliqué — en construisant un vrai système évolutif.

### 🌍 Classes d'actifs suivies (par défaut)
| Actif | Classe | Fournisseur | Symbole |
|-------|--------|-------------|---------|
| Bitcoin | crypto | ccxt (Binance) | `BTC/USDT` |
| Or | matière première | yfinance | `GC=F` |
| Apple | action (bourse) | yfinance | `AAPL` |
| EUR/USD | devises (forex) | yfinance | `EURUSD=X` |

Chaque actif a son **portefeuille indépendant** (capital de départ identique) →
on compare la performance de la stratégie sur chaque marché. Personnalisable via
la variable `INSTRUMENTS` (cf. `.env.example`) : ajoute Ethereum, Tesla, S&P 500…

> ℹ️ Données crypto temps réel ; or/actions/forex via Yahoo Finance (légèrement
> différées, et figées hors heures d'ouverture des marchés actions).

---

## 🚀 Démarrage rapide (Docker)

```bash
docker compose up --build
```

Puis ouvrir le dashboard : **http://localhost:8000**

C'est tout. Le bot commence immédiatement à :
1. collecter les bougies du marché (auto-backfill de 100 bougies),
2. calculer un signal à chaque nouvelle bougie,
3. simuler des ordres (paper trading),
4. afficher le tout en temps réel sur le dashboard.

### Sans docker-compose
```bash
docker build -t pitradelab .
docker run -p 8000:8000 -v "$(pwd)/data:/app/data" pitradelab
```

### En local (sans Docker)
```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 🔑 Faut-il des clés API ?

**Non.** Le paper trading utilise uniquement les **données publiques** de l'exchange
(bougies OHLCV via `ccxt`), gratuites et sans authentification.

Les clés API ne deviennent nécessaires que pour passer de **vrais ordres** ou lire
un **solde réel** (trading live, phase future). Variables prévues mais désactivées :
`EXCHANGE_API_KEY` / `EXCHANGE_SECRET`.

---

## 🧠 Architecture

```
                    ┌─────────────────────────────────────┐
                    │       Conteneur Docker (1 seul)      │
   Exchange ──ccxt──▶  collector ─┐                        │
                    │             ▼                        │
   News (RSS) ──────▶  analyste IA (Gemini) ─┐             │
                    │             │          ▼             │
                    │          SQLite ◀──── trader         │
                    │             │   (technique + IA)     │
                    │             ▼                        │
   Navigateur ◀─────▶  FastAPI (dashboard + chat + ordres) │
                    └─────────────────────────────────────┘
```

| Module | Rôle |
|--------|------|
| `app/instruments.py` | Définition des actifs suivis (multi-classes) |
| `app/providers/`   | Fournisseurs de données : `ccxt` (crypto) + `yfinance` (or/actions/forex) |
| `app/collector.py` | Récupère les bougies OHLCV de chaque actif et les stocke |
| `app/strategy.py`  | Analyse technique → score `[-1, +1]` |
| `app/ai.py`        | Client Gemini (REST) |
| `app/news.py`      | Actualités (RSS) par classe d'actif |
| `app/analyst.py`   | Analyse IA périodique (marché + news) → score IA, par actif |
| `app/trader.py`    | Fusionne technique + IA, simule les ordres, par actif |
| `app/state.py`     | État partagé thread-safe — un portefeuille par actif |
| `app/main.py`      | FastAPI : dashboard, API, chat, commandes |
| `web/index.html`   | Dashboard temps réel avec sélecteur d'actifs (auto-refresh 3 s) |

### Décision = 2 cerveaux fusionnés
```
final = (1 - AI_WEIGHT) × score_technique  +  AI_WEIGHT × score_IA
```
- **Technique** (`strategy.py`) : MA20/MA50 (±0.40) + RSI (±0.40) + Volume (×1.2/×0.7)
- **IA** (`analyst.py`) : Gemini analyse marché + actualités → score `[-1, +1]` + sentiment + raison

### 💬 Piloter depuis le dashboard
- **Boutons** : Acheter / Vendre / Pause / État → ordres manuels immédiats
- **Chat** : pose une question (« faut-il acheter ? ») → l'IA répond avec le contexte du bot
- **Commandes** dans le chat : `/buy`, `/sell`, `/pause`, `/resume`, `/status`
- **P&L global vert/rouge** en haut + carte portefeuille colorée par actif

> ⚠️ L'IA **conseille** et **influence** le score auto, mais n'exécute jamais d'ordre seule :
> seuls tes boutons / commandes déclenchent un ordre manuel.

### ⚙️ Page de configuration (`/config`)
Modifiable **à chaud** (les threads réagissent sans redémarrage), persistée dans `data/settings.json` :
- **Langue** : Français / English / Español
- **Actifs à trader** : choix parmi 19 (crypto, or, argent, pétrole, actions, forex, indices), **5 max**
- **Stratégie** : `MA+RSI+Volume`, `RSI retour à la moyenne`, `Croisement de moyennes`, `Momentum` + seuils + poids IA
- **Clé IA (Gemini)** : ajout/remplacement depuis l'interface
- **Compte exchange** : clés Binance (ou autre), bouton « Tester la connexion » (lit le solde réel), mode **Paper** (défaut) ou **Live**

> ⚠️ Le mode **Live** engage de vrais fonds (ordres réels via ccxt). Le **Paper** (virtuel) reste le défaut.

---

## 🔐 Clé IA (Gemini)

1. Génère une clé sur **https://aistudio.google.com/apikey**
2. Mets-la dans un fichier **`.env`** (déjà gitignoré, jamais commité) :
   ```
   GEMINI_API_KEY=AIza...
   ```
3. `docker compose up` la lit automatiquement.

Sans clé, le bot tourne normalement en **analyse technique pure** (l'IA se désactive proprement).

---

## ⚙️ Configuration

Tout est pilotable par variables d'environnement (voir `.env.example` ou
`docker-compose.yml`). Aucune n'est obligatoire.

| Variable | Défaut | Description |
|----------|--------|-------------|
| `EXCHANGE` | `binance` | Exchange ccxt par défaut pour la collecte crypto (kraken, binanceus…) ; surchargeable à chaud depuis la page de configuration |
| `INSTRUMENTS` | _(4 actifs)_ | Liste d'actifs suivis (JSON) ; sinon BTC + Or + Apple + EUR/USD |
| `INITIAL_BALANCE` | `1000` | Capital virtuel de départ |
| `BUY_THRESHOLD` / `SELL_THRESHOLD` | `0.35` / `-0.35` | Seuils de décision |
| `GEMINI_API_KEY` | _(vide)_ | Clé Gemini — active la couche IA |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Modèle Gemini utilisé |
| `AI_INTERVAL` | `1800` | Fréquence d'analyse IA par actif (s) |
| `AI_WEIGHT` | `0.5` | Poids de l'IA dans le score final `[0..1]` |
| `NEWS_ENABLED` | `true` | Active la récupération des actualités (RSS) pour l'IA |
| `NEWS_RSS_URL` | CoinTelegraph | Flux RSS par défaut (autres classes : flux dédiés) |

> Si Binance est bloqué dans ta région, essaie `EXCHANGE=binanceus` ou `EXCHANGE=kraken`.

---

## 🗺️ Roadmap

- [x] **Phase 1** — Infrastructure (collecte, DB, paper trading, API)
- [x] **Phase 2** — Analyse technique (MA, RSI, Volume) + dashboard temps réel
- [x] **Phase 5 (anticipée)** — Couche IA Gemini : analyse news + chat + ordres manuels
- [x] **Multi-actifs** — crypto + or + actions + forex, un portefeuille par actif
- [ ] **Phase 3** — Backtesting sur données historiques
- [ ] **Phase 4** — Machine Learning local (probabilités de mouvement)
