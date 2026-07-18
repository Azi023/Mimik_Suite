import type { JSX } from "react";
import type { Job } from "@/lib/mock";
import { StatusPill } from "./StatusPill";

interface JobRowProps {
  job: Job;
}

/** A single row on the ops board: title + pillar/format/SLA meta + status pill. */
export function JobRow({ job }: JobRowProps): JSX.Element {
  return (
    <article className="job-row">
      <div className="job-row__body">
        <h3 className="job-row__title">{job.title}</h3>
        <div className="job-row__meta">
          <span>{job.pillar}</span>
          <span className="job-row__sep" aria-hidden="true">
            ·
          </span>
          <span>{job.format}</span>
          <span className="job-row__sep" aria-hidden="true">
            ·
          </span>
          <span>{job.sla}</span>
        </div>
      </div>
      <div className="job-row__status">
        <StatusPill status={job.status} />
      </div>
    </article>
  );
}
