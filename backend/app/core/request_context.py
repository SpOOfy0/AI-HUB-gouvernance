"""Identifiant de requête (request_id) propagé dans tous les logs via une contextvar."""
import uuid
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def new_request_id() -> str:
    return uuid.uuid4().hex


def get_request_id() -> str:
    rid = request_id_var.get()
    if rid == "-":
        rid = new_request_id()
        request_id_var.set(rid)
    return rid
