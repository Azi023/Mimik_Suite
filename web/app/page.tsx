import type { JSX } from "react";
import { AppShell } from "@/components/AppShell";
import { PillarChips } from "@/components/PillarChips";
import { Board } from "@/components/Board";
import { ReviewPanel } from "@/components/ReviewPanel";
import { jobs, pillars, reviewDoc } from "@/lib/mock";

/** Board view — the default dashboard screen. */
export default function BoardPage(): JSX.Element {
  return (
    <AppShell>
      <section className="section">
        <h2 className="section__label">Content pillars</h2>
        <PillarChips pillars={pillars} />
      </section>

      <section className="section">
        <h2 className="section__label">This week · approvals</h2>
        <Board jobs={jobs} />
      </section>

      <section className="section">
        <h2 className="section__label">In review</h2>
        <ReviewPanel doc={reviewDoc} />
      </section>
    </AppShell>
  );
}
