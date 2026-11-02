"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AuditItem } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { Table, TD, TH, THead, TR } from "@/components/ui/table";
import { SeverityBadge } from "@/components/badges";
import { Pagination } from "@/components/pagination";
import { EVENT_LABELS, summarize } from "@/lib/events";
import { formatDate } from "@/lib/utils";

const LIMIT = 25;

export function EventsTab() {
  const [data, setData] = useState<{ total: number; by_type: Record<string, number>; items: AuditItem[] } | null>(null);
  const [severity, setSeverity] = useState("");
  const [eventType, setEventType] = useState("");
  const [days, setDays] = useState("30");
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    const params = new URLSearchParams({ days, limit: String(LIMIT), offset: String(offset) });
    if (severity) params.set("severity", severity);
    if (eventType) params.set("event_type", eventType);
    api<typeof data>(`/security/events?${params}`).then(setData);
  }, [severity, eventType, days, offset]);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {Object.entries(data?.by_type ?? {})
          .sort((a, b) => b[1] - a[1])
          .slice(0, 5)
          .map(([type, count]) => (
            <Card key={type} className="cursor-pointer p-3 hover:border-primary/40" onClick={() => { setEventType(type); setOffset(0); }}>
              <div className="text-[11px] text-muted-foreground">{EVENT_LABELS[type] ?? type}</div>
              <div className="mt-1 text-xl font-semibold tabular-nums">{count}</div>
            </Card>
          ))}
      </div>

      <Card>
        <div className="flex flex-wrap items-center gap-2 border-b p-3">
          <Select className="w-48" value={days} onChange={(e) => { setDays(e.target.value); setOffset(0); }}>
            <option value="1">Dernières 24 h</option>
            <option value="7">7 derniers jours</option>
            <option value="30">30 derniers jours</option>
            <option value="90">90 derniers jours</option>
          </Select>
          <Select className="w-44" value={severity} onChange={(e) => { setSeverity(e.target.value); setOffset(0); }}>
            <option value="">Toutes gravités</option>
            <option value="CRITICAL">CRITICAL</option>
            <option value="WARNING">WARNING</option>
            <option value="INFO">INFO</option>
          </Select>
          <Select className="w-56" value={eventType} onChange={(e) => { setEventType(e.target.value); setOffset(0); }}>
            <option value="">Tous les types</option>
            {["REQUEST_BLOCKED", "MANUAL_MODEL_REFUSED", "LOGIN_FAILED", "RATE_LIMITED", "NO_MODEL_AVAILABLE", "QUOTA_THRESHOLD", "QUOTA_EXCEEDED"].map((t) => (
              <option key={t} value={t}>{EVENT_LABELS[t]}</option>
            ))}
          </Select>
        </div>
        <Table>
          <THead>
            <tr>
              <TH>Date</TH>
              <TH>Type</TH>
              <TH>Gravité</TH>
              <TH>Utilisateur</TH>
              <TH>Détails (métadonnées)</TH>
              <TH>request_id</TH>
            </tr>
          </THead>
          <tbody>
            {data?.items.map((e) => (
              <TR key={e.id}>
                <TD className="whitespace-nowrap text-muted-foreground">{formatDate(e.ts)}</TD>
                <TD className="whitespace-nowrap font-medium">{EVENT_LABELS[e.event_type] ?? e.event_type}</TD>
                <TD><SeverityBadge severity={e.severity} /></TD>
                <TD className="whitespace-nowrap text-muted-foreground">{e.user_email ?? "—"}</TD>
                <TD className="max-w-md">{summarize(e.event_type, e.details)}</TD>
                <TD className="font-mono text-[11px] text-muted-foreground">{e.request_id?.slice(0, 12) ?? "—"}</TD>
              </TR>
            ))}
            {data && data.items.length === 0 && (
              <TR><TD colSpan={6} className="py-6 text-center text-muted-foreground">Aucun événement.</TD></TR>
            )}
          </tbody>
        </Table>
        {data && <Pagination total={data.total} limit={LIMIT} offset={offset} onChange={setOffset} />}
      </Card>
    </div>
  );
}
