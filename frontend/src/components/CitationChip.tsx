import { BookOpen } from "lucide-react";
import * as React from "react";
import { cn } from "../lib/cn";

export interface CitationChipProps {
  citation: string;
  // Absent means nothing opens, and the chip is then text. This is the rule
  // `docs/decisions.md#0034` left behind: the chip was made static because it
  // rendered as a button whose `onOpen` no call site supplied, so a reviewer
  // could press it and nothing happened. The product now holds the wording of
  // every section its rules cite (`assets/cfr/`, `docs/decisions.md#0046`), so
  // the results page supplies one — and anywhere that does not, the chip goes
  // back to being text rather than offering a control that does nothing.
  onOpen?: (citation: string) => void;
  // The citation the panel is currently showing, so a reviewer reading down a
  // column of chips can see which one they are looking at.
  selected?: boolean;
  // The id of the panel this chip fills, announced to assistive technology so
  // the relationship between the chip and the column is not purely visual.
  controls?: string;
  className?: string;
}

const _SHELL =
  "inline-flex items-center gap-1 rounded-md border border-border bg-muted px-2 py-1 text-xs font-medium text-muted-foreground";

export function CitationChip({
  citation,
  onOpen,
  selected,
  controls,
  className,
}: CitationChipProps): React.JSX.Element {
  if (!onOpen) {
    return (
      <span className={cn(_SHELL, className)}>
        <BookOpen aria-hidden className="h-3 w-3" />
        <span>{citation}</span>
      </span>
    );
  }
  return (
    <button
      type="button"
      onClick={() => onOpen(citation)}
      aria-pressed={selected ?? false}
      aria-controls={controls}
      className={cn(
        _SHELL,
        "hover:bg-muted/70 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2",
        selected && "border-foreground/40 bg-background text-foreground",
        className,
      )}
    >
      <BookOpen aria-hidden className="h-3 w-3" />
      <span>{citation}</span>
    </button>
  );
}
