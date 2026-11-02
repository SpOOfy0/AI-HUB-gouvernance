"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type CurrentUser, type PublicConfig } from "./api";

interface AuthState {
  user: CurrentUser | null;
  config: PublicConfig | null;
  loading: boolean;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api<CurrentUser>("/auth/me"), api<PublicConfig>("/config/public")])
      .then(([u, c]) => {
        setUser(u);
        setConfig(c);
      })
      .catch(() => router.replace("/login"))
      .finally(() => setLoading(false));
  }, [router]);

  const logout = useCallback(async () => {
    await api("/auth/logout", { method: "POST" }).catch(() => undefined);
    router.replace("/login");
  }, [router]);

  return <AuthContext.Provider value={{ user, config, loading, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth doit être utilisé dans AuthProvider");
  return ctx;
}
