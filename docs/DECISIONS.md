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
