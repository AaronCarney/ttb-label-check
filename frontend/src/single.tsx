import * as React from "react";
import { createRoot } from "react-dom/client";
import "./tokens/globals.css";
import { AISuggestionBlock } from "./components/AISuggestionBlock";
import { ConfidenceIndicator } from "./components/ConfidenceIndicator";
import { DispositionPill } from "./components/DispositionPill";
import { FieldCard } from "./components/FieldCard";
import { IncompleteCheckCard } from "./components/IncompleteCheckCard";
import { LiveRegion } from "./components/LiveRegion";
import { NeedsBetterPhotoCard } from "./components/NeedsBetterPhotoCard";
import { OverrideDrawer } from "./components/OverrideDrawer";
import { ProcessingTime } from "./components/ProcessingTime";
import { RawJSONDrawer } from "./components/RawJSONDrawer";
import { RuleVerdict } from "./components/RuleVerdict";
import { Toast } from "./components/Toast";
import { useKeyboardShortcuts } from "./hooks/useKeyboardShortcuts";
import { engineFailureCode, wasStoppedEarly } from "./lib/incompleteCheck";
import { needsBetterPhotoFrom } from "./lib/needsBetterPhoto";
import type { DispositionEnvelope } from "./types/envelopes";
import type { ReasonCodeEntry } from "./components/ReasonCodePicker";

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
const _REASON_CODES: ReasonCodeEntry[] = [
  { code: "BRAND.NAME.MISMATCH", description: "Brand mismatch", disposition: "fail" },
  { code: "BRAND.NAME.NEEDS_REVIEW", description: "Brand needs review", disposition: "needs_review" },
  { code: "WARNING.STYLE.HEADING_NOT_BOLD_CAPS", description: "Heading not bold caps", disposition: "fail" },
  { code: "WARNING.LEGIBILITY.LOW_RESOLUTION", description: "Low resolution", disposition: "needs_review" },
  { code: "WARNING.LEGIBILITY.GLARE", description: "Glare", disposition: "needs_review" },
  { code: "ALCOHOL_CONTENT.TOLERANCE.OUT_OF_BAND", description: "ABV out of band", disposition: "fail" },
  { code: "CLASS_TYPE.SOI.NO_MATCH", description: "Class/Type SOI mismatch", disposition: "fail" },
];

function _disposition_for(code: string): "fail" | "needs_review" {
  const entry = _REASON_CODES.find((e) => e.code === code);
  return entry?.disposition ?? "needs_review";
}

export function SingleApp({ envelope }: { envelope: DispositionEnvelope | null }): React.JSX.Element {
  const [overrideOpen, setOverrideOpen] = React.useState(false);
  const [announcement, setAnnouncement] = React.useState("");
  const [toast, setToast] = React.useState<{kind: "error" | "success"; message: string} | null>(null);
  useKeyboardShortcuts({
    onOverride: () => setOverrideOpen(true),
    onEscape: () => setOverrideOpen(false),
  });

  if (!envelope) {
    return (
      <div className="p-4">
        <p>No label checked yet. Upload a label image above, fill in the application it was filed
        with, and choose Evaluate. The results appear here.</p>
      </div>
    );
  }

  const needsBetterPhoto = needsBetterPhotoFrom(envelope);
  // A check that came back with no fields, or one the evaluation guard stopped
  // partway. Without this the page mapped `envelope.fields` with no empty-state
  // branch, so a check that produced nothing rendered a results page with no
  // cards on it and nothing saying why — a blank result rather than an error,
  // on the path a reviewer actually takes. The batch panel has said this since
  // it was written; both now say it with the same component, so the two
  // surfaces cannot describe one envelope differently (docs/PRD.md FR-12).
  //
  // The image-quality gate gets its own card just below, which says what to ask
  // the applicant for, so it is not doubled up here.
  const trace = envelope.audit_trail?.per_rule_trace ?? [];
  const incomplete =
    needsBetterPhoto === null && (envelope.fields.length === 0 || wasStoppedEarly(trace));

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">{envelope.label_ref}</h2>
          <p className="break-words font-mono text-xs text-muted-foreground">{envelope.evaluation_id}</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <DispositionPill disposition={envelope.disposition} />
          <ConfidenceIndicator
            band={envelope.disposition_confidence.band}
            numeric={envelope.disposition_confidence.numeric}
          />
          <ProcessingTime metrics={envelope.metrics} stoppedEarly={wasStoppedEarly(trace)} />
          <RawJSONDrawer enabled={document.body.dataset.devMode === "1"} payload={envelope} />
        </div>
      </header>

      {needsBetterPhoto && (
        <NeedsBetterPhotoCard
          reasonCode={needsBetterPhoto.reasonCode}
          applicantMessage={needsBetterPhoto.applicantMessage}
        />
      )}

      {incomplete && (
        <IncompleteCheckCard
          reasonCode={engineFailureCode(trace)}
          fieldCount={envelope.fields.length}
        />
      )}

      <div className="grid grid-cols-1 gap-4">
        {envelope.fields.map((field) => (
          <FieldCard
            key={field.field_name}
            field={field}
            verdict={field.rule_findings[0] ? <RuleVerdict finding={field.rule_findings[0]} /> : null}
            aiSuggestion={<AISuggestionBlock suggestion={field.ai_suggestion} />}
          />
        ))}
      </div>

      <OverrideDrawer
        open={overrideOpen}
        onOpenChange={setOverrideOpen}
        codes={_REASON_CODES}
        // The single-label flow reaches the same endpoint a batch does. Its
        // result is kept by `app/api/ui/results.py`, so the override has a
        // record to amend rather than answering 404.
        onSubmit={async (p) => {
          const body = {
            field_name: null,
            applied_disposition: _disposition_for(p.reasonCode),
            reason_code: p.reasonCode,
            justification_text: p.justification || null,
          };
          try {
            const res = await fetch(
              `/labels/${encodeURIComponent(envelope.evaluation_id)}/overrides`,
              { method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body) },
            );
            if (!res.ok) {
              const errBody = await res.json().catch(() => ({detail: "Override request failed"}));
              const detail = Array.isArray(errBody.detail)
                ? errBody.detail.map((d: {msg?: string}) => d.msg).filter(Boolean).join("; ")
                : (errBody.detail ?? "Override request failed");
              setToast({kind: "error", message: detail});
              return;
            }
            setAnnouncement(`Override saved: ${p.reasonCode}`);
            setOverrideOpen(false);
          } catch {
            setToast({kind: "error", message: "Network error — override not saved"});
          }
        }}
      />
      <LiveRegion message={announcement} />
      {toast && (
        <Toast
          message={toast.message}
          onDismiss={() => setToast(null)}
        />
      )}
    </div>
  );
}

function _readEnvelope(): DispositionEnvelope | null {
  const tag = document.getElementById("envelope");
  if (!tag) return null;
  try {
    return JSON.parse(tag.textContent ?? "null") as DispositionEnvelope | null;
  } catch {
    return null;
  }
}

// Exported so the unit test can call it explicitly per-test (Vitest caches
// modules — relying on the auto-mount side effect would render only on the
// first `it` block). Production code path uses the auto-mount below.
//
// Idempotent: a second call against the same #root no-ops, preventing the
// React-DOM "createRoot on a container that has already been passed" warning
// when both the auto-mount block and a test's explicit mount() hit the same
// node within one module-load.
export function mount(): void {
  const root = document.getElementById("root");
  if (!root) return;
  if (root.dataset.mounted === "true") return;
  const reactRoot = createRoot(root);
  const render = (envelope: DispositionEnvelope | null): void => {
    reactRoot.render(
      <React.StrictMode>
        <SingleApp envelope={envelope} />
      </React.StrictMode>,
    );
  };
  const initial = _readEnvelope();
  render(initial);
  root.setAttribute("data-mounted", "true");
  if (initial === null) {
    _waitForEnvelope((envelope) => render(envelope));
  }
}

// Handles a race where the envelope <script> tag is injected after the island
// module evaluates (e.g. Playwright's page.add_init_script with a
// DOMContentLoaded listener, future SSE/router-driven hydration). Watches the
// document for a <script id="envelope"> addition and re-renders. Self-cleans
// after 5s to avoid leaking observers in production.
//
// Disconnects any prior active observer first — defensive against double-mount
// in development (HMR) or test re-renders.
let _activeEnvelopeObserver: MutationObserver | null = null;
function _waitForEnvelope(onArrival: (envelope: DispositionEnvelope) => void): void {
  if (typeof MutationObserver === "undefined") return;
  if (_activeEnvelopeObserver) {
    _activeEnvelopeObserver.disconnect();
    _activeEnvelopeObserver = null;
  }
  let settled = false;
  const observer = new MutationObserver(() => {
    if (settled) return;
    const envelope = _readEnvelope();
    if (envelope !== null) {
      settled = true;
      observer.disconnect();
      if (_activeEnvelopeObserver === observer) _activeEnvelopeObserver = null;
      onArrival(envelope);
    }
  });
  _activeEnvelopeObserver = observer;
  observer.observe(document.documentElement, { childList: true, subtree: true });
  setTimeout(() => {
    if (!settled) {
      settled = true;
      observer.disconnect();
      if (_activeEnvelopeObserver === observer) _activeEnvelopeObserver = null;
    }
  }, 5000);
}

// Auto-mount in browsers; Vitest sets MODE='test' and tests call mount() per-it.
if (import.meta.env.MODE !== "test" && typeof document !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
}
