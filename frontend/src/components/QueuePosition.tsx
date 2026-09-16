import * as React from "react";
import { cn } from "../lib/cn";

export interface QueuePositionProps {
  current: number;
  total: number;
  className?: string;
}

export function QueuePosition({ current, total, className }: QueuePositionProps): React.JSX.Element {
  const safeCurrent = Math.max(1, Math.min(current, total));
  return (
    <span
      role="status"
      aria-label={`Reviewing label ${safeCurrent} of ${total}`}
      className={cn("inline-flex items-center gap-2 rounded-md border border-border bg-muted px-3 py-1 text-sm font-semibold tabular-nums", className)}
    >
      {safeCurrent} of {total}
    </span>
  );
}
