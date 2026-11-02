"""Énumérations métier partagées.

Les niveaux de classification sont ordonnés : PUBLIC < INTERNAL < CONFIDENTIAL < RESTRICTED.
"""
from enum import StrEnum


class Level(StrEnum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"

    @property
    def rank(self) -> int:
        return LEVEL_ORDER.index(self)

    @staticmethod
    def max(*levels: "Level | None") -> "Level":
        present = [lvl for lvl in levels if lvl is not None]
        return max(present, key=lambda lvl: lvl.rank) if present else Level.PUBLIC


LEVEL_ORDER = [Level.PUBLIC, Level.INTERNAL, Level.CONFIDENTIAL, Level.RESTRICTED]


class Role(StrEnum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    DEVELOPER = "DEVELOPER"
    USER = "USER"


class Hosting(StrEnum):
    EXTERNAL = "EXTERNAL"
    PRIVATE = "PRIVATE"


class Tier(StrEnum):
    ECO = "eco"
    STANDARD = "standard"
    PREMIUM = "premium"

    @property
    def rank(self) -> int:
        return [Tier.ECO, Tier.STANDARD, Tier.PREMIUM].index(self)


class Decision(StrEnum):
    ALLOW = "ALLOW"
    PRIVATE_ONLY = "PRIVATE_ONLY"
    BLOCK = "BLOCK"


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class App(StrEnum):
    CHAT = "chat"
    DEVELOPER = "developer"
    EVALUATION = "evaluation"
