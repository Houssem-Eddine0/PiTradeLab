# 🚀 PiTradeLab

> 🧠 Projet d’apprentissage en Python et d’initiation aux systèmes de trading automatisés (paper trading) sur Raspberry Pi.

---

## 📌 À propos du projet

**PiTradeLab** est un projet personnel développé dans un objectif d’apprentissage :

- 🐍 Approfondir mes compétences en **Python**
- 📊 Découvrir les bases de la **finance de marché**
- ⚙️ Comprendre l’architecture d’un **bot de trading**
- 🧩 Construire un système modulaire (data → stratégie → décision)

⚠️ Ce projet n’est **pas destiné au trading réel** mais à la **simulation (paper trading)** et à l’expérimentation.

---

## 🎯 Objectifs

- Collecter des données de marché en temps réel  
- Stocker ces données localement (SQLite)  
- Implémenter des stratégies de trading  
- Simuler des trades (achat / vente)  
- Analyser les performances  
- Préparer une future intégration de **machine learning**

---

## 🧱 Architecture du projet

```text
PiTradeLab/
├── bot/              # Logique de trading (paper trading)
├── collectors/       # Collecte des données marché
├── strategy/         # Stratégies de décision
├── data/             # Base SQLite (non versionnée)
├── logs/             # Logs du système
├── venv/             # Environnement Python (ignoré)
└── README.md
```

---

## ⚙️ Fonctionnement global

```text
API marché (Binance via ccxt)
            ↓
     Collecteur de données
            ↓
        Base SQLite
            ↓
         Stratégie
            ↓
      Paper Trading
            ↓
        Logs / Analyse
```

---

## 📊 Fonctionnalités actuelles

- ✅ Collecte de données en temps réel (BTC/USDT)
- ✅ Stockage des bougies (OHLCV) dans SQLite
- ✅ Stratégie simple (comparaison de prix)
- ✅ Simulation de trades (paper trading)
- ✅ Historique des actions et des performances

---

## 🧠 Ce que j’apprends avec ce projet

### Python
- Manipulation de données (`pandas`)
- Gestion de scripts longue durée
- Structuration d’un projet
- Interaction avec des API (`ccxt`)

### Systèmes
- Exécution sur Raspberry Pi
- Gestion de services (`tmux` / `systemd`)
- Base de données SQLite
- Architecture modulaire

### Finance (initiation)
- Compréhension des marchés
- Notions de stratégie de trading
- Analyse de données de marché
- Simulation de décisions

---

## 🚀 Installation

```bash
git clone [https://github.com/Houssem-Eddine0/PiTradeLab.git](https://github.com/Houssem-Eddine0/PiTradeLab.git)
cd PiTradeLab

python3 -m venv venv
source venv/bin/activate

pip install ccxt pandas numpy ta scikit-learn joblib
```

### ▶️ Lancement

**📡 Lancer le collecteur**
```bash
python -m collectors.collector
```

**🤖 Lancer le paper trader**
```bash
python -m bot.paper_trader
```

---

## 📂 Base de données

Le projet utilise SQLite.  
Tables principales :

- **`prices`** → données marché (OHLCV)
- **`signals`** → décisions de la stratégie
- **`paper_trades`** → trades simulés

---

## 🔮 Roadmap

- [x] Structure du projet
- [x] Collecte des données
- [x] Paper trading simple
- [ ] Stratégie avancée (RSI, MA, etc.)
- [ ] API HTTP (communication externe)
- [ ] Dashboard local
- [ ] Dashboard distant
- [ ] Machine Learning (prédiction)
- [ ] Gestion du risque

---

## ⚠️ Disclaimer

Ce projet est purement éducatif.

- ❌ Aucun conseil financier
- ❌ Aucun trading réel recommandé
- ⚠️ Les stratégies implémentées ne garantissent aucun gain

---

## 📌 Auteur

👤 **Houssem-Eddine NANE** 🎓 BTS CIEL – Informatique & Réseaux  
💡 Passionné par les systèmes, l’automatisation et les projets techniques  

---

## ⭐ Conclusion

PiTradeLab est un projet évolutif qui me permet de :
- passer de scripts simples à une architecture complète
- comprendre les bases des systèmes de trading
- construire un projet concret et présentable

---

## ✅ Là c’est nickel

- ✔ pas de bloc cassé  
- ✔ compatible GitHub  
- ✔ rendu propre  
- ✔ lisible sur mobile et PC  

---

## 🔥 Upgrade possible (si tu veux après)

- badges GitHub (Python, status, etc.)
- schéma stylé (draw.io / image)
- GIF démo du bot
- section “screenshots dashboard”
