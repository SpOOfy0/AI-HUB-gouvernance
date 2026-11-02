export type Level = "PUBLIC" | "INTERNAL" | "CONFIDENTIAL" | "RESTRICTED";

export interface Detection {
  type: string;
  label: string;
  level: Level;
  count: number;
  category: string;
}

export interface Routing {
  classification: Level;
  sources?: Record<string, Level>;
  detections: Detection[];
  decision: "ALLOW" | "PRIVATE_ONLY" | "BLOCK";
  mode?: "auto" | "manual";
  complexity?: "SIMPLE" | "COMPLEX";
  reason: string;
  provider?: string;
  model?: string;
  model_display?: string;
  hosting?: "EXTERNAL" | "PRIVATE";
  fallback_used?: boolean;
  attempts?: { model: string; error: string }[];
  latency_ms?: number;
  input_tokens?: number;
  output_tokens?: number;
  tokens_estimated?: boolean;
  cost_eur?: string | null;
  cost_available?: boolean;
  price_is_demo?: boolean;
  simulated?: boolean;
  backend?: string;
}

export interface ChatResponse {
  status: "SUCCESS" | "BLOCKED" | "REFUSED";
  request_id: string;
  conversation_id: number | null;
  message: { id: number; role: "assistant"; content: string } | null;
  routing: Routing;
  alerts: { scope: string; threshold: number; pct: number }[];
  can_fallback_private: boolean;
}

export interface AvailableModel {
  id: number;
  display_name: string;
  provider: string;
  hosting: "EXTERNAL" | "PRIVATE";
  max_classification: Level;
  tier: string;
  simulated: boolean;
  price: { input_per_mtok: string; output_per_mtok: string; is_demo: boolean } | null;
}

export interface ConversationSummary {
  id: number;
  title: string;
  max_classification: Level;
  updated_at: string;
}

export interface AuditItem {
  id: number;
  ts: string;
  user_email: string | null;
  event_type: string;
  category: string;
  severity: "INFO" | "WARNING" | "CRITICAL";
  status: string;
  request_id: string | null;
  details: Record<string, unknown>;
  hash?: string;
  prev_hash?: string;
}
