import type { NextConfig } from "next";

// Le navigateur appelle /api/* sur la même origine que le frontend ; Next relaie vers FastAPI.
// Avantage : le cookie de session httpOnly reste "same-origin", pas de CORS à ouvrir.
const backend = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
