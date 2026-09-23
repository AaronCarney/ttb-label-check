import { HelpCircle } from "lucide-react";
import * as React from "react";
import { cn } from "../lib/cn";

export interface NeedsReviewFlagProps {
  /** What is left for the reviewer, such as "2 fields to confirm". */
  detail?: string;
  className?: string;
}

// Sits beside the pre-filled answer, never in place of it: the answer is the
// check's best guess, and this says a person must confirm it before it stands
// (docs/decisions.md#0065). Colour, shape and text, as the result pill.
export function NeedsReviewFlag({ detail, className }: NeedsReviewFlagProps): React.JSX.Element {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border border-warning px-2 py-0.5 text-sm font-medium text-foreground",
        className,
      )}
    >
      <HelpCircle aria-hidden className="h-4 w-4" />
      <span>Needs review{detail ? `: ${detail}` : ""}</span>
    </span>
  );
}
