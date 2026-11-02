"""Politique modifiable par l'ADMIN, journalisée, et bac à sable de classification."""
from sqlalchemy import select

from app.models import AuditEvent
from tests.conftest import chat, login


def test_sandbox_classifies_without_calling_any_model(client, providers):
    login(client, "ADMIN")
    r = client.post("/api/classify", json={"message": "Voici le mdp : Hunter2!"})
    body = r.json()
    assert body["classification"] == "RESTRICTED" and body["decision"] == "BLOCK"
    assert body["would_select"] is None and providers.calls == []


def test_sandbox_shows_eligible_models(client, providers):
    login(client, "ADMIN")
    body = client.post("/api/classify", json={"message": "Analyse les tarifs négociés"}).json()
    assert body["decision"] == "PRIVATE_ONLY"
    assert body["eligible_models"] and all(m["hosting"] == "PRIVATE" for m in body["eligible_models"])


def test_lexicon_term_added_by_admin_changes_routing_and_is_logged(client, providers, db):
    login(client, "ADMIN")
    r = client.post("/api/policy/lexicon", json={"term": "Tartempion SA", "category": "client", "level": "CONFIDENTIAL"})
    assert r.status_code == 201
    body = chat(client, "Volume annuel du client Tartempion SA ?").json()
    assert body["routing"]["classification"] == "CONFIDENTIAL" and body["routing"]["hosting"] == "PRIVATE"
    assert db.scalar(select(AuditEvent).where(AuditEvent.event_type == "CONFIG_CHANGED")) is not None


def test_invalid_regex_rejected(client):
    login(client, "ADMIN")
    r = client.post("/api/policy/lexicon", json={"term": "([abc", "category": "client", "level": "CONFIDENTIAL",
                                                 "is_regex": True})
    assert r.status_code == 422


def test_policy_update_logged_and_secret_level_locked(client, db):
    login(client, "ADMIN")
    r = client.put("/api/policy", json={"detection_levels": {"personal_data": "RESTRICTED"}})
    assert r.status_code == 200
    assert r.json()["policy"]["detection_levels"]["personal_data"] == "RESTRICTED"
    event = db.scalar(select(AuditEvent).where(AuditEvent.event_type == "CONFIG_CHANGED"))
    assert event.details["target"] == "policy.detection_levels"
    assert client.put("/api/policy", json={"detection_levels": {"secret": "PUBLIC"}}).status_code == 422


def test_policy_change_applies_to_gateway(client, providers):
    login(client, "ADMIN")
    client.put("/api/policy", json={"detection_levels": {"personal_data": "RESTRICTED"}})
    body = chat(client, "Écris à jean.dupont@client.fr").json()
    assert body["status"] == "BLOCKED" and providers.calls == []
