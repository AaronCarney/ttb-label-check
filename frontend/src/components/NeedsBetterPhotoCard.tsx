import { Camera, Copy } from "lucide-react";
import * as React from "react";
import { cn } from "../lib/cn";

export interface NeedsBetterPhotoCardProps {
  reasonCode: string;
  applicantMessage: string;
  className?: string;
}

export function NeedsBetterPhotoCard({ reasonCode, applicantMessage, className }: NeedsBetterPhotoCardProps): React.JSX.Element {
  const [copied, setCopied] = React.useState(false);
  const handleCopy = async () => {
    await navigator.clipboard.writeText(applicantMessage);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <section
      role="region"
      aria-label="Needs better photo"
      className={cn("rounded-lg border border-warning/40 bg-warning/10 p-4 space-y-3", className)}
    >
      <header className="flex items-center gap-2">
        <Camera aria-hidden className="h-5 w-5" />
        <h3 className="font-semibold">Needs better photo</h3>
      </header>
      <p className="font-mono text-xs text-muted-foreground">{reasonCode}</p>
      <p className="text-sm">{applicantMessage}</p>
      <button
        type="button"
        onClick={handleCopy}
        className="inline-flex items-center gap-1 rounded-md border border-border bg-background px-3 py-1 text-sm hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Copy aria-hidden className="h-4 w-4" />
        {copied ? "Copied" : "Copy message"}
      </button>
    </section>
  );
}
