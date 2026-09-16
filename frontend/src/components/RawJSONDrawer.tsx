import * as Dialog from "@radix-ui/react-dialog";
import { Code, X } from "lucide-react";
import * as React from "react";
import { cn } from "../lib/cn";

export interface RawJSONDrawerProps {
  enabled: boolean;
  payload: unknown;
  className?: string;
}

export function RawJSONDrawer({ enabled, payload, className }: RawJSONDrawerProps): React.JSX.Element | null {
  const [open, setOpen] = React.useState(false);
  if (!enabled) return null;
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <button
          type="button"
          className={cn(
            "inline-flex items-center gap-2 rounded-md border border-border bg-background px-3 py-1 text-sm hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring",
            className,
          )}
        >
          <Code aria-hidden className="h-4 w-4" />
          Show raw JSON
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50" />
        <Dialog.Content className="fixed right-0 top-0 z-50 h-full w-[min(720px,90vw)] overflow-y-auto bg-background p-6 shadow-lg">
          <header className="flex items-center justify-between">
            <Dialog.Title className="text-lg font-semibold">Raw JSON (DEV_MODE)</Dialog.Title>
            <Dialog.Close aria-label="Close" className="rounded-md p-1 hover:bg-muted">
              <X aria-hidden className="h-5 w-5" />
            </Dialog.Close>
          </header>
          <pre className="mt-4 whitespace-pre-wrap break-all rounded-md bg-muted p-3 font-mono text-xs">
            {JSON.stringify(payload, null, 2)}
          </pre>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
