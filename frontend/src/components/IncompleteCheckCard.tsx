import { AlertTriangle } from "lucide-react";
import type * as React from "react";
import { cn } from "../lib/cn";

export interface IncompleteCheckCardProps {
  /** The engine failure that ended the check, or null if none was recorded. */
  reasonCode: string | null;
  /** How many fields the check did come back with. */
  fieldCount: number;
  className?: string;
}

/** What to say about a check that did not finish.
 *
 *  Two cases, and they need different words. When nothing came back, an empty
 *  panel would read as a label with nothing wrong with it, which is the
 *  opposite of what happened: nothing about it was checked. When some fields
 *  came back — which is what the evaluation guard now returns rather than
 *  discarding a finished read — the danger is the reverse: a page of field
 *  cards reads as a completed check, and the rules that never ran are missing
 *  rather than satisfied.
 *
 *  Both surfaces use this one component so the single-label page and the batch
 *  panel cannot describe the same envelope differently (docs/PRD.md FR-12).
 */
export function IncompleteCheckCard({
  reasonCode,
  fieldCount,
  className,
}: IncompleteCheckCardProps): React.JSX.Element {
  const partial = fieldCount > 0;
  return (
    <section
      role="region"
      aria-label={partial ? "Check did not finish" : "Label not checked"}
      className={cn(
        "rounded-lg border border-warning/40 bg-warning/10 p-4 space-y-2",
        className,
      )}
    >
      <header className="flex items-center gap-2">
        <AlertTriangle aria-hidden className="h-5 w-5" />
        <h3 className="font-semibold">
          {partial ? "This check did not finish" : "This label was not checked"}
        </h3>
      </header>
      {reasonCode !== null && (
        <p className="break-words font-mono text-xs text-muted-foreground">{reasonCode}</p>
      )}
      {partial ? (
        <p className="text-sm">
          The check was stopped before it finished. What is below is what it had read by then.
          Any rule that had not run yet reported nothing, which is not the same as finding
          nothing wrong, so treat this as incomplete rather than as a verdict. Submitting the
          label again may complete it.
        </p>
      ) : (
        <p className="text-sm">
          No field on this label was checked. Anything else submitted with it was checked as
          usual. Submit this label on its own to see what went wrong with it.
        </p>
      )}
    </section>
  );
}
