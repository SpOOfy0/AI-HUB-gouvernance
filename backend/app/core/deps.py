"""Dépendances FastAPI : utilisateur courant et contrôle des rôles.

La sécurité est appliquée ici, côté backend, sur chaque route.
Le frontend ne fait que masquer des menus (confort, pas sécurité).
"""
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.enums import Role
from app.core.security import decode_access_token
from app.db import get_db
from app.models import User


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(get_settings().cookie_name)
    user_id = decode_access_token(token) if token else None
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentification requise")
    # Le rôle est relu en base à chaque requête : un changement de rôle s'applique immédiatement.
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Compte inactif ou inexistant")
    return user


def require_roles(*roles: Role) -> Callable[..., User]:
    allowed = {r.value for r in roles}

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Accès refusé pour votre rôle")
        return user

    return checker


require_admin = require_roles(Role.ADMIN)
