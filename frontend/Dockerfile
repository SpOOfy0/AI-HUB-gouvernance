# --- Dépendances ---
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
# CA d'entreprise optionnelle (proxy TLS de la DSI), fournie comme secret de build.
RUN --mount=type=secret,id=corporate_ca,required=false \
    if [ -f /run/secrets/corporate_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/corporate_ca; fi; \
    npm ci

# --- Build ---
FROM node:22-alpine AS build
WORKDIR /app
ARG BACKEND_INTERNAL_URL=http://backend:8000
ENV BACKEND_INTERNAL_URL=$BACKEND_INTERNAL_URL NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# --- Exécution (sortie standalone, image légère, utilisateur non root) ---
FROM node:22-alpine AS run
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
USER node
EXPOSE 3000
CMD ["node", "server.js"]
