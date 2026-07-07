"""Fournisseur Mistral AI (API chat completions, compatible OpenAI). Auth Bearer."""
import requests

NAME = "Mistral"
DEFAULT_MODEL = "mistral-small-latest"
MODELS = ["mistral-small-latest", "mistral-large-latest", "open-mistral-nemo"]

URL = "https://api.mistral.ai/v1/chat/completions"


def ask(prompt: str, system: str = None, json_mode: bool = False,
        api_key: str = None, model: str = None, timeout: int = 30) -> str:
    if not api_key:
        raise RuntimeError("clé Mistral manquante")
    model = model or DEFAULT_MODEL

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    body = {"model": model, "messages": messages}
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    r = requests.post(URL, json=body, timeout=timeout,
                      headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
    r.raise_for_status()
    data = r.json()
    choices = data.get("choices")
    if not choices:
        raise RuntimeError("réponse Mistral vide")
    return (choices[0].get("message", {}).get("content") or "").strip()
