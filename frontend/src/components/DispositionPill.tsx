import { Check, HelpCircle, X } from "lucide-react";
import * as React from "react";
import { cn } from "../lib/cn";
import type { Disposition } from "../types/envelopes";

export interface DispositionPillProps {
  disposition: Disposition;
  className?: string;
}

// WCAG 1.4.1: a disposition is carried by colour AND shape AND text, never
// by colour alone. The shape is asserted structurally by
// tests/test_disposition_pill_wcag_141.py.
const _META: Record<
  Disposition,
  {
    label: string;
    shape: "check" | "x" | "question";
    bg: string;
    fg: string;
    Icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  }
> = {
  pass: {
    label: "Pass",
    shape: "check",
    bg: "bg-[hsl(var(--uswds-success))]",
    fg: "text-white",
    Icon: Check,
  },
  fail: {
    label: "Fail",
    shape: "x",
    bg: "bg-destructive",
    fg: "text-destructive-foreground",
    Icon: X,
  },
  needs_review: {
    label: "Needs review",
    shape: "question",
    bg: "bg-warning",
    fg: "text-warning-foreground",
    Icon: HelpCircle,
  },
};

export function DispositionPill({
  disposition,
  className,
}: DispositionPillProps): React.JSX.Element {
  const meta = _META[disposition];
  return (
    <span
      role="status"
      aria-label={`Disposition: ${meta.label}`}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-semibold",
        meta.bg,
        meta.fg,
        className,
      )}
    >
      <meta.Icon aria-hidden className="h-4 w-4" />
      <span data-shape={meta.shape} aria-hidden="true" />
      <span>{meta.label}</span>
    </span>
  );
}
