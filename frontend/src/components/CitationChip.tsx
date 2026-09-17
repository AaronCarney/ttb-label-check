import { BookOpen } from "lucide-react";
import * as React from "react";
import { cn } from "../lib/cn";

export interface CitationChipProps {
  citation: string;
  className?: string;
}

// Static text, not a control. The chip names the CFR section a finding rests
// on, so a reviewer knows what to look up. It does not open it: the rules cite
// 43 distinct citations and this product holds the wording of one of them, and
// a button that opens nothing tells a reviewer there is more here to see when
// there is not. See `docs/decisions.md#0034`.
export function CitationChip({ citation, className }: CitationChipProps): React.JSX.Element {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border border-border bg-muted px-2 py-1 text-xs font-medium text-muted-foreground",
        className,
      )}
    >
      <BookOpen aria-hidden className="h-3 w-3" />
      <span>{citation}</span>
    </span>
  );
}
