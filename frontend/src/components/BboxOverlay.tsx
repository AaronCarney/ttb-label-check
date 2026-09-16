import * as React from "react";
import { cn } from "../lib/cn";

export interface BboxItem {
  id: string;
  bbox: [number, number, number, number];
  label: string;
}

export interface BboxOverlayProps {
  imageSrc: string;
  imageWidth: number;
  imageHeight: number;
  bboxes: BboxItem[];
  altText?: string;
  onSelect?: (id: string) => void;
  className?: string;
}

export function BboxOverlay({
  imageSrc,
  imageWidth,
  imageHeight,
  bboxes,
  altText = "Label image",
  onSelect,
  className,
}: BboxOverlayProps): React.JSX.Element {
  const [pressed, setPressed] = React.useState<Set<string>>(new Set());

  const toggle = (id: string) => {
    setPressed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
    onSelect?.(id);
  };

  return (
    <div
      className={cn("relative inline-block", className)}
      style={{ width: imageWidth, maxWidth: "100%" }}
    >
      <img
        src={imageSrc}
        alt={altText}
        width={imageWidth}
        height={imageHeight}
        style={{ display: "block", width: "100%", height: "auto" }}
      />
      <svg
        viewBox={`0 0 ${imageWidth} ${imageHeight}`}
        preserveAspectRatio="xMidYMid meet"
        className="absolute inset-0 h-full w-full"
      >
        {bboxes.map(({ id, bbox, label }) => {
          const [x, y, w, h] = bbox;
          const isPressed = pressed.has(id);
          return (
            <g
              key={id}
              role="button"
              tabIndex={0}
              aria-pressed={isPressed}
              aria-label={label}
              onClick={() => toggle(id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  toggle(id);
                }
              }}
              className="cursor-pointer outline-none focus-visible:[outline:3px_solid_hsl(var(--ring))]"
            >
              <rect
                x={x}
                y={y}
                width={w}
                height={h}
                fill={isPressed ? "hsl(var(--uswds-primary)/0.18)" : "transparent"}
                stroke={isPressed ? "hsl(var(--uswds-primary-vivid))" : "hsl(var(--uswds-primary))"}
                strokeWidth={isPressed ? 3 : 2}
              />
            </g>
          );
        })}
      </svg>
    </div>
  );
}
