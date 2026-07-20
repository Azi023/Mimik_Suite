/**
 * Mock data for the Mimik Suite dashboard shell.
 *
 * These types MIRROR the mimik-contracts Pydantic shapes (the shared vocabulary
 * described in the data-model spine: Client → Brand → Brief → Job → CreativeDoc → Layer).
 * They are intentionally a frontend-local subset — no API calls happen here yet.
 * When the API phase lands, these interfaces get replaced by generated contract types.
 */

/** Tone of a colored pill/avatar — maps 1:1 to `--tag-*` tokens in design/tokens.css. */
export type TagTone = "blue" | "green" | "orange" | "pink" | "purple" | "gray";

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

/** One production sub-step tracked on a job card. Maps to mimik-contracts Task. */
export interface ChecklistItem {
  id: string;
  label: string;
  done: boolean;
}

/** A team member assigned to a job (avatar-stack rendering data). */
export interface Assignee {
  id: string;
  name: string;
  initials: string;
  tone: TagTone;
}

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
  /** Production sub-steps shown as the card checklist. */
  checklist: ChecklistItem[];
  /** Team members on the card's avatar stack. */
  assignees: Assignee[];
  /** Comment count shown in the card footer. */
  comments: number;
  /** Attachment count shown in the card footer. */
  attachments: number;
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
  /**
   * API Job id backing this creative — set on the live path (`lib/data.ts`), undefined
   * for mocks. Without it the review panel renders but submits show the offline note.
   */
  jobId?: string;
  /** API CreativeDoc id — same live/mock split as `jobId`. */
  creativeDocId?: string;
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

/* ---------------------------------------------------------------------------
   Tag tones — which `--tag-*` color a pill takes, per format / pillar.
--------------------------------------------------------------------------- */

export const FORMAT_TONE: Record<JobFormat, TagTone> = {
  "IG Reel": "purple",
  "IG Post": "blue",
  Poster: "orange",
  Story: "pink",
  Carousel: "green",
};

export const PILLAR_TONE: Record<string, TagTone> = {
  Educational: "blue",
  "Behind the Scenes": "orange",
  Promotional: "pink",
  "Social Proof": "green",
};

/* ---------------------------------------------------------------------------
   Team (drives avatar stacks in the top bar + job cards).
--------------------------------------------------------------------------- */

export const team: Assignee[] = [
  { id: "aisha", name: "Aisha Khan", initials: "AK", tone: "blue" },
  { id: "ravi", name: "Ravi Perera", initials: "RP", tone: "purple" },
  { id: "maya", name: "Maya Silva", initials: "MS", tone: "pink" },
  { id: "dinesh", name: "Dinesh Fernando", initials: "DF", tone: "green" },
  { id: "zara", name: "Zara Ismail", initials: "ZI", tone: "orange" },
];

const [aisha, ravi, maya, dinesh, zara] = team;

/** Content pillars for the active client's board. */
export const pillars: Pillar[] = [
  { id: "educational", label: "Educational", active: true },
  { id: "bts", label: "Behind the Scenes", active: false },
  { id: "promotional", label: "Promotional", active: false },
  { id: "social-proof", label: "Social Proof", active: false },
  { id: "custom", label: "+ Custom", active: false, custom: true },
];

/* ---------------------------------------------------------------------------
   Kanban columns — status dot color follows the reference:
   red = needs attention, orange = in progress, green = complete.
--------------------------------------------------------------------------- */

export interface BoardColumn {
  status: JobStatus;
  title: string;
  dot: "new" | "progress" | "done";
}

export const boardColumns: BoardColumn[] = [
  { status: "at_risk", title: "At risk", dot: "new" },
  { status: "in_review", title: "In review", dot: "progress" },
  { status: "approved", title: "Approved", dot: "done" },
];

/** This week's jobs awaiting approval. */
export const jobs: Job[] = [
  {
    id: "job-meet-dr-aisha",
    title: "Meet Dr. Aisha",
    pillar: "Behind the Scenes",
    format: "IG Post",
    status: "at_risk",
    sla: "publish Aug 5",
    checklist: [
      { id: "c1", label: "Shoot approved", done: true },
      { id: "c2", label: "Caption draft", done: false },
    ],
    assignees: [maya, ravi],
    comments: 4,
    attachments: 1,
  },
  {
    id: "job-lip-filler-aftercare",
    title: "Lip-filler aftercare — do's & don'ts",
    pillar: "Educational",
    format: "Story",
    status: "at_risk",
    sla: "approve by Aug 3",
    checklist: [
      { id: "c1", label: "Clinical review", done: false },
      { id: "c2", label: "Story frames composited", done: true },
    ],
    assignees: [aisha],
    comments: 2,
    attachments: 0,
  },
  {
    id: "job-botox-myths",
    title: "Botox myths — 5 things nobody tells you",
    pillar: "Educational",
    format: "IG Reel",
    status: "in_review",
    sla: "approve by Aug 2",
    checklist: [
      { id: "c1", label: "Hook + script locked", done: true },
      { id: "c2", label: "L4 headline & CTA", done: true },
      { id: "c3", label: "Brand-QA pass", done: false },
    ],
    assignees: [aisha, zara],
    comments: 3,
    attachments: 2,
  },
  {
    id: "job-glow-season",
    title: "Glow season — hydrafacial carousel",
    pillar: "Promotional",
    format: "Carousel",
    status: "in_review",
    sla: "approve by Aug 4",
    checklist: [
      { id: "c1", label: "5 slides composited", done: true },
      { id: "c2", label: "Offer copy locked", done: false },
    ],
    assignees: [ravi, maya, dinesh],
    comments: 1,
    attachments: 3,
  },
  {
    id: "job-testimonial-nadia",
    title: "Client story — Nadia's 3-month glow-up",
    pillar: "Social Proof",
    format: "IG Post",
    status: "in_review",
    sla: "approve by Aug 6",
    checklist: [],
    assignees: [zara],
    comments: 5,
    attachments: 1,
  },
  {
    id: "job-skin-booster-launch",
    title: "Skin-booster launch",
    pillar: "Promotional",
    format: "Poster",
    status: "approved",
    sla: "publish Aug 9",
    checklist: [
      { id: "c1", label: "Final art delivered", done: true },
      { id: "c2", label: "Client sign-off", done: true },
    ],
    assignees: [aisha, ravi],
    comments: 8,
    attachments: 2,
  },
  {
    id: "job-clinic-tour",
    title: "Inside the clinic — Saturday tour",
    pillar: "Behind the Scenes",
    format: "IG Reel",
    status: "approved",
    sla: "publish Aug 12",
    checklist: [{ id: "c1", label: "Voiceover mixed", done: true }],
    assignees: [dinesh, maya],
    comments: 2,
    attachments: 1,
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

/**
 * Derive a display-only CreativeDoc for a job the review panel hasn't fetched a
 * real creative for (e.g. clicking any card other than the server-resolved one).
 *
 * It carries NO `jobId`/`creativeDocId`, so the panel keeps the honest offline
 * note on submit rather than posting a guessed id. The `reviewDoc` a job's real
 * creative maps to (via `lib/data.ts`) is preferred whenever it is available.
 */
export function jobToReviewDoc(job: Job): CreativeDoc {
  return {
    id: `preview-${job.id}`,
    thumbnailLabel: job.title.toUpperCase().slice(0, 24),
    layers: [
      { id: `${job.id}-l1`, label: "L1", active: false },
      { id: `${job.id}-l2`, label: "L2", active: false },
      { id: `${job.id}-l3`, label: "L3", active: false },
      { id: `${job.id}-l4`, label: "L4", active: true },
      { id: `${job.id}-l5`, label: "L5", active: false },
    ],
    note: `${job.pillar} · ${job.format} — Editing Layer 4`,
  };
}

/* ---------------------------------------------------------------------------
   Navigation — icon rail (glyphs resolved in Sidebar) + client list groups.
--------------------------------------------------------------------------- */

/** Sidebar navigation items. `active` marks the current route (Board). */
export interface NavItem {
  id: string;
  label: string;
  active: boolean;
  /** Small red notification badge on the rail glyph. */
  badge?: number;
}

export const navItems: NavItem[] = [
  { id: "clients", label: "Clients", active: false },
  { id: "board", label: "Board", active: true, badge: 2 },
  { id: "calendar", label: "Calendar", active: false },
  { id: "creatives", label: "Creatives", active: false },
  { id: "brand-briefs", label: "Brand Briefs", active: false },
  { id: "settings", label: "Settings", active: false },
];

/** Geometric glyph shown next to a client in the secondary sidebar. */
export type ProjectShape = "circle" | "square" | "diamond" | "triangle";

/** A client entry in the secondary sidebar (reference: "project" rows). */
export interface SidebarProject {
  id: string;
  name: string;
  /** Open-job count badge. 0 hides the badge. */
  count: number;
  tone: TagTone;
  shape: ProjectShape;
  active: boolean;
}

export interface SidebarGroup {
  id: string;
  label: string;
  projects: SidebarProject[];
}

export const sidebarGroups: SidebarGroup[] = [
  {
    id: "favorites",
    label: "Favorites",
    projects: [
      { id: "rcd-central", name: "RCD Central", count: 7, tone: "blue", shape: "circle", active: true },
      { id: "jasmine-beauty", name: "Jasmine Beauty", count: 4, tone: "pink", shape: "diamond", active: false },
    ],
  },
  {
    id: "all-clients",
    label: "All clients",
    projects: [
      { id: "rcd-central", name: "RCD Central", count: 7, tone: "blue", shape: "circle", active: true },
      { id: "jasmine-beauty", name: "Jasmine Beauty", count: 4, tone: "pink", shape: "diamond", active: false },
      { id: "lumiere-skin", name: "Lumière Skin", count: 3, tone: "purple", shape: "square", active: false },
      { id: "apex-dental", name: "Apex Dental", count: 2, tone: "green", shape: "triangle", active: false },
      { id: "kandy-wellness", name: "Kandy Wellness", count: 5, tone: "orange", shape: "circle", active: false },
    ],
  },
];
