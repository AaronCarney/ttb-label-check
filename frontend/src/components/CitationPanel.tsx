import * as React from "react";
import { cn } from "../lib/cn";

export interface HeldSection {
  key: string;
  heading: string;
  text: string;
  paragraph: string | null;
  source_url: string;
  version_date: string;
  retrieved: string;
}

export interface CitationPanelProps {
  citation: string | null;
  /** The id the citation chips name in `aria-controls`, so the tie between a
   * chip and the column it fills is announced and not only drawn. */
  id?: string;
  className?: string;
}

type State =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "held"; sections: HeldSection[] }
  | { kind: "not-held" }
  | { kind: "failed" };

// The regulation behind whichever citation the reviewer chose, in a column that
// is on the page whether they have chosen one or not.
//
// Reserved rather than summoned, and filled in place: a pop-up or an overlay
// would put the regulation on top of the finding it explains, and comparing the
// two is the whole reason to open it. It is reached from a citation chip, which
// is a button — so keyboard and pointer reach it the same way, and nothing here
// appears on hover.
//
// The text is the regulation's own wording, fetched from the eCFR once and
// committed (`assets/cfr/`, `tools/fetch_cfr.py`). The panel says which issue it
// is showing and when it was retrieved, because a compliance tool quoting a
// regulation without saying which version is asking to be trusted rather than
// checked. See `docs/decisions.md#0046`.
export function CitationPanel({ citation, id, className }: CitationPanelProps): React.JSX.Element {
  const [state, setState] = React.useState<State>({ kind: "idle" });

  React.useEffect(() => {
    if (citation === null) {
      setState({ kind: "idle" });
      return;
    }
    // A reviewer clicking down a column of chips must not be shown the answer
    // to a citation they have moved on from, so a superseded request drops its
    // own result rather than racing the current one into the panel.
    let current = true;
    setState({ kind: "loading" });
    fetch(`/cfr?citation=${encodeURIComponent(citation)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((body: { sections: HeldSection[] }) => {
        if (!current) return;
        setState(
          body.sections.length > 0
            ? { kind: "held", sections: body.sections }
            : { kind: "not-held" },
        );
      })
      .catch(() => {
        if (current) setState({ kind: "failed" });
      });
    return () => {
      current = false;
    };
  }, [citation]);

  return (
    <section
      id={id}
      role="region"
      aria-label="The regulation"
      aria-live="polite"
      className={cn(
        "rounded-lg border border-border bg-background p-4 space-y-3",
        className,
      )}
    >
      <header>
        <h3 className="text-base font-semibold">The regulation</h3>
        {citation && <p className="text-sm text-muted-foreground">{citation}</p>}
      </header>

      {state.kind === "idle" && (
        <p className="text-sm text-muted-foreground">
          Choose a citation on any finding to read the section it rests on.
        </p>
      )}

      {state.kind === "loading" && <p className="text-sm text-muted-foreground">Loading…</p>}

      {state.kind === "not-held" && (
        <p className="text-sm text-muted-foreground">
          This product does not hold the text of that section. The citation is on the finding;
          looking it up is yours to do.
        </p>
      )}

      {state.kind === "failed" && (
        <p className="text-sm text-muted-foreground">
          The regulation could not be loaded. Choose the citation again to retry.
        </p>
      )}

      {state.kind === "held" &&
        state.sections.map((section) => (
          <article key={section.key} className="space-y-2 border-t border-border pt-3 first:border-t-0 first:pt-0">
            <h4 className="text-sm font-semibold">{section.heading}</h4>
            {section.paragraph && (
              <p className="text-xs text-muted-foreground">
                The finding rests on {section.paragraph}, shown here in the whole section.
              </p>
            )}
            <div className="max-h-96 overflow-y-auto whitespace-pre-wrap text-sm leading-relaxed">
              {section.text}
            </div>
            <p className="text-xs text-muted-foreground">
              eCFR issue of {section.version_date}, retrieved {section.retrieved}.
            </p>
          </article>
        ))}
    </section>
  );
}
