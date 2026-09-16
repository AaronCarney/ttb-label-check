import { AlertCircle, Info, AlertTriangle } from "lucide-react";
import * as React from "react";
import { cn } from "../lib/cn";

export type AlertSeverity = "info" | "warning" | "error";

export interface AlertProps {
  severity: AlertSeverity;
  title: string;
  message: string;
  className?: string;
}

const _META: Record<
  AlertSeverity,
  {
    role: "alert" | "status";
    live: "assertive" | "polite";
    bg: string;
    Icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  }
> = {
  error: {
    role: "alert",
    live: "assertive",
    bg: "bg-destructive/10 border-destructive text-destructive",
    Icon: AlertCircle,
  },
  warning: {
    role: "status",
    live: "polite",
    bg: "bg-warning/10 border-warning text-warning",
    Icon: AlertTriangle,
  },
  info: {
    role: "status",
    live: "polite",
    bg: "bg-[hsl(var(--uswds-info-light))] border-[hsl(var(--uswds-info))] text-[hsl(var(--uswds-info-dark))]",
    Icon: Info,
  },
};

export function Alert({ severity, title, message, className }: AlertProps): React.JSX.Element {
  const m = _META[severity];
  return (
    <div
      role={m.role}
      aria-live={m.live}
      className={cn("flex items-start gap-3 rounded-md border p-4", m.bg, className)}
    >
      <m.Icon aria-hidden className="h-5 w-5 mt-0.5 shrink-0" />
      <div>
        <p className="font-semibold">{title}</p>
        <p className="text-sm">{message}</p>
      </div>
    </div>
  );
}
