"""DLP (Data Loss Prevention) en couches.

Couche 1 - secrets et identifiants : regex + entropie + contrôle de Luhn.
Couche 2 - données personnelles et financières : email, téléphone, IBAN (clé mod 97), NIR.
Couche 3 - lexique métier configurable en base (clients, expressions commerciales, sites...).

Chaque détection renvoie uniquement : type, catégorie, niveau, nombre d'occurrences.
JAMAIS la valeur détectée.

Fail closed : si un détecteur lève une exception, on considère qu'il a trouvé
quelque chose au niveau maximal qu'il peut attribuer.

Limites connues (voir SECURITY.md) : des regex ne détectent pas tout (reformulation,
encodage base64, texte découpé), et produisent des faux positifs (ex. "marge d'erreur").
"""
import logging
import math
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

from app.core.enums import Level

logger = logging.getLogger(__name__)

# Catégories de détection -> niveau par défaut. Surchargé par la politique en base
# (clé "detection_levels"), modifiable par un ADMIN.
DEFAULT_DETECTION_LEVELS: dict[str, str] = {
    "secret": Level.RESTRICTED,
    "payment_card": Level.RESTRICTED,
    "personal_data": Level.CONFIDENTIAL,
    "financial": Level.CONFIDENTIAL,
}


@dataclass(frozen=True)
class Detection:
    type: str        # ex. "api_key", "iban", "lexique:commercial"
    category: str    # secret | payment_card | personal_data | financial | lexicon | detector_error
    level: Level
    count: int
    layer: str       # secrets | personal | lexicon

    def to_dict(self) -> dict:
        return {"type": self.type, "category": self.category, "level": str(self.level),
                "count": self.count, "layer": self.layer}


@dataclass(frozen=True)
class LexiconEntry:
    """Vue simple d'un terme du lexique (découplée du modèle SQLAlchemy pour les tests)."""
    term: str
    category: str
    level: Level
    is_regex: bool = False


def normalize(text: str) -> str:
    """Minuscule et sans accents : 'Négocié' et 'negocie' sont équivalents."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


# ---------------------------------------------------------------------------
# Couche 1 : secrets
# ---------------------------------------------------------------------------
SECRET_PATTERNS: dict[str, re.Pattern] = {
    # sk-... (OpenAI, Anthropic sk-ant-, DeepSeek). Volontairement large (4+ caractères) :
    # "sk-xxxx" suffit à bloquer. Fail closed, faux positifs acceptés.
    "api_key": re.compile(
        r"\b(?:sk|rk|pk)-[A-Za-z0-9_\-]{4,}"
        r"|\bgh[pousr]_[A-Za-z0-9]{20,}"
        r"|\bglpat-[A-Za-z0-9_\-]{20,}"
        r"|\bAKIA[0-9A-Z]{16}\b"
        r"|\bAIza[0-9A-Za-z_\-]{35}"
        r"|\bxox[abprs]-[A-Za-z0-9-]{10,}"
    ),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}"),
    "private_key": re.compile(r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----"),
    "password": re.compile(
        r"(?:password|passwd|pwd|mot de passe|mdp|pass)\s*[:=]\s*\S+", re.IGNORECASE
    ),
    "connection_string": re.compile(
        r"\b(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis|amqp|mssql|sqlserver)://[^\s:/@]+:[^\s@]+@",
        re.IGNORECASE,
    ),
    "api_key_assignment": re.compile(
        r"\b(?:api[_-]?key|apikey|secret[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret)\s*[:=]\s*['\"]?[A-Za-z0-9_\-./+=]{8,}",
        re.IGNORECASE,
    ),
}

# Chaînes candidates pour le test d'entropie : longues, sans espace, alphanumériques étendues.
_ENTROPY_CANDIDATE = re.compile(r"[A-Za-z0-9+/=_\-]{32,}")
ENTROPY_THRESHOLD = 4.5  # bits/caractère. Un hash hexadécimal plafonne à 4.0 : non détecté (voulu).


def shannon_entropy(s: str) -> float:
    freq = {c: s.count(c) for c in set(s)}
    return -sum((n / len(s)) * math.log2(n / len(s)) for n in freq.values())


def _count_high_entropy(text: str) -> int:
    count = 0
    for candidate in _ENTROPY_CANDIDATE.findall(text):
        has_digit = any(c.isdigit() for c in candidate)
        has_alpha = any(c.isalpha() for c in candidate)
        if has_digit and has_alpha and shannon_entropy(candidate) >= ENTROPY_THRESHOLD:
            count += 1
    return count


def luhn_valid(number: str) -> bool:
    digits = [int(d) for d in number if d.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


_CARD_CANDIDATE = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")


def _count_cards(text: str) -> int:
    return sum(1 for m in _CARD_CANDIDATE.findall(text) if luhn_valid(m))


# ---------------------------------------------------------------------------
# Couche 2 : données personnelles et financières
# ---------------------------------------------------------------------------
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE = re.compile(
    r"(?<!\d)(?:(?:\+|00)33[\s.-]?|0)[1-9](?:[\s.-]?\d{2}){4}(?!\d)"   # France
    r"|(?<!\d)\+(?!33)\d{1,3}[\s.-]?\d{2,4}(?:[\s.-]?\d{2,4}){2,4}(?!\d)"  # international
)
_IBAN_CANDIDATE = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}(?:[ ]?[A-Z0-9]{1,4})?\b")
_NIR_CANDIDATE = re.compile(r"\b([12])[ ]?(\d{2})[ ]?(0[1-9]|1[0-2]|[2-9]\d)[ ]?(\d{2}|2[AB])[ ]?(\d{3})[ ]?(\d{3})[ ]?(\d{2})\b")


def iban_valid(candidate: str) -> bool:
    iban = candidate.replace(" ", "").upper()
    if not 15 <= len(iban) <= 34:
        return False
    rearranged = iban[4:] + iban[:4]
    numeric = "".join(str(int(c, 36)) for c in rearranged)
    return int(numeric) % 97 == 1


def _count_ibans(text: str) -> int:
    return sum(1 for m in _IBAN_CANDIDATE.finditer(text) if iban_valid(m.group(0)))


def _count_nir(text: str) -> int:
    """Numéro de sécurité sociale français, avec contrôle de la clé (97 - n mod 97)."""
    count = 0
    for m in _NIR_CANDIDATE.finditer(text):
        sex, year, month, dept, commune, order, key = m.groups()
        dept_num = dept.replace("2A", "19").replace("2B", "18")
        number = int(sex + year + month + dept_num + commune + order)
        if 97 - (number % 97) == int(key):
            count += 1
    return count


# ---------------------------------------------------------------------------
# Détecteurs : (nom, catégorie, couche, fonction de comptage)
# ---------------------------------------------------------------------------
def _regex_counter(pattern: re.Pattern) -> Callable[[str], int]:
    return lambda text: len(pattern.findall(text))


BUILTIN_DETECTORS: list[tuple[str, str, str, Callable[[str], int]]] = [
    *[(name, "secret", "secrets", _regex_counter(p)) for name, p in SECRET_PATTERNS.items()],
    ("high_entropy_string", "secret", "secrets", _count_high_entropy),
    ("payment_card", "payment_card", "secrets", _count_cards),
    ("email", "personal_data", "personal", _regex_counter(EMAIL)),
    ("phone", "personal_data", "personal", _regex_counter(PHONE)),
    ("social_security_number", "personal_data", "personal", _count_nir),
    ("iban", "financial", "personal", _count_ibans),
]


def _compile_lexicon(entry: LexiconEntry) -> re.Pattern:
    pattern = normalize(entry.term)
    if not entry.is_regex:
        pattern = r"\b" + re.escape(pattern) + r"\b"
    return re.compile(pattern, re.IGNORECASE)


def scan(
    text: str,
    lexicon: list[LexiconEntry] | None = None,
    detection_levels: dict[str, str] | None = None,
) -> list[Detection]:
    """Analyse un texte et renvoie la liste des détections (sans les valeurs)."""
    levels = {**DEFAULT_DETECTION_LEVELS, **(detection_levels or {})}
    detections: list[Detection] = []

    for name, category, layer, counter in BUILTIN_DETECTORS:
        try:
            count = counter(text)
        except Exception:  # fail closed
            logger.exception("Détecteur DLP en erreur : %s", name)
            detections.append(Detection(f"detector_error:{name}", "detector_error",
                                        Level(levels.get(category, Level.RESTRICTED)), 1, layer))
            continue
        if count:
            detections.append(Detection(name, category, Level(levels.get(category, Level.RESTRICTED)), count, layer))

    # Lexique métier : on agrège par catégorie (ex. "lexique:commercial") en gardant le niveau max.
    normalized = normalize(text)
    by_category: dict[str, tuple[Level, int]] = {}
    for entry in lexicon or []:
        try:
            count = len(_compile_lexicon(entry).findall(normalized))
            level = entry.level
        except Exception:  # regex invalide saisie par un admin : fail closed au niveau du terme
            logger.exception("Terme de lexique invalide (catégorie %s)", entry.category)
            count, level = 1, Level.max(entry.level, Level.CONFIDENTIAL)
        if count:
            prev_level, prev_count = by_category.get(entry.category, (Level.PUBLIC, 0))
            by_category[entry.category] = (Level.max(prev_level, level), prev_count + count)
    for category, (level, count) in by_category.items():
        detections.append(Detection(f"lexique:{category}", "lexicon", level, count, "lexicon"))

    return detections


def max_level(detections: list[Detection]) -> Level:
    return Level.max(*(d.level for d in detections))
