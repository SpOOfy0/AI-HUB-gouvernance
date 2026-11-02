"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, FlaskConical, Route } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { DecisionBadge, HostingBadge, LevelBadge } from "@/components/badges";
import type { Routing } from "@/lib/types";
import { formatEur } from "@/lib/utils";

const SOURCE_LABEL: Record<string, string> = {
  message: "Message",
  context: "Contexte complet",
  declared: "Niveau déclaré",
  conversation: "Conversation",
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="mt-0.5 truncate text-xs">{children}</div>
    </div>
  );
}

/** Transparence du routage : ce que la passerelle a décidé, et pourquoi. Jamais le contenu détecté. */
export function RoutingPanel({ routing, requestId }: { routing: Routing; requestId?: string }) {
  const [open, setOpen] = useState(false);
  const blocked = routing.decision === "BLOCK";

  return (
    <div className="mt-2 rounded-md border bg-muted/40 text-xs">
      <button onClick={() => setOpen((v) => !v)} className="flex w-full flex-wrap items-center gap-1.5 px-3 py-2 text-left">
        {open ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
        <Route className="size-3.5 text-muted-foreground" />
        <span className="font-medium">Routage</span>
        <LevelBadge level={routing.classification} />
        <DecisionBadge decision={routing.decision} />
        {routing.model_display && <Badge variant="outline">{routing.model_display}</Badge>}
        <HostingBadge hosting={routing.hosting} />
        {routing.fallback_used && <Badge variant="warning">fallback</Badge>}
        {routing.simulated && (
          <Badge variant="warning">
            <FlaskConical className="size-3" /> simulé
          </Badge>
        )}
        {!blocked && routing.latency_ms !== undefined && (
          <span className="ml-auto tabular-nums text-muted-foreground">
            {routing.latency_ms} ms · {routing.cost_available ? formatEur(routing.cost_eur, 6) : "coût non disponible"}
          </span>
        )}
      </button>

      <div className="border-t px-3 py-2 text-[12px] leading-relaxed text-foreground/90">{routing.reason}</div>

      {open && (
        <div className="space-y-3 border-t px-3 py-3">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Field label="Classification">
              <LevelBadge level={routing.classification} />
            </Field>
            <Field label="Décision">
              <DecisionBadge decision={routing.decision} />
            </Field>
            <Field label="Mode">{routing.mode === "manual" ? "Manuel" : "Automatique"}</Field>
            <Field label="Complexité">{routing.complexity ?? "—"}</Field>
            <Field label="Fournisseur">{routing.provider ?? "aucun (non appelé)"}</Field>
            <Field label="Modèle">{routing.model ?? "—"}</Field>
            <Field label="Latence">{routing.latency_ms !== undefined ? `${routing.latency_ms} ms` : "—"}</Field>
            <Field label="Tokens entrée / sortie">
              {routing.input_tokens !== undefined ? `${routing.input_tokens} / ${routing.output_tokens}` : "—"}
              {routing.tokens_estimated && <span className="ml-1 text-muted-foreground">(estimé)</span>}
            </Field>
            <Field label="Coût">
              {routing.cost_available === undefined ? "—" : routing.cost_available ? formatEur(routing.cost_eur, 6) : "coût non disponible"}
              {routing.price_is_demo && <span className="ml-1 text-muted-foreground">(prix fictif)</span>}
            </Field>
            <Field label="Exécution">
              {routing.backend === "mock-private"
                ? "Mock privé (Ollama non joignable)"
                : routing.backend === "mock"
                  ? "Fournisseur simulé (démo)"
                  : routing.backend === "ollama"
                    ? "Ollama (réel, local)"
                    : routing.backend ?? "—"}
            </Field>
            {requestId && (
              <Field label="request_id">
                <span className="font-mono text-[11px]">{requestId}</span>
              </Field>
            )}
          </div>

          {routing.sources && (
            <div>
              <div className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">
                Sources de classification (niveau final = maximum)
              </div>
              <div className="flex flex-wrap gap-2">
                {Object.entries(routing.sources).map(([k, v]) => (
                  <span key={k} className="flex items-center gap-1">
                    <span className="text-muted-foreground">{SOURCE_LABEL[k] ?? k} :</span> <LevelBadge level={v} />
                  </span>
                ))}
              </div>
            </div>
          )}

          <div>
            <div className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">Détections (types uniquement, jamais les valeurs)</div>
            {routing.detections.length === 0 ? (
              <span className="text-muted-foreground">Aucune</span>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {routing.detections.map((d) => (
                  <Badge key={d.type} variant="outline">
                    {d.label} × {d.count} · {d.level}
                  </Badge>
                ))}
              </div>
            )}
          </div>

          {routing.attempts && routing.attempts.length > 0 && (
            <div>
              <div className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">Tentatives échouées (même ensemble éligible)</div>
              {routing.attempts.map((a, i) => (
                <div key={i} className="font-mono text-[11px]">
                  {a.model} : {a.error}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
