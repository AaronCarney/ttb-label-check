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
        // `bg-muted` needs its paired foreground stated: the global `button` rule in
// tokens/globals.css paints every button white-on-blue, and overriding only the
// background left white text on a near-white chip (1.09:1). The hover variant is
// named too, because `button:hover` sets the colour back to white.
        "inline-flex items-center gap-1 rounded-md border border-border bg-muted px-2 py-1 text-xs font-medium text-muted-foreground hover:bg-[hsl(var(--uswds-primary-lighter))] hover:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring",
        className,
      )}
    >
      <BookOpen aria-hidden className="h-3 w-3" />
      <span>{citation}</span>
    </button>
  );
}
