import type { JSX } from "react";
import type { Job } from "@/lib/mock";
import { JobRow } from "./JobRow";

interface BoardProps {
  jobs: Job[];
}

/** The approvals board — a stacked list of job rows inside a bordered panel. */
export function Board({ jobs }: BoardProps): JSX.Element {
  return (
    <div className="board">
      {jobs.map((job) => (
        <JobRow key={job.id} job={job} />
      ))}
    </div>
  );
}
