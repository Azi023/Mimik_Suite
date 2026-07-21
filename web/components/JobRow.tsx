import type { JSX, KeyboardEvent } from "react";
import { FORMAT_TONE, PILLAR_TONE, type Job } from "@/lib/view-models";
import { CheckIcon, ClipIcon, ClockIcon, CommentIcon } from "./icons";

interface JobRowProps {
  job: Job;
  /** Whether this card is the one open in the review panel (drives the selected ring). */
  selected: boolean;
  /** Fired on click / Enter / Space — selects this job into the review panel. */
  onSelect: (job: Job) => void;
}

/**
 * A kanban card: colored format/pillar tags, title, circular-checkbox
 * checklist, SLA line, and a footer with the avatar stack + comment /
 * attachment counts — mirroring the reference card anatomy. The whole card is
 * a button (role + keyboard) that selects the job into the review panel.
 */
export function JobRow({ job, selected, onSelect }: JobRowProps): JSX.Element {
  const pillarTone = PILLAR_TONE[job.pillar] ?? "gray";

  function handleKeyDown(event: KeyboardEvent<HTMLElement>): void {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelect(job);
    }
  }

  return (
    <article
      className={`job-card${selected ? " job-card--selected" : ""}`}
      data-animate="card"
      role="button"
      tabIndex={0}
      aria-pressed={selected}
      aria-label={`Review ${job.title}`}
      onClick={(): void => onSelect(job)}
      onKeyDown={handleKeyDown}
    >
      <div className="job-card__tags">
        <span className={`tag tag--${FORMAT_TONE[job.format]}`}>{job.format}</span>
        <span className={`tag tag--${pillarTone}`}>{job.pillar}</span>
        {job.generating === true && (
          <span className="job-badge job-badge--generating">
            <span className="job-badge__pulse" aria-hidden="true" />
            Generating
          </span>
        )}
        {job.atRisk === true && job.generating !== true && (
          <span className="job-badge job-badge--risk">At risk</span>
        )}
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

        {(job.comments !== null || job.attachments !== null) && (
          <div className="job-card__counts">
            {job.comments !== null && (
              <span className="meta-count" aria-label={`${job.comments} comments`}>
                <CommentIcon />
                {job.comments}
              </span>
            )}
            {job.attachments !== null && (
              <span className="meta-count" aria-label={`${job.attachments} attachments`}>
                <ClipIcon />
                {job.attachments}
              </span>
            )}
          </div>
        )}
      </footer>
    </article>
  );
}
