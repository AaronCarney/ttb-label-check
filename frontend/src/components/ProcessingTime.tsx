import * as React from "react";
import { cn } from "../lib/cn";
import type { Metrics } from "../types/envelopes";

export interface ProcessingTimeProps {
  /** The envelope's telemetry block. Null or missing renders nothing rather
   *  than a zero — an absent measurement is not a fast one. */
  metrics: Metrics | null | undefined;
  /** The evaluation guard stopped this check partway. The duration is then how
   *  long it ran before being stopped, not how long a whole check takes. */
  stoppedEarly?: boolean;
  className?: string;
}

/** Milliseconds as a reviewer reads them: "18 ms" below a second, "4.2 s" at
 *  or above one.
 *
 *  Not seconds throughout: a cache hit costs single-digit milliseconds, and
 *  "0.0 s" on screen reads as a broken measurement rather than a fast one.
 *  Negative and non-finite inputs floor at zero so a clock oddity cannot put
 *  "-1 ms" in front of a reviewer. */
export function formatDuration(ms: number): string {
  const safe = Number.isFinite(ms) && ms > 0 ? ms : 0;
  if (safe < 1000) return `${Math.round(safe)} ms`;
  return `${(safe / 1000).toFixed(1)} s`;
}

// How long the check took, on the screen a reviewer actually sees. The number
// has been on the envelope since `metrics` was added and reachable only
// through the raw-JSON drawer, which is off unless DEV_MODE is set.
//
// Two cases where the bare number would mislead, so each gets its own wording
// rather than a shared "Checked in":
//
//  - A cache hit. The durations then describe what returning the stored answer
//    cost, not what checking the label cost (app/schemas/metrics.py).
//  - A check the evaluation guard stopped. That now reports the
//    real elapsed time rather than 0, so the number is how far it got. The
//    IncompleteCheckCard below says what that means for the results.
export function ProcessingTime({
  metrics,
  stoppedEarly = false,
  className,
}: ProcessingTimeProps): React.JSX.Element | null {
  if (!metrics) return null;

  const total = formatDuration(metrics.total_duration_ms);
  const text = metrics.cache_hit
    ? `Served from cache in ${total}`
    : stoppedEarly
      ? `Stopped after ${total}`
      : `Checked in ${total}`;

  // Supplementary, not load-bearing: the headline stands without it, and the
  // full per-rule split is in the raw-JSON drawer.
  const detail =
    !metrics.cache_hit && metrics.vision_duration_ms > 0
      ? `Reading the label took ${formatDuration(metrics.vision_duration_ms)} of that.`
      : undefined;

  return (
    <span
      data-testid="processing-time"
      title={detail}
      className={cn("text-sm tabular-nums text-muted-foreground", className)}
    >
      {text}
    </span>
  );
}
