"""Seed déterministe des données de démonstration (toutes fictives).

Usage :
    python -m app.seed.seed            # ne fait rien si la base contient déjà des utilisateurs
    python -m app.seed.seed --reset    # supprime le schéma, rejoue les migrations, puis seed

La graine aléatoire est fixe (42) : le contenu généré est identique à chaque exécution
(les dates sont relatives au jour d'exécution).
"""
import argparse
import logging
import random
import uuid
from functools import lru_cache
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.enums import Level, Severity
from app.core.security import hash_password
from app.db import SessionLocal, engine
from app.models import (
    Conversation,
    Department,
    LexiconTerm,
    LlmModel,
    LlmRequest,
    Message,
    ModelPrice,
    PolicySetting,
    Provider,
    QuotaAlert,
    User,
)
from app.seed import data
from app.services import audit_service, cost_service, model_router, policy_service, quota_service
from app.services.classification_service import ClassificationResult
from app.services.policy_store import DEFAULT_POLICY

logger = logging.getLogger("seed")
SEED = 42
TARGET_REQUESTS = 2850  # + ~150 requêtes de scénarios de quota ≈ 3 000
DAYS = 30


@lru_cache
def _hash(password: str) -> str:
    """argon2 est volontairement lent : on ne hache qu'une fois chaque mot de passe de démo."""
    return hash_password(password)


# ---------------------------------------------------------------------------
# Données de référence (aussi utilisées par les tests)
# ---------------------------------------------------------------------------
def seed_reference(db: Session) -> None:
    depts = {}
    for name, budget, tokens, cap in data.DEPARTMENTS:
        d = Department(name=name, monthly_budget_eur=Decimal(budget), monthly_token_limit=tokens,
                       manager_quota_cap_eur=Decimal(cap))
        db.add(d)
        depts[name] = d
    db.flush()

    for acc in data.DEMO_ACCOUNTS:
        db.add(User(email=acc["email"], full_name=acc["full_name"], password_hash=_hash(acc["password"]),
                    role=acc["role"], department_id=depts[acc["department"]].id,
                    monthly_budget_eur=Decimal(acc["budget"])))

    providers = {}
    for name, kind, env in data.PROVIDERS:
        p = Provider(name=name, kind=kind, api_key_env_var=env)
        db.add(p)
        providers[name] = p
    db.flush()

    for prov, display, litellm_name, hosting, max_level, tier, roles, pin, pout in data.MODELS:
        m = LlmModel(provider_id=providers[prov].id, display_name=display, litellm_name=litellm_name,
                     hosting=hosting, max_classification=max_level, tier=tier, allowed_roles=roles, is_active=True)
        db.add(m)
        db.flush()
        if pin is not None:
            db.add(ModelPrice(model_id=m.id, input_per_mtok=Decimal(str(pin)), output_per_mtok=Decimal(str(pout)),
                              currency="EUR", source="Prix fictifs de démonstration", is_demo=True))

    for key, value in DEFAULT_POLICY.items():
        db.add(PolicySetting(key=key, value=value))
    for term, category, level, is_regex in data.LEXICON:
        db.add(LexiconTerm(term=term, category=category, level=level, is_regex=is_regex))
    db.flush()


# ---------------------------------------------------------------------------
# Activité simulée sur 30 jours
# ---------------------------------------------------------------------------
DETECTION_SAMPLES = {
    Level.INTERNAL: [("lexique:procedure", "lexicon"), ("lexique:site", "lexicon"), ("lexique:internal_id", "lexicon")],
    Level.CONFIDENTIAL: [("lexique:commercial", "lexicon"), ("lexique:client", "lexicon"), ("email", "personal_data"),
                         ("iban", "financial"), ("phone", "personal_data")],
    Level.RESTRICTED: [("api_key", "secret"), ("password", "secret"), ("connection_string", "secret"),
                       ("private_key", "secret"), ("payment_card", "payment_card")],
}


def _detections(rng: random.Random, level: Level) -> list[dict]:
    if level == Level.PUBLIC:
        return []
    dtype, cat = rng.choice(DETECTION_SAMPLES[level])
    return [{"type": dtype, "category": cat, "level": str(level), "count": rng.randint(1, 3),
             "layer": "lexicon" if cat == "lexicon" else ("secrets" if level == Level.RESTRICTED else "personal")}]


def _extra_users(db: Session, rng: random.Random) -> None:
    depts = list(db.scalars(select(Department)))
    by_name = {d.name: d for d in depts}
    pw = _hash("Pilote!2026")  # comptes pilotes fictifs, non affichés
    managed = {"Transport maritime"}  # déjà un manager démo
    names = list(zip(data.FIRST_NAMES, data.LAST_NAMES, strict=True))
    for i, (first, last) in enumerate(names):
        if i < len(depts) and depts[i].name not in managed:
            dept, role, budget = depts[i], "MANAGER", 10
        elif i < 13:
            dept, role, budget = by_name["Informatique"], "DEVELOPER", 15
        else:
            dept, role, budget = rng.choice(depts), "USER", rng.choice([4, 5, 5, 6, 8])
        email = f"{first.lower()}.{last.lower()}@rdt-demo.local".translate(str.maketrans("éèëïî", "eeeii"))
        db.add(User(email=email, full_name=f"{first} {last}", password_hash=pw, role=role, department_id=dept.id,
                    monthly_budget_eur=Decimal(budget)))
    db.flush()


def _ts(rng: random.Random, day: datetime) -> datetime:
    return day.replace(hour=rng.randint(7, 18), minute=rng.randint(0, 59), second=rng.randint(0, 59),
                       microsecond=rng.randint(0, 999999))


def seed_activity(db: Session, rng: random.Random, now: datetime) -> None:
    _extra_users(db, rng)
    users = list(db.scalars(select(User).where(User.email != "quota@rdt-demo.local")))
    models = list(db.scalars(select(LlmModel)).unique())
    weights = {u.id: rng.uniform(0.3, 2.0) for u in users}

    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    days = [today - timedelta(days=i) for i in range(DAYS - 1, -1, -1)]
    day_w = [1.0 if d.weekday() < 5 else 0.12 for d in days]
    per_day = [round(TARGET_REQUESTS * w / sum(day_w)) for w in day_w]

    events: list[tuple] = []  # (ts, kwargs pour audit_service.log_event) triés à la fin
    level_weights = [(Level.PUBLIC, 45), (Level.INTERNAL, 32), (Level.CONFIDENTIAL, 22), (Level.RESTRICTED, 1)]
    logged_in: set[tuple[int, str]] = set()

    for day, count in zip(days, per_day, strict=True):
        for _ in range(count):
            ts = _ts(rng, day)
            if ts > now:
                ts = now - timedelta(minutes=rng.randint(1, 120))
            user = rng.choices(users, weights=[weights[u.id] for u in users])[0]
            if (user.id, day.date().isoformat()) not in logged_in:
                logged_in.add((user.id, day.date().isoformat()))
                events.append((ts - timedelta(minutes=5), dict(event_type="LOGIN_SUCCESS", category="auth",
                               user_id=user.id, details={"ip": f"10.0.0.{rng.randint(2, 250)}"})))
            app = "developer" if user.role == "DEVELOPER" and rng.random() < 0.6 else (
                "evaluation" if rng.random() < 0.02 else "chat")
            level = rng.choices([lvl for lvl, _ in level_weights], weights=[w for _, w in level_weights])[0]
            detections = _detections(rng, level)
            decision = policy_service.decide(level)
            rid = uuid.UUID(int=rng.getrandbits(128)).hex
            base = dict(request_id=rid, user_id=user.id, department_id=user.department_id, app=app,
                        classification=str(level), detections=detections, decision=str(decision),
                        is_simulated=True, created_at=ts)
            if decision.value == "BLOCK":
                db.add(LlmRequest(**base, routing_reason="Secret détecté : requête bloquée, aucun modèle appelé.",
                                  status="BLOCKED"))
                events.append((ts, dict(event_type="REQUEST_BLOCKED", category="security", severity=Severity.CRITICAL,
                                        status="BLOCKED", user_id=user.id, request_id=rid,
                                        details={"classification": str(level), "detections": detections, "app": app})))
                continue

            eligible = policy_service.eligible_models(models, level, user.role)
            complexity = model_router.Complexity("COMPLEX" if rng.random() < 0.3 else "SIMPLE", 0)
            candidates = model_router.order_candidates(eligible, complexity)
            # Un peu de mode manuel parmi les modèles éligibles, pour varier la répartition.
            if rng.random() < 0.25:
                rng.shuffle(candidates)
            fallback = rng.random() < 0.03 and len(candidates) > 1
            if fallback:
                failed = candidates[0]
                events.append((ts, dict(event_type="PROVIDER_ERROR", category="ai", severity=Severity.WARNING,
                                        status="ERROR", user_id=user.id, request_id=rid,
                                        details={"model": failed.litellm_name, "provider": failed.provider.name,
                                                 "error": "Timeout"})))
            model = candidates[1] if fallback else candidates[0]
            tin, tout = rng.randint(60, 1800), rng.randint(80, 900)
            if complexity.level == "COMPLEX":
                tin, tout = tin * 2, tout * 2
            cost = cost_service.compute_cost(model.price, tin, tout)
            latency = rng.randint(500, 3500) if model.hosting == "EXTERNAL" else rng.randint(900, 6000)
            reason = policy_service.explain(ClassificationResult(level, [], {"message": level}), decision)
            db.add(LlmRequest(**base, routing_reason=reason, complexity=complexity.level, provider=model.provider.name,
                              model=model.litellm_name, hosting=model.hosting, fallback_used=fallback,
                              input_tokens=tin, output_tokens=tout, tokens_estimated=False, cost_eur=cost,
                              latency_ms=latency, status="SUCCESS"))
            events.append((ts, dict(event_type="AI_REQUEST", category="ai", user_id=user.id, request_id=rid,
                                    details={"app": app, "classification": str(level), "decision": str(decision),
                                             "mode": "auto", "model": model.litellm_name, "hosting": model.hosting,
                                             "fallback_used": fallback, "detections": detections,
                                             "cost_eur": str(cost) if cost is not None else None,
                                             "simulated": True})))

    # Autres événements de sécurité variés.
    for _ in range(7):
        ts = _ts(rng, rng.choice(days))
        events.append((min(ts, now), dict(event_type="LOGIN_FAILED", category="security", severity=Severity.WARNING,
                                          status="FAILED", details={"email_domain": "rdt-demo.local",
                                                                    "ip": f"10.0.1.{rng.randint(2, 250)}"})))
    for _ in range(4):
        ts = _ts(rng, rng.choice(days))
        u = rng.choice([u for u in users if u.role == "USER"])
        events.append((min(ts, now), dict(event_type="MANUAL_MODEL_REFUSED", category="security",
                                          severity=Severity.WARNING, status="REFUSED", user_id=u.id,
                                          details={"requested_model": "anthropic/claude-sonnet-4-5",
                                                   "classification": "CONFIDENTIAL",
                                                   "reason": "Modèle non autorisé pour le niveau de confidentialité"})))
    ts = _ts(rng, days[-5])
    events.append((ts, dict(event_type="RATE_LIMITED", category="security", severity=Severity.WARNING,
                            status="DENIED", details={"route": "login", "ip": "10.0.1.77"})))

    db.flush()
    _quota_scenarios(db, rng, now, models, events)

    # Le journal est chaîné : on insère dans l'ordre chronologique.
    events.sort(key=lambda e: e[0])
    for ts, kwargs in events:
        audit_service.log_event(db, ts=ts, **kwargs)


def _fill_month(db: Session, rng: random.Random, user: User, model: LlmModel, target: Decimal, now: datetime,
                events: list) -> None:
    """Ajoute des requêtes ce mois-ci jusqu'à ce que la consommation du mois atteigne `target`."""
    start = quota_service.month_start(now)
    current = Decimal(db.scalar(select(func.coalesce(func.sum(LlmRequest.cost_eur), 0)).where(
        LlmRequest.user_id == user.id, LlmRequest.created_at >= start)))
    span = max(60, int((now - start).total_seconds()) - 60)
    while current < target:
        remaining = target - current
        tin, tout = 50000, 5000
        cost = cost_service.compute_cost(model.price, tin, tout)
        if cost >= remaining:  # dernière requête : ajustée pour tomber pile sur la cible
            tout = max(1, int(remaining * cost_service.MILLION / model.price.output_per_mtok))
            tin = 0
            cost = remaining
        ts = start + timedelta(seconds=rng.randint(0, span))
        rid = uuid.UUID(int=rng.getrandbits(128)).hex
        db.add(LlmRequest(request_id=rid, user_id=user.id, department_id=user.department_id, app="chat",
                          classification="INTERNAL", detections=[], decision="ALLOW",
                          routing_reason="Requête de démonstration (consommation de quota)", complexity="COMPLEX",
                          provider=model.provider.name, model=model.litellm_name, hosting=model.hosting,
                          input_tokens=tin, output_tokens=tout, cost_eur=cost, latency_ms=rng.randint(800, 3000),
                          status="SUCCESS", is_simulated=True, created_at=ts))
        events.append((ts, dict(event_type="AI_REQUEST", category="ai", user_id=user.id, request_id=rid,
                                details={"app": "chat", "classification": "INTERNAL", "decision": "ALLOW",
                                         "mode": "auto", "model": model.litellm_name, "hosting": model.hosting,
                                         "cost_eur": str(cost), "simulated": True})))
        current += cost
    db.flush()


def _quota_scenarios(db: Session, rng: random.Random, now: datetime, models: list[LlmModel], events: list) -> None:
    haiku = next(m for m in models if m.litellm_name == "anthropic/claude-haiku-4-5")
    scenarios = [("user@rdt-demo.local", Decimal("0.91")), ("quota@rdt-demo.local", Decimal("1.00"))]
    # Trois utilisateurs pilotes (non démo) proches de leur quota.
    others = [u for u in db.scalars(select(User).where(User.role == "USER").order_by(User.id))
              if u.email not in {a["email"] for a in data.DEMO_ACCOUNTS}][:3]
    scenarios += [(u.email, pct) for u, pct in zip(others, [Decimal("0.72"), Decimal("0.84"), Decimal("0.95")], strict=True)]

    period = quota_service.month_start(now).strftime("%Y-%m")
    for email, pct in scenarios:
        user = db.scalar(select(User).where(User.email == email))
        target = (user.monthly_budget_eur * pct).quantize(Decimal("0.000001"))
        _fill_month(db, rng, user, haiku, target, now, events)
        for threshold in (70, 90, 100):
            if pct * 100 >= threshold:
                db.add(QuotaAlert(scope="user", scope_id=user.id, period=period, threshold=threshold))
                events.append((now - timedelta(minutes=rng.randint(5, 600)), dict(
                    event_type="QUOTA_THRESHOLD", category="quota",
                    severity=Severity.CRITICAL if threshold == 100 else Severity.WARNING, status="ALERT",
                    user_id=user.id, details={"scope": "user", "scope_id": user.id, "threshold": threshold,
                                              "pct": float(pct * 100)})))
    db.flush()


def _sample_conversations(db: Session, now: datetime) -> None:
    """Deux conversations d'exemple pour le compte utilisateur démo (contenu fictif et PUBLIC)."""
    user = db.scalar(select(User).where(User.email == "user@rdt-demo.local"))
    samples = [
        ("Différence FOB / CIF", "Explique-moi la différence entre FOB et CIF.",
         "[Réponse simulée] En FOB, le risque est transféré quand la marchandise est à bord ; en CIF, le vendeur "
         "paie en plus le fret et l'assurance jusqu'au port de destination."),
        ("Rôle du connaissement", "À quoi sert un connaissement (B/L) ?",
         "[Réponse simulée] Le connaissement est un reçu de la marchandise, une preuve du contrat de transport et "
         "un titre représentatif de la marchandise."),
    ]
    for i, (title, question, answer) in enumerate(samples):
        ts = now - timedelta(days=2 - i, hours=3)
        conv = Conversation(user_id=user.id, title=title, max_classification="PUBLIC", created_at=ts, updated_at=ts)
        db.add(conv)
        db.flush()
        db.add(Message(conversation_id=conv.id, role="user", content=question, classification="PUBLIC", created_at=ts))
        db.add(Message(conversation_id=conv.id, role="assistant", content=answer, classification="PUBLIC",
                       created_at=ts, routing={"classification": "PUBLIC", "decision": "ALLOW", "simulated": True,
                                               "reason": "Exemple de démonstration.", "detections": []}))
    db.flush()


def run(reset: bool = False) -> None:
    if reset:
        with engine.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
        from alembic import command
        from alembic.config import Config
        command.upgrade(Config("alembic.ini"), "head")

    with SessionLocal() as db:
        if db.scalar(select(func.count(User.id))):
            logger.info("Base déjà initialisée : seed ignoré.")
            return
        now = datetime.now(UTC)
        rng = random.Random(SEED)
        seed_reference(db)
        seed_activity(db, rng, now)
        _sample_conversations(db, now)
        db.commit()
        logger.info("Seed terminé : %s utilisateurs, %s requêtes.", db.scalar(select(func.count(User.id))),
                    db.scalar(select(func.count(LlmRequest.id))))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="supprime toutes les données puis réinitialise")
    run(parser.parse_args().reset)
