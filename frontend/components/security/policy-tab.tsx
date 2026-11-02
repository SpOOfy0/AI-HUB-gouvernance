"use client";

import { useEffect, useState } from "react";
import { Check, Lock } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select, Textarea } from "@/components/ui/input";

interface Policy {
  detection_levels: Record<string, string>;
  complexity: { long_message_chars: number; very_long_message_chars: number; complex_score_threshold: number; keywords: string[] };
  retention: { conversation_days: number };
  quota: { alert_thresholds: number[] };
}

const CATEGORY_LABELS: Record<string, string> = {
  secret: "Secrets (clés API, mots de passe, tokens, clés privées)",
  payment_card: "Numéros de carte bancaire",
  personal_data: "Données personnelles (email, téléphone, NIR)",
  financial: "Données financières (IBAN)",
};

export function PolicyTab() {
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [locked, setLocked] = useState<Record<string, string>>({});
  const [keywords, setKeywords] = useState("");
  const [thresholds, setThresholds] = useState("");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function apply(res: { policy: Policy; locked_categories: Record<string, string> }) {
    setPolicy(res.policy);
    setLocked(res.locked_categories);
    setKeywords(res.policy.complexity.keywords.join(", "));
    setThresholds(res.policy.quota.alert_thresholds.join(", "));
  }

  useEffect(() => {
    api<{ policy: Policy; locked_categories: Record<string, string> }>("/policy").then(apply);
  }, []);

  if (!policy) return null;

  async function save() {
    if (!policy) return;
    setError(null);
    setSaved(false);
    try {
      const res = await api<{ policy: Policy; locked_categories: Record<string, string> }>("/policy", {
        method: "PUT",
        json: {
          detection_levels: Object.fromEntries(Object.entries(policy.detection_levels).filter(([k]) => !(k in locked))),
          complexity: { ...policy.complexity, keywords: keywords.split(",").map((k) => k.trim()).filter(Boolean) },
          retention: policy.retention,
          quota: { alert_thresholds: thresholds.split(",").map((t) => Number(t.trim())).filter((n) => !Number.isNaN(n)) },
        },
      });
      apply(res);
      setSaved(true);
    } catch (e) {
      setError((e as ApiError).message);
    }
  }

  const setComplexity = (key: keyof Policy["complexity"], value: number) =>
    setPolicy({ ...policy, complexity: { ...policy.complexity, [key]: value } });

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Mapping détection → niveau</CardTitle>
            <CardDescription>Valeurs par défaut à valider avec la DSI, le RSSI et le DPO.</CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-2.5">
          {Object.entries(policy.detection_levels).map(([cat, level]) => (
            <div key={cat} className="flex items-center justify-between gap-3">
              <span className="text-xs">{CATEGORY_LABELS[cat] ?? cat}</span>
              {cat in locked ? (
                <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Lock className="size-3.5" /> {level} (figé)
                </span>
              ) : (
                <Select
                  className="w-40"
                  value={level}
                  onChange={(e) => setPolicy({ ...policy, detection_levels: { ...policy.detection_levels, [cat]: e.target.value } })}
                >
                  <option value="INTERNAL">INTERNAL</option>
                  <option value="CONFIDENTIAL">CONFIDENTIAL</option>
                  <option value="RESTRICTED">RESTRICTED</option>
                </Select>
              )}
            </div>
          ))}
          <p className="pt-1 text-[11px] leading-relaxed text-muted-foreground">
            Règles fixes : RESTRICTED → blocage, CONFIDENTIAL → modèles privés uniquement, PUBLIC / INTERNAL → modèles dont le niveau
            maximal couvre la requête. Les niveaux des termes métier se règlent dans l&apos;onglet Lexique.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div>
            <CardTitle>Complexité, rétention, alertes</CardTitle>
            <CardDescription>Heuristique déterministe utilisée par le mode automatique.</CardDescription>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1">
              <Label>Message long (car.)</Label>
              <Input type="number" value={policy.complexity.long_message_chars} onChange={(e) => setComplexity("long_message_chars", Number(e.target.value))} />
            </div>
            <div className="space-y-1">
              <Label>Très long (car.)</Label>
              <Input type="number" value={policy.complexity.very_long_message_chars} onChange={(e) => setComplexity("very_long_message_chars", Number(e.target.value))} />
            </div>
            <div className="space-y-1">
              <Label>Seuil COMPLEXE (score)</Label>
              <Input type="number" value={policy.complexity.complex_score_threshold} onChange={(e) => setComplexity("complex_score_threshold", Number(e.target.value))} />
            </div>
          </div>
          <div className="space-y-1">
            <Label>Mots-clés d&apos;analyse (séparés par des virgules)</Label>
            <Textarea rows={3} value={keywords} onChange={(e) => setKeywords(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Rétention des conversations (jours)</Label>
              <Input
                type="number"
                value={policy.retention.conversation_days}
                onChange={(e) => setPolicy({ ...policy, retention: { conversation_days: Number(e.target.value) } })}
              />
            </div>
            <div className="space-y-1">
              <Label>Seuils d&apos;alerte quota (%)</Label>
              <Input value={thresholds} onChange={(e) => setThresholds(e.target.value)} />
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="flex items-center gap-3 lg:col-span-2">
        <Button onClick={save}>Enregistrer la politique</Button>
        {saved && (
          <span className="flex items-center gap-1 text-xs text-success">
            <Check className="size-3.5" /> Enregistré et journalisé (CONFIG_CHANGED)
          </span>
        )}
        {error && <span className="text-xs text-danger">{error}</span>}
      </div>
    </div>
  );
}
