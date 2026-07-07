"""
IA du bot de base (paper trading). S'appuie sur la couche multi-fournisseurs
`app/llm`. Le fournisseur actif et la clé sont lus dynamiquement depuis les
settings → modifier la clé/fournisseur dans la page de configuration active l'IA
sans redémarrer.

Les aventures, elles, peuvent utiliser leur propre fournisseur/clé (voir
app/adventures.py) ou retomber sur cette configuration de base.
"""
import logging

from app import settings
from app.llm import ask as llm_ask

log = logging.getLogger("ai")

LANG_INSTRUCTION = {
    "fr": "Réponds en français.",
    "en": "Answer in English.",
    "es": "Responde en español.",
}


def _active():
    """(provider, api_key, model) de l'IA de base selon les settings."""
    provider = settings.get("ai_provider") or "gemini"
    if provider == "mistral":
        return "mistral", settings.get("mistral_api_key"), settings.get("mistral_model")
    return "gemini", settings.get("gemini_api_key"), settings.get("gemini_model")


def ai_available() -> bool:
    _, key, _ = _active()
    return bool(key)


def lang_instruction() -> str:
    return LANG_INSTRUCTION.get(settings.get("language", "fr"), LANG_INSTRUCTION["fr"])


def ask(prompt: str, system: str = None, json_mode: bool = False, timeout: int = 30) -> str:
    provider, key, model = _active()
    if not key:
        raise RuntimeError("clé IA manquante")
    return llm_ask(prompt, system=system, json_mode=json_mode,
                   provider=provider, api_key=key, model=model, timeout=timeout)
