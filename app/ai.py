"""
Client Gemini (API Google Generative Language) via REST.

Clé et modèle lus dynamiquement depuis les settings : modifier la clé dans la
page de configuration active l'IA sans redémarrer. Auth par clé API (?key=) avec
repli Bearer si la clé est en fait un token OAuth.
"""
import logging

import requests

from app import settings

log = logging.getLogger("ai")

BASE = "https://generativelanguage.googleapis.com/v1beta/models"

LANG_INSTRUCTION = {
    "fr": "Réponds en français.",
    "en": "Answer in English.",
    "es": "Responde en español.",
}


def ai_available() -> bool:
    return bool(settings.get("gemini_api_key"))


def lang_instruction() -> str:
    return LANG_INSTRUCTION.get(settings.get("language", "fr"), LANG_INSTRUCTION["fr"])


def _extract_text(data: dict) -> str:
    candidates = data.get("candidates")
    if not candidates:
        raise RuntimeError(f"réponse vide de Gemini ({data.get('promptFeedback')})")
    parts = candidates[0].get("content", {}).get("parts")
    if not parts:
        raise RuntimeError("réponse Gemini sans contenu (filtrée ?)")
    return parts[0].get("text", "").strip()


def ask(prompt: str, system: str = None, json_mode: bool = False, timeout: int = 30) -> str:
    key = settings.get("gemini_api_key")
    model = settings.get("gemini_model") or "gemini-2.5-flash"
    if not key:
        raise RuntimeError("clé Gemini manquante")

    body = {"contents": [{"parts": [{"text": prompt}]}]}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    if json_mode:
        body["generationConfig"] = {"responseMimeType": "application/json"}

    endpoint = f"{BASE}/{model}:generateContent"
    r = requests.post(f"{endpoint}?key={key}", json=body, timeout=timeout)
    if r.status_code in (401, 403):
        r = requests.post(endpoint, json=body, timeout=timeout,
                          headers={"Authorization": f"Bearer {key}"})
    r.raise_for_status()
    return _extract_text(r.json())
