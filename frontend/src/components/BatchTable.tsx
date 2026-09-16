import * as React from "react";
import { cn } from "../lib/cn";
import type { BatchSSEEvent } from "../types/sse";
import { DispositionPill } from "./DispositionPill";

export type SortKey = "position" | "disposition";
export type SortDir = "asc" | "desc";

export interface BatchTableProps {
  rows: BatchSSEEvent[];
  onSelect: (labelRef: string) => void;
  className?: string;
}

const _DISPOSITION_RANK: Record<string, number> = {
  pass: 0,
  needs_review: 1,
  fail: 2,
};

export function BatchTable({ rows, onSelect, className }: BatchTableProps): React.JSX.Element {
  const [sort, setSort] = React.useState<{ key: SortKey; dir: SortDir }>({
    key: "position",
    dir: "asc",
  });

  const sorted = React.useMemo(() => {
    const out = [...rows];
    out.sort((a, b) => {
      const av = sort.key === "position" ? a.queue_position : _DISPOSITION_RANK[a.disposition] ?? 0;
      const bv = sort.key === "position" ? b.queue_position : _DISPOSITION_RANK[b.disposition] ?? 0;
      return sort.dir === "asc" ? av - bv : bv - av;
    });
    return out;
  }, [rows, sort]);

  const toggleSort = (key: SortKey) => {
    setSort((prev) =>
      prev.key === key
        ? { key, dir: prev.dir === "asc" ? "desc" : "asc" }
        : { key, dir: "asc" },
    );
  };

  return (
    <table
      className={cn("w-full border-collapse text-sm", className)}
      aria-label="Batch labels"
    >
      <thead>
        <tr className="border-b-2 border-border bg-muted/40 text-left">
          <th scope="col" className="p-2">
            <button type="button" onClick={() => toggleSort("position")} className="font-semibold underline-offset-2 hover:underline">
              Sort by Position {sort.key === "position" ? (sort.dir === "asc" ? "↑" : "↓") : ""}
            </button>
          </th>
          <th scope="col" className="p-2">Label</th>
          <th scope="col" className="p-2">
            <button type="button" onClick={() => toggleSort("disposition")} className="font-semibold underline-offset-2 hover:underline">
              Sort by Disposition {sort.key === "disposition" ? (sort.dir === "asc" ? "↑" : "↓") : ""}
            </button>
          </th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((row) => (
          <tr
            key={row.evaluation_id}
            role="row"
            tabIndex={0}
            onClick={() => onSelect(row.label_ref)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelect(row.label_ref);
              }
            }}
            className="cursor-pointer border-b border-border hover:bg-muted/40 focus-visible:[outline:3px_solid_hsl(var(--ring))]"
          >
            <td data-col="position" className="p-2 tabular-nums">{row.queue_position}</td>
            <td className="p-2 font-mono text-xs">{row.label_ref}</td>
            <td className="p-2"><DispositionPill disposition={row.disposition} /></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
