import * as React from "react";
import { cn } from "../lib/cn";

export type Politeness = "polite" | "assertive";

export interface LiveRegionProps {
  message: string;
  politeness?: Politeness;
  className?: string;
}

// Visually hidden but exposed to AT (NFR-A11Y-002 / NFR-A11Y-003).
const _SR_ONLY =
  "absolute -m-px h-px w-px overflow-hidden whitespace-nowrap border-0 p-0 [clip:rect(0,0,0,0)]";

export function LiveRegion({
  message,
  politeness = "polite",
  className,
}: LiveRegionProps): React.JSX.Element {
  const role = politeness === "assertive" ? "alert" : "status";
  return (
    <div
      role={role}
      aria-live={politeness}
      aria-atomic="true"
      className={cn(_SR_ONLY, className)}
    >
      {message}
    </div>
  );
}
