/** Frontend view models derived from API responses. */

/** Tone of a colored pill/avatar — maps to tokens in design/tokens.css. */
export type TagTone = "blue" | "green" | "orange" | "pink" | "purple" | "gray";

/** Content pillar a job belongs to. */
export interface Pillar {
  id: string;
  label: string;
  active: boolean;
  custom?: boolean;
}

/** Review lifecycle status shown by the board. */
export type JobStatus = "in_review" | "at_risk" | "approved";

/** Publishing format shown by the board. */
export type JobFormat = "IG Reel" | "IG Post" | "Poster" | "Story" | "Carousel";

/** One production sub-step tracked on a job card. */
export interface ChecklistItem {
  id: string;
  label: string;
  done: boolean;
}

/** A team member assigned to a job. */
export interface Assignee {
  id: string;
  name: string;
  initials: string;
  tone: TagTone;
}

/** A single unit of work on the ops board. */
export interface Job {
  id: string;
  title: string;
  pillar: string;
  format: JobFormat;
  status: JobStatus;
  sla: string;
  checklist: ChecklistItem[];
  assignees: Assignee[];
  comments: number | null;
  attachments: number | null;
  atRisk?: boolean;
  generating?: boolean;
}

/** One compositing layer of a creative document. */
export interface Layer {
  id: string;
  label: string;
  active: boolean;
}

/** A creative document under review. */
export interface CreativeDoc {
  id: string;
  jobId: string;
  creativeDocId: string;
  thumbnailLabel: string;
  layers: Layer[];
  note: string;
}

/** A tenant client rendered in the top-bar client chip. */
export interface Client {
  id: string;
  name: string;
  vertical: string;
}

/** The active workspace label. */
export const workspaceName = "Mimik Studio";

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

export interface NavItem {
  id: "clients" | "board" | "calendar" | "creatives" | "brand-briefs" | "settings";
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

/** Geometric glyph shown next to a client in the secondary sidebar. */
export type ProjectShape = "circle" | "square" | "diamond" | "triangle";

export interface SidebarProject {
  id: string;
  name: string;
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
