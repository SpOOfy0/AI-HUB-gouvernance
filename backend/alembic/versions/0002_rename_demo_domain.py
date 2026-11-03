"""Changement de nom de la plateforme (RDT AI Hub -> AI Hub Gouvernance) : données existantes

- comptes de démonstration : @rdt-demo.local -> @aihub-demo.local
- format fictif de numéro de dossier interne dans le lexique : RDT-AAAA-NNNNN -> DOS-AAAA-NNNNN

Le journal d'audit n'est pas modifié : il est en ajout seul, et l'historique reste tel qu'il a été écrit.

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

OLD_DOMAIN, NEW_DOMAIN = "@rdt-demo.local", "@aihub-demo.local"
OLD_TERM, NEW_TERM = r"\brdt-\d{4}-\d{5}\b", r"\bdos-\d{4}-\d{5}\b"


def _rename(old_domain: str, new_domain: str, old_term: str, new_term: str) -> None:
    op.execute(sa.text("UPDATE users SET email = replace(email, :old, :new) WHERE email LIKE :pattern")
               .bindparams(old=old_domain, new=new_domain, pattern=f"%{old_domain}"))
    op.execute(sa.text("UPDATE dlp_lexicon_terms SET term = :new WHERE term = :old")
               .bindparams(old=old_term, new=new_term))


def upgrade() -> None:
    _rename(OLD_DOMAIN, NEW_DOMAIN, OLD_TERM, NEW_TERM)


def downgrade() -> None:
    _rename(NEW_DOMAIN, OLD_DOMAIN, NEW_TERM, OLD_TERM)
