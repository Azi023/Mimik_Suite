/**
 * Data facade for the board view.
 *
 * API responses are mapped into frontend view models. Empty responses, missing API
 * configuration, and request failures all return empty view data so the UI can render
 * truthful empty states.
 */

import {
  type ApiBrand,
  type ApiBoardCard,
  type ApiBoardResponse,
  type ApiClient,
  type ApiContentPillar,
  type ApiCreativeDoc,
  type ApiJob,
  type ApiJobStatus,
  fetchBoard,
  getBrand,
  getClient,
  isApiConfigured,
  listBriefs,
  listClients,
  listJobCreatives,
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
} from "./view-models";
import {
  DEFAULT_BRANDING,
  resolveTenantBranding,
  type TenantBranding,
} from "./branding";

/** Everything the board page renders. */
export interface BoardData {
  pillars: Pillar[];
  jobs: Job[];
  reviewDoc: CreativeDoc | null;
}

/** Everything the sidebar + top-bar client chip render. */
export interface SidebarData {
  groups: SidebarGroup[];
  activeClient: Client | null;
  /** The current tenant's white-label branding (product name, wordmark/logo, accent). */
  branding: TenantBranding;
}

/** Prefilled values for the client details + brand brief editor. */
export interface ClientBrandEditData {
  client: ApiClient;
  brand: ApiBrand | null;
}

/* ---------------------------------------------------------------------------
   API -> view-shape mapping.
--------------------------------------------------------------------------- */

/**
 * Collapse the API's 8-state job lifecycle into the board's three columns,
 * using red for attention, orange for work in review, and green for completed work.
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
 * Compose the card's SLA line: approved cards show the
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
    // Task/checklist, comment, and attachment feeds are not present in this response.
    checklist: [],
    assignees: toAssignees(card.job.assignee),
    comments: null,
    attachments: null,
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
  if (apiPillars.length === 0) {
    return [];
  }
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
export function toReviewDoc(doc: ApiCreativeDoc): CreativeDoc {
  const kinds = new Set(doc.manifest.layers.map((layer) => layer.kind));
  // Show the full L1..L5 strip; the active layer is L4 (message) when present, else the
  // last layer the manifest actually has.
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
    jobId: doc.job_id,
    creativeDocId: doc.id,
    thumbnailLabel: headline !== undefined ? headline.toUpperCase().slice(0, 24) : "PREVIEW",
    previewUrl: `/api/creatives/${encodeURIComponent(doc.id)}/preview`,
    svgUrl: `/api/creatives/${encodeURIComponent(doc.id)}/svg`,
    psdUrl: `/api/creatives/${encodeURIComponent(doc.id)}/psd`,
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

function emptyBoardData(): BoardData {
  return { pillars: [], jobs: [], reviewDoc: null };
}

/**
 * Best-effort: the latest creative of the first in-review job, for the review panel.
 * Missing creatives and request failures remain empty rather than inventing a preview.
 */
async function resolveReviewDoc(jobs: Job[], sessionToken?: string): Promise<CreativeDoc | null> {
  const candidate = jobs.find((job) => job.status === "in_review") ?? jobs[0];
  if (candidate === undefined) {
    return null;
  }
  try {
    const docs = await listJobCreatives(candidate.id, sessionToken);
    const latest = docs[docs.length - 1];
    return latest !== undefined ? toReviewDoc(latest) : null;
  } catch (error) {
    console.warn(`[mimik-web] Creative request failed; rendering an empty review (${String(error)})`);
    return null;
  }
}

/* ---------------------------------------------------------------------------
   Sidebar + top-bar client chip — API -> view-shape mapping.
--------------------------------------------------------------------------- */

/** Marker tones cycled for real client rows. */
const CLIENT_TONES: readonly TagTone[] = ["blue", "pink", "purple", "green", "orange"];

/** Geometric shapes cycled for real client rows. */
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
 * The API has no favorite flag, so only the truthful all-clients group is rendered.
 */
function toSidebarGroups(
  clients: ApiClient[],
  counts: ReadonlyMap<string, number>,
  selectedClientId?: string,
): SidebarGroup[] {
  const activeId = clients.some((client) => client.id === selectedClientId)
    ? selectedClientId
    : clients[0]?.id;
  const all = clients.map((client) =>
    toSidebarProject(client, counts.get(client.id) ?? 0, client.id === activeId),
  );
  return [{ id: "all-clients", label: "All clients", projects: all }];
}

function emptySidebarData(branding: TenantBranding = DEFAULT_BRANDING): SidebarData {
  return { groups: [], activeClient: null, branding };
}

/** Load the selected client and the brand attached to its latest brief. */
export async function getClientBrandEditData(
  clientId: string,
  sessionToken?: string,
): Promise<ClientBrandEditData | null> {
  if (!isApiConfigured(sessionToken)) {
    return null;
  }
  try {
    const [client, briefs] = await Promise.all([
      getClient(clientId, sessionToken),
      listBriefs(clientId, sessionToken),
    ]);
    const latestBrief = briefs[briefs.length - 1];
    const brand =
      latestBrief === undefined ? null : await getBrand(latestBrief.brand_id, sessionToken);
    return { client, brand };
  } catch (error) {
    console.warn(
      `[mimik-web] Client edit data unavailable; rendering a not-found state (${String(error)})`,
    );
    return null;
  }
}

/** The sidebar + top-bar client chip's API-backed data entrypoint. */
export async function getSidebarData(
  sessionToken?: string,
  selectedClientId?: string,
): Promise<SidebarData> {
  if (!isApiConfigured(sessionToken)) {
    return emptySidebarData();
  }
  try {
    const [clients, board, branding] = await Promise.all([
      listClients(sessionToken),
      fetchBoard(sessionToken),
      resolveTenantBranding(sessionToken),
    ]);
    if (clients.length === 0) {
      return emptySidebarData(branding);
    }
    const counts = jobCountsByClient(board);
    const activeClient = clients.find((client) => client.id === selectedClientId) ?? clients[0];
    return {
      groups: toSidebarGroups(clients, counts, selectedClientId),
      activeClient: toActiveClient(activeClient),
      branding,
    };
  } catch (error) {
    console.warn(
      `[mimik-web] API unreachable or returned an error; rendering an empty sidebar (${String(error)})`,
    );
    return emptySidebarData();
  }
}

/** The board page's API-backed data entrypoint. */
export async function getBoardData(sessionToken?: string): Promise<BoardData> {
  if (!isApiConfigured(sessionToken)) {
    return emptyBoardData();
  }
  try {
    const [board, apiPillars] = await Promise.all([
      fetchBoard(sessionToken),
      listPillars(undefined, sessionToken),
    ]);
    const pillarNameById = new Map(apiPillars.map((pillar) => [pillar.id, pillar.name]));
    const jobs = flattenBoard(board, pillarNameById);
    const pillars = toPillarChips(apiPillars);
    const reviewDoc = await resolveReviewDoc(jobs, sessionToken);
    return { pillars, jobs, reviewDoc };
  } catch (error) {
    console.warn(
      `[mimik-web] API unreachable or returned an error; rendering an empty board (${String(error)})`,
    );
    return emptyBoardData();
  }
}
