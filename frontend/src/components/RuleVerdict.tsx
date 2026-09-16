import * as React from "react";
import { cn } from "../lib/cn";
import type { RuleFindingWire } from "../types/envelopes";
import { DispositionPill } from "./DispositionPill";

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
        <DispositionPill disposition={finding.disposition} />
      </header>
      <p className="text-sm">{finding.plain_language_explanation}</p>
      <p className="font-mono text-xs text-muted-foreground">{finding.reason_code}</p>
    </section>
  );
}
