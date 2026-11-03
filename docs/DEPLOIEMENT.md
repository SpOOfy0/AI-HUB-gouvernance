# Déployer RDT AI Hub gratuitement (Render + Neon)

Ce guide met l'application en ligne sur une adresse publique en HTTPS, **sans carte bancaire**.

| Brique | Service | Offre gratuite (vérifiée en novembre 2026, peut évoluer) |
|---|---|---|
| Application (API + interface) | [Render](https://render.com) | 1 service web Docker, 512 Mo de RAM, mise en veille après 15 min d'inactivité |
| Base PostgreSQL | [Neon](https://neon.com) | 1 Go par projet, sans limite de durée, sans carte bancaire |
| Modèle d'IA (mode réel) | [Google AI Studio](https://aistudio.google.com) | Clé Gemini gratuite, quotas de débit limités |

Pourquoi Neon plutôt que la base gratuite de Render : celle de Render expire 30 jours après sa création.

Ce qu'il faut savoir avant de commencer :
- **Mise en veille** : après 15 minutes sans visite, le service s'endort. La visite suivante prend 30 à 60 secondes. Avant un entretien, ouvre l'adresse une minute avant pour réveiller le service.
- **Un seul conteneur** : en ligne, FastAPI sert l'API et l'interface (export statique Next.js) depuis la même image (`Dockerfile` à la racine). En local, `docker compose` garde les deux services séparés.

---

## Étape 1 : mettre le code sur GitHub

1. Crée un dépôt **vide** sur https://github.com/new (privé ou public), par exemple `rdt-ai-hub`, sans README.
2. Dans le dossier du projet :
   ```bash
   git remote add origin https://github.com/<ton-compte>/rdt-ai-hub.git
   ```
   ```bash
   git push -u origin main
   ```

## Étape 2 : créer la base PostgreSQL (Neon)

1. Crée un compte sur https://neon.com (connexion avec GitHub possible).
2. Crée un projet : nom `rdt-ai-hub`, version PostgreSQL 16 ou plus, région **AWS Europe (Frankfurt)**.
3. Dans **Connect**, copie la chaîne de connexion. Désactive l'option « Connection pooling » pour obtenir l'adresse directe (sans `-pooler` dans le nom d'hôte). **Clique sur « Show password » avant de copier** : sinon le mot de passe copié est masqué (`****`) et la connexion échoue. La chaîne ressemble à :
   ```
   postgresql://neondb_owner:xxxxx@ep-nom-123456.eu-central-1.aws.neon.tech/neondb?sslmode=require
   ```
   Le format `postgresql://` est converti automatiquement par l'application.

## Étape 3 : déployer sur Render

1. Crée un compte sur https://render.com (connexion avec GitHub).
2. **New → Blueprint**, puis choisis ton dépôt `rdt-ai-hub`. Render lit le fichier `render.yaml`.
3. Render demande la valeur de `DATABASE_URL` : colle la chaîne Neon de l'étape 2.
4. Clique sur **Apply**. Le premier build prend 5 à 10 minutes : installation des dépendances, build de l'interface, puis migrations et données de démo au démarrage.
5. Ouvre l'adresse affichée, par exemple `https://rdt-ai-hub.onrender.com`.

L'application tourne alors en **mode démo** : les comptes de démonstration sont affichés sur la page de connexion et les réponses des modèles sont simulées. C'est la bonne configuration pour une présentation : rien ne coûte, rien ne sort.

## Étape 4 (optionnelle) : passer en mode réel avec une clé gratuite

1. **Clé Gemini gratuite** : sur https://aistudio.google.com, choisis « Get API key » puis « Create API key ».
2. **Nouvelle base propre** : dans Neon, crée une seconde base (par exemple `rdt_prod`) et copie sa chaîne de connexion. Ce n'est pas obligatoire : si tu gardes la base de démo, les comptes de démo sont désactivés automatiquement, mais l'historique fictif reste visible.
3. Dans Render, ouvre le service, puis **Environment**, et modifie ou ajoute :

   | Variable | Valeur |
   |---|---|
   | `DEMO_MODE` | `false` |
   | `ADMIN_EMAIL` | ton adresse email |
   | `ADMIN_PASSWORD` | un mot de passe d'au moins 12 caractères |
   | `GEMINI_API_KEY` | la clé Google |
   | `DATABASE_URL` | la chaîne de la nouvelle base (si tu en as créé une) |

4. Enregistre : Render redéploie. Connecte-toi avec `ADMIN_EMAIL` / `ADMIN_PASSWORD`.

### Ce qui fonctionne selon les clés configurées

La politique de sécurité ne change jamais. Les clés déterminent seulement quels modèles peuvent répondre.

| Niveau de la requête | Modèles autorisés | Avec `GEMINI_API_KEY` seule | Pour obtenir une réponse |
|---|---|---|---|
| PUBLIC | Gemini, DeepSeek, GPT, Claude, modèles locaux | Réponse de Gemini | Rien de plus |
| INTERNAL | GPT, Claude, modèles locaux | Erreur claire « aucun modèle configuré » | `OPENAI_API_KEY` ou `ANTHROPIC_API_KEY` (payantes, quelques euros de crédit) |
| CONFIDENTIAL | Modèles locaux (Ollama) uniquement | Erreur claire | Un serveur Ollama dans le SI (impossible sur une offre gratuite) |
| RESTRICTED | Aucun | Bloqué | Toujours bloqué, c'est voulu |

Gemini gratuit est limité au niveau PUBLIC parce que les données envoyées sur l'offre gratuite peuvent être utilisées par Google pour améliorer ses produits. C'est exactement le type de décision que la plateforme sert à appliquer.

Pour ajouter une autre clé plus tard (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`), ajoute simplement la variable dans Render : le modèle correspondant devient disponible sans modification de code.

## Vérifications après déploiement

- `https://<ton-service>.onrender.com/api/health` renvoie `{"status":"ok"}`.
- Page Sécurité → « Tester la classification » avec une fausse clé `sk-test1234` : décision BLOCK.
- Journal d'audit → « Vérifier l'intégrité du journal » : chaîne intègre.

## Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| Le build échoue sur `npm ci` ou `pip install` | Problème réseau passager chez Render | Manual Deploy → Clear build cache & deploy |
| Le service ne démarre pas, log « Mode réel : définir ADMIN_EMAIL et ADMIN_PASSWORD » | Mode réel sans administrateur | Ajouter les deux variables (mot de passe ≥ 12 caractères) |
| `password authentication failed for user 'neondb_owner'` | Mot de passe masqué (`****`) copié depuis Neon | Neon → Connect → Show password, recopier ; ou Roles → Reset password. Puis Render → Environment → `DATABASE_URL` → Save, rebuild, and deploy |
| `Network is unreachable` sur des adresses IPv6 | Render n'utilise pas IPv6 | Sans importance : la connexion se fait ensuite en IPv4 |
| Autre erreur de connexion à la base | Mauvaise chaîne, ou adresse « pooler » | Recopier la chaîne Neon directe, avec `sslmode=require` |
| Première visite très lente | Réveil du service gratuit | Normal (30 à 60 s) |
| Requête PUBLIC en erreur 503 en mode réel | Clé Gemini absente, invalide ou quota dépassé | Vérifier la clé ; regarder les événements `PROVIDER_ERROR` dans le journal |

## Limites de cet hébergement gratuit

C'est un hébergement de **démonstration et de pilote**, pas une production d'entreprise. Pour un usage réel avec des données du groupe, il faudrait :
- un hébergement dans le SI ou un cloud sous contrat, avec sauvegardes et supervision ;
- un serveur GPU interne avec Ollama ou vLLM pour les données confidentielles ;
- le SSO Entra ID (interface prévue, voir `backend/app/core/auth_provider.py`) ;
- des contrats fournisseurs validés (non-entraînement, localisation des données, durée de rétention) ;
- l'écran de gestion des utilisateurs (phase 4) : en mode réel, seul l'administrateur existe pour l'instant.
