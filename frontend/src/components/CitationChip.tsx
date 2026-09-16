import { BookOpen } from "lucide-react";
import * as React from "react";
import { cn } from "../lib/cn";

export interface CitationChipProps {
  citation: string;
  onOpen: () => void;
  className?: string;
}

export function CitationChip({ citation, onOpen, className }: CitationChipProps): React.JSX.Element {
  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn(
        "inline-flex items-center gap-1 rounded-md border border-border bg-muted px-2 py-1 text-xs font-medium hover:bg-[hsl(var(--uswds-primary-lighter))] focus-visible:ring-2 focus-visible:ring-ring",
        className,
      )}
    >
      <BookOpen aria-hidden className="h-3 w-3" />
      <span>{citation}</span>
    </button>
  );
}
