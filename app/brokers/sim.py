"""Courtier simulé : aucun ordre réel, aucune clé requise. Exécution toujours OK
(la comptabilité est tenue par AdventureBook). Défaut sûr pour démarrer une aventure."""

NAME = "Simulation (sans argent réel)"
NEEDS_KEYS = False


def test_connection(adv: dict) -> dict:
    return {"ok": True, "message": "Mode simulation — prix réels, ordres virtuels, aucun risque."}


def execute(adv: dict, instrument, action: str, price: float, cash: float, position: float) -> dict:
    return {"ok": True, "simulated": True}
