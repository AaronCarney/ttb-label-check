import * as React from "react";
import { cn } from "../lib/cn";

export interface ReasonCodeEntry {
  code: string;
  description: string;
  /** Applied disposition when this code is chosen as an override target.
   *  Sourced from rules/reason_codes.yaml severity (reject → fail,
   *  warn → needs_review). Optional here so callers that only use the
   *  picker for display don't have to populate it. */
  disposition?: "fail" | "needs_review";
}

export interface ReasonCodePickerProps {
  codes: ReasonCodeEntry[];
  /** Fires whenever the resolved code changes (auto-resolve on unique
   *  prefix, click on a row, or Enter on the highlighted row). Use for
   *  display state (e.g. "Selected: …" pill). */
  onSelect: (code: string) => void;
  /** Fires only on explicit Enter against the highlighted row. Use for
   *  the submit action — the third keystroke of the override path. When
   *  omitted, Enter falls back to firing onSelect. */
  onSubmit?: (code: string) => void;
  autoFocus?: boolean;
  className?: string;
}

export function ReasonCodePicker({
  codes,
  onSelect,
  onSubmit,
  autoFocus = true,
  className,
}: ReasonCodePickerProps): React.JSX.Element {
  const [query, setQuery] = React.useState("");
  const [highlight, setHighlight] = React.useState(0);
  const inputRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    if (autoFocus) inputRef.current?.focus();
  }, [autoFocus]);

  const filtered = React.useMemo(() => {
    const q = query.toUpperCase();
    if (!q) return codes;
    return codes.filter((c) => c.code.startsWith(q));
  }, [codes, query]);

  // Single-keystroke resolution: when the typed prefix matches exactly one
  // code, that code is selected without a further keystroke.
  React.useEffect(() => {
    if (query && filtered.length === 1) {
      onSelect(filtered[0]!.code);
    }
  }, [filtered, query, onSelect]);

  React.useEffect(() => {
    setHighlight(0);
  }, [filtered.length]);

  const handleKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlight((h) => Math.min(h + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight((h) => Math.max(h - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const sel = filtered[highlight];
      if (!sel) return;
      onSelect(sel.code);
      if (onSubmit) onSubmit(sel.code);
    }
  };

  const listboxId = React.useId();
  return (
    <div className={cn("space-y-2", className)}>
      <input
        ref={inputRef}
        role="combobox"
        aria-expanded={filtered.length > 0}
        aria-autocomplete="list"
        aria-controls={listboxId}
        aria-activedescendant={filtered[highlight] ? `${listboxId}-${highlight}` : undefined}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={handleKey}
        placeholder="Type a reason-code prefix (e.g., W, BR, AL)…"
        className="w-full rounded-md border border-border bg-background px-3 py-2 text-base focus-visible:ring-2 focus-visible:ring-ring"
      />
      <ul
        id={listboxId}
        role="listbox"
        aria-label="Reason codes"
        className="max-h-64 overflow-y-auto rounded-md border border-border"
      >
        {filtered.map((c, i) => (
          <li
            id={`${listboxId}-${i}`}
            key={c.code}
            role="option"
            aria-selected={i === highlight}
            onMouseDown={(e) => {
              e.preventDefault();
              onSelect(c.code);
            }}
            className={cn(
              "cursor-pointer px-3 py-2 text-sm",
              i === highlight && "bg-muted",
            )}
          >
            <div className="font-mono">{c.code}</div>
            <div className="text-xs text-muted-foreground">{c.description}</div>
          </li>
        ))}
        {filtered.length === 0 && (
          <li className="px-3 py-2 text-sm text-muted-foreground">No matches.</li>
        )}
      </ul>
    </div>
  );
}
