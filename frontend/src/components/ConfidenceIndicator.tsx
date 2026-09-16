import * as React from "react";
import { cn } from "../lib/cn";
import type { Band } from "../types/envelopes";

export interface ConfidenceIndicatorProps {
  band: Band;
  numeric: number;
  className?: string;
}

const _BAND_LABEL: Record<Band, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
};

const _BAND_BAR: Record<Band, string> = {
  high: "w-full bg-[hsl(var(--uswds-success))]",
  medium: "w-2/3 bg-[hsl(var(--uswds-warning-dark))]",
  low: "w-1/3 bg-destructive",
};

export function ConfidenceIndicator({ band, numeric, className }: ConfidenceIndicatorProps): React.JSX.Element {
  const clamped = Math.max(0, Math.min(1, numeric));
  return (
    <div
      role="group"
      aria-label={`Confidence: ${_BAND_LABEL[band]} (${clamped.toFixed(2)})`}
      className={cn("flex items-center gap-2", className)}
    >
      <span className="text-sm font-medium tabular-nums">
        {clamped.toFixed(2)}
      </span>
      <div className="h-2 w-24 overflow-hidden rounded-full bg-muted" aria-hidden>
        <div className={cn("h-full transition-[width]", _BAND_BAR[band])} />
      </div>
      <span
        role="meter"
        aria-label={`Confidence band: ${_BAND_LABEL[band]}`}
        aria-valuemin={0}
        aria-valuemax={1}
        aria-valuenow={clamped}
        aria-valuetext={`${_BAND_LABEL[band]} (${band})`}
        className="text-sm"
      >
        {_BAND_LABEL[band]}
      </span>
    </div>
  );
}
