import * as React from "react";
import { cn } from "../lib/cn";

export interface ToastProps {
  message: string;
  duration?: number;
  onDismiss?: () => void;
  className?: string;
}

export function Toast({ message, duration = 4000, onDismiss, className }: ToastProps): React.JSX.Element {
  React.useEffect(() => {
    if (!onDismiss) return;
    const t = setTimeout(onDismiss, duration);
    return () => clearTimeout(t);
  }, [duration, onDismiss]);

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "rounded-md border border-border bg-foreground px-4 py-2 text-sm text-background shadow-md",
        className,
      )}
    >
      {message}
    </div>
  );
}
