"""Purge des conversations au-delà de la durée de rétention (politique "retention").

Exécutée au démarrage du backend. En production : tâche planifiée quotidienne (cron / CronJob).
"""
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import Conversation
from app.services.policy_store import get_policy

logger = logging.getLogger(__name__)


def purge_expired(db: Session) -> int:
    days = int(get_policy(db)["retention"]["conversation_days"])
    cutoff = datetime.now(UTC) - timedelta(days=days)
    # Les messages sont supprimés en cascade (ON DELETE CASCADE).
    result = db.execute(delete(Conversation).where(Conversation.updated_at < cutoff))
    db.commit()
    return result.rowcount or 0


if __name__ == "__main__":
    from app.db import SessionLocal

    logging.basicConfig(level=logging.INFO)
    with SessionLocal() as session:
        logger.info("Conversations purgées : %s", purge_expired(session))
