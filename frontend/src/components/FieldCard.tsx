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
  className?: string;
}

// Null means no rule ran against this field — the application did not state a
// value for it, or no rule covers it for this beverage. That is not a pass, and
// showing one would tell the reviewer a check succeeded that never happened.
function _fieldDisposition(field: FieldFindingWire): "pass" | "fail" | "needs_review" | null {
  const dispositions = field.rule_findings.map((r) => r.disposition);
  if (dispositions.length === 0) return null;
  if (dispositions.includes("fail")) return "fail";
  if (dispositions.includes("needs_review")) return "needs_review";
  return "pass";
}

// "brand_name" reads as "Brand name" on the card. The accessible name keeps the
// field's own identifier, which is what the tests and the audit trail use.
function _fieldLabel(fieldName: string): string {
  const words = fieldName.replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

// "back" reads as "Back" on the card, matching the caption under the
// photograph itself on the result page. Empty means the reading did not record
// a face, and the card then says nothing rather than pointing at the wrong
// picture.
function _faceLabel(faceTag: string): string {
  return faceTag.charAt(0).toUpperCase() + faceTag.slice(1);
}

// An application declares more than one value a label may carry — a brand, a
// fanciful name, trade names it says are printed on the label — and a rule that
// passes on one of the others leaves a card reading "Expected FABIO SIGNORELLI /
// Found Rossastro / PASS". The verdict is right and the card contradicts it, so
// the card names the value that was matched.
function _matchedValue(field: FieldFindingWire): string {
  const named = field.rule_findings.find((r) => r.matched_value);
  return named ? named.matched_value : "";
}

export function FieldCard({ field, verdict, aiSuggestion, className }: FieldCardProps): React.JSX.Element {
  const fieldDisp = _fieldDisposition(field);
  return (
    <section
      role="region"
      aria-label={`Field: ${field.field_name}`}
      className={cn("rounded-lg border border-border bg-background p-4 space-y-3", className)}
    >
      <header className="flex items-center justify-between gap-3">
        <h3 className="text-base font-semibold">{_fieldLabel(field.field_name)}</h3>
        {fieldDisp === null ? (
          <span className="inline-flex items-center rounded-md border border-border bg-muted px-3 py-1 text-sm font-semibold text-muted-foreground">
            Not checked
          </span>
        ) : (
          <DispositionPill disposition={fieldDisp} />
        )}
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
        {_matchedValue(field) ? (
          <div>
            <dt className="font-medium text-muted-foreground">Matched against</dt>
            <dd className="break-words">{_matchedValue(field)}</dd>
          </div>
        ) : null}
        {field.evidence.face_tag ? (
          <div>
            <dt className="font-medium text-muted-foreground">Read from</dt>
            <dd className="break-words">{_faceLabel(field.evidence.face_tag)}</dd>
          </div>
        ) : null}
      </dl>
      {verdict ?? null}
      {aiSuggestion ?? null}
      <footer className="flex flex-wrap items-center gap-3">
        <ConfidenceIndicator band={field.field_confidence.band} numeric={field.field_confidence.numeric} />
        <div className="flex flex-wrap gap-2">
          {field.rule_findings.map((rf) => (
            <CitationChip key={rf.rule_id} citation={rf.cfr_citation} />
          ))}
        </div>
      </footer>
    </section>
  );
}
