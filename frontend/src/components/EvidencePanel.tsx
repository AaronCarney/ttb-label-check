import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import * as React from "react";
import { cn } from "../lib/cn";

export interface EvidencePanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  citation: string;
  regulationText: string;
  evidenceText: string;
  className?: string;
}

export function EvidencePanel({
  open,
  onOpenChange,
  citation,
  regulationText,
  evidenceText,
  className,
}: EvidencePanelProps): React.JSX.Element {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50" />
        <Dialog.Content
          aria-describedby="evidence-desc"
          className={cn(
            "fixed left-1/2 top-1/2 z-50 w-[min(960px,90vw)] -translate-x-1/2 -translate-y-1/2 rounded-lg border border-border bg-background p-6 shadow-lg",
            className,
          )}
        >
          <header className="flex items-center justify-between">
            <Dialog.Title className="text-lg font-semibold">{citation}</Dialog.Title>
            <Dialog.Close
              aria-label="Close"
              className="rounded-md p-1 hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
            >
              <X aria-hidden className="h-5 w-5" />
            </Dialog.Close>
          </header>
          <div id="evidence-desc" className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <article aria-label="Regulation text">
              <h3 className="font-semibold text-muted-foreground">Regulation</h3>
              <p className="mt-1 whitespace-pre-wrap">{regulationText}</p>
            </article>
            <article aria-label="Extracted evidence">
              <h3 className="font-semibold text-muted-foreground">Evidence</h3>
              <p className="mt-1 whitespace-pre-wrap">{evidenceText}</p>
            </article>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
