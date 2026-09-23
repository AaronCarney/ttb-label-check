import * as React from "react";
import { cn } from "../lib/cn";
import type { DispositionEnvelope, Lean, OverrideEntry } from "../types/envelopes";
import { AISuggestionBlock } from "./AISuggestionBlock";
import { ConfidenceIndicator } from "./ConfidenceIndicator";
import { DispositionPill } from "./DispositionPill";
import { NeedsReviewFlag } from "./NeedsReviewFlag";
import { FieldCard } from "./FieldCard";
import { IncompleteCheckCard } from "./IncompleteCheckCard";
import { LiveRegion } from "./LiveRegion";
import { NeedsBetterPhotoCard } from "./NeedsBetterPhotoCard";
import { OverrideDrawer } from "./OverrideDrawer";
import { ProcessingTime } from "./ProcessingTime";
import { RawJSONDrawer } from "./RawJSONDrawer";
import { RuleVerdict } from "./RuleVerdict";
import { Toast } from "./Toast";
import {
  CONFIRMATION_CODES,
  CORRECTION_CODES,
  fieldCorrection,
  fieldsToConfirm,
  isConfirmation,
  preFilled,
  withOverride,
  type OverrideApplied,
  type Verdict,
} from "../lib/corrections";
import { decidingFinding } from "../lib/decidingFinding";
import { engineFailureCode, wasStoppedEarly } from "../lib/incompleteCheck";
import { needsBetterPhotoFrom } from "../lib/needsBetterPhoto";
import { useKeyboardShortcuts } from "../hooks/useKeyboardShortcuts";
import type { ReasonCodeEntry } from "./ReasonCodePicker";

// A minimal hard-coded reason-code catalog mirroring rules/reason_codes.yaml.
// Each entry pins the applied_disposition the override request records when
// the reviewer picks this code, taken from the registry's `severity` field
// (reject → fail, warn → needs_review). The disposition is pinned per code
// rather than derived from the code-name prefix, which produced wrong audit
// entries because the catalog uses BIN.SUB.SPECIFIC, not FAIL./PASS.
//
// ORDER INVARIANT — the three-keystroke override path:
// for each reason code a reviewer reaches by prefix, this array's FIRST entry
// that shares the same starting letter MUST be that code. The picker
// auto-selects only when the filter narrows to one entry; otherwise ENTER
// picks `filtered[highlight]` and `highlight` resets to 0 on a filter change.
// Together those mean `O → <letter> → ENTER` lands on the first code with
// that prefix in this array.
//
// Verified for WARNING.STYLE.HEADING_NOT_BOLD_CAPS: 'w' → highlight 0 among
// the three W-prefixed codes, so that entry must stay first among them.
//
// Reorder this array only after re-checking that the keyboard test still
// passes; the picker's own unit tests do not assert this invariant. See also
// the `tests/manual/a11y-smoke.md` step 7 narration.
export const REASON_CODES: ReasonCodeEntry[] = [
  { code: "BRAND.NAME.MISMATCH", description: "Brand mismatch", disposition: "fail" },
  { code: "BRAND.NAME.NEEDS_REVIEW", description: "Brand needs review", disposition: "needs_review" },
  { code: "WARNING.STYLE.HEADING_NOT_BOLD_CAPS", description: "Heading not bold caps", disposition: "fail" },
  { code: "WARNING.LEGIBILITY.LOW_RESOLUTION", description: "Low resolution", disposition: "needs_review" },
  { code: "WARNING.LEGIBILITY.GLARE", description: "Glare", disposition: "needs_review" },
  { code: "ALCOHOL_CONTENT.TOLERANCE.OUT_OF_BAND", description: "ABV out of band", disposition: "fail" },
  { code: "CLASS_TYPE.SOI.NO_MATCH", description: "Class/Type SOI mismatch", disposition: "fail" },
];

// "1 field to confirm", "3 fields to confirm". Nothing when no field card is
// waiting, as when only a stopped check keeps the label with a reviewer.
function _toConfirmWords(n: number): string | undefined {
  if (n === 0) return undefined;
  return `${n} ${n === 1 ? "field" : "fields"} to confirm`;
}

function dispositionFor(code: string): "fail" | "needs_review" {
  const entry = REASON_CODES.find((e) => e.code === code);
  return entry?.disposition ?? "needs_review";
}

/** One photograph of the checked label, as the server says it holds it. */
export interface LabelFace {
  tag: string;
  caption: string;
  url: string;
}

export interface LabelResultProps {
  /** The label being read now, or null before the first result arrives. */
  envelope: DispositionEnvelope | null;
  /** True while the override control should be offered. */
  overridable?: boolean;
  /** Told of each override the endpoint records, so whatever holds the
   * envelope (the batch table's rows) shows the corrected result too. */
  onOverrideApplied?: (evaluationId: string, applied: OverrideApplied) => void;
  /** Opens a finding's citation in the regulation panel beside this result. */
  onOpenCitation?: (citation: string) => void;
  /** The citation the panel is showing. */
  openCitation?: string | null;
  /** The id of that panel. */
  citationPanelId?: string;
  className?: string;
}

// The stream carries every result in full, so opening a label is a render and
// not a fetch. This is the whole of what the product reports about one label —
// its photographs, its verdict, every field card, and the override — and it is
// the only such component, so no two surfaces can describe one envelope
// differently (docs/PRD.md FR-12).

export function LabelResult({
  envelope: received,
  overridable = true,
  onOverrideApplied,
  onOpenCitation,
  openCitation,
  citationPanelId,
  className,
}: LabelResultProps): React.JSX.Element {
  const headingRef = React.useRef<HTMLHeadingElement>(null);
  const [faces, setFaces] = React.useState<LabelFace[]>([]);
  const [overrideOpen, setOverrideOpen] = React.useState(false);
  const [announcement, setAnnouncement] = React.useState("");
  const [toast, setToast] = React.useState<{ kind: "error" | "success"; message: string } | null>(null);
  const evaluationId = received?.evaluation_id ?? null;
  // Overrides recorded from this page, kept here as well as handed up, so the
  // page shows its own correction whether or not its holder passes it back.
  // Applying one the envelope already carries changes nothing.
  const [applied, setApplied] = React.useState<{ evaluationId: string; entries: OverrideApplied[] }>({
    evaluationId: "",
    entries: [],
  });
  const envelope = React.useMemo(() => {
    if (received === null || applied.evaluationId !== received.evaluation_id) return received;
    return applied.entries.reduce(withOverride, received);
  }, [received, applied]);

  // Records one override and reports whether it was saved. A refusal is shown
  // in the reviewer's words, from the endpoint's own detail.
  const postOverride = React.useCallback(
    async (body: {
      field_name: string | null;
      applied_disposition: Verdict;
      reason_code: string;
      justification_text: string | null;
    }): Promise<boolean> => {
      if (evaluationId === null) return false;
      try {
        const res = await fetch(`/labels/${encodeURIComponent(evaluationId)}/overrides`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!res.ok) {
          const errBody = await res.json().catch(() => ({ detail: "Override request failed" }));
          const detail = Array.isArray(errBody.detail)
            ? errBody.detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join("; ")
            : (errBody.detail ?? "Override request failed");
          setToast({ kind: "error", message: detail });
          return false;
        }
        const {
          label_disposition: labelDisposition,
          label_lean: labelLean,
          ...entry
        } = (await res.json()) as OverrideEntry & { label_disposition?: Verdict; label_lean?: Lean };
        const done: OverrideApplied = { entry, labelDisposition, labelLean };
        setApplied((prev) => ({
          evaluationId,
          entries: prev.evaluationId === evaluationId ? [...prev.entries, done] : [done],
        }));
        onOverrideApplied?.(evaluationId, done);
        return true;
      } catch {
        setToast({ kind: "error", message: "Network error — override not saved" });
        return false;
      }
    },
    [evaluationId, onOverrideApplied],
  );

  // `O` opens the override, Escape closes it. Registered here rather than on
  // the island because the drawer's open state belongs to the label on show.
  useKeyboardShortcuts({
    onOverride: () => {
      if (overridable && envelope !== null) setOverrideOpen(true);
    },
    onEscape: () => setOverrideOpen(false),
  });

  // Opening a label moves focus into the panel. A reviewer who pressed Enter
  // on a table row otherwise stays in the table, with what they just opened
  // somewhere below them and nothing saying it arrived.
  React.useEffect(() => {
    if (evaluationId !== null) headingRef.current?.focus();
  }, [evaluationId]);

  // Which photographs to show is asked for rather than assumed. Rendering an
  // <img> per face the label might have and letting the ones that are not
  // there fail puts broken pictures on the page of a product whose job is to
  // be trusted.
  React.useEffect(() => {
    if (evaluationId === null) {
      setFaces([]);
      return;
    }
    let live = true;
    setFaces([]);
    fetch(`/labels/${encodeURIComponent(evaluationId)}/faces`)
      .then((res) => (res.ok ? res.json() : { faces: [] }))
      .then((body: { faces?: LabelFace[] }) => {
        if (live) setFaces(body.faces ?? []);
      })
      .catch(() => {
        // The photographs are context, not the verdict. A result page that
        // shows the findings and no pictures is still a usable answer.
        if (live) setFaces([]);
      });
    return () => {
      live = false;
    };
  }, [evaluationId]);

  if (envelope === null) {
    return (
      <p
        className={cn(
          "rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground",
          className,
        )}
      >
        No result yet. The first label to finish opens here.
      </p>
    );
  }

  const needsBetterPhoto = needsBetterPhotoFrom(envelope);
  // A check that came back with no fields, or one the evaluation guard stopped
  // partway. An engine failure happens before or instead of a rule, so it has
  // no field to hang off and the code naming it is in the audit trail and
  // nowhere else (docs/PRD.md FR-13, docs/decisions.md#0020). Without this a
  // check that produced nothing rendered a page with no cards on it and
  // nothing saying why — a blank result rather than an error.
  //
  // The image-quality gate gets its own card just below, which says what to
  // ask the applicant for, so it is not doubled up here.
  const trace = envelope.audit_trail.per_rule_trace;
  const incomplete =
    needsBetterPhoto === null && (envelope.fields.length === 0 || wasStoppedEarly(trace));

  return (
    <section
      role="region"
      aria-label={`Check results for ${envelope.label_ref}`}
      className={cn("space-y-4", className)}
    >
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3
            ref={headingRef}
            tabIndex={-1}
            className="text-lg font-semibold focus-visible:[outline:3px_solid_hsl(var(--ring))]"
          >
            {envelope.label_ref}
          </h3>
          <p className="break-words font-mono text-xs text-muted-foreground">{envelope.evaluation_id}</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {envelope.disposition === "needs_review" && (
            <NeedsReviewFlag detail={_toConfirmWords(fieldsToConfirm(envelope))} />
          )}
          <DispositionPill disposition={preFilled(envelope.disposition, envelope.lean)} />
          {envelope.audit_trail.overrides.length > 0 && (
            // The result on show is no longer only the check's, and the
            // reviewer who opens this label later needs to know that.
            <span className="text-sm text-muted-foreground">
              {envelope.audit_trail.overrides.every(isConfirmation)
                ? "Confirmed by the reviewer"
                : "Corrected by the reviewer"}
            </span>
          )}
          <ConfidenceIndicator
            band={envelope.disposition_confidence.band}
            numeric={envelope.disposition_confidence.numeric}
          />
          <ProcessingTime metrics={envelope.metrics} stoppedEarly={wasStoppedEarly(trace)} />
          <RawJSONDrawer
            enabled={typeof document !== "undefined" && document.body.dataset.devMode === "1"}
            payload={envelope}
          />
        </div>
      </header>

      {faces.length > 0 && (
        // Every face checked, not just the front. A label's mandatory elements
        // are spread across its panels — the government warning is usually on
        // the back — so a reviewer checking a finding has to be able to look at
        // the photograph it was read from.
        <section className="label-preview-set" aria-label="Photographs of this label">
          {faces.map((face) => (
            <figure className="label-preview" data-face={face.tag} key={face.tag}>
              <img src={face.url} alt={`The ${face.caption.toLowerCase()} of the label being reviewed`} />
              <figcaption>
                {faces.length > 1 ? face.caption : "Source label image"} — what the extractor saw.
              </figcaption>
            </figure>
          ))}
        </section>
      )}

      {needsBetterPhoto && (
        <NeedsBetterPhotoCard
          reasonCode={needsBetterPhoto.reasonCode}
          applicantMessage={needsBetterPhoto.applicantMessage}
        />
      )}

      {incomplete && (
        <IncompleteCheckCard reasonCode={engineFailureCode(trace)} fieldCount={envelope.fields.length} />
      )}

      {envelope.fields.length > 0 && (
        <div className="grid grid-cols-1 gap-4">
          {envelope.fields.map((field) => (
            <FieldCard
              key={field.field_name}
              field={field}
              verdict={(() => {
                const deciding = decidingFinding(field);
                return deciding ? <RuleVerdict finding={deciding} /> : null;
              })()}
              aiSuggestion={<AISuggestionBlock suggestion={field.ai_suggestion} />}
              correction={fieldCorrection(envelope, field.field_name)}
              onCorrect={
                overridable
                  ? async (verdict) => {
                      const saved = await postOverride({
                        field_name: field.field_name,
                        applied_disposition: verdict,
                        reason_code: CORRECTION_CODES[verdict],
                        justification_text: null,
                      });
                      if (saved) setAnnouncement(`Correction saved: ${field.field_name} is now ${verdict.replace("_", " ")}`);
                      return saved;
                    }
                  : undefined
              }
              onConfirm={
                overridable
                  ? async (answer) => {
                      const saved = await postOverride({
                        field_name: field.field_name,
                        applied_disposition: answer,
                        reason_code: CONFIRMATION_CODES[answer],
                        justification_text: null,
                      });
                      if (saved) setAnnouncement(`Confirmed: ${field.field_name} is ${answer}`);
                      return saved;
                    }
                  : undefined
              }
              onOpenCitation={onOpenCitation}
              openCitation={openCitation}
              citationPanelId={citationPanelId}
            />
          ))}
        </div>
      )}

      {overridable && (
        <OverrideDrawer
          open={overrideOpen}
          onOpenChange={setOverrideOpen}
          codes={REASON_CODES}
          onSubmit={async (p) => {
            const saved = await postOverride({
              field_name: null,
              applied_disposition: dispositionFor(p.reasonCode),
              reason_code: p.reasonCode,
              justification_text: p.justification || null,
            });
            if (saved) {
              setAnnouncement(`Override saved: ${p.reasonCode}`);
              setOverrideOpen(false);
            }
          }}
        />
      )}
      <LiveRegion message={announcement} />
      {toast && <Toast message={toast.message} onDismiss={() => setToast(null)} />}
    </section>
  );
}
