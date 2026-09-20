import * as React from "react";
import { createRoot } from "react-dom/client";
import "./tokens/globals.css";
import { BatchTable } from "./components/BatchTable";
import { LabelResult } from "./components/LabelResult";
import { LiveRegion } from "./components/LiveRegion";
import { QueuePosition } from "./components/QueuePosition";
import { useBatchStream } from "./sse/useBatchStream";

// One graded label per moment, and the whole submission processed behind it.
// The engine has always worked that way — the worker broadcasts each result as
// it lands and deliberately does not hold the first one back — and this is the
// surface that finally shows it: the first result to arrive opens itself, and
// the list of what else is running appears only once there is something else.
export function ResultsApp({ batchId }: { batchId: string }): React.JSX.Element {
  const { events, error, total, done } = useBatchStream(batchId);
  const latest = events[events.length - 1];

  // Which label the reviewer has open, held by label_ref rather than by index,
  // so a re-sort of the table does not move the selection onto a different
  // label than the one they opened.
  const [selectedRef, setSelectedRef] = React.useState<string | null>(null);
  React.useEffect(() => {
    // The first result opens itself. Waiting for a click would mean a reviewer
    // who uploaded one label watching a table of one row and having to ask for
    // the answer they submitted the label to get.
    const first = events[0];
    if (selectedRef === null && first !== undefined) setSelectedRef(first.label_ref);
  }, [events, selectedRef]);
  const selected = React.useMemo(
    () => events.find((e) => e.label_ref === selectedRef) ?? null,
    [events, selectedRef],
  );

  // Until the worker reports the submission's size, the count of results
  // received is the only honest number there is; a denominator taken from that
  // same count would say the check had finished from the first result on.
  const checking = !done;
  const progress = done
    ? `Finished — ${events.length} of ${total ?? events.length} labels checked`
    : events.length === 0
      ? "Checking. The first result appears as soon as it is ready…"
      : `${events.length} checked so far, and still going`;

  // The list of everything in the submission is worth the room only when there
  // is more than one thing in it. One label shows its result and nothing else.
  const several = events.length > 1 || (total ?? 0) > 1;

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">{several ? "Results" : "Result"}</h2>
          <p className="text-sm text-muted-foreground">{progress}</p>
        </div>
        {several && latest && total !== null && (
          <QueuePosition current={latest.queue_position} total={total} />
        )}
      </header>
      {error && (
        <p
          role="alert"
          className="rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-[hsl(var(--uswds-error-dark))]"
        >
          {error}
        </p>
      )}
      {several && <BatchTable rows={events} onSelect={setSelectedRef} selectedRef={selectedRef} />}
      <LabelResult envelope={selected} />
      <LiveRegion
        message={
          latest ? `Label ${latest.label_ref}: ${latest.disposition}` : checking ? "Checking" : ""
        }
      />
    </div>
  );
}

// Exported so tests can call it explicitly per-test (Vitest caches modules
// — see the corresponding note in app.test.tsx). Production uses the
// auto-mount block below.
//
// Idempotent: a second call against the same #root no-ops, preventing the
// React-DOM "createRoot on a container that has already been passed" warning.
export function mount(): void {
  const root = document.getElementById("root");
  if (!root) return;
  if (root.dataset.mounted === "true") return;
  const batchId = root.getAttribute("data-batch-id") ?? "";
  createRoot(root).render(
    <React.StrictMode>
      <ResultsApp batchId={batchId} />
    </React.StrictMode>,
  );
  root.setAttribute("data-mounted", "true");
}

// Auto-mount in browsers; Vitest sets MODE='test' and tests call mount() per-it.
if (import.meta.env.MODE !== "test" && typeof document !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
}
