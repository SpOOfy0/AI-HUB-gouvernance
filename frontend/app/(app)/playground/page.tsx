"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, Ban, Bot, Loader2, Lock, MessageSquarePlus, Send, ShieldAlert, Trash2, User } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { AvailableModel, ChatResponse, ConversationSummary, Level, Routing } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Label, Select, Textarea } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { LevelBadge } from "@/components/badges";
import { RoutingPanel } from "@/components/playground/routing-panel";
import { cn, formatDate } from "@/lib/utils";

type UiMessage =
  | { kind: "user"; key: string; content: string | null } // null = contenu masqué (requête bloquée)
  | { kind: "assistant"; key: string; content: string; routing?: Routing; requestId?: string }
  | { kind: "blocked"; key: string; routing: Routing; requestId: string }
  | { kind: "refused"; key: string; routing: Routing; canFallback: boolean; retry: () => void }
  | { kind: "error"; key: string; text: string; requestId?: string };

const EXAMPLES = [
  { label: "PUBLIC", text: "Explique-moi la différence entre FOB et CIF." },
  { label: "INTERNAL", text: "Résume la procédure interne d'ouverture d'un dossier export au site de Fos." },
  { label: "CONFIDENTIAL", text: "Analyse les tarifs négociés avec notre armateur pour la ligne Asie." },
  { label: "RESTRICTED", text: "Voici notre clé API : sk-xxxx, pourquoi ça ne marche pas ?" },
];

let keySeq = 0;
const nextKey = () => `m${++keySeq}`;

export default function PlaygroundPage() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [convLevel, setConvLevel] = useState<Level | null>(null);
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [models, setModels] = useState<AvailableModel[]>([]);
  const [modelId, setModelId] = useState<string>("auto");
  const [declared, setDeclared] = useState<string>("");
  const [deep, setDeep] = useState(false);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const loadConversations = useCallback(() => api<ConversationSummary[]>("/conversations").then(setConversations), []);

  useEffect(() => {
    loadConversations();
    api<AvailableModel[]>("/models/available").then(setModels);
  }, [loadConversations]);

  useEffect(() => {
    // Accolades nécessaires : scrollIntoView renvoie une Promise dans les navigateurs récents.
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  async function openConversation(id: number) {
    const conv = await api<{ id: number; max_classification: Level; messages: { id: number; role: string; content: string; routing: Routing | null }[] }>(
      `/conversations/${id}`,
    );
    setActiveId(conv.id);
    setConvLevel(conv.max_classification);
    setNotice(null);
    setMessages(
      conv.messages.map((m) =>
        m.role === "user"
          ? { kind: "user", key: `db${m.id}`, content: m.content }
          : { kind: "assistant", key: `db${m.id}`, content: m.content, routing: m.routing ?? undefined },
      ),
    );
  }

  function newConversation() {
    setActiveId(null);
    setConvLevel(null);
    setMessages([]);
    setNotice(null);
  }

  async function deleteConversation(id: number) {
    await api(`/conversations/${id}`, { method: "DELETE" });
    if (id === activeId) newConversation();
    loadConversations();
  }

  async function send(text: string, acceptPrivateFallback = false) {
    if (!text.trim() || sending) return;
    const userKey = nextKey();
    setMessages((prev) => [...prev, { kind: "user", key: userKey, content: text }]);
    setInput("");
    setSending(true);
    setNotice(null);
    try {
      const res = await api<ChatResponse>("/chat/completions", {
        method: "POST",
        json: {
          message: text,
          conversation_id: activeId,
          model_id: modelId === "auto" ? null : Number(modelId),
          declared_level: declared || null,
          deep_reasoning: deep,
          accept_private_fallback: acceptPrivateFallback,
        },
      });
      if (res.status === "BLOCKED") {
        // On masque le message de l'utilisateur à l'écran : il contient une donnée sensible.
        setMessages((prev) => [
          ...prev.map((m): UiMessage => (m.key === userKey ? { kind: "user", key: userKey, content: null } : m)),
          { kind: "blocked", key: nextKey(), routing: res.routing, requestId: res.request_id },
        ]);
      } else if (res.status === "REFUSED") {
        const refusedKey = nextKey();
        setMessages((prev) => [
          ...prev,
          {
            kind: "refused",
            key: refusedKey,
            routing: res.routing,
            canFallback: res.can_fallback_private,
            retry: () => {
              // On retire le message refusé et la carte de refus, puis on renvoie avec bascule privée acceptée.
              setMessages((p) => p.filter((m) => m.key !== userKey && m.key !== refusedKey));
              send(text, true);
            },
          },
        ]);
      } else if (res.message) {
        setMessages((prev) => [
          ...prev,
          { kind: "assistant", key: nextKey(), content: res.message!.content, routing: res.routing, requestId: res.request_id },
        ]);
        setConvLevel(res.routing.classification);
        if (activeId === null && res.conversation_id) setActiveId(res.conversation_id);
        loadConversations();
      }
      if (res.alerts.length > 0) {
        const a = res.alerts[0];
        setNotice(
          a.threshold >= 100
            ? "Quota atteint : vos prochaines requêtes seront refusées."
            : `Alerte : ${a.threshold} % du budget ${a.scope === "user" ? "personnel" : "du département"} atteint.`,
        );
      }
    } catch (err) {
      const e = err as ApiError;
      setMessages((prev) => [...prev, { kind: "error", key: nextKey(), text: e.message, requestId: e.requestId }]);
    } finally {
      setSending(false);
      window.dispatchEvent(new Event("rdt:usage-changed"));
    }
  }

  const privateOnly = convLevel === "CONFIDENTIAL";

  return (
    <div className="-m-6 grid h-[calc(100vh-3.5rem-25px)] grid-cols-[260px_1fr]">
      {/* Liste des conversations */}
      <aside className="flex min-h-0 flex-col border-r bg-card">
        <div className="border-b p-3">
          <Button variant="outline" className="w-full" onClick={newConversation}>
            <MessageSquarePlus /> Nouvelle conversation
          </Button>
        </div>
        <div className="min-h-0 flex-1 space-y-0.5 overflow-y-auto p-2">
          {conversations.length === 0 && <p className="p-2 text-xs text-muted-foreground">Aucune conversation.</p>}
          {conversations.map((c) => (
            <div
              key={c.id}
              className={cn("group flex cursor-pointer items-start gap-2 rounded-md px-2 py-1.5 hover:bg-muted", c.id === activeId && "bg-muted")}
              onClick={() => openConversation(c.id)}
            >
              <div className="min-w-0 flex-1">
                <div className="truncate text-[13px]">{c.title}</div>
                <div className="mt-0.5 flex items-center gap-1.5 text-[10px] text-muted-foreground">
                  <LevelBadge level={c.max_classification} /> {formatDate(c.updated_at)}
                </div>
              </div>
              <button
                aria-label="Supprimer la conversation"
                className="invisible rounded p-1 text-muted-foreground hover:bg-card hover:text-danger group-hover:visible"
                onClick={(e) => {
                  e.stopPropagation();
                  deleteConversation(c.id);
                }}
              >
                <Trash2 className="size-3.5" />
              </button>
            </div>
          ))}
        </div>
        <p className="border-t p-3 text-[10px] leading-relaxed text-muted-foreground">
          Seuls les échanges autorisés sont conservés (rétention 90 jours). Les requêtes bloquées ne sont jamais stockées.
        </p>
      </aside>

      {/* Zone de conversation */}
      <section className="flex min-h-0 flex-col">
        {privateOnly && (
          <div className="flex items-center gap-2 border-b bg-warning/10 px-6 py-1.5 text-xs text-[oklch(0.45_0.1_70)]">
            <Lock className="size-3.5" /> Conversation classée CONFIDENTIAL : elle reste limitée aux modèles privés. Ouvrez une nouvelle
            conversation pour un sujet public.
          </div>
        )}
        {notice && (
          <div className="flex items-center gap-2 border-b bg-danger/8 px-6 py-1.5 text-xs text-danger">
            <AlertTriangle className="size-3.5" /> {notice}
          </div>
        )}

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          <div className="mx-auto max-w-3xl space-y-4">
            {messages.length === 0 && (
              <div className="py-10 text-center">
                <h2 className="text-base font-semibold">Chaque requête passe par la passerelle</h2>
                <p className="mx-auto mt-1 max-w-md text-xs text-muted-foreground">
                  Classification, décision de politique et choix du modèle sont affichés sous chaque réponse. Essayez un exemple :
                </p>
                <div className="mx-auto mt-5 grid max-w-2xl grid-cols-2 gap-2 text-left">
                  {EXAMPLES.map((ex) => (
                    <button key={ex.label} onClick={() => setInput(ex.text)} className="rounded-lg border bg-card p-3 text-xs hover:border-primary/40">
                      <LevelBadge level={ex.label as Level} />
                      <div className="mt-1.5 text-foreground/80">{ex.text}</div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m) => {
              if (m.kind === "user")
                return (
                  <div key={m.key} className="flex gap-3">
                    <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-muted">
                      <User className="size-3.5" />
                    </div>
                    <div className="pt-1 text-[13px] leading-relaxed whitespace-pre-wrap">
                      {m.content ?? <span className="italic text-muted-foreground">Message non envoyé (contenu masqué car sensible).</span>}
                    </div>
                  </div>
                );
              if (m.kind === "assistant")
                return (
                  <div key={m.key} className="flex gap-3">
                    <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                      <Bot className="size-3.5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <Card className="px-3.5 py-2.5 text-[13px] leading-relaxed whitespace-pre-wrap">{m.content}</Card>
                      {m.routing && <RoutingPanel routing={m.routing} requestId={m.requestId} />}
                    </div>
                  </div>
                );
              if (m.kind === "blocked")
                return (
                  <div key={m.key} className="ml-10">
                    <div className="rounded-lg border border-danger/30 bg-danger/5 p-3.5">
                      <div className="flex items-center gap-2 text-[13px] font-semibold text-danger">
                        <ShieldAlert className="size-4" /> Requête bloquée
                      </div>
                      <p className="mt-1 text-xs leading-relaxed">
                        Votre message contient des données qui ne doivent être envoyées à aucun modèle (
                        {m.routing.detections
                          .filter((d) => d.level === "RESTRICTED")
                          .map((d) => d.label)
                          .join(", ")}
                        ). Il n&apos;a été transmis à aucun fournisseur et n&apos;a pas été conservé. Retirez la donnée sensible puis reformulez.
                      </p>
                      <p className="mt-1 text-[11px] text-muted-foreground">Un événement de sécurité a été enregistré (sans le contenu).</p>
                    </div>
                    <RoutingPanel routing={m.routing} requestId={m.requestId} />
                  </div>
                );
              if (m.kind === "refused")
                return (
                  <div key={m.key} className="ml-10 rounded-lg border border-warning/40 bg-warning/8 p-3.5">
                    <div className="flex items-center gap-2 text-[13px] font-semibold">
                      <Ban className="size-4 text-[oklch(0.55_0.13_70)]" /> Modèle demandé non autorisé
                    </div>
                    <p className="mt-1 text-xs leading-relaxed">{m.routing.reason}</p>
                    <p className="mt-1 text-[11px] text-muted-foreground">Le message n&apos;a pas été envoyé. Aucun envoi n&apos;est forcé vers un modèle non éligible.</p>
                    {m.canFallback && (
                      <Button size="sm" className="mt-2" onClick={m.retry} disabled={sending}>
                        <Lock /> Envoyer à un modèle privé à la place
                      </Button>
                    )}
                  </div>
                );
              return (
                <div key={m.key} className="ml-10 rounded-lg border border-danger/30 bg-danger/5 p-3 text-xs">
                  <span className="font-semibold text-danger">Requête refusée : </span>
                  {m.text}
                  {m.requestId && <span className="ml-2 font-mono text-[10px] text-muted-foreground">{m.requestId}</span>}
                </div>
              );
            })}
            {sending && (
              <div className="ml-10 flex items-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="size-3.5 animate-spin" /> Classification, routage et appel du modèle…
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        {/* Saisie */}
        <div className="border-t bg-card px-6 py-3">
          <div className="mx-auto max-w-3xl">
            <div className="mb-2 flex flex-wrap items-end gap-3">
              <div className="w-72 space-y-1">
                <Label>Modèle</Label>
                <Select value={modelId} onChange={(e) => setModelId(e.target.value)}>
                  <option value="auto">Auto (recommandé)</option>
                  {models.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.display_name} · {m.hosting === "PRIVATE" ? "privé" : "externe"} · max {m.max_classification}
                      {m.simulated ? " · simulé" : ""}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="w-56 space-y-1">
                <Label>Niveau de confidentialité déclaré</Label>
                <Select value={declared} onChange={(e) => setDeclared(e.target.value)}>
                  <option value="">Aucun (détection auto)</option>
                  <option value="INTERNAL">INTERNAL</option>
                  <option value="CONFIDENTIAL">CONFIDENTIAL</option>
                  <option value="RESTRICTED">RESTRICTED</option>
                </Select>
              </div>
              <label className="flex h-8 cursor-pointer items-center gap-2 text-xs">
                <input type="checkbox" checked={deep} onChange={(e) => setDeep(e.target.checked)} className="accent-[var(--primary)]" />
                Raisonnement approfondi
              </label>
            </div>
            <div className="flex items-end gap-2">
              <Textarea
                rows={2}
                value={input}
                placeholder="Posez votre question (Entrée pour envoyer, Maj+Entrée pour un saut de ligne)…"
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    send(input);
                  }
                }}
                className="resize-none"
              />
              <Button size="lg" onClick={() => send(input)} disabled={sending || !input.trim()}>
                <Send /> Envoyer
              </Button>
            </div>
            <div className="mt-1.5 flex items-center gap-2 text-[10px] text-muted-foreground">
              Le niveau déclaré peut relever la classification, jamais l&apos;abaisser.
              <Badge variant="outline">{models.some((m) => m.simulated) ? "Réponses simulées en mode démo" : "Fournisseurs réels"}</Badge>
              {convLevel && (
                <span className="ml-auto flex items-center gap-1.5">
                  Niveau de la conversation : <LevelBadge level={convLevel} />
                </span>
              )}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
