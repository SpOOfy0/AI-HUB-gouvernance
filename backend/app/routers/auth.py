"""Connexion / déconnexion. JWT stocké dans un cookie httpOnly, Secure, SameSite=Lax."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.auth_provider import AuthProvider, get_auth_provider
from app.core.deps import get_current_user
from app.core.enums import Severity
from app.core.rate_limit import limiter
from app.core.request_context import get_request_id
from app.core.security import create_access_token
from app.db import get_db
from app.models import User
from app.schemas.auth import LoginIn, UserOut
from app.services import audit_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


def user_out(user: User) -> UserOut:
    return UserOut(id=user.id, email=user.email, full_name=user.full_name, role=user.role,
                   department_id=user.department_id, department_name=user.department.name)


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db),
          auth: AuthProvider = Depends(get_auth_provider)) -> UserOut:
    settings = get_settings()
    client_ip = request.client.host if request.client else "unknown"
    if not limiter.allow(f"login:{client_ip}", settings.rate_limit_login_per_minute):
        audit_service.log_event(db, "RATE_LIMITED", category="security", severity=Severity.WARNING, status="DENIED",
                                request_id=get_request_id(), details={"route": "login", "ip": client_ip})
        db.commit()
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Trop de tentatives, réessayez dans une minute.")

    user = auth.authenticate(db, body.email, body.password)
    if user is None:
        # On journalise le domaine de l'email seulement (minimisation), jamais le mot de passe.
        domain = body.email.split("@")[-1][:100] if "@" in body.email else "invalide"
        audit_service.log_event(db, "LOGIN_FAILED", category="security", severity=Severity.WARNING, status="FAILED",
                                request_id=get_request_id(), details={"email_domain": domain, "ip": client_ip})
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Identifiants invalides")

    response.set_cookie(
        settings.cookie_name, create_access_token(user.id), httponly=True, secure=settings.cookie_secure,
        samesite="lax", max_age=settings.jwt_expire_minutes * 60, path="/",
    )
    audit_service.log_event(db, "LOGIN_SUCCESS", category="auth", user_id=user.id, request_id=get_request_id(),
                            details={"ip": client_ip})
    db.commit()
    return user_out(user)


@router.post("/logout", status_code=204)
def logout(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    audit_service.log_event(db, "LOGOUT", category="auth", user_id=user.id, request_id=get_request_id())
    db.commit()
    response.delete_cookie(get_settings().cookie_name, path="/")
    response.status_code = 204
    return response


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return user_out(user)
