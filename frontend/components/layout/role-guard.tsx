"use client";

import { ShieldOff } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import type { Role } from "@/lib/api";

// Confort d'affichage uniquement : le backend renvoie de toute façon 403 aux autres rôles.
export function RoleGuard({ roles, children }: { roles: Role[]; children: React.ReactNode }) {
  const { user } = useAuth();
  if (!user || !roles.includes(user.role)) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center text-sm text-muted-foreground">
        <ShieldOff className="mb-2 size-6" />
        Cette page est réservée aux rôles : {roles.join(", ")}.
      </div>
    );
  }
  return <>{children}</>;
}
