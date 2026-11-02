from app.routers import auth, me, meta

ROUTERS = [meta.router, auth.router, me.router]
