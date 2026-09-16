import { Sparkles } from "lucide-react";
import * as React from "react";
import { cn } from "../lib/cn";
import type { AISuggestionWire } from "../types/envelopes";

export interface AISuggestionBlockProps {
  suggestion: AISuggestionWire;
  className?: string;
}

const _TASK_LABEL: Record<string, string> = {
  brand_borderline: "Brand-name disambiguation",
  reasoning_enrichment: "Reasoning enrichment",
  ocr_reconciliation: "OCR reconciliation",
};

export function AISuggestionBlock({ suggestion, className }: AISuggestionBlockProps): React.JSX.Element | null {
  if (!suggestion.present) return null;
  const taskLabel = suggestion.task ? _TASK_LABEL[suggestion.task] ?? suggestion.task : "AI suggestion";
  return (
    <aside
      role="complementary"
      aria-label="AI suggestion"
      className={cn(
        // Distinct styling from RuleVerdict: left-border accent + muted bg.
        "rounded-md border-l-4 border-l-[hsl(var(--uswds-info))] border border-border bg-[hsl(var(--uswds-info-light))]/30 p-3 space-y-1",
        className,
      )}
    >
      <header className="flex items-center gap-2">
        <Sparkles aria-hidden className="h-4 w-4 text-[hsl(var(--uswds-info-dark))]" />
        <h4 className="text-sm font-semibold">
          {taskLabel} <span className="font-normal text-muted-foreground">— advisory</span>
        </h4>
      </header>
      <p className="text-sm">{suggestion.text}</p>
    </aside>
  );
}
