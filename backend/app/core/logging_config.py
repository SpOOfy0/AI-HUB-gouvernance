"""Configuration des logs applicatifs.

Règle : aucun contenu de prompt, aucun secret, aucun header Authorization dans les logs.
Le code n'écrit jamais de contenu ; ce filtre est une ceinture de sécurité supplémentaire
qui masque les motifs les plus évidents si un message en contenait par erreur.
"""
import logging
import re

from app.core.request_context import request_id_var

_REDACTIONS = [
    re.compile(r"(authorization\s*[:=]\s*)(\S+(\s+\S+)?)", re.IGNORECASE),
    re.compile(r"(cookie\s*[:=]\s*)(\S+)", re.IGNORECASE),
    re.compile(r"()(\b(sk|ghp|gho|glpat|xox[abprs])[-_][A-Za-z0-9_\-]{4,})"),
    re.compile(r"()(eyJ[\w-]+\.eyJ[\w-]+\.[\w-]+)"),
]


class RequestIdAndRedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        msg = record.getMessage()
        for pattern in _REDACTIONS:
            msg = pattern.sub(lambda m: m.group(1) + "[MASQUÉ]", msg)
        record.msg, record.args = msg, ()
        return True


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"))
    handler.addFilter(RequestIdAndRedactFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    # LiteLLM peut être verbeux et journaliser des payloads : on le limite aux erreurs.
    for noisy in ("LiteLLM", "litellm", "httpx"):
        logging.getLogger(noisy).setLevel(logging.ERROR)
