import * as React from "react";
import { createRoot } from "react-dom/client";
import "./tokens/globals.css";
import { BatchItemDetail } from "./components/BatchItemDetail";
import { BatchTable } from "./components/BatchTable";
import { LiveRegion } from "./components/LiveRegion";
import { QueuePosition } from "./components/QueuePosition";
import { useBatchStream } from "./sse/useBatchStream";

function BatchApp({ batchId }: { batchId: string }): React.JSX.Element {
  const { events, error, total, done } = useBatchStream(batchId);
  const latest = events[events.length - 1];
  // Which label the reviewer has opened, held by label_ref rather than by
  // index, so a re-sort of the table does not move the selection onto a
  // different label than the one they opened.
  const [selectedRef, setSelectedRef] = React.useState<string | null>(null);
  const selected = React.useMemo(
    () => events.find((e) => e.label_ref === selectedRef) ?? null,
    [events, selectedRef],
  );
  // Until the worker reports the batch size, the count of results received is
  // the only honest number there is; a denominator taken from that same count
  // would tell the reviewer the batch had finished from the first result on.
  const progress = done
    ? `Finished — ${events.length} of ${total ?? events.length} labels checked`
    : `Checking labels — ${events.length} finished so far`;
  return (
    <main className="mx-auto max-w-5xl space-y-4 p-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold">Batch {batchId}</h2>
          <p className="text-sm text-muted-foreground">{progress}</p>
        </div>
        {latest && total !== null && <QueuePosition current={latest.queue_position} total={total} />}
      </header>
      {error && (
        <p role="alert" className="rounded-md border border-destructive bg-destructive/10 p-3 text-sm text-[hsl(var(--uswds-error-dark))]">
          {error}
        </p>
      )}
      <BatchTable rows={events} onSelect={setSelectedRef} selectedRef={selectedRef} />
      <BatchItemDetail row={selected} />
      <LiveRegion message={latest ? `Label ${latest.label_ref}: ${latest.disposition}` : ""} />
    </main>
  );
}

// Exported so tests can call it explicitly per-test (Vitest caches modules
// — see corresponding NOTE in batch.test.tsx). Production uses the
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
      <BatchApp batchId={batchId} />
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
