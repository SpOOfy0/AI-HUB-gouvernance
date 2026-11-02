"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

// Redirection côté client : compatible avec l'export statique.
export default function Home() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/playground");
  }, [router]);
  return null;
}
