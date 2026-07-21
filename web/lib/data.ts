/**
 * Data facade for the board view.
 *
 * Exposes the SAME view shapes `lib/mock.ts` defines (Job, Pillar, CreativeDoc), sourced
 * live from the FastAPI backend when it is configured AND reachable, and from the mocks
 * otherwise — the board never renders blank/broken because the API is down.
 *
 * Live path gate (see `isApiConfigured` in lib/api.ts): `NEXT_PUBLIC_API_URL` must be set
 * AND a bearer must be resolvable — either the per-user Supabase session token threaded in
 * from the server component (`lib/session.getSessionToken`) or the DEV-ONLY dev token. Any
 * fetch/parse failure inside the live path also drops to the mock set (with a server-side
 * console.warn so the fallback is observable).
 *
 * The `sessionToken` argument is the real per-user Supabase bearer. When present it flows
 * through every API call so fetches run as the authenticated user (tenant-scoped by the
 * backend); when absent, the dev-token fallback applies.
 */

import {
  type ApiBoardCard,
  type ApiBoardResponse,
  type ApiClient,
  type ApiContentPillar,
  type ApiCreativeDoc,
  type ApiJob,
  type ApiJobStatus,
  fetchBoard,
  isApiConfigured,
  listClients,
  listCreatives,
  listPillars,
} from "./api";
import {
  type Assignee,
  type Client,
  type CreativeDoc,
  type Job,
  type JobFormat,
  type JobStatus,
  type Layer,
  type Pillar,
  type ProjectShape,
  type SidebarGroup,
  type SidebarProject,
  type TagTone,
  activeClient as mockActiveClient,
  jobs as mockJobs,
  pillars as mockPillars,
  reviewDoc as mockReviewDoc,
  sidebarGroups as mockSidebarGroups,
} from "./mock";

/** Everything the board page renders, in the mock's view shapes. */
export interface BoardData {
  pillars: Pillar[];
  jobs: Job[];
  reviewDoc: CreativeDoc;
}

/** Everything the sidebar + top-bar client chip render, in the mock's view shapes. */
export interface SidebarData {
  groups: SidebarGroup[];
  activeClient: Client;
}

/* ---------------------------------------------------------------------------
   API -> view-shape mapping.
--------------------------------------------------------------------------- */

/**
 * Collapse the API's 8-state job lifecycle into the board's three columns,
 * keeping the mock semantics: red = needs attention (SLA breached or blocked),
 * orange = moving through review, green = done.
 */
function toBoardStatus(status: ApiJobStatus, atRisk: boolean): JobStatus {
  if (status === "approved" || status === "delivered" || status === "archived") {
    return "approved";
  }
  if (atRisk || status === "blocked") {
    return "at_risk";
  }
  return "in_review";
}

/** API format presets (mimik_contracts.formats.PRESETS keys) -> the board's display labels. */
const FORMAT_LABEL: Record<string, JobFormat> = {
  ig_post: "IG Post",
  ig_story: "Story",
  fb_post: "IG Post",
  poster_a: "Poster",
  carousel: "Carousel",
};

function toFormat(formatKey: string): JobFormat {
  return FORMAT_LABEL[formatKey] ?? "IG Post";
}

function formatDay(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/**
 * Compose the card's SLA line with the mock's semantics: approved cards show the
 * publish date; everything else shows the approve-by deadline (publish_date minus
 * the approval lead buffer — mirrors Job.approve_by in mimik-contracts).
 */
function toSla(job: ApiJob, boardStatus: JobStatus): string {
  if (job.publish_date === null) {
    return "unscheduled";
  }
  if (boardStatus === "approved") {
    return `publish ${formatDay(job.publish_date)}`;
  }
  const publish = new Date(job.publish_date);
  const approveBy = new Date(publish.getTime() - job.approval_lead_days * 86_400_000);
  return `approve by ${formatDay(approveBy.toISOString())}`;
}

const ASSIGNEE_TONES: readonly TagTone[] = ["blue", "purple", "pink", "green", "orange"];

/** Stable, deterministic tone per assignee name (same name -> same avatar color). */
function toneFor(name: string): TagTone {
  let hash = 0;
  for (let i = 0; i < name.length; i += 1) {
    hash = (hash * 31 + name.charCodeAt(i)) % 997;
  }
  return ASSIGNEE_TONES[hash % ASSIGNEE_TONES.length];
}

/** The API stores a single free-text assignee; render it as a one-avatar stack. */
function toAssignees(assignee: string | null): Assignee[] {
  if (assignee === null || assignee.trim() === "") {
    return [];
  }
  const words = assignee.trim().split(/\s+/);
  const initials = words
    .slice(0, 2)
    .map((word) => word.charAt(0).toUpperCase())
    .join("");
  return [
    {
      id: assignee.trim().toLowerCase().replace(/\s+/g, "-"),
      name: assignee.trim(),
      initials,
      tone: toneFor(assignee.trim()),
    },
  ];
}

function toJob(card: ApiBoardCard, pillarNameById: ReadonlyMap<string, string>): Job {
  const status = toBoardStatus(card.job.status, card.at_risk);
  const pillarName =
    card.job.pillar_id !== null ? (pillarNameById.get(card.job.pillar_id) ?? "General") : "General";
  return {
    id: card.job.id,
    title: card.job.title,
    pillar: pillarName,
    format: toFormat(card.job.format_key),
    status,
    sla: toSla(card.job, status),
    // Task/checklist, comment, and attachment feeds are later API phases — render empty for now.
    checklist: [],
    assignees: toAssignees(card.job.assignee),
    comments: 0,
    attachments: 0,
    atRisk: card.at_risk,
    generating: card.job.status === "generating",
  };
}

/** Flatten the board response's status columns into one list, preserving API card order. */
function flattenBoard(
  board: ApiBoardResponse,
  pillarNameById: ReadonlyMap<string, string>,
): Job[] {
  return Object.values(board.columns)
    .flat()
    .map((card) => toJob(card, pillarNameById));
}

/** Map API pillars into filter chips: first chip active, "+ Custom" affordance appended. */
function toPillarChips(apiPillars: ApiContentPillar[]): Pillar[] {
  const chips: Pillar[] = apiPillars.map((pillar, index) => ({
    id: pillar.id,
    label: pillar.name,
    active: index === 0,
  }));
  chips.push({ id: "custom", label: "+ Custom", active: false, custom: true });
  return chips;
}

const LAYER_ORDER = ["L1_base", "L2_concept", "L3_scaffold", "L4_message", "L5_finish"] as const;

/** Map a persisted CreativeDoc manifest into the review panel's layer-strip shape. */
function toReviewDoc(doc: ApiCreativeDoc): CreativeDoc {
  const kinds = new Set(doc.manifest.layers.map((layer) => layer.kind));
  // Show the full L1..L5 strip; the active layer is L4 (message) when present, else the
  // last layer the manifest actually has — mirrors the mock's "editing L4" semantics.
  const lastPresent = [...LAYER_ORDER].reverse().find((kind) => kinds.has(kind));
  const activeKind = kinds.has("L4_message") ? "L4_message" : lastPresent;
  const layers: Layer[] = LAYER_ORDER.map((kind, index) => ({
    id: kind,
    label: `L${index + 1}`,
    active: kind === activeKind,
  }));
  const activeIndex = activeKind !== undefined ? LAYER_ORDER.indexOf(activeKind) : -1;
  const headline = doc.manifest.copy_block?.headline;
  return {
    id: doc.id,
    // Real API ids — the review panel needs both to POST /approvals. Mock docs leave
    // them undefined, so the panel degrades to the inline offline note on submit.
    jobId: doc.job_id,
    creativeDocId: doc.id,
    thumbnailLabel: headline !== undefined ? headline.toUpperCase().slice(0, 24) : "PREVIEW",
    layers,
    note:
      activeIndex >= 0
        ? `Editing Layer ${activeIndex + 1} · ${doc.manifest.template_key ?? doc.manifest.format_key}`
        : `Template ${doc.manifest.template_key ?? doc.manifest.format_key}`,
  };
}

/* ---------------------------------------------------------------------------
   Facade.
--------------------------------------------------------------------------- */

function mockBoardData(): BoardData {
  return { pillars: mockPillars, jobs: mockJobs, reviewDoc: mockReviewDoc };
}

/**
 * Best-effort: the latest creative of the first in-review job, for the review panel.
 * Falls back to the mock review doc when no creative exists yet (or the call fails) —
 * the panel is a preview surface, not a data-critical one.
 */
async function resolveReviewDoc(jobs: Job[], sessionToken?: string): Promise<CreativeDoc> {
  const candidate = jobs.find((job) => job.status === "in_review") ?? jobs[0];
  if (candidate === undefined) {
    return mockReviewDoc;
  }
  try {
    const docs = await listCreatives(candidate.id, sessionToken);
    const latest = docs[docs.length - 1];
    return latest !== undefined ? toReviewDoc(latest) : mockReviewDoc;
  } catch {
    return mockReviewDoc;
  }
}

/* ---------------------------------------------------------------------------
   Sidebar + top-bar client chip — API -> view-shape mapping.
--------------------------------------------------------------------------- */

/** Marker tones cycled for real client rows (same palette the mock rows draw from). */
const CLIENT_TONES: readonly TagTone[] = ["blue", "pink", "purple", "green", "orange"];

/** Geometric shapes cycled for real client rows (mirrors the mock's marker variety). */
const CLIENT_SHAPES: readonly ProjectShape[] = ["circle", "diamond", "square", "triangle"];

/** Stable, deterministic index from a client id (same id -> same tone/shape every render). */
function hashIndex(id: string, modulo: number): number {
  let hash = 0;
  for (let i = 0; i < id.length; i += 1) {
    hash = (hash * 31 + id.charCodeAt(i)) % 100_003;
  }
  return hash % modulo;
}

/** Count jobs per client_id straight off the board response — no per-client fetch (N+1). */
function jobCountsByClient(board: ApiBoardResponse): ReadonlyMap<string, number> {
  const counts = new Map<string, number>();
  for (const card of Object.values(board.columns).flat()) {
    const id = card.job.client_id;
    counts.set(id, (counts.get(id) ?? 0) + 1);
  }
  return counts;
}

/** Map one API client + its job count into a sidebar row. */
function toSidebarProject(
  client: ApiClient,
  count: number,
  active: boolean,
): SidebarProject {
  return {
    id: client.id,
    name: client.name,
    count,
    tone: CLIENT_TONES[hashIndex(client.id, CLIENT_TONES.length)],
    shape: CLIENT_SHAPES[hashIndex(client.id, CLIENT_SHAPES.length)],
    active,
  };
}

/** Map an API client into the top-bar switcher chip shape (industry -> vertical). */
function toActiveClient(client: ApiClient): Client {
  const industry = client.industry?.trim();
  return {
    id: client.id,
    name: client.name,
    vertical: industry !== undefined && industry !== "" ? industry : "Client",
  };
}

/**
 * Build the sidebar groups from the real client list.
 *
 * The `mimik-contracts` Client model has NO "favorite" flag, so we can't source a
 * real favorites set. Choice: the first client (the one the chip + board reflect)
 * is pinned to "Favorites" as the working client; every client — including that
 * one — is listed under "All clients". This keeps both groups populated and the
 * grouping structure the sidebar already renders, without inventing a flag.
 */
function toSidebarGroups(
  clients: ApiClient[],
  counts: ReadonlyMap<string, number>,
): SidebarGroup[] {
  const activeId = clients[0]?.id;
  const all = clients.map((client) =>
    toSidebarProject(client, counts.get(client.id) ?? 0, client.id === activeId),
  );
  const favorites = all.slice(0, 1);
  return [
    { id: "favorites", label: "Favorites", projects: favorites },
    { id: "all-clients", label: "All clients", projects: all },
  ];
}

function mockSidebarData(): SidebarData {
  return { groups: mockSidebarGroups, activeClient: mockActiveClient };
}

/**
 * The sidebar + top-bar client chip's single data entrypoint. Live API when
 * configured + reachable, mock set otherwise — identical shapes either way, so
 * the chrome renders the same and never blanks out when the API is down.
 */
export async function getSidebarData(sessionToken?: string): Promise<SidebarData> {
  if (!isApiConfigured(sessionToken)) {
    return mockSidebarData();
  }
  try {
    const [clients, board] = await Promise.all([
      listClients(sessionToken),
      fetchBoard(sessionToken),
    ]);
    // An empty tenant (no clients yet) still gets the full demo sidebar rather
    // than a lone empty group — the chrome must never look broken.
    if (clients.length === 0) {
      return mockSidebarData();
    }
    const counts = jobCountsByClient(board);
    return {
      groups: toSidebarGroups(clients, counts),
      activeClient: toActiveClient(clients[0]),
    };
  } catch (error) {
    console.warn(
      `[mimik-web] API unreachable or returned an error — rendering mock sidebar (${String(error)})`,
    );
    return mockSidebarData();
  }
}

/**
 * The board page's single data entrypoint. Live API when configured + reachable,
 * mock set otherwise — identical shapes either way, so the board renders the same.
 */
export async function getBoardData(sessionToken?: string): Promise<BoardData> {
  if (!isApiConfigured(sessionToken)) {
    return mockBoardData();
  }
  try {
    const [board, apiPillars] = await Promise.all([
      fetchBoard(sessionToken),
      listPillars(undefined, sessionToken),
    ]);
    const pillarNameById = new Map(apiPillars.map((pillar) => [pillar.id, pillar.name]));
    const jobs = flattenBoard(board, pillarNameById);
    // An empty tenant (no pillars yet) still gets the full demo chip row rather than
    // a lone "+ Custom" — the board must never look broken.
    const pillars = apiPillars.length > 0 ? toPillarChips(apiPillars) : mockPillars;
    const reviewDoc = await resolveReviewDoc(jobs, sessionToken);
    return { pillars, jobs, reviewDoc };
  } catch (error) {
    console.warn(
      `[mimik-web] API unreachable or returned an error — rendering mock board (${String(error)})`,
    );
    return mockBoardData();
  }
}
