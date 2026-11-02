"""Journal d'audit append-only et vérification d'intégrité (test 11)."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.enums import Severity
from app.db import engine
from app.services import audit_service
from tests.conftest import login


def _seed_events(db, n=5):
    for i in range(n):
        audit_service.log_event(db, "TEST_EVENT", category="admin", severity=Severity.INFO, details={"i": i})
    db.commit()


@pytest.mark.parametrize("statement", [
    "UPDATE audit_events SET status = 'X'",
    "DELETE FROM audit_events",
    "TRUNCATE audit_events",
])
def test_11_audit_table_refuses_update_delete_truncate(db, statement):
    _seed_events(db)
    with pytest.raises(DBAPIError, match="ajout seul"):
        with engine.begin() as conn:
            conn.execute(text(statement))


def test_11b_chain_is_valid_after_normal_inserts(db):
    _seed_events(db)
    assert audit_service.verify_chain(db) == {"valid": True, "checked": 5, "first_invalid_id": None, "reason": None}


def test_11c_integrity_check_detects_tampering(db):
    _seed_events(db)
    # Simulation d'un administrateur de base qui contourne le trigger (superutilisateur).
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE audit_events DISABLE TRIGGER audit_events_no_update_delete"))
        conn.execute(text("""UPDATE audit_events SET details = '{"i": 99}' WHERE id = 3"""))
        conn.execute(text("ALTER TABLE audit_events ENABLE TRIGGER audit_events_no_update_delete"))
    db.expire_all()
    result = audit_service.verify_chain(db)
    assert result["valid"] is False and result["first_invalid_id"] == 3 and result["reason"] == "contenu modifié"


def test_11d_integrity_check_detects_deleted_event(db):
    _seed_events(db)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE audit_events DISABLE TRIGGER audit_events_no_update_delete"))
        conn.execute(text("DELETE FROM audit_events WHERE id = 2"))
        conn.execute(text("ALTER TABLE audit_events ENABLE TRIGGER audit_events_no_update_delete"))
    result = audit_service.verify_chain(db)
    assert result["valid"] is False and result["first_invalid_id"] == 3 and result["reason"] == "chaînage rompu"


def test_11e_verify_endpoint(client, db):
    _seed_events(db)
    login(client, "ADMIN")  # la connexion ajoute elle-même un événement
    r = client.post("/api/audit/verify")
    assert r.status_code == 200 and r.json()["valid"] is True


def test_sanitize_removes_content_keys(db):
    ev = audit_service.log_event(db, "TEST_EVENT", category="admin",
                                 details={"prompt": "secret", "content": "x", "model": "m", "long": "a" * 500})
    assert "prompt" not in ev.details and "content" not in ev.details
    assert ev.details["model"] == "m" and len(ev.details["long"]) <= 201
