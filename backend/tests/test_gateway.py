"""Tests de la passerelle : routage selon la confidentialité, blocage, fallback, conversations.

Numérotation = tests obligatoires du cahier des charges (section 14).
"""
from app.core.enums import Hosting
from tests.conftest import chat, login, model_id

FOB = "Explique-moi la différence entre FOB et CIF."
CONFIDENTIAL = "Analyse les tarifs négociés avec notre armateur pour la ligne Asie."
SECRET = "Voici notre clé API : sk-proj-AbCdEf1234567890XyZ, pourquoi ça ne marche pas ?"


# 1. PUBLIC -> peut aller vers un fournisseur externe autorisé
def test_01_public_request_routed_to_external_provider(client, providers):
    login(client, "USER")
    r = chat(client, FOB)
    body = r.json()
    assert r.status_code == 200 and body["status"] == "SUCCESS"
    assert body["routing"]["classification"] == "PUBLIC"
    assert body["routing"]["decision"] == "ALLOW"
    # Requête simple : le moins cher éligible est Gemini Flash (offre gratuite, externe, niveau max PUBLIC).
    assert body["routing"]["model"] == "gemini/gemini-2.5-flash"
    assert body["routing"]["hosting"] == Hosting.EXTERNAL
    assert providers.calls[0]["hosting"] == Hosting.EXTERNAL


# 2. CONFIDENTIAL -> modèles privés uniquement, y compris en mode manuel
def test_02_confidential_request_only_routed_to_private_model(client, providers, db):
    login(client, "DEVELOPER")
    r = chat(client, CONFIDENTIAL)
    body = r.json()
    assert body["routing"]["classification"] == "CONFIDENTIAL"
    assert body["routing"]["decision"] == "PRIVATE_ONLY"
    assert body["routing"]["hosting"] == Hosting.PRIVATE
    assert all(c["hosting"] == Hosting.PRIVATE for c in providers.calls)


def test_02b_manual_external_model_refused_for_confidential(client, providers, db):
    login(client, "DEVELOPER")
    r = chat(client, CONFIDENTIAL, model_id=model_id(db, "anthropic/claude-sonnet-4-5"))
    body = r.json()
    assert body["status"] == "REFUSED"
    assert body["can_fallback_private"] is True
    assert "niveau de confidentialité" in body["routing"]["reason"]
    assert providers.calls == []  # jamais d'envoi forcé


def test_02c_manual_external_model_with_private_fallback_accepted(client, providers, db):
    login(client, "DEVELOPER")
    r = chat(client, CONFIDENTIAL, model_id=model_id(db, "openai/gpt-4.1"), accept_private_fallback=True)
    body = r.json()
    assert body["status"] == "SUCCESS"
    assert body["routing"]["hosting"] == Hosting.PRIVATE
    assert [c["hosting"] for c in providers.calls] == [Hosting.PRIVATE]


# 3. Clé API -> bloquée, fournisseur jamais appelé
def test_03_api_key_is_blocked_and_provider_never_called(client, providers):
    login(client, "USER")
    r = chat(client, SECRET)
    body = r.json()
    assert r.status_code == 200 and body["status"] == "BLOCKED"
    assert body["routing"]["classification"] == "RESTRICTED"
    assert body["routing"]["decision"] == "BLOCK"
    assert body["message"] is None
    assert providers.calls == []
    assert {d["type"] for d in body["routing"]["detections"]} >= {"api_key"}
    assert "sk-proj" not in r.text  # la réponse ne répète pas le secret


def test_03b_spec_example_short_key_is_blocked(client, providers):
    login(client, "USER")
    body = chat(client, "Voici notre clé API : sk-xxxx, pourquoi ça ne marche pas ?").json()
    assert body["status"] == "BLOCKED" and providers.calls == []


# 6. Erreur fournisseur -> fallback dans le même ensemble éligible, sinon 503 propre
def test_06_provider_error_falls_back_within_eligible_set(client, providers):
    login(client, "USER")
    providers.failing = {"gemini/gemini-2.5-flash"}
    body = chat(client, FOB).json()
    assert body["status"] == "SUCCESS"
    assert body["routing"]["fallback_used"] is True
    assert body["routing"]["attempts"] == [{"model": "gemini/gemini-2.5-flash", "error": "ProviderError"}]
    assert [c["model"] for c in providers.calls][0] == "gemini/gemini-2.5-flash"
    assert body["routing"]["model"] == "deepseek/deepseek-chat"  # suivant le moins cher du même ensemble


def test_06b_all_providers_down_returns_clean_503(client, providers, db):
    from sqlalchemy import select

    from app.models import AuditEvent

    login(client, "USER")
    providers.failing = {c for c in [
        "gemini/gemini-2.5-flash", "deepseek/deepseek-chat", "openai/gpt-4.1-mini", "anthropic/claude-haiku-4-5",
        "ollama/llama3.1:8b", "ollama/qwen2.5:14b",
    ]}
    r = chat(client, FOB)
    assert r.status_code == 503
    assert r.json()["code"] == "ALL_PROVIDERS_FAILED" and r.json()["request_id"]
    assert db.scalar(select(AuditEvent).where(AuditEvent.event_type == "NO_MODEL_AVAILABLE")) is not None


# 8. Une conversation devenue CONFIDENTIAL le reste
def test_08_conversation_stays_confidential(client, providers):
    login(client, "USER")
    first = chat(client, CONFIDENTIAL).json()
    assert first["routing"]["classification"] == "CONFIDENTIAL"
    second = chat(client, FOB, conversation_id=first["conversation_id"]).json()
    assert second["routing"]["classification"] == "CONFIDENTIAL"
    assert second["routing"]["hosting"] == Hosting.PRIVATE
    assert second["routing"]["sources"]["message"] == "PUBLIC"
    assert all(c["hosting"] == Hosting.PRIVATE for c in providers.calls)


# 9. Un fallback ne passe jamais d'un modèle privé à un modèle externe
def test_09_fallback_never_crosses_from_private_to_external(client, providers):
    login(client, "DEVELOPER")
    providers.failing = {"ollama/llama3.1:8b", "ollama/qwen2.5:14b", "ollama/mistral-nemo"}
    r = chat(client, CONFIDENTIAL)
    assert r.status_code == 503
    assert providers.calls and all(c["hosting"] == Hosting.PRIVATE for c in providers.calls)


# 10. Le niveau déclaré peut relever, jamais abaisser
def test_10_declared_level_can_raise_but_not_lower(client, providers):
    login(client, "USER")
    raised = chat(client, FOB, declared_level="CONFIDENTIAL").json()
    assert raised["routing"]["classification"] == "CONFIDENTIAL"
    assert raised["routing"]["hosting"] == Hosting.PRIVATE
    lowered = chat(client, CONFIDENTIAL, declared_level="PUBLIC").json()
    assert lowered["routing"]["classification"] == "CONFIDENTIAL"
    assert lowered["routing"]["hosting"] == Hosting.PRIVATE


def test_internal_request_excludes_deepseek(client, providers):
    login(client, "USER")
    body = chat(client, "Résume la procédure interne d'ouverture d'un dossier export au site de Fos.").json()
    assert body["routing"]["classification"] == "INTERNAL"
    assert body["routing"]["model"] not in {"deepseek/deepseek-chat", "gemini/gemini-2.5-flash"}


def test_complex_request_uses_highest_tier_allowed_for_role(client, providers):
    login(client, "DEVELOPER")
    body = chat(client, "Compare les Incoterms FOB et CIF", deep_reasoning=True).json()
    assert body["routing"]["complexity"] == "COMPLEX"
    assert body["routing"]["model"] in {"openai/gpt-4.1", "anthropic/claude-sonnet-4-5"}


def test_manual_model_not_allowed_for_role_is_refused(client, providers, db):
    login(client, "USER")  # Claude Sonnet est réservé aux rôles ADMIN, MANAGER, DEVELOPER
    body = chat(client, FOB, model_id=model_id(db, "anthropic/claude-sonnet-4-5")).json()
    assert body["status"] == "REFUSED" and "rôle" in body["routing"]["reason"]
    assert providers.calls == []


def test_context_sent_to_model_includes_history(client, providers):
    login(client, "USER")
    first = chat(client, FOB).json()
    chat(client, "Et pour le DAP ?", conversation_id=first["conversation_id"])
    assert len(providers.calls[-1]["messages"]) == 3  # question 1, réponse 1, question 2


def test_cannot_use_another_users_conversation(client, providers):
    login(client, "USER")
    conv = chat(client, FOB).json()["conversation_id"]
    login(client, "DEVELOPER")
    assert chat(client, FOB, conversation_id=conv).status_code == 404
    assert client.get(f"/api/conversations/{conv}").status_code == 404
