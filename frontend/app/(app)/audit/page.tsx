"use client";

import { Fragment, useEffect, useState } from "react";
import { ChevronDown, ChevronRight, Loader2, ShieldCheck, ShieldX } from "lucide-react";
import { api } from "@/lib/api";
import type { AuditItem } from "@/lib/types";
import { PageHeader } from "@/components/layout/page-header";
import { RoleGuard } from "@/components/layout/role-guard";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { Table, TD, TH, THead, TR } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { SeverityBadge } from "@/components/badges";
import { Pagination } from "@/components/pagination";
import { EVENT_LABELS, summarize } from "@/lib/events";
import { formatDate } from "@/lib/utils";

const LIMIT = 50;

interface VerifyResult {
  valid: boolean;
  checked: number;
  first_invalid_id: number | null;
  reason: string | null;
}

function AuditContent() {
  const [data, setData] = useState<{ total: number; items: AuditItem[] } | null>(null);
  const [filters, setFilters] = useState({ category: "", severity: "", event_type: "", user_email: "", request_id: "" });
  const [offset, setOffset] = useState(0);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [verify, setVerify] = useState<VerifyResult | null>(null);
  const [verifying, setVerifying] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams({ limit: String(LIMIT), offset: String(offset) });
    Object.entries(filters).forEach(([k, v]) => v && params.set(k, v.trim()));
    const t = setTimeout(() => api<typeof data>(`/audit?${params}`).then(setData), 250); // petit délai pour la saisie
    return () => clearTimeout(t);
  }, [filters, offset]);

  const setFilter = (k: keyof typeof filters, v: string) => {
    setFilters({ ...filters, [k]: v });
    setOffset(0);
  };

  async function runVerify() {
    setVerifying(true);
    try {
      setVerify(await api<VerifyResult>("/audit/verify", { method: "POST" }));
      setFilters({ ...filters }); // recharge : la vérification est elle-même journalisée
    } finally {
      setVerifying(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Journal d'audit"
        description="Ajout seul (trigger PostgreSQL) et chaîné par hash SHA-256. Métadonnées uniquement : aucun contenu de prompt ni de réponse."
        actions={
          <Button onClick={runVerify} disabled={verifying}>
            {verifying ? <Loader2 className="animate-spin" /> : <ShieldCheck />} Vérifier l&apos;intégrité du journal
          </Button>
        }
      />

      {verify && (
        <div
          className={`mb-4 flex items-center gap-2 rounded-lg border px-4 py-2.5 text-xs ${
            verify.valid ? "border-success/30 bg-success/8 text-success" : "border-danger/30 bg-danger/8 text-danger"
          }`}
        >
          {verify.valid ? <ShieldCheck className="size-4" /> : <ShieldX className="size-4" />}
          {verify.valid
            ? `Chaîne intègre : ${verify.checked.toLocaleString("fr-FR")} événements recalculés, aucun écart.`
            : `Altération détectée à l'événement #${verify.first_invalid_id} (${verify.reason}). ${verify.checked} événements valides avant.`}
        </div>
      )}

      <Card>
        <div className="flex flex-wrap items-center gap-2 border-b p-3">
          <Select className="w-44" value={filters.category} onChange={(e) => setFilter("category", e.target.value)}>
            <option value="">Toutes catégories</option>
            <option value="auth">auth</option>
            <option value="ai">ai</option>
            <option value="security">security</option>
            <option value="quota">quota</option>
            <option value="config">config</option>
            <option value="admin">admin</option>
          </Select>
          <Select className="w-40" value={filters.severity} onChange={(e) => setFilter("severity", e.target.value)}>
            <option value="">Toutes gravités</option>
            <option value="CRITICAL">CRITICAL</option>
            <option value="WARNING">WARNING</option>
            <option value="INFO">INFO</option>
          </Select>
          <Select className="w-52" value={filters.event_type} onChange={(e) => setFilter("event_type", e.target.value)}>
            <option value="">Tous les types</option>
            {Object.entries(EVENT_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </Select>
          <Input className="w-52" placeholder="Utilisateur (email)" value={filters.user_email} onChange={(e) => setFilter("user_email", e.target.value)} />
          <Input className="w-64 font-mono text-xs" placeholder="request_id" value={filters.request_id} onChange={(e) => setFilter("request_id", e.target.value)} />
        </div>
        <Table>
          <THead>
            <tr>
              <TH className="w-6" />
              <TH>#</TH>
              <TH>Horodatage</TH>
              <TH>Type</TH>
              <TH>Catégorie</TH>
              <TH>Gravité</TH>
              <TH>Utilisateur</TH>
              <TH>Résumé</TH>
              <TH>Hash</TH>
            </tr>
          </THead>
          <tbody>
            {data?.items.map((e) => (
              <Fragment key={e.id}>
                <TR className="cursor-pointer" onClick={() => setExpanded(expanded === e.id ? null : e.id)}>
                  <TD>{expanded === e.id ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}</TD>
                  <TD className="tabular-nums text-muted-foreground">{e.id}</TD>
                  <TD className="whitespace-nowrap text-muted-foreground">{formatDate(e.ts)}</TD>
                  <TD className="whitespace-nowrap font-medium">{EVENT_LABELS[e.event_type] ?? e.event_type}</TD>
                  <TD><Badge variant="outline">{e.category}</Badge></TD>
                  <TD><SeverityBadge severity={e.severity} /></TD>
                  <TD className="whitespace-nowrap text-muted-foreground">{e.user_email ?? "—"}</TD>
                  <TD className="max-w-xs truncate">{summarize(e.event_type, e.details)}</TD>
                  <TD className="font-mono text-[11px] text-muted-foreground">{e.hash?.slice(0, 8)}…</TD>
                </TR>
                {expanded === e.id && (
                  <tr className="border-b bg-muted/30">
                    <td colSpan={9} className="px-4 py-3">
                      <div className="grid gap-3 text-xs md:grid-cols-2">
                        <div>
                          <div className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">Détails (JSON)</div>
                          <pre className="overflow-x-auto rounded-md border bg-card p-2 font-mono text-[11px]">{JSON.stringify(e.details, null, 2)}</pre>
                        </div>
                        <div className="space-y-1.5 font-mono text-[11px]">
                          <div><span className="text-muted-foreground">statut :</span> {e.status}</div>
                          <div><span className="text-muted-foreground">request_id :</span> {e.request_id ?? "—"}</div>
                          <div className="break-all"><span className="text-muted-foreground">prev_hash :</span> {e.prev_hash}</div>
                          <div className="break-all"><span className="text-muted-foreground">hash :</span> {e.hash}</div>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </Table>
        {data && <Pagination total={data.total} limit={LIMIT} offset={offset} onChange={setOffset} />}
      </Card>
    </>
  );
}

// Le garde est à l'extérieur : les appels API de la page ne partent que pour un ADMIN.
export default function AuditPage() {
  return (
    <RoleGuard roles={["ADMIN"]}>
      <AuditContent />
    </RoleGuard>
  );
}
