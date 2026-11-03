# AI Hub Gouvernance

**Enterprise AI Governance Platform** : passerelle centralisée de gouvernance, de sécurité et de routage
des modèles d'IA pour la DSI d'un groupe de transit et de logistique internationale (prototype).

> Ce n'est pas un chatbot : chaque requête est classifiée (DLP), routée selon sa confidentialité vers un
> modèle autorisé, comptée dans les quotas, puis journalisée dans un journal d'audit infalsifiable.

## Démarrage rapide

```bash
cp .env.example .env
docker compose up --build
```

- Interface : http://localhost:3000 (comptes de démo affichés sur la page de connexion)
- API et Swagger : http://localhost:8000/docs
- Tests : `docker compose exec backend pytest`

Aucune clé API n'est nécessaire : en mode démo (`DEMO_MODE=true`), la génération de texte est simulée.
La classification, le routage, les quotas, les coûts et l'audit s'exécutent réellement.

## Mise en ligne gratuite

Render (application) + Neon (PostgreSQL), sans carte bancaire : voir [docs/DEPLOIEMENT.md](docs/DEPLOIEMENT.md).
Pour un mode réel gratuit, une clé Gemini (Google AI Studio) suffit pour les requêtes PUBLIC.

## Documentation
- [docs/DEPLOIEMENT.md](docs/DEPLOIEMENT.md) : déploiement gratuit et mode réel
- [SECURITY.md](SECURITY.md) : modèle de menace, limites de la DLP, RGPD
- [docs/DECISIONS.md](docs/DECISIONS.md) : décisions d'architecture
- [docs/NOTES-ENTRETIEN.md](docs/NOTES-ENTRETIEN.md) : questions et réponses
- `CLAUDE.md` : contexte et commandes de développement

## État du prototype

| Module | État |
|---|---|
| Socle (Docker, PostgreSQL, Alembic, auth, rôles, layout) | Fait |
| Passerelle : DLP, classification, politique, routage, fallback, coûts, quotas | Fait, 111 tests |
| Mode réel (clés API, administrateur initial, aucun mock) + déploiement Render | Fait |
| Journal d'audit append-only chaîné par hash + vérification | Fait |
| Playground avec panneau de routage | Fait |
| Sécurité : événements, bac à sable, politique, lexique | Fait |
| Dashboard, coûts, modèles, utilisateurs, Developer Guard | Phases 4-5 (à venir) |

*(README complet : phase 5.)*
