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
