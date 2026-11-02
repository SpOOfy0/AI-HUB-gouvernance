"use client";

import { cn } from "@/lib/utils";

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: string }[]; value: T; onChange: (v: T) => void }) {
  return (
    <div className="mb-4 flex gap-1 border-b">
      {tabs.map((t) => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className={cn(
            "-mb-px border-b-2 border-transparent px-3 py-2 text-[13px] text-muted-foreground hover:text-foreground",
            value === t.id && "border-primary font-medium text-foreground",
          )}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
