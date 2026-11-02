"use client";

import { AuthProvider, useAuth } from "@/lib/auth-context";
import { Sidebar } from "@/components/layout/sidebar";
import { Header } from "@/components/layout/header";
import { DemoBanner } from "@/components/layout/demo-banner";

function Shell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading || !user) {
    return <div className="flex h-screen items-center justify-center text-xs text-muted-foreground">Chargement…</div>;
  }
  return (
    <div className="min-h-screen">
      <Sidebar />
      <div className="pl-60">
        <DemoBanner />
        <Header />
        <main className="p-6">{children}</main>
      </div>
    </div>
  );
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <Shell>{children}</Shell>
    </AuthProvider>
  );
}
