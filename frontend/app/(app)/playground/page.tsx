"use client";

import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { useAuth } from "@/lib/auth-context";

// Page provisoire de la phase 1 (le playground complet arrive en phase 3).
export default function PlaygroundPage() {
  const { user } = useAuth();
  return (
    <>
      <PageHeader title="Playground" description="Chat multi-modèles avec transparence du routage." />
      <Card>
        <CardContent>Bienvenue {user?.full_name}. Le socle (authentification, rôles, layout) est en place.</CardContent>
      </Card>
    </>
  );
}
