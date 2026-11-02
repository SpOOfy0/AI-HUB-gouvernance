#!/bin/sh
# Démarrage du backend : migrations, seed si base vide, purge de rétention, puis API.
set -e
echo "[entrypoint] Migrations Alembic..."
alembic upgrade head
echo "[entrypoint] Seed (ignoré si la base contient déjà des données)..."
python -m app.seed.seed
echo "[entrypoint] Purge des conversations au-delà de la durée de rétention..."
python -m app.services.retention_service
echo "[entrypoint] Démarrage de l'API"
# PORT : imposé par certains hébergeurs (Render). FORWARDED_ALLOW_IPS : proxys dont on accepte X-Forwarded-For.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1}"
