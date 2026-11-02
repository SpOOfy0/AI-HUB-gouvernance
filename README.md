# RDT AI Hub

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

## Documentation
- [docs/DECISIONS.md](docs/DECISIONS.md) : décisions d'architecture
- [docs/NOTES-ENTRETIEN.md](docs/NOTES-ENTRETIEN.md) : questions et réponses
- `CLAUDE.md` : contexte et commandes de développement

*(README complet : phase 5.)*
