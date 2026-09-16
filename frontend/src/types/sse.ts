import type { DispositionEnvelope } from "./envelopes";

/** Per-label SSE event: a §6.2 envelope augmented with batch_id +
 *  queue_position. The augmentation lives at the SSE layer; the underlying
 *  envelope shape is unmodified. */
export interface BatchSSEEvent extends DispositionEnvelope {
  batch_id: string;
  queue_position: number;
}
