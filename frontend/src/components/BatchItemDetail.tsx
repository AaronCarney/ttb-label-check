import * as React from "react";
import { cn } from "../lib/cn";
import type { BatchSSEEvent } from "../types/sse";
import { AISuggestionBlock } from "./AISuggestionBlock";
import { ConfidenceIndicator } from "./ConfidenceIndicator";
import { DispositionPill } from "./DispositionPill";
import { FieldCard } from "./FieldCard";
import { RuleVerdict } from "./RuleVerdict";

export interface BatchItemDetailProps {
  /** The opened row, or null when the reviewer has not opened one yet. */
  row: BatchSSEEvent | null;
  className?: string;
}

// The stream already carries every result in full, so opening a row is a
// render and not a fetch: the batch page holds the same envelope the
// single-label page is given, and builds it out of the same cards so the two
// surfaces cannot report the same label differently (docs/PRD.md FR-12).

// An item the app could not check carries no fields at all, and the code
// naming why is its one audit-trail row. Reading it here is the only way the
// panel can say what happened (docs/PRD.md FR-13, docs/decisions.md#0020).
function _notCheckedReasonCode(row: BatchSSEEvent): string | null {
  return row.audit_trail.per_rule_trace[0]?.rule_id ?? null;
}

export function BatchItemDetail({ row, className }: BatchItemDetailProps): React.JSX.Element {
  const headingRef = React.useRef<HTMLHeadingElement>(null);
  const labelRef = row?.label_ref ?? null;

  // Opening a row moves focus into the panel. A reviewer who pressed Enter on
  // a table row otherwise stays in the table, with what they just opened
  // somewhere below them and nothing saying it arrived.
  React.useEffect(() => {
    if (labelRef !== null) headingRef.current?.focus();
  }, [labelRef]);

  if (row === null) {
    return (
      <p
        className={cn(
          "rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground",
          className,
        )}
      >
        Choose a label above to see its check results.
      </p>
    );
  }

  const notCheckedCode = row.fields.length === 0 ? _notCheckedReasonCode(row) : null;

  return (
    <section
      role="region"
      aria-label={`Check results for ${row.label_ref}`}
      className={cn("space-y-4", className)}
    >
      <header className="flex flex-wrap items-center justify-between gap-3 border-t-2 border-border pt-4">
        <div>
          <h3
            ref={headingRef}
            tabIndex={-1}
            className="text-lg font-semibold focus-visible:[outline:3px_solid_hsl(var(--ring))]"
          >
            {row.label_ref}
          </h3>
          <p className="break-words font-mono text-xs text-muted-foreground">{row.evaluation_id}</p>
        </div>
        <div className="flex items-center gap-3">
          <DispositionPill disposition={row.disposition} />
          <ConfidenceIndicator
            band={row.disposition_confidence.band}
            numeric={row.disposition_confidence.numeric}
          />
        </div>
      </header>

      {row.fields.length === 0 ? (
        // Not a verdict about the label. An empty panel here would read as a
        // label with nothing wrong with it, which is the opposite of what
        // happened: nothing about it was checked.
        <p className="rounded-md border border-border bg-muted/30 p-3 text-sm">
          No field on this label was checked.
          {notCheckedCode !== null && (
            <>
              {" "}The batch recorded{" "}
              <span className="font-mono text-xs">{notCheckedCode}</span> against it.
            </>
          )}{" "}
          The rest of the batch was checked. Submit this label on its own to see what went wrong
          with it.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {row.fields.map((field) => (
            <FieldCard
              key={field.field_name}
              field={field}
              verdict={
                field.rule_findings[0] ? <RuleVerdict finding={field.rule_findings[0]} /> : null
              }
              aiSuggestion={<AISuggestionBlock suggestion={field.ai_suggestion} />}
            />
          ))}
        </div>
      )}
    </section>
  );
}
