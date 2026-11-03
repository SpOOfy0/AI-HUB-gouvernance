# Image unique pour l'hébergement (Render, ou tout hébergeur de conteneurs) :
# FastAPI sert l'API (/api/*) ET l'interface (export statique Next.js).
# Pour le développement local, utiliser docker-compose.yml (frontend et backend séparés).
# Volontairement sans fonctionnalité BuildKit avancée (secrets de build) : compatible avec tous les builders.

# --- 1. Build de l'interface en site statique ---
FROM node:22-alpine AS frontend
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ENV NEXT_OUTPUT=export NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# --- 2. Backend Python (sans outils de test) + interface statique ---
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    LITELLM_LOCAL_MODEL_COST_MAP=True STATIC_DIR=/app/static
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install -r requirements.txt
COPY backend/ ./
COPY --from=frontend /web/out ./static
RUN useradd --create-home --uid 1000 app && chown -R app /app
USER app
EXPOSE 8000
CMD ["./entrypoint.sh"]
