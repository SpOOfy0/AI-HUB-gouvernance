"use client";

import { FlaskConical } from "lucide-react";
import { useAuth } from "@/lib/auth-context";

export function DemoBanner() {
  const { config } = useAuth();
  if (!config?.demo_mode) return null;
  return (
    <div className="flex items-center justify-center gap-2 border-b border-warning/30 bg-warning/10 px-4 py-1 text-[11px] font-medium text-[oklch(0.45_0.1_70)]">
      <FlaskConical className="size-3.5" />
      MODE DÉMO : réponses simulées, données fictives. La classification, le routage, les quotas et l&apos;audit sont réels.
    </div>
  );
}
