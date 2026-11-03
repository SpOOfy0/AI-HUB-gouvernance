"""Tests unitaires de la DLP (test 13) : exemples positifs, négatifs, et limites connues.

Les faux positifs et faux négatifs listés ici sont DOCUMENTÉS et ASSUMÉS : ils décrivent
le comportement actuel, pas un comportement souhaitable. Voir SECURITY.md.
"""
import pytest

from app.core.enums import Level
from app.seed.data import LEXICON
from app.services import dlp_service
from app.services.dlp_service import LexiconEntry, iban_valid, luhn_valid, scan

LEX = [LexiconEntry(t, c, Level(lvl), rx) for t, c, lvl, rx in LEXICON]


def level_of(text: str) -> Level:
    return dlp_service.max_level(scan(text, LEX))


def types_of(text: str) -> set[str]:
    return {d.type for d in scan(text, LEX)}


# --- Exemples du cahier des charges ----------------------------------------------------------
@pytest.mark.parametrize("text,expected", [
    ("Explique-moi la différence entre FOB et CIF.", Level.PUBLIC),
    ("Résume la procédure interne d'ouverture d'un dossier export au site de Fos.", Level.INTERNAL),
    ("Analyse les tarifs négociés avec notre armateur pour la ligne Asie.", Level.CONFIDENTIAL),
    ("Voici notre clé API : sk-xxxx, pourquoi ça ne marche pas ?", Level.RESTRICTED),
])
def test_13_spec_examples(text, expected):
    assert level_of(text) == expected


# --- Couche 1 : secrets (RESTRICTED) ---------------------------------------------------------------
@pytest.mark.parametrize("text,dtype", [
    ("export OPENAI_API_KEY=sk-proj-abcdefghij1234567890", "api_key"),
    ("clé anthropic sk-ant-api03-AbCdEfGh12345678", "api_key"),
    ("token github ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789", "api_key"),
    ("AWS AKIAIOSFODNN7EXAMPLE", "api_key"),
    ("Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U", "jwt"),
    ("-----BEGIN RSA PRIVATE KEY-----\nMIIEow...", "private_key"),
    ("-----BEGIN OPENSSH PRIVATE KEY-----", "private_key"),
    ("le password=Azerty123 ne marche plus", "password"),
    ("mdp : Transit2026!", "password"),
    ("DATABASE_URL=postgresql://admin:S3cret@db.interne:5432/tms", "connection_string"),
    ("api_key: '9f8e7d6c5b4a3f2e1d0c'", "api_key_assignment"),
    ("valeur Zx8Qp2Lm9Rt4Vb7Nc1Kd6Hf3Jg5Ws0Ya8Ue2Io", "high_entropy_string"),
    ("CB du client 4111 1111 1111 1111 exp 12/27", "payment_card"),
])
def test_13_secrets_detected(text, dtype):
    assert dtype in types_of(text)
    assert level_of(text) == Level.RESTRICTED


# --- Couche 2 : données personnelles et financières (CONFIDENTIAL) ------------------------------
@pytest.mark.parametrize("text,dtype", [
    ("Contact : jean.dupont@transit-client.fr", "email"),
    ("Appelez le 06 12 34 56 78", "phone"),
    ("Tél. +33 4 91 23 45 67", "phone"),
    ("IBAN FR76 3000 6000 0112 3456 7890 189", "iban"),
    ("NIR 1 85 05 78 006 084 91", "social_security_number"),  # clé de contrôle valide
])
def test_13_personal_data_detected(text, dtype):
    assert dtype in types_of(text)
    assert level_of(text) == Level.CONFIDENTIAL


# --- Couche 3 : lexique métier -----------------------------------------------------------------------
@pytest.mark.parametrize("text,expected", [
    ("Prépare la cotation client pour NordAgro", Level.CONFIDENTIAL),
    ("Le CONTRAT CADRE avec Groupe Valmer arrive à échéance", Level.CONFIDENTIAL),
    ("Quelle marge sur ce dossier ?", Level.CONFIDENTIAL),
    ("Statut du dossier DOS-2026-00142 ?", Level.INTERNAL),
    ("Horaires de l'entrepôt de Roissy", Level.INTERNAL),
    ("Tarifs negocies sans accents", Level.CONFIDENTIAL),  # insensible aux accents et à la casse
])
def test_13_business_lexicon(text, expected):
    assert level_of(text) == expected


# --- Négatifs : vocabulaire métier public ---------------------------------------------------------
@pytest.mark.parametrize("text", [
    "Le conteneur MSCU1234567 est arrivé au terminal.",
    "Quel est le code SH 8471300000 pour un ordinateur portable ?",
    "Mon numéro EORI FR12345678901234 est-il valide ?",
    "Explique les surestaries et la détention de conteneur.",
    "Différence entre un connaissement et une lettre de transport aérien (LTA).",
    "Hash du commit : 9fceb02d0ae598e95dc970b74767f19372d61af8",  # hexadécimal : entropie < seuil
    "Combien de tokens consomme ma requête ?",
])
def test_13_public_business_text_not_flagged(text):
    assert level_of(text) == Level.PUBLIC, types_of(text)


# --- Limites connues (documentées) -------------------------------------------------------------------
def test_13_known_false_positive_marge_d_erreur():
    """Faux positif connu : « marge d'erreur » contient le terme commercial « marge ».
    Accepté (fail closed) : la requête part vers un modèle privé au lieu d'un modèle externe."""
    assert level_of("Quelle est la marge d'erreur de cette estimation ?") == Level.CONFIDENTIAL


def test_13_known_false_positive_sk_prefix():
    """Faux positif connu : tout mot commençant par « sk- » suivi de 4 caractères est bloqué."""
    assert level_of("La référence produit sk-2024 est épuisée") == Level.RESTRICTED


def test_13_known_false_negative_obfuscated_secret():
    """Faux négatif connu : un secret découpé ou reformulé échappe aux expressions régulières."""
    assert level_of("ma clé commence par s k tiret p r o j puis abc123") == Level.PUBLIC


def test_13_known_false_negative_base64():
    """Faux négatif connu : un texte encodé en base64 court n'est pas décodé avant analyse."""
    assert level_of("bW90IGRlIHBhc3NlOiBhYmM=") == Level.PUBLIC


def test_13_known_false_negative_unknown_client():
    """Faux négatif connu : un client absent du lexique n'est pas reconnu."""
    assert level_of("Analyse le volume annuel du client Tartempion SA") == Level.PUBLIC


# --- Contrôles algorithmiques ---------------------------------------------------------------------
def test_luhn_and_iban_checks_reduce_false_positives():
    assert luhn_valid("4111111111111111") and not luhn_valid("4111111111111112")
    assert iban_valid("FR7630006000011234567890189") and not iban_valid("FR7630006000011234567890188")
    assert "payment_card" not in types_of("Référence 4111 1111 1111 1112")


def test_detections_never_contain_value():
    detections = scan("clé sk-proj-abcdefghij1234567890 et jean@exemple.fr", LEX)
    for d in detections:
        assert set(d.to_dict()) == {"type", "category", "level", "count", "layer"}
        assert "abcdefghij" not in str(d.to_dict())


def test_detector_error_fails_closed(monkeypatch):
    def boom(_text):
        raise RuntimeError("panne")

    detectors = [(n, c, layer, boom if n == "email" else f) for n, c, layer, f in dlp_service.BUILTIN_DETECTORS]
    monkeypatch.setattr(dlp_service, "BUILTIN_DETECTORS", detectors)
    detections = scan("texte anodin", LEX)
    assert any(d.type == "detector_error:email" and d.level == Level.CONFIDENTIAL for d in detections)


def test_invalid_lexicon_regex_fails_closed():
    detections = scan("texte anodin", [LexiconEntry("([invalide", "client", Level.CONFIDENTIAL, True)])
    assert dlp_service.max_level(detections) == Level.CONFIDENTIAL


def test_classification_error_fails_closed(monkeypatch):
    from app.services import classification_service

    monkeypatch.setattr(dlp_service, "scan", lambda *a, **k: 1 / 0)
    result = classification_service.classify("bonjour", [], None, None, [])
    assert result.level == Level.RESTRICTED


def test_nir_with_invalid_key_is_ignored():
    assert "social_security_number" not in types_of("NIR 1 85 05 78 006 084 36")
