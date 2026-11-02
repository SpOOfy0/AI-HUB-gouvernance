// Libellés et résumé lisible des événements du journal (métadonnées uniquement).

export const EVENT_LABELS: Record<string, string> = {
  LOGIN_SUCCESS: "Connexion",
  LOGOUT: "Déconnexion",
  LOGIN_FAILED: "Échec de connexion",
  RATE_LIMITED: "Limite de débit",
  AI_REQUEST: "Requête IA",
  REQUEST_BLOCKED: "Requête bloquée",
  MANUAL_MODEL_REFUSED: "Modèle manuel refusé",
  NO_MODEL_AVAILABLE: "Aucun modèle disponible",
  PROVIDER_ERROR: "Erreur fournisseur",
  QUOTA_THRESHOLD: "Seuil de quota",
  QUOTA_EXCEEDED: "Quota dépassé",
  CONFIG_CHANGED: "Changement de configuration",
  AUDIT_VERIFIED: "Vérification d'intégrité",
  CONVERSATION_DELETED: "Conversation supprimée",
};

type Details = Record<string, unknown>;

export function summarize(eventType: string, d: Details): string {
  const detections = Array.isArray(d.detections) ? (d.detections as { type: string; count: number }[]).map((x) => x.type).join(", ") : "";
  switch (eventType) {
    case "REQUEST_BLOCKED":
      return `${d.classification} · détections : ${detections}`;
    case "AI_REQUEST":
      return `${d.classification} → ${d.model}${d.fallback_used ? " (fallback)" : ""}${d.cost_eur ? ` · ${d.cost_eur} €` : ""}`;
    case "MANUAL_MODEL_REFUSED":
      return `${d.requested_model} · ${d.reason}`;
    case "QUOTA_THRESHOLD":
      return `${d.scope === "user" ? "Utilisateur" : "Département"} : seuil ${d.threshold} % (${d.pct} %)`;
    case "QUOTA_EXCEEDED":
      return `Quota ${d.scope === "user" ? "utilisateur" : "département"} atteint`;
    case "PROVIDER_ERROR":
      return `${d.model} : ${d.error}`;
    case "LOGIN_FAILED":
      return `domaine ${d.email_domain} · IP ${d.ip}`;
    case "RATE_LIMITED":
      return `route ${d.route}${d.ip ? ` · IP ${d.ip}` : ""}`;
    case "CONFIG_CHANGED":
      return `${d.target}${d.action ? ` · ${d.action}` : ""}`;
    case "AUDIT_VERIFIED":
      return d.valid ? `chaîne valide (${d.checked} événements)` : `altération détectée à l'événement #${d.first_invalid_id}`;
    case "NO_MODEL_AVAILABLE":
      return `${d.classification ?? ""} · ${d.cause ?? "tous les fournisseurs en échec"}`;
    default:
      return Object.entries(d)
        .slice(0, 3)
        .map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`)
        .join(" · ");
  }
}
