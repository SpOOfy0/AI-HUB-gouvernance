# Notes d'entretien

Questions probables d'un DSI ou d'un ingénieur Data & IA, avec une réponse courte et honnête.

## Phase 1 : socle

**Pourquoi FastAPI et pas Django ?**
FastAPI donne la validation Pydantic, la documentation Swagger automatique et un système de dépendances qui rend le contrôle des rôles explicite sur chaque route. L'admin Django ne servait pas ici : les écrans sont spécifiques. Limite : moins de « batteries incluses » (admin, migrations intégrées), d'où Alembic.

**Comment est gérée la session ? Pourquoi pas un JWT dans le localStorage ?**
Le JWT est dans un cookie httpOnly, donc illisible par le JavaScript en cas de XSS, avec Secure et SameSite=Lax. Le frontend et l'API sont sur la même origine grâce au rewrite Next.js : pas de CORS. Le rôle est relu en base à chaque requête. Limite : pas de révocation individuelle avant expiration (8 h).

**Si je modifie le frontend pour afficher le menu Admin à un simple utilisateur ?**
Il verra les pages, mais toutes les routes d'administration renverront 403 : la vérification est faite côté backend par `require_roles`, route par route. Un test vérifie le 403 sur toutes les routes admin.

**Comment brancheriez-vous Entra ID ?**
Via l'interface `AuthProvider` : flux OIDC authorization code + PKCE, validation du `id_token` (JWKS, issuer, audience), mapping des groupes AD vers nos rôles, puis émission de notre propre cookie de session. Rien ne change dans les routes métier. C'est documenté, pas implémenté.

**Les données de démo sont-elles réalistes ?**
Elles sont fictives et générées avec une graine fixe : ~3 000 requêtes sur 30 jours, jours ouvrés plus chargés, routage cohérent avec la politique (le seed réutilise les fonctions du routeur). Les prix sont fictifs et marqués comme tels. Les volumes et les coûts ne valent pas une étude de marché.

## Phase 2 : cœur de la passerelle

**Pourquoi des expressions régulières plutôt que Presidio ou un LLM classifieur ?**
Les regex sont déterministes, rapides, explicables et testables, et les contrôles algorithmiques (Luhn, clé IBAN, clé NIR) réduisent les faux positifs. Leurs limites sont réelles et testées : reformulation, encodage base64, clients absents du lexique. En production, j'ajouterais Microsoft Presidio (NER multilingue) et éventuellement un classifieur LLM exécuté uniquement sur le modèle local, jamais chez un fournisseur externe.

**Comment êtes-vous sûr qu'une requête CONFIDENTIAL ne part jamais chez OpenAI ?**
Trois niveaux de défense : (1) `eligible_models` ne garde que les modèles PRIVATE ; (2) le fallback ne parcourt que cette liste ; (3) juste avant chaque appel, l'invariant est revérifié et une exception est levée en cas de violation. Les tests utilisent un faux fournisseur qui enregistre chaque appel avec l'hébergement du modèle : on vérifie qu'aucun appel EXTERNAL n'a eu lieu, y compris en mode manuel et quand tous les modèles privés tombent en panne.

**Que se passe-t-il si la DLP rate un secret ?**
Le secret part vers un modèle autorisé pour le niveau détecté. Pour une requête classée PUBLIC, cela peut être DeepSeek. C'est la limite principale : la DLP réduit le risque, elle ne l'élimine pas. Les mesures complémentaires sont la formation, les contrats fournisseurs (pas d'entraînement, rétention courte), un modèle local par défaut pour les services sensibles, et la détection de secrets dans le code (gitleaks) en amont.

**Pourquoi le contrôle de quota est-il fait avant la classification, avec une estimation ?**
C'est l'ordre demandé : on refuse au plus tôt, sans même analyser le contenu. L'estimation est pessimiste (modèle le plus cher autorisé pour le rôle, 800 tokens de sortie). Limite : deux requêtes simultanées peuvent passer ensemble. En production, on réserverait le budget avant l'appel puis on ajusterait.

**Le journal d'audit est-il vraiment infalsifiable ?**
Pas absolument. Le trigger empêche UPDATE, DELETE et TRUNCATE pour l'application. Un superutilisateur PostgreSQL peut le désactiver, mais le chaînage par hash rend toute modification ou suppression détectable (testé). Pour aller plus loin : rôle applicatif sans droits DDL, export régulier du dernier hash vers un stockage WORM ou un SIEM, pour qu'une réécriture complète de la chaîne soit elle aussi détectable.

## Phase 3 : interfaces du cœur

**Que voit l'utilisateur quand sa requête est bloquée ?**
Une carte rouge qui donne le type de donnée détectée (« clé API »), précise que rien n'a été transmis ni conservé et qu'un événement de sécurité a été créé. Son message est masqué à l'écran. Il ne voit jamais la valeur détectée : l'API ne la renvoie pas, puisque la DLP ne la stocke pas.

**Comment un administrateur ajuste-t-il la politique sans développeur ?**
Dans Sécurité → Politique (mapping, seuils, rétention, alertes) et Lexique métier (termes ou regex). Le bac à sable « Tester la classification » montre la décision et les modèles éligibles sans appeler de modèle. Chaque modification crée un événement `CONFIG_CHANGED` avec l'ancienne et la nouvelle valeur. Les secrets et cartes bancaires restent figés à RESTRICTED.

**Comment prouvez-vous en démo que le journal n'a pas été altéré ?**
Le bouton « Vérifier l'intégrité du journal » recalcule toute la chaîne SHA-256 (environ 4 000 événements en moins d'une seconde) et indique le premier événement incohérent s'il y en a un. La vérification est elle-même journalisée. Une altération directe en base est démontrée par un test automatisé, qui désactive le trigger en superutilisateur.

**Pourquoi le niveau d'une conversation ne redescend-il jamais ?**
Tout l'historique est envoyé au modèle à chaque tour. Si un message confidentiel est dans l'historique, un message anodin qui suit transporterait quand même ce contexte vers un modèle externe. La solution pour l'utilisateur est d'ouvrir une nouvelle conversation, et le bandeau le lui indique.

**Qu'est-ce qui est simulé dans ce que je vois ?**
Uniquement le texte des réponses (badge « simulé », préfixe « [Réponse simulée] ») et les tokens associés (marqués « estimé »). Les prix sont fictifs (« prix fictif »). La classification, le routage, le fallback, les quotas, les coûts calculés et l'audit sont réellement exécutés.
