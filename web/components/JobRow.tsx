import type { JSX } from "react";
import { FORMAT_TONE, PILLAR_TONE, type Job } from "@/lib/mock";
import { CheckIcon, ClipIcon, ClockIcon, CommentIcon } from "./icons";

interface JobRowProps {
  job: Job;
}

/**
 * A kanban card: colored format/pillar tags, title, circular-checkbox
 * checklist, SLA line, and a footer with the avatar stack + comment /
 * attachment counts — mirroring the reference card anatomy.
 */
export function JobRow({ job }: JobRowProps): JSX.Element {
  const pillarTone = PILLAR_TONE[job.pillar] ?? "gray";

  return (
    <article className="job-card" data-animate="card">
      <div className="job-card__tags">
        <span className={`tag tag--${FORMAT_TONE[job.format]}`}>{job.format}</span>
        <span className={`tag tag--${pillarTone}`}>{job.pillar}</span>
      </div>

      <h4 className="job-card__title">{job.title}</h4>

      {job.checklist.length > 0 && (
        <ul className="job-card__checklist">
          {job.checklist.map((item) => (
            <li
              key={item.id}
              className={`check${item.done ? " check--done" : ""}`}
            >
              <span className="check__circle" aria-hidden="true">
                {item.done && <CheckIcon />}
              </span>
              <span className="check__label">{item.label}</span>
            </li>
          ))}
        </ul>
      )}

      <p className="job-card__sla">
        <ClockIcon />
        {job.sla}
      </p>

      <footer className="job-card__footer">
        <div
          className="avatar-stack avatar-stack--sm"
          aria-label={`Assigned: ${job.assignees.map((a) => a.name).join(", ")}`}
        >
          {job.assignees.map((assignee) => (
            <span
              key={assignee.id}
              className={`avatar avatar--${assignee.tone}`}
              title={assignee.name}
            >
              {assignee.initials}
            </span>
          ))}
        </div>

        <div className="job-card__counts">
          <span className="meta-count" aria-label={`${job.comments} comments`}>
            <CommentIcon />
            {job.comments}
          </span>
          <span
            className="meta-count"
            aria-label={`${job.attachments} attachments`}
          >
            <ClipIcon />
            {job.attachments}
          </span>
        </div>
      </footer>
    </article>
  );
}
