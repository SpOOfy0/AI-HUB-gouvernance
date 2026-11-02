"""Routes publiques : santé et configuration d'affichage (mode démo)."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.seed.data import DEMO_ACCOUNTS

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.get("/config/public")
def public_config() -> dict:
    settings = get_settings()
    # Les identifiants de démo ne sont exposés QUE si DEMO_MODE=true.
    accounts = [{"email": a["email"], "password": a["password"], "role": a["role"], "label": a["label"]}
                for a in DEMO_ACCOUNTS] if settings.demo_mode else []
    return {"demo_mode": settings.demo_mode, "demo_accounts": accounts}
