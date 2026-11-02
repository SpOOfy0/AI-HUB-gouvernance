from app.routers import audit, auth, chat, me, meta, security

ROUTERS = [meta.router, auth.router, me.router, chat.router, security.router, audit.router]
