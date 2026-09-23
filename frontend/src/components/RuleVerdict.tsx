import * as React from "react";
import { cn } from "../lib/cn";
import { preFilled } from "../lib/corrections";
import type { RuleFindingWire } from "../types/envelopes";
import { DispositionPill } from "./DispositionPill";
import { NeedsReviewFlag } from "./NeedsReviewFlag";

export interface RuleVerdictProps {
  finding: RuleFindingWire;
  className?: string;
}

export function RuleVerdict({ finding, className }: RuleVerdictProps): React.JSX.Element {
  return (
    <section
      role="region"
      aria-label="Rule verdict"
      className={cn(
        "rounded-md border border-border bg-muted/30 p-3 space-y-2",
        className,
      )}
    >
      <header className="flex items-center justify-between">
        <h4 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Rule verdict
        </h4>
        {/* A rule sent to review shows which way it leans, flagged, as the
            field card does (docs/decisions.md#0065). */}
        <div className="flex flex-wrap items-center gap-2">
          {finding.disposition === "needs_review" && <NeedsReviewFlag />}
          <DispositionPill disposition={preFilled(finding.disposition, finding.lean)} />
        </div>
      </header>
      <p className="text-sm">{finding.plain_language_explanation}</p>
      <p className="break-words font-mono text-xs text-muted-foreground">{finding.reason_code}</p>
    </section>
  );
}
