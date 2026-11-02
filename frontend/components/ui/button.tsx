// Composants au style shadcn/ui, écrits à la main (le registre shadcn n'était pas joignable
// depuis l'environnement de build). Même API et mêmes conventions (cva + cn).
import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90 shadow-xs",
        outline: "border bg-card hover:bg-muted",
        ghost: "hover:bg-muted",
        danger: "bg-danger text-white hover:bg-danger/90",
      },
      size: { default: "h-8 px-3", sm: "h-7 px-2.5 text-xs", lg: "h-9 px-4", icon: "size-8" },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export function Button({
  className,
  variant,
  size,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof buttonVariants>) {
  return <button className={cn(buttonVariants({ variant, size }), className)} {...props} />;
}
