import { MessagesSquare, ShieldCheck, ScrollText, type LucideIcon } from "lucide-react";
import type { Role } from "./api";

// Navigation filtrée selon le rôle. C'est du confort d'affichage :
// chaque route backend vérifie elle-même le rôle (la sécurité est côté serveur).
// Seules les pages réellement implémentées figurent ici.
export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  roles: Role[];
}

export const NAV: NavItem[] = [
  { href: "/playground", label: "Playground", icon: MessagesSquare, roles: ["ADMIN", "MANAGER", "DEVELOPER", "USER"] },
  { href: "/security", label: "Sécurité", icon: ShieldCheck, roles: ["ADMIN"] },
  { href: "/audit", label: "Journal d'audit", icon: ScrollText, roles: ["ADMIN"] },
];
