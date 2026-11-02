"""Point d'entrée FastAPI de RDT AI Hub."""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

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

app = FastAPI(
    title="RDT AI Hub API",
    description="Passerelle de gouvernance, sécurité et routage des modèles d'IA (prototype).",
    version="0.1.0",
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


for router in ROUTERS:
    app.include_router(router)
