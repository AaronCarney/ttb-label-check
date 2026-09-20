import * as React from "react";
import { cn } from "../lib/cn";
import type { BatchSSEEvent } from "../types/sse";
import { AISuggestionBlock } from "./AISuggestionBlock";
import { ConfidenceIndicator } from "./ConfidenceIndicator";
import { DispositionPill } from "./DispositionPill";
import { FieldCard } from "./FieldCard";
import { IncompleteCheckCard } from "./IncompleteCheckCard";
import { ProcessingTime } from "./ProcessingTime";
import { RuleVerdict } from "./RuleVerdict";
import { decidingFinding } from "../lib/decidingFinding";
import { engineFailureCode, wasStoppedEarly } from "../lib/incompleteCheck";

export interface BatchItemDetailProps {
  /** The opened row, or null when the reviewer has not opened one yet. */
  row: BatchSSEEvent | null;
  className?: string;
}

// The stream already carries every result in full, so opening a row is a
// render and not a fetch: the batch page holds the same envelope the
// single-label page is given, and builds it out of the same cards so the two
// surfaces cannot report the same label differently (docs/PRD.md FR-12).

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

  // An item the app could not finish checking carries the code naming why in
  // its audit trail, and nowhere else — an engine failure happens before or
  // instead of a rule, so it has no field to hang off (docs/PRD.md FR-13,
  // docs/decisions.md#0020). Two ways a check can be incomplete: it came back
  // with nothing, or the evaluation guard stopped it partway and it came back
  // with what it had.
  const trace = row.audit_trail.per_rule_trace;
  const incomplete = row.fields.length === 0 || wasStoppedEarly(trace);

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
          <ProcessingTime metrics={row.metrics} stoppedEarly={wasStoppedEarly(trace)} />
        </div>
      </header>

      {incomplete && (
        <IncompleteCheckCard
          reasonCode={engineFailureCode(trace)}
          fieldCount={row.fields.length}
        />
      )}

      {row.fields.length > 0 && (
        <div className="grid grid-cols-1 gap-4">
          {row.fields.map((field) => (
            <FieldCard
              key={field.field_name}
              field={field}
              verdict={(() => {
                const deciding = decidingFinding(field);
                return deciding ? <RuleVerdict finding={deciding} /> : null;
              })()}
              aiSuggestion={<AISuggestionBlock suggestion={field.ai_suggestion} />}
            />
          ))}
        </div>
      )}
    </section>
  );
}
