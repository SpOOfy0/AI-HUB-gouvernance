"""Une requête bloquée ne laisse son contenu nulle part (test 7)."""
import logging

from sqlalchemy import text

from tests.conftest import TABLES, chat, login

SECRET = "sk-proj-SuperSecret9876543210abcdef"
PASSWORD = "MotDePasseUltraSecret!42"


def _dump_database(db) -> str:
    """Toutes les lignes de toutes les tables, sérialisées en texte."""
    parts = []
    for table in TABLES:
        parts += [row[0] for row in db.execute(text(f"SELECT row_to_json(t)::text FROM {table} t"))]
    return "\n".join(parts)


def test_07_blocked_request_content_is_stored_nowhere(client, providers, db, caplog):
    caplog.set_level(logging.DEBUG)
    login(client, "USER")
    message = f"Connexion prod : mdp = {PASSWORD} et la clé {SECRET}, tu peux vérifier ?"
    r = chat(client, message)
    assert r.json()["status"] == "BLOCKED"
    assert providers.calls == []

    dump = _dump_database(db)
    logs = caplog.text
    for sensitive in (SECRET, PASSWORD, "Connexion prod"):
        assert sensitive not in dump, "contenu retrouvé en base"
        assert sensitive not in logs, "contenu retrouvé dans les logs applicatifs"
        assert sensitive not in r.text, "contenu renvoyé dans la réponse"
    # Les métadonnées, elles, sont bien conservées.
    assert "REQUEST_BLOCKED" in dump and "api_key" in dump


def test_07b_blocked_message_in_existing_conversation_is_not_added(client, providers, db):
    login(client, "USER")
    conv = chat(client, "Qu'est-ce qu'un connaissement ?").json()["conversation_id"]
    chat(client, f"ma clé : {SECRET}", conversation_id=conv)
    messages = client.get(f"/api/conversations/{conv}").json()["messages"]
    assert len(messages) == 2 and all(SECRET not in m["content"] for m in messages)


def test_07c_audit_details_never_contain_prompt_for_allowed_requests(client, providers, db):
    login(client, "USER")
    chat(client, "Question anodine sur le code SH 8471")
    audit = "\n".join(r[0] for r in db.execute(text("SELECT details::text FROM audit_events")))
    assert "anodine" not in audit
