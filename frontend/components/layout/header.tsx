"use client";

import { useEffect, useRef, useState } from "react";
import { Bell, LogOut } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";

interface UsageInfo {
  user: { pct: number; cost_eur: string; budget_eur: string };
  department: { pct: number };
  alerts: { scope: string; threshold: number; created_at: string }[];
}

const ROLE_LABEL = { ADMIN: "Administrateur", MANAGER: "Manager", DEVELOPER: "Développeur", USER: "Utilisateur" };

// Petit hook : ferme un menu déroulant au clic extérieur.
function useClickOutside<T extends HTMLElement>(onOutside: () => void) {
  const ref = useRef<T>(null);
  useEffect(() => {
    const handler = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && onOutside();
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [onOutside]);
  return ref;
}

export function Header() {
  const { user, logout } = useAuth();
  const [usage, setUsage] = useState<UsageInfo | null>(null);
  const [openBell, setOpenBell] = useState(false);
  const [openProfile, setOpenProfile] = useState(false);
  const bellRef = useClickOutside<HTMLDivElement>(() => setOpenBell(false));
  const profileRef = useClickOutside<HTMLDivElement>(() => setOpenProfile(false));

  useEffect(() => {
    const load = () => api<UsageInfo>("/me/usage").then(setUsage).catch(() => undefined);
    load();
    // Rafraîchi quand le playground signale une nouvelle requête (consommation modifiée).
    window.addEventListener("aihub:usage-changed", load);
    return () => window.removeEventListener("aihub:usage-changed", load);
  }, []);

  if (!user) return null;
  const alerts = usage?.alerts ?? [];
  const initials = user.full_name.split(" ").map((p) => p[0]).join("").slice(0, 2);

  return (
    <header className="sticky top-0 z-10 flex h-14 items-center justify-end gap-2 border-b bg-card/90 px-6 backdrop-blur">
      {usage && (
        <div className="mr-2 hidden items-center gap-2 text-xs text-muted-foreground md:flex">
          <span>Mon quota du mois</span>
          <div className="h-1.5 w-24 overflow-hidden rounded-full bg-muted">
            <div
              className={cn("h-full rounded-full", usage.user.pct >= 90 ? "bg-danger" : usage.user.pct >= 70 ? "bg-warning" : "bg-primary")}
              style={{ width: `${Math.min(100, usage.user.pct)}%` }}
            />
          </div>
          <span className="tabular-nums">{usage.user.pct.toFixed(0)} %</span>
        </div>
      )}

      <div className="relative" ref={bellRef}>
        <button
          aria-label="Notifications"
          onClick={() => setOpenBell((v) => !v)}
          className="relative flex size-8 items-center justify-center rounded-md hover:bg-muted"
        >
          <Bell className="size-4" />
          {alerts.length > 0 && (
            <span className="absolute right-1 top-1 flex size-4 items-center justify-center rounded-full bg-danger text-[9px] font-semibold text-white">
              {alerts.length}
            </span>
          )}
        </button>
        {openBell && (
          <div className="absolute right-0 mt-2 w-80 rounded-lg border bg-card p-2 shadow-lg">
            <div className="px-2 py-1 text-xs font-semibold">Alertes de quota (mois en cours)</div>
            {alerts.length === 0 && <div className="px-2 py-3 text-xs text-muted-foreground">Aucune alerte.</div>}
            {alerts.map((a, i) => (
              <div key={i} className="rounded-md px-2 py-1.5 text-xs hover:bg-muted">
                <span className={cn("font-medium", a.threshold >= 100 ? "text-danger" : "text-[oklch(0.5_0.12_70)]")}>
                  {a.threshold >= 100 ? "Quota atteint" : `Seuil de ${a.threshold} % franchi`}
                </span>{" "}
                · {a.scope === "user" ? "votre budget" : "budget du département"}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="relative" ref={profileRef}>
        <button onClick={() => setOpenProfile((v) => !v)} className="flex items-center gap-2 rounded-md px-1.5 py-1 hover:bg-muted">
          <span className="flex size-7 items-center justify-center rounded-full bg-primary/10 text-[11px] font-semibold text-primary">
            {initials}
          </span>
          <span className="hidden text-left leading-tight sm:block">
            <span className="block text-xs font-medium">{user.full_name}</span>
            <span className="block text-[10px] text-muted-foreground">
              {ROLE_LABEL[user.role]} · {user.department_name}
            </span>
          </span>
        </button>
        {openProfile && (
          <div className="absolute right-0 mt-2 w-56 rounded-lg border bg-card p-1 shadow-lg">
            <div className="px-2 py-1.5 text-xs text-muted-foreground">{user.email}</div>
            <button onClick={logout} className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-xs hover:bg-muted">
              <LogOut className="size-3.5" /> Se déconnecter
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
