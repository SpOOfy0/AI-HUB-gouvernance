import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(iso: string) {
  return new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });
}

export function formatEur(value: string | number | null | undefined, digits = 4) {
  if (value === null || value === undefined) return "coût non disponible";
  return `${Number(value).toLocaleString("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: digits })} €`;
}
