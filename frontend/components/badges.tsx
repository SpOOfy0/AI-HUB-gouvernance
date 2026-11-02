import { Badge } from "@/components/ui/badge";
import type { Level } from "@/lib/types";

const LEVEL_VARIANT = { PUBLIC: "default", INTERNAL: "primary", CONFIDENTIAL: "warning", RESTRICTED: "danger" } as const;

export function LevelBadge({ level }: { level: Level }) {
  return <Badge variant={LEVEL_VARIANT[level] ?? "default"}>{level}</Badge>;
}

const DECISION = {
  ALLOW: { label: "ALLOW", variant: "success" },
  PRIVATE_ONLY: { label: "PRIVATE ONLY", variant: "warning" },
  BLOCK: { label: "BLOCK", variant: "danger" },
} as const;

export function DecisionBadge({ decision }: { decision: keyof typeof DECISION }) {
  const d = DECISION[decision];
  return <Badge variant={d.variant}>{d.label}</Badge>;
}

export function SeverityBadge({ severity }: { severity: string }) {
  const variant = severity === "CRITICAL" ? "danger" : severity === "WARNING" ? "warning" : "outline";
  return <Badge variant={variant}>{severity}</Badge>;
}

export function HostingBadge({ hosting }: { hosting?: string }) {
  if (!hosting) return null;
  return <Badge variant={hosting === "PRIVATE" ? "primary" : "outline"}>{hosting === "PRIVATE" ? "Privé (SI)" : "Externe"}</Badge>;
}
