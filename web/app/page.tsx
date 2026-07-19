import type { JSX } from "react";
import { AppShell } from "@/components/AppShell";
import { PillarChips } from "@/components/PillarChips";
import { Board } from "@/components/Board";
import { ReviewPanel } from "@/components/ReviewPanel";
import { getBoardData, getSidebarData } from "@/lib/data";

// The board reflects live job state — always render per-request, never a build-time
// snapshot (and never let `next build` try to reach the API).
export const dynamic = "force-dynamic";

/** Board view — the default dashboard screen. Data comes from the `lib/data.ts`
 * facade: live API when configured + reachable, mock set otherwise. */
export default async function BoardPage(): Promise<JSX.Element> {
  const [{ pillars, jobs, reviewDoc }, sidebar] = await Promise.all([
    getBoardData(),
    getSidebarData(),
  ]);

  return (
    <AppShell sidebar={sidebar}>
      <div className="board-view">
        <div className="board-view__main">
          <section className="board-view__filters" aria-label="Content pillars">
            <h2 className="visually-hidden">Content pillars</h2>
            <PillarChips pillars={pillars} />
          </section>

          <section aria-label="This week's approvals">
            <h2 className="visually-hidden">This week · approvals</h2>
            <Board jobs={jobs} />
          </section>
        </div>

        <ReviewPanel doc={reviewDoc} />
      </div>
    </AppShell>
  );
}
