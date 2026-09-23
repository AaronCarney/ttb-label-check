import * as React from "react";
import { withOverride, type OverrideApplied, type Verdict } from "../lib/corrections";
import type { DispositionEnvelope, Lean, OverrideEntry } from "../types/envelopes";
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
  | { type: "override"; evaluationId: string; applied: OverrideApplied }
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
    case "override":
      return {
        ...state,
        events: state.events.map((e) =>
          e.evaluation_id === action.evaluationId ? { ...e, ...withOverride(e, action.applied) } : e,
        ),
      };
    case "reset":
      return { events: [], error: null, total: null, done: false };
  }
}

export interface BatchStream extends BatchStreamState {
  /** Puts a reviewer's correction on the label it corrects, so the batch table
   * and the result page show the corrected result. The page calls this with
   * the endpoint's answer, because a finished batch has closed its stream and
   * will not hear the broadcast. */
  applyOverride: (evaluationId: string, applied: OverrideApplied) => void;
}

// The batch stream carries four named SSE events: label-result,
// anomaly-advisory and stream-end from the worker, and override-applied from
// the override endpoint. This hook consumes all but anomaly-advisory, which is
// not surfaced in the interface yet.
export function useBatchStream(batchId: string): BatchStream {
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

    const _onOverrideApplied = (msg: MessageEvent) => {
      try {
        const payload = JSON.parse(msg.data as string) as {
          evaluation_id: string;
          entry: OverrideEntry;
          label_disposition?: Verdict;
          label_lean?: Lean;
        };
        dispatch({
          type: "override",
          evaluationId: payload.evaluation_id,
          applied: {
            entry: payload.entry,
            labelDisposition: payload.label_disposition,
            labelLean: payload.label_lean,
          },
        });
      } catch {
        dispatch({ type: "error", message: "Malformed SSE payload" });
      }
    };

    es.addEventListener("label-result", _onLabelResult);
    es.addEventListener("stream-end", _onStreamEnd);
    es.addEventListener("override-applied", _onOverrideApplied);
    es.onerror = () => dispatch({ type: "error", message: "SSE connection error" });

    return () => {
      es.removeEventListener("label-result", _onLabelResult);
      es.removeEventListener("stream-end", _onStreamEnd);
      es.removeEventListener("override-applied", _onOverrideApplied);
      es.close();
    };
  }, [batchId]);

  const applyOverride = React.useCallback(
    (evaluationId: string, applied: OverrideApplied) => dispatch({ type: "override", evaluationId, applied }),
    [],
  );
  return { ...state, applyOverride };
}
