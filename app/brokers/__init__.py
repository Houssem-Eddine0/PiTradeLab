"""
Abstraction courtiers pour l'exécution des aventures.

Interface commune :
    test_connection(adv) -> {ok, message|error, balance?, currency?}
    execute(adv, instrument, action, price, cash, position) -> {ok, ...}
      - BUY  : `cash`     = liquidité allouée à dépenser (devise de cotation)
      - SELL : `position` = quantité (base) à clôturer

- sim          : aucun ordre réel, exécution simulée (prix réels). Toujours dispo.
- alpaca_paper : compte « paper » Alpaca (actions/crypto US).      [étape 3]
- oanda_paper  : compte « practice » OANDA (forex/CFD or, indices). [étape 3]
"""
from app.brokers import alpaca_paper, oanda_paper, sim

_REGISTRY = {
    "sim": sim,
    "alpaca_paper": alpaca_paper,
    "oanda_paper": oanda_paper,
}


def get_broker(name: str):
    return _REGISTRY.get(name) or sim


def test_connection(adv: dict) -> dict:
    return get_broker(adv.get("broker", "sim")).test_connection(adv)


def account_state(adv: dict) -> dict:
    """État RÉEL du compte courtier : {ok, balance, equity, currency, positions:[...]}.
    Sert à réconcilier l'affichage avec la réalité du compte."""
    b = get_broker(adv.get("broker", "sim"))
    fn = getattr(b, "account_state", None)
    if fn is None:
        return {"ok": False, "error": "non disponible"}
    return fn(adv)


def execute(adv: dict, instrument, action: str, price: float, cash: float, position: float) -> dict:
    return get_broker(adv.get("broker", "sim")).execute(adv, instrument, action, price, cash, position)
