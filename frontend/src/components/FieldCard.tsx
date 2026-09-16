import * as React from "react";
import { cn } from "../lib/cn";
import type { FieldFindingWire } from "../types/envelopes";
import { ConfidenceIndicator } from "./ConfidenceIndicator";
import { CitationChip } from "./CitationChip";
import { DispositionPill } from "./DispositionPill";

export interface FieldCardProps {
  field: FieldFindingWire;
  verdict?: React.ReactNode;
  aiSuggestion?: React.ReactNode;
  onCitationOpen?: (citation: string) => void;
  className?: string;
}

function _fieldDisposition(field: FieldFindingWire): "pass" | "fail" | "needs_review" {
  const dispositions = field.rule_findings.map((r) => r.disposition);
  if (dispositions.includes("fail")) return "fail";
  if (dispositions.includes("needs_review")) return "needs_review";
  return "pass";
}

export function FieldCard({ field, verdict, aiSuggestion, onCitationOpen, className }: FieldCardProps): React.JSX.Element {
  const fieldDisp = _fieldDisposition(field);
  return (
    <section
      role="region"
      aria-label={`Field: ${field.field_name}`}
      className={cn("rounded-lg border border-border bg-background p-4 space-y-3", className)}
    >
      <header className="flex items-center justify-between gap-3">
        <h3 className="text-base font-semibold">{field.field_name.replace(/_/g, " ")}</h3>
        <DispositionPill disposition={fieldDisp} />
      </header>
      <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
        <div>
          <dt className="font-medium text-muted-foreground">Extracted</dt>
          <dd className="break-words">{field.extracted_value || <em>(empty)</em>}</dd>
        </div>
        <div>
          <dt className="font-medium text-muted-foreground">Expected</dt>
          <dd className="break-words">{field.expected_value || <em>(empty)</em>}</dd>
        </div>
      </dl>
      {verdict ?? null}
      {aiSuggestion ?? null}
      <footer className="flex flex-wrap items-center gap-3">
        <ConfidenceIndicator band={field.field_confidence.band} numeric={field.field_confidence.numeric} />
        <div className="flex flex-wrap gap-2">
          {field.rule_findings.map((rf) => (
            <CitationChip
              key={rf.rule_id}
              citation={rf.cfr_citation}
              onOpen={() => onCitationOpen?.(rf.cfr_citation)}
            />
          ))}
        </div>
      </footer>
    </section>
  );
}
