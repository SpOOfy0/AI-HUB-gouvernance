# Décisions d'architecture

Format : contexte, décision, alternatives écartées, conséquences. Chaque fiche est courte et
assumée comme un choix de prototype, à réévaluer pour la production.

---

## D1. LiteLLM comme bibliothèque, pas LiteLLM Proxy
- **Contexte** : il faut appeler OpenAI, Anthropic, DeepSeek et Ollama avec une interface unique, et appliquer nos propres règles de gouvernance.
- **Décision** : LiteLLM est utilisé comme SDK Python dans FastAPI, uniquement pour uniformiser l'appel (`litellm.completion`). DLP, routage, quotas, audit sont dans notre code.
- **Écartées** : LiteLLM Proxy, Portkey, Kong AI Gateway (passerelles prêtes à l'emploi, avec leurs propres budgets, clés virtuelles et logs).
- **Conséquences** : contrôle total et logique explicable ligne à ligne. En contrepartie, on maintient nous-mêmes ce que ces produits offrent (clés virtuelles, cache, retries). En production, une passerelle du marché couplée à nos règles via ses plugins ou hooks serait à étudier (voir README « Construire ou acheter »).

## D2. Backend synchrone (SQLAlchemy sync, routes `def`)
- **Contexte** : prototype en 24 h, 40 utilisateurs pilotes, code à expliquer en entretien.
- **Décision** : code synchrone. FastAPI exécute les routes `def` dans un pool de threads.
- **Écartées** : async/await de bout en bout (asyncpg, httpx async).
- **Conséquences** : lecture simple. Chaque appel LLM occupe un thread : suffisant pour un pilote, à passer en async (ou à multiplier les workers) au-delà de quelques centaines d'utilisateurs simultanés.

## D3. Événements de sécurité = journal d'audit (catégorie `security`)
- **Contexte** : le cahier des charges demande un journal d'audit ET des événements de sécurité.
- **Décision** : une seule table `audit_events`, avec une colonne `category` (auth, ai, security, quota, config, admin).
- **Écartées** : une table `security_events` séparée.
- **Conséquences** : une seule source de vérité, entièrement couverte par le chaînage par hash. La page Sécurité est un filtre du journal.

## D4. Journal append-only : trigger PostgreSQL + chaînage par hash
- **Contexte** : le journal doit être infalsifiable, ou du moins toute altération doit être détectable.
- **Décision** : un trigger refuse UPDATE, DELETE et TRUNCATE. Chaque événement stocke `prev_hash` et `hash = SHA-256(prev_hash + JSON canonique)`. Un verrou consultatif (`pg_advisory_xact_lock`) sérialise les insertions pour éviter les fourches de chaîne.
- **Écartées** : simple table sans protection ; stockage WORM externe (S3 Object Lock) ; base dédiée au journal.
- **Conséquences** : un superutilisateur PostgreSQL peut désactiver le trigger, mais l'altération est alors détectée par la vérification. En production : rôle applicatif sans droits DDL, export régulier du dernier hash vers un stockage externe (ancrage) ou un SIEM.

## D5. Session : JWT dans un cookie httpOnly, frontend et API sur la même origine
- **Contexte** : éviter l'exposition du jeton au JavaScript (XSS) et la complexité CORS.
- **Décision** : cookie `httpOnly`, `Secure`, `SameSite=Lax`. Next.js relaie `/api/*` vers FastAPI (rewrite). Le rôle est relu en base à chaque requête.
- **Écartées** : jeton dans `localStorage` ; CORS ouvert entre deux origines.
- **Conséquences** : changement de rôle ou désactivation effectifs immédiatement. Pas de révocation de jeton individuelle (expiration à 8 h) : en production, ajouter une liste de révocation ou des sessions côté serveur. SameSite=Lax et l'API en JSON limitent le CSRF ; un jeton CSRF serait ajouté en production.

## D6. Authentification locale derrière une interface `AuthProvider`
- **Contexte** : la cible est un SSO Entra ID / AD, hors périmètre du prototype.
- **Décision** : interface `AuthProvider.authenticate()` avec une implémentation locale (argon2). Le flux OIDC est décrit dans `core/auth_provider.py` mais non implémenté.
- **Conséquences** : brancher le SSO ne touche ni aux routes métier ni aux contrôles de rôle.

## D7. Hypothèses de niveaux maximaux par modèle
- **Contexte** : il faut décider quels fournisseurs peuvent recevoir quelles données.
- **Décision (démo)** : DeepSeek API ≤ PUBLIC (souveraineté et localisation à évaluer) ; GPT et Claude ≤ INTERNAL (hypothèse : contrat entreprise sans entraînement sur les données) ; Ollama local ≤ CONFIDENTIAL (données ne sortant pas du SI) ; RESTRICTED jamais envoyé.
- **Conséquences** : valeurs stockées en base, modifiables sans code. Elles doivent être validées par la DSI, le RSSI et le DPO à partir des contrats réels.

## D8. Composants UI au style shadcn écrits à la main
- **Contexte** : le registre shadcn n'était pas joignable depuis l'environnement de build.
- **Décision** : composants équivalents (Button, Card, Badge, Input, Table) écrits dans `components/ui`, avec les mêmes conventions (`cva`, `cn`).
- **Conséquences** : pas de dépendance Radix pour l'instant. Les menus sont simples. On pourra les remplacer par les composants shadcn officiels sans changer les pages.

## D9. CA d'entreprise optionnelle au build Docker
- **Contexte** : derrière un proxy TLS de DSI, `pip` et `npm` refusent le certificat.
- **Décision** : secret de build BuildKit optionnel `corporate_ca`, fourni par un `docker-compose.override.yml` local (exemple versionné).
- **Conséquences** : le certificat n'est jamais copié dans l'image et le Dockerfile reste identique avec ou sans proxy.

## D10. Règles de décision codées, paramètres configurables
- **Contexte** : la politique doit être modifiable par un ADMIN, sans permettre de casser la sécurité par erreur.
- **Décision** : les trois règles (RESTRICTED → BLOCK, CONFIDENTIAL → PRIVATE_ONLY, sinon ALLOW selon le niveau max du modèle) sont codées dans `policy_service` et testées. Sont configurables en base : le mapping détection → niveau, le lexique, les seuils de complexité, la rétention et les seuils d'alerte. Les catégories `secret` et `payment_card` restent figées à RESTRICTED.
- **Écartées** : un moteur de règles entièrement paramétrable (OPA/Rego, règles JSON).
- **Conséquences** : un administrateur ne peut pas faire sortir un secret par une mauvaise configuration. Toute modification est journalisée avec l'ancienne et la nouvelle valeur.

## D11. Fail closed à chaque étape
- **Contexte** : un détecteur peut planter (regex invalide saisie par un admin, bug).
- **Décision** : détecteur en erreur → détection fictive au niveau maximal que ce détecteur peut attribuer. Erreur de classification globale → RESTRICTED (blocage). Regex de lexique invalide → au moins CONFIDENTIAL.
- **Conséquences** : une panne produit un excès de prudence (blocage, routage privé), jamais une fuite. Les erreurs sont visibles dans les logs.

## D12. Classification : maximum de quatre sources, niveau de conversation monotone
- **Contexte** : un message anodin peut suivre un message confidentiel ; tout l'historique est envoyé au modèle.
- **Décision** : niveau = max(message, contexte complet, niveau déclaré, niveau déjà atteint par la conversation). `conversations.max_classification` ne redescend jamais. Un message bloqué n'est pas stocké, donc il ne fait pas partie du contexte et ne relève pas le niveau de la conversation.
- **Conséquences** : une conversation devenue CONFIDENTIAL reste sur les modèles privés. L'utilisateur peut ouvrir une nouvelle conversation pour revenir aux modèles externes.

## D13. Quota : estimation pessimiste avant appel, coût réel après
- **Contexte** : le modèle n'est pas encore connu au moment du contrôle (la classification vient après, conformément au pipeline).
- **Décision** : estimation = tokens du contexte + 800 tokens de sortie, au prix du modèle le plus cher autorisé pour le rôle. Refus si consommation + estimation dépasse 100 % (utilisateur ou département). Après l'appel, la consommation réelle (somme de `llm_requests`) déclenche les alertes 70/90/100 %, une seule fois par seuil et par mois (table `quota_alerts`).
- **Écartées** : réservation de budget transactionnelle.
- **Conséquences** : on peut refuser une requête un peu avant 100 %. Deux requêtes simultanées peuvent passer ensemble le contrôle (dépassement borné à une requête). En production : réservation puis ajustement, ou verrou par utilisateur.

## D14. Traitement des requêtes refusées
- **Contexte** : une requête bloquée contient par définition une donnée qu'on ne veut stocker nulle part.
- **Décision** : BLOCK → réponse 200 avec `status=BLOCKED` et le panneau de routage (types détectés, jamais les valeurs). Rien n'est écrit en dehors des métadonnées (`llm_requests`, `audit_events`), aucune conversation n'est créée. Un modèle manuel non éligible → `status=REFUSED` avec le motif et la possibilité de basculer vers un modèle privé (jamais d'envoi forcé).
- **Conséquences** : l'interface affiche une explication claire. Un test vérifie l'absence du contenu dans toutes les tables, les logs capturés et la réponse.

## D15. Fallback limité à l'ensemble éligible, invariant revérifié avant chaque appel
- **Contexte** : le fallback ne doit jamais franchir une frontière de confidentialité.
- **Décision** : la liste de candidats est calculée une seule fois à partir des modèles éligibles. Avant chaque appel, `is_model_allowed_for_level` est revérifié (défense en profondeur : une violation lève une exception plutôt que d'envoyer). Si tous les candidats échouent : 503 et événement `NO_MODEL_AVAILABLE`.
- **Conséquences** : une panne d'Ollama sur une requête CONFIDENTIAL donne une erreur 503, pas un envoi vers GPT. C'est voulu.

## D16. Limitation de débit en mémoire
- **Décision** : fenêtre glissante d'une minute par IP (login) et par utilisateur (chat), dans le processus.
- **Conséquences** : simple et testable, mais non partagée entre plusieurs instances. En production : Redis ou reverse proxy (NGINX, API Gateway).

## D17. Playground : transparence du routage, message bloqué masqué à l'écran
- **Contexte** : l'utilisateur doit comprendre pourquoi sa requête a été routée ou bloquée, sans que l'interface réaffiche une donnée sensible.
- **Décision** : sous chaque réponse, un panneau de routage montre la classification, les quatre sources, les types détectés, la décision, le modèle, la latence, les tokens (marqués « estimé » si besoin), le coût (ou « coût non disponible ») et un badge « simulé ». Si la requête est bloquée, le message saisi est remplacé à l'écran par « contenu masqué ». En cas de refus d'un modèle manuel, un bouton propose explicitement la bascule vers un modèle privé.
- **Conséquences** : une démonstration lisible pour un DSI. Le panneau est reconstruit à partir des métadonnées stockées avec le message (`messages.routing`), jamais à partir du contenu.

## D18. Gardes de rôle côté frontend = confort uniquement
- **Décision** : `RoleGuard` et la navigation filtrée évitent d'afficher des pages inutiles, et les appels API d'une page protégée ne partent que si le rôle est autorisé. La sécurité reste dans les dépendances FastAPI (403 testés sur toutes les routes d'administration).

## D19. Déploiement gratuit : un seul conteneur (API + interface statique)
- **Contexte** : les offres gratuites (Render) donnent un service à 512 Mo qui s'endort après 15 minutes. Deux services signifieraient deux réveils à froid et une URL d'API à connaître dès le build du frontend.
- **Décision** : `Dockerfile` racine en deux étapes. Next.js est exporté en site statique (`NEXT_OUTPUT=export`), et FastAPI le sert avec `StaticFiles`, monté après les routes `/api`. `docker compose` garde l'architecture à deux services pour le développement.
- **Écartées** : deux services Render ; un proxy Node au démarrage.
- **Conséquences** : même origine, donc toujours aucun CORS et un cookie httpOnly simple. Environ 230 Mo de mémoire mesurés avec LiteLLM chargé. Les pages étant toutes des composants client, l'export statique ne perd aucune fonctionnalité.

## D20. Disponibilité ≠ éligibilité
- **Contexte** : en mode réel, certains modèles n'ont pas de clé (ou Ollama est absent).
- **Décision** : la politique calcule les modèles **éligibles** (sécurité). La fabrique de fournisseurs indique s'ils sont **disponibles** (configuration). Un modèle éligible mais non configuré est ignoré sans appel ni événement d'erreur. Si aucun modèle n'est disponible, l'utilisateur reçoit une erreur 503 `NO_CONFIGURED_PROVIDER` qui explique le niveau concerné. Hors démo, aucun mock n'est jamais utilisé.
- **Conséquences** : une instance avec la seule clé Gemini répond aux requêtes PUBLIC et refuse proprement les autres, sans jamais affaiblir la politique pour « trouver » un modèle.

## D21. Démarrage en mode réel
- **Décision** : avec `DEMO_MODE=false`, une base vide reçoit uniquement la configuration (départements, catalogue, politique, lexique) et un administrateur défini par `ADMIN_EMAIL` / `ADMIN_PASSWORD` (12 caractères minimum, sinon refus de démarrer). Si la base vient de la démo, les comptes `@aihub-demo.local` sont désactivés et l'administrateur est créé s'il manque.
- **Conséquences** : impossible de déployer en production avec les mots de passe publics de la démo.

## D22. Mise à jour des dépendances après audit
- **Contexte** : `pip-audit` et `npm audit` (novembre 2026) signalaient des vulnérabilités dans les versions épinglées initialement, et LiteLLM 1.67.4 ne s'importait plus du tout (module `enterprise` manquant). Les tests ne le voyaient pas, parce qu'ils remplacent le fournisseur.
- **Décision** : passage à LiteLLM 1.106.6, FastAPI 0.162 (Starlette corrigé), Next.js 15.5.28 et PostCSS 8.5.32 (override npm). Ajout d'un test d'intégration qui exécute un vrai appel LiteLLM vers un faux serveur local (formats OpenAI et Ollama).
- **Conséquences** : la découverte des routes dans le test des rôles passe désormais par le schéma OpenAPI (FastAPI stocke les routeurs inclus autrement). Il reste un risque connu sur `filelock` (contrainte de LiteLLM), documenté dans SECURITY.md.

## D23. Gemini (offre gratuite) plafonné à PUBLIC
- **Décision** : ajout de Gemini 2.5 Flash au catalogue (prix 0, source « offre gratuite »). Son niveau maximal est PUBLIC, car les données de l'offre gratuite peuvent être réutilisées par Google.
- **Conséquences** : un mode réel est possible sans dépense, et l'exemple illustre la logique de la plateforme : le niveau maximal d'un modèle découle de son contrat, pas de sa qualité.

## D24. Changement de nom : AI Hub Gouvernance
- **Décision** : la plateforme s'appelle « AI HUB GOUVERNANCE » (interface, API, documentation). Les comptes de démo passent à `@aihub-demo.local`. Le format fictif de dossier interne devient `DOS-AAAA-NNNNN`.
- **Données existantes** : la migration Alembic `0002` renomme les comptes et le terme du lexique dans les bases déjà déployées, sans réinitialisation. Le journal d'audit n'est pas modifié : il est en ajout seul, et l'historique garde son état d'origine (la chaîne de hash reste valide).
- **Non renommés** (invisibles pour l'utilisateur) : le nom du service Render `rdt-ai-hub` (le changer créerait un nouveau service et une nouvelle URL), les identifiants de la base PostgreSQL locale de `docker compose`, le nom du dossier.
