import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

type BadgeTone = "default" | "success" | "warning" | "danger" | "neutral";

const tones: Record<BadgeTone, string> = {
  default: "bg-white border border-[rgb(var(--border))] text-[rgb(var(--foreground))]",
  success: "bg-[rgb(var(--primary))] text-black border-transparent",
  warning: "bg-yellow-300 text-black border-transparent",
  danger: "bg-red-400 text-white border-transparent",
  neutral: "bg-gray-100 text-gray-500 border-transparent",
};

export function Badge({
  className,
  tone = "default",
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone?: BadgeTone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold shadow-sm",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}
