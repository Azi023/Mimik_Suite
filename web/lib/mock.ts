/**
 * Mock data for the Mimik Suite dashboard shell.
 *
 * These types MIRROR the mimik-contracts Pydantic shapes (the shared vocabulary
 * described in the data-model spine: Client → Brand → Brief → Job → CreativeDoc → Layer).
 * They are intentionally a frontend-local subset — no API calls happen here yet.
 * When the API phase lands, these interfaces get replaced by generated contract types.
 */

/** Content pillar a job belongs to (per-client editorial category). */
export interface Pillar {
  id: string;
  label: string;
  /** Whether this pillar is the currently selected filter on the board. */
  active: boolean;
  /** A "+ Custom" affordance renders as a dashed add-chip rather than a real pillar. */
  custom?: boolean;
}

/** Review lifecycle status for a job. Maps to mimik-contracts Job.status. */
export type JobStatus = "in_review" | "at_risk" | "approved";

/** Publishing format / channel for a job. Maps to mimik-contracts Job.format. */
export type JobFormat = "IG Reel" | "IG Post" | "Poster" | "Story" | "Carousel";

/** A single unit of work on the ops board. Maps to mimik-contracts Job. */
export interface Job {
  id: string;
  title: string;
  /** Label of the pillar this job belongs to (denormalized for display). */
  pillar: string;
  format: JobFormat;
  status: JobStatus;
  /**
   * Human-readable SLA line, e.g. "approve by Aug 2" or "publish Aug 5".
   * The verb ("approve" | "publish") + date are pre-composed for the mock.
   */
  sla: string;
}

/** One compositing layer of a creative document. Maps to mimik-contracts Layer (L1..L5). */
export interface Layer {
  id: string;
  /** Short label shown in the layer strip, e.g. "L1". */
  label: string;
  /** Whether this is the layer currently being edited. */
  active: boolean;
}

/** A creative document under review. Maps to mimik-contracts CreativeDoc + Layer[]. */
export interface CreativeDoc {
  id: string;
  /** Short caption rendered on the thumbnail, e.g. "SKIN BOOSTERS". */
  thumbnailLabel: string;
  layers: Layer[];
  /** Editor note, e.g. "Editing Layer 4 · headline & CTA". */
  note: string;
}

/** A tenant's client. Maps to mimik-contracts Client. */
export interface Client {
  id: string;
  name: string;
  /** Brand/vertical descriptor shown in the switcher chip, e.g. "Aesthetics". */
  vertical: string;
}

/** The active workspace label (agency/tenant display name). */
export const workspaceName = "Mimik Studio";

/** The currently selected client (drives the top-bar switcher chip). */
export const activeClient: Client = {
  id: "rcd-central",
  name: "RCD Central",
  vertical: "Aesthetics",
};

/** Content pillars for the active client's board. */
export const pillars: Pillar[] = [
  { id: "educational", label: "Educational", active: true },
  { id: "bts", label: "Behind the Scenes", active: false },
  { id: "promotional", label: "Promotional", active: false },
  { id: "social-proof", label: "Social Proof", active: false },
  { id: "custom", label: "+ Custom", active: false, custom: true },
];

/** This week's jobs awaiting approval. */
export const jobs: Job[] = [
  {
    id: "job-botox-myths",
    title: "Botox myths — 5 things nobody tells you",
    pillar: "Educational",
    format: "IG Reel",
    status: "in_review",
    sla: "approve by Aug 2",
  },
  {
    id: "job-meet-dr-aisha",
    title: "Meet Dr. Aisha",
    pillar: "Behind the Scenes",
    format: "IG Post",
    status: "at_risk",
    sla: "publish Aug 5",
  },
  {
    id: "job-skin-booster-launch",
    title: "Skin-booster launch",
    pillar: "Promotional",
    format: "Poster",
    status: "approved",
    sla: "publish Aug 9",
  },
];

/** The creative currently open in the review panel. */
export const reviewDoc: CreativeDoc = {
  id: "doc-skin-boosters",
  thumbnailLabel: "SKIN BOOSTERS",
  layers: [
    { id: "l1", label: "L1", active: false },
    { id: "l2", label: "L2", active: false },
    { id: "l3", label: "L3", active: false },
    { id: "l4", label: "L4", active: true },
    { id: "l5", label: "L5", active: false },
  ],
  note: "Editing Layer 4 · headline & CTA",
};

/** Sidebar navigation items. `active` marks the current route (Board). */
export interface NavItem {
  id: string;
  label: string;
  active: boolean;
}

export const navItems: NavItem[] = [
  { id: "clients", label: "Clients", active: false },
  { id: "board", label: "Board", active: true },
  { id: "calendar", label: "Calendar", active: false },
  { id: "creatives", label: "Creatives", active: false },
  { id: "brand-briefs", label: "Brand Briefs", active: false },
  { id: "settings", label: "Settings", active: false },
];
