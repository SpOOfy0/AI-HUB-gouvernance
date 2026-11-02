"use client";

import { useState } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { Tabs } from "@/components/ui/tabs";
import { EventsTab } from "@/components/security/events-tab";
import { SandboxTab } from "@/components/security/sandbox-tab";
import { PolicyTab } from "@/components/security/policy-tab";
import { LexiconTab } from "@/components/security/lexicon-tab";
import { RoleGuard } from "@/components/layout/role-guard";

type Tab = "events" | "sandbox" | "policy" | "lexicon";

export default function SecurityPage() {
  const [tab, setTab] = useState<Tab>("events");
  return (
    <RoleGuard roles={["ADMIN"]}>
      <PageHeader title="Sécurité" description="Événements de sécurité, politique de classification et lexique métier." />
      <Tabs
        value={tab}
        onChange={setTab}
        tabs={[
          { id: "events", label: "Événements" },
          { id: "sandbox", label: "Tester la classification" },
          { id: "policy", label: "Politique" },
          { id: "lexicon", label: "Lexique métier" },
        ]}
      />
      {tab === "events" && <EventsTab />}
      {tab === "sandbox" && <SandboxTab />}
      {tab === "policy" && <PolicyTab />}
      {tab === "lexicon" && <LexiconTab />}
    </RoleGuard>
  );
}
