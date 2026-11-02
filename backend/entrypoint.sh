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
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
