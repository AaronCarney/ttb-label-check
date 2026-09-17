import * as React from "react";
import type { DispositionEnvelope } from "../types/envelopes";
import type { BatchSSEEvent } from "../types/sse";

export interface BatchStreamState {
  events: BatchSSEEvent[];
  error: string | null;
  // How many labels the batch holds. The worker reports it on stream-end and
  // not before, so it is null while the batch is running. A batch whose
  // denominator is guessed from the results received so far always reads as
  // finished, which is why nothing here invents one.
  total: number | null;
  // True once the worker has said the batch is over.
  done: boolean;
}

type _Action =
  | { type: "push"; event: BatchSSEEvent }
  | { type: "error"; message: string }
  | { type: "end"; total: number | null }
  | { type: "reset" };

function _reducer(state: BatchStreamState, action: _Action): BatchStreamState {
  switch (action.type) {
    case "push":
      if (state.events.some((e) => e.label_ref === action.event.label_ref)) {
        return state;
      }
      return { ...state, events: [...state.events, action.event] };
    case "error":
      return { ...state, error: action.message };
    case "end":
      return { ...state, total: action.total, done: true };
    case "reset":
      return { events: [], error: null, total: null, done: false };
  }
}

// The batch stream carries four named SSE events: label-result,
// anomaly-advisory and stream-end from the worker, and override-applied from
// the override endpoint. This hook consumes only label-result and stream-end;
// the other two are not surfaced in the interface yet.
export function useBatchStream(batchId: string): BatchStreamState {
  const [state, dispatch] = React.useReducer(_reducer, { events: [], error: null, total: null, done: false });

  React.useEffect(() => {
    if (!batchId) return;
    const url = `/batches/${encodeURIComponent(batchId)}/stream`;
    const es = new EventSource(url);

    const _onLabelResult = (msg: MessageEvent) => {
      try {
        const wrapped = JSON.parse(msg.data as string) as {
          batch_id: string;
          queue_position: number;
          envelope: DispositionEnvelope;
        };
        const flat: BatchSSEEvent = {
          ...wrapped.envelope,
          batch_id: wrapped.batch_id,
          queue_position: wrapped.queue_position,
        };
        dispatch({ type: "push", event: flat });
      } catch {
        dispatch({ type: "error", message: "Malformed SSE payload" });
      }
    };
    const _onStreamEnd = (msg: MessageEvent) => {
      let total: number | null = null;
      try {
        const payload = JSON.parse((msg.data as string) || "{}") as { total_count?: number };
        if (typeof payload.total_count === "number") total = payload.total_count;
      } catch {
        // An unreadable stream-end still ends the batch. The count stays
        // unknown rather than being guessed.
      }
      dispatch({ type: "end", total });
      es.close();
    };

    es.addEventListener("label-result", _onLabelResult);
    es.addEventListener("stream-end", _onStreamEnd);
    es.onerror = () => dispatch({ type: "error", message: "SSE connection error" });

    return () => {
      es.removeEventListener("label-result", _onLabelResult);
      es.removeEventListener("stream-end", _onStreamEnd);
      es.close();
    };
  }, [batchId]);

  return state;
}
