"use client";

import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Level } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { Table, TD, TH, THead, TR } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { LevelBadge } from "@/components/badges";

interface Term {
  id: number;
  term: string;
  category: string;
  level: Level;
  is_regex: boolean;
  is_active: boolean;
}

const CATEGORIES = { client: "Client", commercial: "Commercial", internal_id: "Identifiant interne", site: "Site", procedure: "Procédure" };

export function LexiconTab() {
  const [terms, setTerms] = useState<Term[]>([]);
  const [form, setForm] = useState({ term: "", category: "client", level: "CONFIDENTIAL", is_regex: false });
  const [error, setError] = useState<string | null>(null);

  const load = () => api<Term[]>("/policy/lexicon").then(setTerms);
  useEffect(() => {
    load();
  }, []);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api("/policy/lexicon", { method: "POST", json: form });
      setForm({ ...form, term: "" });
      load();
    } catch (err) {
      setError((err as ApiError).message);
    }
  }

  async function toggle(t: Term) {
    await api(`/policy/lexicon/${t.id}`, { method: "PUT", json: { ...t, is_active: !t.is_active } });
    load();
  }

  async function remove(t: Term) {
    await api(`/policy/lexicon/${t.id}`, { method: "DELETE" });
    load();
  }

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Lexique métier</CardTitle>
          <CardDescription>
            Noms de clients, expressions commerciales, formats d&apos;identifiants internes. Comparaison insensible à la casse et aux accents.
            Toute modification est journalisée.
          </CardDescription>
        </div>
      </CardHeader>
      <form onSubmit={add} className="flex flex-wrap items-center gap-2 border-b p-3">
        <Input className="w-72" placeholder="Terme ou expression régulière" value={form.term} onChange={(e) => setForm({ ...form, term: e.target.value })} required />
        <Select className="w-44" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
          {Object.entries(CATEGORIES).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </Select>
        <Select className="w-40" value={form.level} onChange={(e) => setForm({ ...form, level: e.target.value })}>
          <option value="INTERNAL">INTERNAL</option>
          <option value="CONFIDENTIAL">CONFIDENTIAL</option>
          <option value="RESTRICTED">RESTRICTED</option>
        </Select>
        <label className="flex items-center gap-1.5 text-xs">
          <input type="checkbox" checked={form.is_regex} onChange={(e) => setForm({ ...form, is_regex: e.target.checked })} /> Regex
        </label>
        <Button type="submit" size="sm">
          <Plus /> Ajouter
        </Button>
        {error && <span className="text-xs text-danger">{error}</span>}
      </form>
      <Table>
        <THead>
          <tr>
            <TH>Terme</TH>
            <TH>Catégorie</TH>
            <TH>Niveau</TH>
            <TH>Type</TH>
            <TH>Actif</TH>
            <TH className="w-10" />
          </tr>
        </THead>
        <tbody>
          {terms.map((t) => (
            <TR key={t.id} className={t.is_active ? "" : "opacity-50"}>
              <TD className="font-mono text-xs">{t.term}</TD>
              <TD>{CATEGORIES[t.category as keyof typeof CATEGORIES] ?? t.category}</TD>
              <TD><LevelBadge level={t.level} /></TD>
              <TD>{t.is_regex ? <Badge variant="outline">regex</Badge> : <span className="text-muted-foreground">terme</span>}</TD>
              <TD>
                <input type="checkbox" checked={t.is_active} onChange={() => toggle(t)} aria-label="Activer le terme" />
              </TD>
              <TD>
                <button aria-label="Supprimer" onClick={() => remove(t)} className="rounded p-1 text-muted-foreground hover:text-danger">
                  <Trash2 className="size-3.5" />
                </button>
              </TD>
            </TR>
          ))}
        </tbody>
      </Table>
    </Card>
  );
}
