import type { JSX } from "react";
import type { JobStatus } from "@/lib/mock";

interface StatusPillProps {
  status: JobStatus;
}

interface StatusMeta {
  label: string;
  /** Maps to the semantic tone classes in globals.css. */
  variant: "neutral" | "good" | "crit";
}

const STATUS_META: Record<JobStatus, StatusMeta> = {
  in_review: { label: "In review", variant: "neutral" },
  at_risk: { label: "At risk", variant: "crit" },
  approved: { label: "Approved", variant: "good" },
};

/** Small status token for a job. Tone is derived from the job's lifecycle status. */
export function StatusPill({ status }: StatusPillProps): JSX.Element {
  const meta = STATUS_META[status];

  return (
    <span className={`status-pill status-pill--${meta.variant}`}>
      <span className="status-pill__dot" aria-hidden="true" />
      {meta.label}
    </span>
  );
}
