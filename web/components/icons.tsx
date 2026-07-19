import type { JSX } from "react";
import type { ProjectShape } from "@/lib/mock";

/**
 * Hand-rolled 1.7px-stroke glyph set matching the reference's line-icon style.
 * All icons are decorative (aria-hidden) — accessible labels live on the
 * interactive elements that wrap them.
 */

interface IconProps {
  size?: number;
}

function base(size: number): {
  width: number;
  height: number;
  viewBox: string;
  fill: string;
  stroke: string;
  strokeWidth: number;
  strokeLinecap: "round";
  strokeLinejoin: "round";
  "aria-hidden": true;
} {
  return {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.7,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": true,
  };
}

export function GridIcon({ size = 20 }: IconProps): JSX.Element {
  return (
    <svg {...base(size)}>
      <rect x="4" y="4" width="7" height="7" rx="2" />
      <rect x="13" y="4" width="7" height="7" rx="2" />
      <rect x="4" y="13" width="7" height="7" rx="2" />
      <rect x="13" y="13" width="7" height="7" rx="2" />
    </svg>
  );
}

export function UsersIcon({ size = 20 }: IconProps): JSX.Element {
  return (
    <svg {...base(size)}>
      <circle cx="9" cy="8.5" r="3.2" />
      <path d="M3.5 19.5c.6-3 2.8-4.7 5.5-4.7s4.9 1.7 5.5 4.7" />
      <path d="M15.5 5.7a3.2 3.2 0 0 1 0 5.6M17.5 15.2c1.7.6 2.7 2 3 4.3" />
    </svg>
  );
}

export function CalendarIcon({ size = 20 }: IconProps): JSX.Element {
  return (
    <svg {...base(size)}>
      <rect x="4" y="5.5" width="16" height="14.5" rx="2.5" />
      <path d="M4 10h16M8.5 3.5v3.5M15.5 3.5v3.5" />
    </svg>
  );
}

export function ImageIcon({ size = 20 }: IconProps): JSX.Element {
  return (
    <svg {...base(size)}>
      <rect x="4" y="4.5" width="16" height="15" rx="2.5" />
      <circle cx="9.2" cy="9.8" r="1.6" />
      <path d="M4.5 17.5l4.7-4.4 3.4 3.1 3.2-2.9 3.7 3.4" />
    </svg>
  );
}

export function FileIcon({ size = 20 }: IconProps): JSX.Element {
  return (
    <svg {...base(size)}>
      <path d="M6.5 3.5h7L18.5 8v10a2 2 0 0 1-2 2h-10a2 2 0 0 1-2-2v-12a2 2 0 0 1 2-2z" />
      <path d="M13.5 3.5V8h4.5M9 12.5h6M9 16h4" />
    </svg>
  );
}

export function SettingsIcon({ size = 20 }: IconProps): JSX.Element {
  return (
    <svg {...base(size)}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 13.5a7.6 7.6 0 0 0 0-3l1.8-1.4-2-3.4-2.1.9a7.6 7.6 0 0 0-2.6-1.5L14.2 3h-4l-.3 2.1a7.6 7.6 0 0 0-2.6 1.5l-2.1-.9-2 3.4 1.8 1.4a7.6 7.6 0 0 0 0 3l-1.8 1.4 2 3.4 2.1-.9a7.6 7.6 0 0 0 2.6 1.5l.3 2.1h4l.3-2.1a7.6 7.6 0 0 0 2.6-1.5l2.1.9 2-3.4z" />
    </svg>
  );
}

export function SearchIcon({ size = 16 }: IconProps): JSX.Element {
  return (
    <svg {...base(size)}>
      <circle cx="11" cy="11" r="6.5" />
      <path d="M15.8 15.8L20.5 20.5" />
    </svg>
  );
}

export function PlusIcon({ size = 16 }: IconProps): JSX.Element {
  return (
    <svg {...base(size)}>
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

export function ChevronDownIcon({ size = 14 }: IconProps): JSX.Element {
  return (
    <svg {...base(size)}>
      <path d="M6 9.5l6 5.5 6-5.5" />
    </svg>
  );
}

export function DotsIcon({ size = 16 }: IconProps): JSX.Element {
  return (
    <svg {...base(size)}>
      <circle cx="12" cy="5.5" r="0.9" fill="currentColor" />
      <circle cx="12" cy="12" r="0.9" fill="currentColor" />
      <circle cx="12" cy="18.5" r="0.9" fill="currentColor" />
    </svg>
  );
}

export function CommentIcon({ size = 14 }: IconProps): JSX.Element {
  return (
    <svg {...base(size)}>
      <path d="M20 11.6a7.6 7.6 0 0 1-8 7.4 8.4 8.4 0 0 1-3.1-.6L4 19.5l1.2-4.3A7.2 7.2 0 0 1 4 11.6a7.6 7.6 0 0 1 8-7.4 7.6 7.6 0 0 1 8 7.4z" />
    </svg>
  );
}

export function ClipIcon({ size = 14 }: IconProps): JSX.Element {
  return (
    <svg {...base(size)}>
      <path d="M20 11.5l-7.5 7.5a5 5 0 0 1-7-7l8-8a3.4 3.4 0 0 1 4.8 4.8l-7.8 7.8a1.8 1.8 0 0 1-2.5-2.5l6.8-6.8" />
    </svg>
  );
}

export function ClockIcon({ size = 14 }: IconProps): JSX.Element {
  return (
    <svg {...base(size)}>
      <circle cx="12" cy="12" r="8" />
      <path d="M12 7.5V12l3 2" />
    </svg>
  );
}

export function CheckIcon({ size = 10 }: IconProps): JSX.Element {
  return (
    <svg {...base(size)} strokeWidth={2.6}>
      <path d="M5 12.5l4.5 4.5L19 7.5" />
    </svg>
  );
}

/** Colored geometric marker for a client row in the secondary sidebar. */
export function ShapeIcon({
  shape,
  size = 14,
}: IconProps & { shape: ProjectShape }): JSX.Element {
  const props = base(size);
  switch (shape) {
    case "circle":
      return (
        <svg {...props} strokeWidth={2.2}>
          <circle cx="12" cy="12" r="7" />
        </svg>
      );
    case "square":
      return (
        <svg {...props} strokeWidth={2.2}>
          <rect x="5.5" y="5.5" width="13" height="13" rx="3" />
        </svg>
      );
    case "diamond":
      return (
        <svg {...props} strokeWidth={2.2}>
          <path d="M12 4.5l7.5 7.5-7.5 7.5L4.5 12z" />
        </svg>
      );
    case "triangle":
      return (
        <svg {...props} strokeWidth={2.2}>
          <path d="M12 5l8 14H4z" />
        </svg>
      );
  }
}
