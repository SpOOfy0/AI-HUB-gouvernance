"""Quotas (test 4) et calcul des coûts (test 12)."""
import uuid
from decimal import Decimal

from sqlalchemy import func, select

from app.models import AuditEvent, Department, LlmRequest, ModelPrice, QuotaAlert, User
from app.services.cost_service import compute_cost
from tests.conftest import chat, login, model_id

FOB = "Explique-moi la différence entre FOB et CIF."


def _consume(db, email: str, cost: str) -> User:
    """Simule une consommation déjà enregistrée ce mois-ci."""
    user = db.scalar(select(User).where(User.email == email))
    db.add(LlmRequest(request_id=uuid.uuid4().hex, user_id=user.id, department_id=user.department_id, app="chat",
                      classification="PUBLIC", detections=[], decision="ALLOW", routing_reason="test",
                      input_tokens=1000, output_tokens=1000, cost_eur=Decimal(cost), status="SUCCESS"))
    db.commit()
    return user


# 4. Un utilisateur ne peut pas dépasser son quota
def test_04_user_cannot_exceed_quota(client, providers, db):
    _consume(db, "user@rdt-demo.local", "3.00")  # budget du compte démo : 3 €
    login(client, "USER")
    r = chat(client, FOB)
    assert r.status_code == 429
    assert r.json()["code"] == "QUOTA_EXCEEDED"
    assert providers.calls == []
    assert db.scalar(select(AuditEvent).where(AuditEvent.event_type == "QUOTA_EXCEEDED")) is not None


def test_04b_request_refused_if_estimate_would_exceed_quota(client, providers, db):
    # 2,999 € consommés sur 3 € : l'estimation pessimiste (~0,004 €) ferait dépasser -> refus.
    _consume(db, "user@rdt-demo.local", "2.999")
    login(client, "USER")
    assert chat(client, FOB).status_code == 429
    assert providers.calls == []


def test_04c_department_budget_is_enforced(client, providers, db):
    user = db.scalar(select(User).where(User.email == "user@rdt-demo.local"))
    db.get(Department, user.department_id).monthly_budget_eur = Decimal("0.001")
    db.commit()
    login(client, "USER")
    r = chat(client, FOB)
    assert r.status_code == 429 and "département" in r.json()["detail"]


def test_04d_threshold_alerts_raised_once(client, providers, db):
    _consume(db, "user@rdt-demo.local", "2.73")  # 91 % de 3 €
    login(client, "USER")
    first = chat(client, FOB).json()
    assert {a["threshold"] for a in first["alerts"] if a["scope"] == "user"} == {70, 90}
    second = chat(client, FOB).json()
    assert second["alerts"] == []  # pas de nouvelle alerte pour les mêmes seuils ce mois-ci
    assert db.scalar(select(func.count(QuotaAlert.id)).where(QuotaAlert.scope == "user")) == 2
    usage = client.get("/api/me/usage").json()
    assert usage["user"]["pct"] >= 91 and len(usage["alerts"]) == 2


# 12. Calcul du coût, et "coût non disponible" si le prix est absent
def test_12_cost_computation():
    price = ModelPrice(input_per_mtok=Decimal("2.00"), output_per_mtok=Decimal("8.00"))
    assert compute_cost(price, 1000, 500) == Decimal("0.006000")
    assert compute_cost(price, 0, 0) == Decimal("0")
    assert compute_cost(None, 1000, 500) is None


def test_12b_cost_not_available_when_price_missing(client, providers, db):
    login(client, "DEVELOPER")
    # Mistral Nemo (local) n'a pas de prix dans la configuration de démo.
    body = chat(client, FOB, model_id=model_id(db, "ollama/mistral-nemo")).json()
    assert body["status"] == "SUCCESS"
    assert body["routing"]["cost_eur"] is None and body["routing"]["cost_available"] is False
    row = db.scalar(select(LlmRequest).where(LlmRequest.request_id == body["request_id"]))
    assert row.cost_eur is None and row.input_tokens == 100


def test_12c_real_cost_recorded_from_provider_tokens(client, providers, db):
    login(client, "USER")
    body = chat(client, FOB).json()  # DeepSeek : 0,14 € / 0,28 € par million ; faux fournisseur : 100 / 50 tokens
    expected = (Decimal(100) * Decimal("0.14") + Decimal(50) * Decimal("0.28")) / Decimal(1_000_000)
    assert Decimal(body["routing"]["cost_eur"]) == expected.quantize(Decimal("0.000001"))
