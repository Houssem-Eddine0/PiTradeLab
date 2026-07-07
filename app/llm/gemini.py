"""Fournisseur Gemini (Google Generative Language) via REST.

Auth par clé API (?key=) avec repli Bearer si la clé est en fait un token OAuth.
"""
import requests

NAME = "Gemini (Google)"
DEFAULT_MODEL = "gemini-2.5-flash"
MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-flash-latest"]

BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _extract_text(data: dict) -> str:
    candidates = data.get("candidates")
    if not candidates:
        raise RuntimeError(f"réponse vide de Gemini ({data.get('promptFeedback')})")
    parts = candidates[0].get("content", {}).get("parts")
    if not parts:
        raise RuntimeError("réponse Gemini sans contenu (filtrée ?)")
    return parts[0].get("text", "").strip()


def ask(prompt: str, system: str = None, json_mode: bool = False,
        api_key: str = None, model: str = None, timeout: int = 30) -> str:
    if not api_key:
        raise RuntimeError("clé Gemini manquante")
    model = model or DEFAULT_MODEL

    body = {"contents": [{"parts": [{"text": prompt}]}]}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    if json_mode:
        body["generationConfig"] = {"responseMimeType": "application/json"}

    endpoint = f"{BASE}/{model}:generateContent"
    r = requests.post(f"{endpoint}?key={api_key}", json=body, timeout=timeout)
    if r.status_code in (401, 403):
        r = requests.post(endpoint, json=body, timeout=timeout,
                          headers={"Authorization": f"Bearer {api_key}"})
    r.raise_for_status()
    return _extract_text(r.json())
