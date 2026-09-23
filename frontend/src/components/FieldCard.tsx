import * as React from "react";
import { cn } from "../lib/cn";
import type { Verdict } from "../lib/corrections";
import type { FieldFindingWire, OverrideEntry } from "../types/envelopes";
import { ConfidenceIndicator } from "./ConfidenceIndicator";
import { CitationChip } from "./CitationChip";
import { DispositionPill } from "./DispositionPill";

export interface FieldCardProps {
  field: FieldFindingWire;
  verdict?: React.ReactNode;
  aiSuggestion?: React.ReactNode;
  /** Opens the citation in the regulation panel. Absent leaves the chips as
   * text, which is what a surface with no panel beside it must do. */
  onOpenCitation?: (citation: string) => void;
  /** The citation the panel is showing, so its chip reads as the open one. */
  openCitation?: string | null;
  /** The id of the panel the chips fill. */
  citationPanelId?: string;
  /** The reviewer's latest correction to this field, which is then its result. */
  correction?: OverrideEntry | null;
  /** Records a correction to this field and says whether it was saved; the
   * choices stay open when it was not. Absent, the card offers none. */
  onCorrect?: (verdict: Verdict) => Promise<boolean>;
  className?: string;
}

const _VERDICT_WORDS: Record<Verdict, string> = {
  pass: "Pass",
  fail: "Fail",
  needs_review: "Needs review",
};

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

export function FieldCard({
  field,
  verdict,
  aiSuggestion,
  onOpenCitation,
  openCitation,
  citationPanelId,
  correction = null,
  onCorrect,
  className,
}: FieldCardProps): React.JSX.Element {
  const checked = _fieldDisposition(field);
  // A result stands until the reviewer says it is wrong, so the card needs no
  // action when the check is right. When it is not, the reviewer's word is the
  // field's result, and the check's own is still shown beside it.
  const fieldDisp = correction ? correction.applied_disposition : checked;
  const [correcting, setCorrecting] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const choicesId = React.useId();
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
      {correction && checked !== null && (
        <p className="text-sm text-muted-foreground">
          Corrected by the reviewer. The check reported {_VERDICT_WORDS[checked]}.
        </p>
      )}
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
            <CitationChip
              key={rf.rule_id}
              citation={rf.cfr_citation}
              onOpen={onOpenCitation}
              selected={openCitation === rf.cfr_citation}
              controls={citationPanelId}
            />
          ))}
        </div>
        {onCorrect && fieldDisp !== null && (
          // Offered on every checked field and never pre-selected: the
          // reviewer names what the field should be, and no choice is made
          // for them (docs/decisions.md#0064).
          <button
            type="button"
            aria-expanded={correcting}
            aria-controls={choicesId}
            onClick={() => setCorrecting((open) => !open)}
            className="ml-auto rounded-md border border-border bg-background px-3 py-1 text-sm text-foreground hover:bg-muted"
          >
            This result is wrong
          </button>
        )}
      </footer>
      {onCorrect && fieldDisp !== null && correcting && (
        <div
          id={choicesId}
          role="group"
          aria-label={`Correct the result for ${_fieldLabel(field.field_name)}`}
          className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-muted p-2 text-sm"
        >
          <span>It should be:</span>
          {(Object.keys(_VERDICT_WORDS) as Verdict[])
            .filter((v) => v !== fieldDisp)
            .map((v) => (
              <button
                key={v}
                type="button"
                disabled={saving}
                onClick={async () => {
                  setSaving(true);
                  try {
                    if (await onCorrect(v)) setCorrecting(false);
                  } finally {
                    setSaving(false);
                  }
                }}
                className="rounded-md border border-border bg-background px-3 py-1 text-foreground hover:bg-background/80 disabled:opacity-50"
              >
                {_VERDICT_WORDS[v]}
              </button>
            ))}
          <button
            type="button"
            onClick={() => setCorrecting(false)}
            className="rounded-md px-3 py-1 text-foreground underline"
          >
            Cancel
          </button>
        </div>
      )}
    </section>
  );
}
