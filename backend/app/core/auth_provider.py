"""Fournisseurs d'authentification.

Seule l'authentification locale (email + mot de passe haché) est implémentée.
L'interface `AuthProvider` permet de brancher plus tard un SSO OIDC
(Entra ID / Active Directory) sans toucher au reste de l'application :

    class OidcAuthProvider(AuthProvider):
        # 1. /auth/oidc/login redirige vers l'IdP (authorization code + PKCE)
        # 2. /auth/oidc/callback échange le code contre un id_token, vérifie
        #    signature (JWKS), issuer, audience, nonce
        # 3. retrouve ou crée l'utilisateur à partir du claim email / oid,
        #    mappe les groupes AD vers les rôles de la plateforme (ADMIN, MANAGER...)
        # 4. émet ensuite notre propre cookie de session, comme aujourd'hui
    NON IMPLÉMENTÉ dans le prototype (voir docs/DECISIONS.md).
"""
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models import User

# Hash factice : on vérifie quand même un mot de passe si l'email est inconnu,
# pour que le temps de réponse ne révèle pas l'existence d'un compte.
_DUMMY_HASH = hash_password("dummy-password-for-timing")


class AuthProvider(Protocol):
    def authenticate(self, db: Session, email: str, password: str) -> User | None: ...


class LocalPasswordAuthProvider:
    def authenticate(self, db: Session, email: str, password: str) -> User | None:
        user = db.scalar(select(User).where(User.email == email.lower().strip()))
        if user is None:
            verify_password(password, _DUMMY_HASH)
            return None
        if not user.is_active or not verify_password(password, user.password_hash):
            return None
        return user


def get_auth_provider() -> AuthProvider:
    return LocalPasswordAuthProvider()
