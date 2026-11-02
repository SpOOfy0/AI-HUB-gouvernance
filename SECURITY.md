# Sécurité : RDT AI Hub (prototype)

## Modèle de menace (simplifié)

| Menace | Mesure en place | Limite |
|---|---|---|
| Fuite de données vers un fournisseur externe | DLP en couches + politique (RESTRICTED bloqué, CONFIDENTIAL privé uniquement), invariant revérifié avant chaque appel | La DLP par règles ne détecte pas tout (voir ci-dessous) |
| Contournement par un utilisateur (niveau déclaré, modèle manuel, conversation) | Le niveau déclaré ne peut que relever ; mode manuel refusé si non éligible ; niveau de conversation monotone | — |
| Accès non autorisé aux fonctions d'administration | Rôle vérifié côté serveur sur chaque route (403 testés automatiquement sur toutes les routes admin) | Pas de MFA ni de SSO (interface prévue) |
| Vol de session | JWT en cookie httpOnly, Secure, SameSite=Lax ; rôle relu en base à chaque requête | Pas de révocation individuelle avant expiration (8 h) |
| Force brute sur la connexion | Limitation de débit par IP, temps de réponse constant (hash factice) | Limitation en mémoire, sur une seule instance |
| Altération du journal d'audit | Trigger append-only + chaînage SHA-256 + vérification | Un superutilisateur PostgreSQL peut réécrire toute la chaîne : ancrer le dernier hash à l'extérieur en production |
| Fuite par les logs | Aucun contenu journalisé ; filtre de masquage en ceinture de sécurité ; erreurs fournisseur réduites à leur type | — |
| Mauvaise configuration en production | Démarrage refusé avec un secret JWT faible ; comptes de démo désactivés hors démo ; aucun mock hors démo ; Swagger désactivé par défaut | — |

## Limites de la DLP (assumées et testées)

- Les expressions régulières ne détectent pas tout : un secret reformulé (« s k tiret… »), découpé ou encodé (base64) passe.
- Faux positifs connus : « marge d'erreur » (terme commercial « marge »), toute chaîne commençant par `sk-`.
- Un client absent du lexique n'est pas reconnu comme confidentiel.
- L'injection de prompt n'est pas traitée : la passerelle contrôle ce qui sort, pas ce que le modèle répond.
- Piste de production : Microsoft Presidio (NER) et un classifieur exécuté uniquement sur un modèle local.

## Secrets

- Les clés API sont lues dans les variables d'environnement du backend et ne sont jamais renvoyées par l'API.
- Aucune clé réelle dans le dépôt (`.env` ignoré par Git, `.env.example` sans valeur).
- `JWT_SECRET` : 32 caractères minimum hors démo (généré par Render dans le Blueprint).

## Données et RGPD

- **Minimisation** : le journal et la table des requêtes contiennent uniquement des métadonnées (types détectés, jamais les valeurs).
- **Requêtes bloquées** : le contenu n'est écrit nulle part.
- **Rétention** : conversations purgées après 90 jours (paramétrable), purge au démarrage. En production, une tâche quotidienne.
- **Localisation** : l'hébergement de démonstration est en UE (Render Frankfurt, Neon Frankfurt). Pour chaque fournisseur de modèle, la localisation, la rétention et le non-entraînement sont à vérifier contractuellement. L'offre gratuite de Gemini peut utiliser les données pour améliorer les produits de Google, d'où son plafond PUBLIC.

## Dépendances

Audit réalisé en novembre 2026 (`pip-audit`, `npm audit`). Les versions vulnérables ont été mises à jour (LiteLLM, FastAPI/Starlette, Next.js, PostCSS). Il reste un risque connu sur `filelock`, une dépendance indirecte de LiteLLM bloquée en version inférieure à 4.0 par LiteLLM lui-même. Cette bibliothèque gère des verrous de fichiers locaux et n'est pas exposée au réseau. Commandes à relancer régulièrement :
```bash
pip-audit -r backend/requirements.txt
```
```bash
cd frontend && npm audit --omit=dev
```

## Signaler un problème

Prototype d'entretien : ouvrir une issue privée sur le dépôt.
