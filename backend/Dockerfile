FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LITELLM_LOCAL_MODEL_COST_MAP=True

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
# Les dépendances de test sont incluses pour permettre `docker compose exec backend pytest`
# (prototype ; en production on construirait une image sans outils de test).
# CA d'entreprise optionnelle (proxy TLS de la DSI) : fournie comme secret de build,
# jamais copiée dans l'image. Voir docker-compose.override.example.yml.
RUN --mount=type=secret,id=corporate_ca,required=false \
    if [ -f /run/secrets/corporate_ca ]; then export PIP_CERT=/run/secrets/corporate_ca; fi; \
    pip install -r requirements.txt -r requirements-dev.txt

COPY . .

# Utilisateur non root
RUN useradd --create-home --uid 1000 app && chown -R app /app
USER app

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"
CMD ["./entrypoint.sh"]
