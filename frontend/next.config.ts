import type { NextConfig } from "next";

// Deux modes de build :
// - par défaut (docker compose) : serveur Next "standalone" qui relaie /api/* vers FastAPI ;
// - NEXT_OUTPUT=export (déploiement en un seul conteneur) : site statique servi par FastAPI,
//   donc /api/* est déjà sur la même origine et aucun relais n'est nécessaire.
// Dans les deux cas, le cookie de session httpOnly reste "same-origin" : pas de CORS à ouvrir.
const backend = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";
const staticExport = process.env.NEXT_OUTPUT === "export";

const nextConfig: NextConfig = staticExport
  ? { output: "export", trailingSlash: true, poweredByHeader: false }
  : {
      output: "standalone",
      poweredByHeader: false,
      async rewrites() {
        return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
      },
    };

export default nextConfig;
