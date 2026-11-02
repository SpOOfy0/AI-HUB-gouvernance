import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px] font-medium leading-none whitespace-nowrap",
  {
    variants: {
      variant: {
        default: "bg-muted text-foreground",
        primary: "border-primary/20 bg-primary/8 text-primary",
        success: "border-success/25 bg-success/10 text-success",
        warning: "border-warning/30 bg-warning/12 text-[oklch(0.5_0.12_70)]",
        danger: "border-danger/25 bg-danger/10 text-danger",
        outline: "bg-card text-muted-foreground",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export function Badge({ className, variant, ...props }: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
