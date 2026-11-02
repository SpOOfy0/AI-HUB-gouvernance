"""Point d'entrée FastAPI de RDT AI Hub."""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.core.logging_config import configure_logging
from app.core.request_context import new_request_id, request_id_var
from app.routers import ROUTERS
from app.services.llm_gateway import GatewayError

configure_logging()

_settings = get_settings()
if not _settings.demo_mode and (len(_settings.jwt_secret) < 32 or _settings.jwt_secret.startswith(("change-me", "dev-only"))):
    # Hors démo, on refuse de démarrer avec un secret faible ou par défaut.
    raise RuntimeError("JWT_SECRET absent ou trop faible (32 caractères minimum hors mode démo).")

_docs = _settings.demo_mode or _settings.enable_api_docs
app = FastAPI(
    title="RDT AI Hub API",
    description="Passerelle de gouvernance, sécurité et routage des modèles d'IA (prototype).",
    version="0.1.0",
    docs_url="/docs" if _docs else None,
    redoc_url=None,
    openapi_url="/openapi.json" if _docs else None,
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Un request_id par requête, présent dans les logs, le journal et l'en-tête de réponse."""
    rid = new_request_id()
    token = request_id_var.set(rid)
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    response.headers["X-Request-ID"] = rid
    return response


@app.exception_handler(GatewayError)
async def gateway_error_handler(_: Request, exc: GatewayError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code,
                        content={"detail": exc.message, "code": exc.code, "request_id": exc.request_id})


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """En-têtes de sécurité de base (clickjacking, sniffing MIME, fuite du Referer)."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    return response


for router in ROUTERS:
    app.include_router(router)

# Déploiement en un seul conteneur : FastAPI sert aussi l'interface (export statique Next.js).
# Monté en dernier : les routes /api/* restent prioritaires.
if _settings.static_dir and Path(_settings.static_dir).is_dir():
    app.mount("/", StaticFiles(directory=_settings.static_dir, html=True), name="frontend")
