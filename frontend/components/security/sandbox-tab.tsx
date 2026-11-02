"use client";

import { useState } from "react";
import { FlaskConical, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import type { Detection, Level } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label, Select, Textarea } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { DecisionBadge, HostingBadge, LevelBadge } from "@/components/badges";

interface ClassifyResult {
  classification: Level;
  decision: "ALLOW" | "PRIVATE_ONLY" | "BLOCK";
  reason: string;
  complexity: string;
  detections: Detection[];
  eligible_models: { display_name: string; hosting: string }[];
  would_select: string | null;
}

export function SandboxTab() {
  const [text, setText] = useState("");
  const [declared, setDeclared] = useState("");
  const [result, setResult] = useState<ClassifyResult | null>(null);
  const [loading, setLoading] = useState(false);

  async function run() {
    setLoading(true);
    try {
      setResult(await api<ClassifyResult>("/classify", { method: "POST", json: { message: text, declared_level: declared || null } }));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Tester la classification</CardTitle>
            <CardDescription>Aucun modèle n&apos;est appelé et le texte n&apos;est pas conservé.</CardDescription>
          </div>
          <FlaskConical className="size-4 text-muted-foreground" />
        </CardHeader>
        <CardContent className="space-y-3">
          <Textarea rows={7} value={text} onChange={(e) => setText(e.target.value)} placeholder="Collez un texte à analyser…" />
          <div className="flex items-end gap-3">
            <div className="w-56 space-y-1">
              <Label>Niveau déclaré</Label>
              <Select value={declared} onChange={(e) => setDeclared(e.target.value)}>
                <option value="">Aucun</option>
                <option value="INTERNAL">INTERNAL</option>
                <option value="CONFIDENTIAL">CONFIDENTIAL</option>
                <option value="RESTRICTED">RESTRICTED</option>
              </Select>
            </div>
            <Button onClick={run} disabled={!text.trim() || loading}>
              {loading && <Loader2 className="animate-spin" />} Analyser
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Décision simulée</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-xs">
          {!result && <p className="text-muted-foreground">Le résultat s&apos;affichera ici.</p>}
          {result && (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <LevelBadge level={result.classification} />
                <DecisionBadge decision={result.decision} />
                <Badge variant="outline">complexité {result.complexity}</Badge>
              </div>
              <p className="leading-relaxed">{result.reason}</p>
              <div>
                <div className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">Détections</div>
                {result.detections.length === 0 ? (
                  <span className="text-muted-foreground">Aucune</span>
                ) : (
                  <div className="flex flex-wrap gap-1.5">
                    {result.detections.map((d) => (
                      <Badge key={d.type} variant="outline">{d.label} × {d.count} · {d.level}</Badge>
                    ))}
                  </div>
                )}
              </div>
              <div>
                <div className="mb-1 text-[10px] uppercase tracking-wide text-muted-foreground">Modèles éligibles (ordre de préférence)</div>
                {result.eligible_models.length === 0 ? (
                  <span className="text-muted-foreground">Aucun : la requête ne serait envoyée à aucun modèle.</span>
                ) : (
                  <ol className="space-y-1">
                    {result.eligible_models.map((m, i) => (
                      <li key={m.display_name} className="flex items-center gap-2">
                        <span className="w-4 text-muted-foreground">{i + 1}.</span> {m.display_name} <HostingBadge hosting={m.hosting} />
                      </li>
                    ))}
                  </ol>
                )}
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
