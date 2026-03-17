# PiTradeLab

Projet de bot de trading expérimental sur Raspberry Pi.

## Objectif

Construire un bot modulaire capable de :

- collecter des données de marché
- stocker les données localement
- exécuter une stratégie de paper trading
- envoyer un état vers une API HTTP
- afficher les résultats sur un dashboard
- préparer une future couche de machine learning

## Stack

- Python
- SQLite
- Raspberry Pi 4
- ccxt
- pandas
- scikit-learn

## Structure du projet

```text
bot/
collectors/
data/
logs/
strategy/
