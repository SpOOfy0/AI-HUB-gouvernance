# CLAUDE.md : contexte pour les sessions de travail

## Projet
RDT AI Hub : prototype de **passerelle de gouvernance IA** pour la DSI d'un groupe de transit
(~700 personnes). Ce n'est pas un chatbot : la passerelle classifie chaque requête (DLP),
applique une politique de routage selon la confidentialité, appelle le modèle (via LiteLLM
en bibliothèque, ou un mock en démo), gère quotas/coûts et journalise tout (audit chaîné).
Destiné à une présentation en entretien technique : le code doit rester simple et explicable.

## État d'avancement
- Phase 0 : plan validé.
- Phase 1 (socle) : FAIT. Docker, PostgreSQL, Alembic, modèles, seed, auth JWT cookie, rôles, layout.
- Phase 2 (cœur passerelle) : FAIT. DLP, classification, politique, routeur, fallback, coûts, quotas, audit. 97 tests.
- Phase 3 (interfaces du cœur) : FAIT. Playground + panneau de routage, Sécurité (événements, bac à sable, politique, lexique), Audit (filtres, intégrité).
- Phases 4-5 : non commencées (dashboard, coûts, modèles, utilisateurs, Developer Guard, P2).

## Commandes
```bash
docker compose up --build -d                 # démo complète (aucune clé API nécessaire)
docker compose exec backend pytest           # tests backend (base rdt_test isolée)
docker compose exec backend ruff check .     # lint backend
docker compose exec backend python -m app.seed.seed --reset   # réinitialise la base de démo
cd frontend && npm run typecheck             # vérification TypeScript
```
Frontend : http://localhost:3000 · API/Swagger : http://localhost:8000/docs

## Architecture (résumé)
- `backend/app/services/llm_gateway.py` orchestre : quota → classification → politique →
  sélection → appel fournisseur → fallback → coût → audit.
- Services séparés et testables : `dlp_service`, `classification_service`, `policy_service`,
  `model_router`, `cost_service`, `quota_service`, `audit_service`.
- `backend/app/providers/` : interface `complete()`, `MockProvider`, `LiteLLMProvider`, fabrique.
- Frontend Next.js (App Router) : `/api/*` relayé vers FastAPI (même origine, cookie httpOnly).

## Vérification visuelle
Playwright est préinstallé dans la sandbox : scripts de capture d'écran possibles contre http://localhost:3000.
Attention : `scrollIntoView` renvoie une Promise dans Chrome récent, ne jamais la retourner depuis un `useEffect`.

## Conventions
- Code et commentaires en français, simples. Pas d'abstraction sans usage réel.
- Sécurité uniquement côté backend (dépendances `require_roles`), le frontend masque seulement.
- Jamais de contenu de prompt ni de secret dans : audit, llm_requests, logs. Requête bloquée = contenu stocké nulle part.
- Fonctionnalité simulée = affichée comme simulée. Un bouton visible doit fonctionner.
- Toute décision d'architecture → `docs/DECISIONS.md`. Questions d'entretien → `docs/NOTES-ENTRETIEN.md`.
- Fin de phase : `docker compose up --build`, tests verts, commit clair.
- Composants UI : style shadcn écrits à la main dans `frontend/components/ui` (registre shadcn inaccessible au build).

## Environnement de build (sandbox)
Derrière un proxy TLS : `docker-compose.override.yml` (non versionné) fournit la CA comme secret de build.
Docker Hub peut limiter le débit (429) : `docker pull mirror.gcr.io/library/node:22-alpine && docker tag ... node:22-alpine`.
