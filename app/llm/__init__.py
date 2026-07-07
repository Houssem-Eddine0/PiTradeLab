"""
Couche LLM multi-fournisseurs.

Chaque fournisseur expose la même interface :
    ask(prompt, system=None, json_mode=False, api_key=..., model=None, timeout=30) -> str
    NAME, DEFAULT_MODEL, MODELS

Permet d'utiliser Gemini, Mistral (ou un autre ajouté plus tard) de façon
interchangeable — clé de base globale OU clé propre à chaque aventure.
"""
from app.llm import gemini, mistral

PROVIDERS = {
    "gemini": gemini,
    "mistral": mistral,
}


def get_provider(name: str):
    return PROVIDERS.get(name) or gemini


def ask(prompt: str, system: str = None, json_mode: bool = False,
        provider: str = "gemini", api_key: str = None, model: str = None, timeout: int = 30) -> str:
    return get_provider(provider).ask(
        prompt, system=system, json_mode=json_mode, api_key=api_key, model=model, timeout=timeout)


def verify(provider: str, api_key: str, model: str = None) -> dict:
    """Teste réellement la clé en faisant un mini appel. {ok, message|error, model}."""
    p = get_provider(provider)
    if not api_key:
        return {"ok": False, "error": "Clé manquante."}
    try:
        p.ask("ping", api_key=api_key, model=model, timeout=15)
        return {"ok": True, "message": f"{p.NAME} OK", "model": model or p.DEFAULT_MODEL}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def providers_info():
    return [{"id": k, "name": v.NAME, "default_model": v.DEFAULT_MODEL, "models": v.MODELS}
            for k, v in PROVIDERS.items()]
