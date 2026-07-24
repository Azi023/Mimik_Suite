/**
 * Typed client for the Mimik Suite FastAPI backend.
 *
 * The interfaces below mirror the `mimik-contracts` Pydantic models EXACTLY as they
 * serialize on the wire (snake_case, ISO datetime strings). They are the raw API
 * shapes — `lib/data.ts` maps them into the view shapes the board components render.
 *
 * Configuration (env, read at build/render time):
 * - `NEXT_PUBLIC_API_URL`   — API origin. Defaults to `http://localhost:8000`.
 * - `NEXT_PUBLIC_DEV_TOKEN` — a first-party HS256 bootstrap bearer token minted by
 *   `POST /tenants` (see api/core/auth.py). This is a DEV-ONLY convenience: a
 *   `NEXT_PUBLIC_*` value is inlined into the client bundle, so it must never carry a
 *   production credential.
 *
 * Bearer precedence (see `resolveBearer`): a per-request Supabase session token
 * (threaded server-side from `lib/session.getSessionToken`) is used when present;
 * the dev bootstrap token is the fallback ONLY. Real user auth is the Supabase path
 * — the backend already accepts it, discriminated by `iss` (api/core/auth.py).
 */

import type { ApiCanvasRevision } from "@/components/canvas/canvas-types";

/* ---------------------------------------------------------------------------
   Wire shapes — mimik-contracts models as JSON.
--------------------------------------------------------------------------- */

/** mimik_contracts.enums.JobStatus */
export type ApiJobStatus =
  | "draft"
  | "generating"
  | "internal_review"
  | "client_review"
  | "approved"
  | "delivered"
  | "archived"
  | "blocked";

/** mimik_contracts.enums.LayerKind */
export type ApiLayerKind =
  | "L1_base"
  | "L2_concept"
  | "L3_scaffold"
  | "L4_message"
  | "L5_finish";

/** mimik_contracts.org.Client */
export interface ApiClient {
  id: string;
  created_at: string;
  tenant_id: string;
  name: string;
  contact_email: string | null;
  phone: string | null;
  industry: string | null;
  website_url: string | null;
  instagram: string | null;
  notes: string | null;
}

/** mimik_contracts.brand.ColorRole */
export interface ApiColorRole {
  name: string;
  hex: string;
  usage: string | null;
}

/** mimik_contracts.brand.Typography */
export interface ApiTypography {
  heading_font: string | null;
  body_font: string | null;
  hierarchy: string[];
}

/** mimik_contracts.brand.LogoSpec */
export interface ApiLogoSpec {
  ref: string | null;
  clear_space: string | null;
  min_size_px: number | null;
  assessment: string | null;
}

/** mimik_contracts.brand.Reference */
export interface ApiReference {
  url: string;
  source: string | null;
  fit_score: number | null;
  note: string | null;
}

/** mimik_contracts.enums.LogoPlacement — the 9-anchor grid the logo defaults to. */
export type ApiLogoPlacement =
  | "top_left"
  | "top_center"
  | "top_right"
  | "middle_left"
  | "center"
  | "middle_right"
  | "bottom_left"
  | "bottom_center"
  | "bottom_right";

/** mimik_contracts.brand.Margins — safe-zone margins as % of the shortest edge, per edge. */
export interface ApiMargins {
  top: number;
  right: number;
  bottom: number;
  left: number;
}

/** mimik_contracts.brand.LayoutGuide — one draggable alignment guide (x = vertical, y = horizontal). */
export interface ApiLayoutGuide {
  axis: "x" | "y";
  pos: number;
}

/** mimik_contracts.brand.BrandLayout — the brand's default layout rules. */
export interface ApiBrandLayout {
  logo_placement: ApiLogoPlacement;
  logo_scale: number;
  margins: ApiMargins;
  header: boolean;
  footer: boolean;
  grid_columns: number;
  grid_gutter_pct: number;
  guides: ApiLayoutGuide[];
  show_guides: boolean;
}

/** mimik_contracts.brand.BrandTokens. `layout` is optional on the wire — the backend fills the
 *  default when omitted (e.g. at brand creation), so older payloads stay valid. */
export interface ApiBrandTokens {
  colors: ApiColorRole[];
  typography: ApiTypography;
  logo: ApiLogoSpec;
  layout?: ApiBrandLayout;
}

/** mimik_contracts.brand.Brand */
export interface ApiBrand {
  id: string;
  created_at: string;
  tenant_id: string;
  client_id: string;
  name: string;
  slug: string;
  niche: string | null;
  services: string[];
  target_audience: string | null;
  brand_voice: string | null;
  tone_keywords: string[];
  dos: string[];
  donts: string[];
  handles: Record<string, string>;
  tokens: ApiBrandTokens;
  imagery_style: string | null;
  references: ApiReference[];
}

/** mimik_contracts.job.Job */
export interface ApiJob {
  id: string;
  created_at: string;
  tenant_id: string;
  client_id: string;
  brand_id: string;
  brief_id: string | null;
  /** Which content pillar this piece belongs to (planning phase). */
  pillar_id: string | null;
  title: string;
  /** Key into the format presets, e.g. "ig_post" | "ig_story" | "poster_a" | "carousel". */
  format_key: string;
  /** ISO datetime or null when unscheduled. */
  publish_date: string | null;
  approval_lead_days: number;
  assignee: string | null;
  status: ApiJobStatus;
  /** ISO datetime stamped while the job sits in GENERATING; null otherwise. */
  generation_started_at: string | null;
}

/** mimik_contracts.pillars.ContentPillar */
export interface ApiContentPillar {
  id: string;
  created_at: string;
  tenant_id: string;
  client_id: string;
  name: string;
  description: string | null;
  is_custom: boolean;
}

/** mimik_contracts.creative.CopyBlock */
export interface ApiCopyBlock {
  headline: string;
  subhead: string | null;
  cta: string | null;
  language: string;
  status: "draft" | "approved" | "edited";
  source_model: string | null;
  prompt_ref: string | null;
}

/** mimik_contracts.creative.LayerRecipe */
export interface ApiLayerRecipe {
  prompt: string | null;
  backend: string | null;
  model: string | null;
  reference_urls: string[];
  params: Record<string, unknown>;
}

/** mimik_contracts.creative.Layer */
export interface ApiLayer {
  kind: ApiLayerKind;
  recipe: ApiLayerRecipe;
  artifact_ref: string | null;
  version: number;
}

/** mimik_contracts.creative.CreativeManifest */
export interface ApiCreativeManifest {
  format_key: string;
  brand_id: string;
  template_key: string | null;
  copy_block: ApiCopyBlock | null;
  layers: ApiLayer[];
  /** Per-creative layout override; absent/null = inherit the brand default. */
  layout?: ApiBrandLayout | null;
}

/** mimik_contracts.creative.CreativeDoc */
export interface ApiCreativeDoc {
  id: string;
  created_at: string;
  tenant_id: string;
  job_id: string;
  manifest: ApiCreativeManifest;
  version: number;
}

/** POST /clients/{id}/creatives:generate response. */
export interface ApiGeneratedCreative {
  creative: ApiCreativeDoc;
  preview_url: string;
  svg_url: string;
  psd_url: string;
}

/** mimik_contracts.canvas.CreativeVersionInfo — one persisted version on a job's history. */
export interface ApiCreativeVersionInfo {
  creative_id: string;
  version: number;
  parent_id: string | null;
  created_at: string;
  created_by: ApiActor | null;
  note: string | null;
  /** Backend artifact path — the web app proxies via /api/creatives/{id}/preview instead. */
  preview_url: string;
  svg_url: string;
}

/** GET /creatives/{id}/versions — the creative's job-wide persisted version history. */
export interface ApiVersionHistory {
  job_id: string;
  versions: ApiCreativeVersionInfo[];
}

/** mimik_contracts.enums.RevisionZone — WHERE on a creative a change request points. */
export type ApiRevisionZone =
  | "headline"
  | "subhead"
  | "cta"
  | "logo"
  | "imagery"
  | "background"
  | "layout"
  | "other";

/** mimik_contracts.workflow.RevisionTarget — one pin-pointed change ask (WHERE + WHAT). */
export interface ApprovalTarget {
  zone: ApiRevisionZone;
  layer?: ApiLayerKind;
  /** Reviewer freeform text, 1..500 chars (contract-capped). */
  instruction: string;
}

/** mimik_contracts.enums.ApprovalAction — the subset the dashboard submits. */
export type ApprovalActionKind = "approve" | "request_change" | "comment";

/** POST /approvals request body (api.routers.approvals.ApprovalRequest). */
export interface ApprovalSubmission {
  job_id: string;
  creative_doc_id: string;
  action: ApprovalActionKind;
  note?: string;
  /** Reject-reason taxonomy tag (feeds the learning loop), e.g. "tone_off". */
  reason_tag?: string;
  /** Pin-pointed change asks — only valid with action="request_change", max 10. */
  targets?: ApprovalTarget[];
}

/** mimik_contracts.workflow.Actor */
export interface ApiActor {
  id: string;
  role: string;
  name: string | null;
}

/** mimik_contracts.workflow.Approval */
export interface ApiApproval {
  id: string;
  created_at: string;
  tenant_id: string;
  job_id: string;
  creative_doc_id: string;
  actor: ApiActor;
  action: string;
  note: string | null;
  targets: ApprovalTarget[];
}

/** mimik_contracts.workflow.Task */
export interface ApiTask {
  id: string;
  created_at: string;
  tenant_id: string;
  client_id: string;
  job_id: string | null;
  type: string;
  status: string;
  title: string;
  detail: string | null;
  created_by: ApiActor;
  assignee: string | null;
  notified: boolean;
  updated_at: string | null;
}

/**
 * POST /approvals response: the recorded approval, the resulting job state, and — on
 * request_change / comment — the ops task the action spawned.
 */
export interface ApprovalResponse {
  approval: ApiApproval;
  job?: ApiJob;
  task?: ApiTask;
}

/** mimik_contracts.workflow.Delivery — one archived-to-Drive record on a job's audit trail. */
export interface ApiDelivery {
  id: string;
  created_at: string;
  tenant_id: string;
  job_id: string;
  creative_doc_id: string;
  drive_path: string;
  delivered_at: string | null;
}

/** GET /jobs/{id}/approvals — the job's full audit trail: every action + every delivery. */
export interface JobAuditTrail {
  approvals: ApiApproval[];
  deliveries: ApiDelivery[];
}

/** One card on GET /ops/board — the serialized Job plus the computed at-risk flag. */
export interface ApiBoardCard {
  job: ApiJob;
  at_risk: boolean;
}

/** GET /ops/board — every JobStatus key is present even when its column is empty. */
export interface ApiBoardResponse {
  columns: Record<ApiJobStatus, ApiBoardCard[]>;
}

/* ---------------------------------------------------------------------------
   Client.
--------------------------------------------------------------------------- */

const DEFAULT_BASE_URL = "http://localhost:8000";

/** Per-request timeout — the board must fall back fast when the API is down. */
const REQUEST_TIMEOUT_MS = 3000;
/** Rendering and PSD assembly launch a compositor, so mutations/downloads get a real ceiling. */
const CREATIVE_TIMEOUT_MS = 240000;

/** API origin, from `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`). */
export function getApiBaseUrl(): string {
  const url = process.env.NEXT_PUBLIC_API_URL;
  return url !== undefined && url !== "" ? url.replace(/\/+$/, "") : DEFAULT_BASE_URL;
}

/** The dev bootstrap bearer token, if configured. */
function getDevToken(): string | undefined {
  const token = process.env.NEXT_PUBLIC_DEV_TOKEN;
  return token !== undefined && token !== "" ? token : undefined;
}

/**
 * The bearer to send on API calls, in precedence order:
 *   1. the caller-supplied Supabase session token (real per-user auth), when present.
 *   2. the DEV-ONLY `NEXT_PUBLIC_DEV_TOKEN` bootstrap token, as a fallback.
 * Returns `undefined` when neither exists — the request goes out unauthenticated and
 * callers handle the resulting error without substituting records.
 */
function resolveBearer(sessionToken?: string): string | undefined {
  if (sessionToken !== undefined && sessionToken !== "") {
    return sessionToken;
  }
  return getDevToken();
}

/**
 * True when `NEXT_PUBLIC_API_URL` is set AND some bearer is resolvable — either the
 * caller-supplied Supabase session token or the dev bootstrap token. This is the gate
 * `lib/data.ts` uses before attempting live fetches; without it the data facade returns
 * empty view data and never touches the network.
 */
export function isApiConfigured(sessionToken?: string): boolean {
  const url = process.env.NEXT_PUBLIC_API_URL;
  return url !== undefined && url !== "" && resolveBearer(sessionToken) !== undefined;
}

/** One FastAPI/Pydantic validation item, normalized for frontend consumers. */
export interface ApiValidationDetail {
  loc: string[];
  msg: string;
}

/** Raised for non-2xx responses so callers can distinguish API errors from network errors. */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: ApiValidationDetail[] | undefined;

  constructor(status: number, message: string, detail?: ApiValidationDetail[]) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function apiGet<T>(path: string, sessionToken?: string): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const token = resolveBearer(sessionToken);
  if (token !== undefined) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    headers,
    cache: "no-store",
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });
  if (!response.ok) {
    throw await apiError(response, `GET ${path} -> ${response.status}`);
  }
  return (await response.json()) as T;
}

interface ParsedErrorDetail {
  message: string;
  validation: ApiValidationDetail[] | undefined;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function validationDetail(value: unknown): ApiValidationDetail[] | undefined {
  if (!Array.isArray(value)) return undefined;

  const parsed: ApiValidationDetail[] = [];
  for (const item of value) {
    if (!isRecord(item) || !Array.isArray(item.loc) || typeof item.msg !== "string") {
      continue;
    }
    const loc = item.loc
      .filter((part): part is string | number => {
        return typeof part === "string" || typeof part === "number";
      })
      .map(String);
    if (loc.length === item.loc.length && loc.length > 0 && item.msg !== "") {
      parsed.push({ loc, msg: item.msg });
    }
  }
  return parsed.length > 0 ? parsed : undefined;
}

/**
 * Prefer the API's JSON `detail` message (the FastAPI error convention) over a generic
 * status line, and retain Pydantic's structured validation array when present.
 * Non-JSON or malformed bodies fall back to the generic message.
 */
async function errorDetail(response: Response, fallback: string): Promise<ParsedErrorDetail> {
  try {
    const body: unknown = await response.json();
    if (!isRecord(body)) return { message: fallback, validation: undefined };
    if (typeof body.detail === "string" && body.detail !== "") {
      return { message: body.detail, validation: undefined };
    }
    return { message: fallback, validation: validationDetail(body.detail) };
  } catch {
    return { message: fallback, validation: undefined };
  }
}

async function apiError(response: Response, fallback: string): Promise<ApiError> {
  const parsed = await errorDetail(response, fallback);
  return new ApiError(response.status, parsed.message, parsed.validation);
}

async function apiPost<T>(
  path: string,
  body: unknown,
  sessionToken?: string,
  timeoutMs: number = REQUEST_TIMEOUT_MS,
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json",
  };
  const token = resolveBearer(sessionToken);
  if (token !== undefined) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    cache: "no-store",
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!response.ok) {
    throw await apiError(response, `POST ${path} -> ${response.status}`);
  }
  return (await response.json()) as T;
}

/** Longer ceiling for multipart uploads (reference images) than the 3s read timeout. */
const UPLOAD_TIMEOUT_MS = 20000;

async function apiPostForm<T>(path: string, form: FormData, sessionToken?: string): Promise<T> {
  // No explicit Content-Type — fetch sets the multipart boundary itself.
  const headers: Record<string, string> = { Accept: "application/json" };
  const token = resolveBearer(sessionToken);
  if (token !== undefined) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    method: "POST",
    headers,
    body: form,
    cache: "no-store",
    signal: AbortSignal.timeout(UPLOAD_TIMEOUT_MS),
  });
  if (!response.ok) {
    throw await apiError(response, `POST ${path} -> ${response.status}`);
  }
  return (await response.json()) as T;
}

async function apiPatch<T>(path: string, body: unknown, sessionToken?: string): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json",
  };
  const token = resolveBearer(sessionToken);
  if (token !== undefined) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    method: "PATCH",
    headers,
    body: JSON.stringify(body),
    cache: "no-store",
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });
  if (!response.ok) {
    throw await apiError(response, `PATCH ${path} -> ${response.status}`);
  }
  return (await response.json()) as T;
}

/**
 * Every endpoint below accepts an optional `sessionToken` — the per-user Supabase
 * bearer, threaded server-side from `lib/session.getSessionToken`. When omitted, the
 * request falls back to the DEV-ONLY `NEXT_PUBLIC_DEV_TOKEN` (see `resolveBearer`).
 */

/** GET /clients — the caller-tenant's clients. */
export function listClients(sessionToken?: string): Promise<ApiClient[]> {
  return apiGet<ApiClient[]>("/clients", sessionToken);
}

/** GET /clients/{id} — one tenant-scoped client. */
export function getClient(clientId: string, sessionToken?: string): Promise<ApiClient> {
  return apiGet<ApiClient>(`/clients/${encodeURIComponent(clientId)}`, sessionToken);
}

export interface UpdateClientBody {
  name?: string;
  industry?: string | null;
  contact_email?: string | null;
}

/** PATCH /clients/{id} — update the editable client details. */
export function updateClient(
  clientId: string,
  body: UpdateClientBody,
  sessionToken?: string,
): Promise<ApiClient> {
  return apiPatch<ApiClient>(`/clients/${encodeURIComponent(clientId)}`, body, sessionToken);
}

/** GET /brands/{id}. */
export function getBrand(brandId: string, sessionToken?: string): Promise<ApiBrand> {
  return apiGet<ApiBrand>(`/brands/${encodeURIComponent(brandId)}`, sessionToken);
}

export interface UpdateBrandBriefBody {
  niche?: string | null;
  target_audience?: string | null;
  brand_voice?: string | null;
  tone_keywords?: string[];
  imagery_style?: string | null;
  dos?: string[];
  donts?: string[];
  tokens?: { colors: ApiColorRole[] };
}

/** PATCH /brands/{id} — update brief fields and palette colors without replacing other tokens. */
export function updateBrandBrief(
  brandId: string,
  body: UpdateBrandBriefBody,
  sessionToken?: string,
): Promise<ApiBrand> {
  return apiPatch<ApiBrand>(`/brands/${encodeURIComponent(brandId)}`, body, sessionToken);
}

/** GET /jobs — optionally filtered to one client. */
export function listJobs(clientId?: string, sessionToken?: string): Promise<ApiJob[]> {
  const query = clientId !== undefined ? `?client_id=${encodeURIComponent(clientId)}` : "";
  return apiGet<ApiJob[]>(`/jobs${query}`, sessionToken);
}

/** GET /jobs/{id} — one job (404s cross-tenant, so a foreign id yields a real not-found). */
export function getJob(jobId: string, sessionToken?: string): Promise<ApiJob> {
  return apiGet<ApiJob>(`/jobs/${encodeURIComponent(jobId)}`, sessionToken);
}

/** GET /pillars — optionally filtered to one client. */
export function listPillars(clientId?: string, sessionToken?: string): Promise<ApiContentPillar[]> {
  const query = clientId !== undefined ? `?client_id=${encodeURIComponent(clientId)}` : "";
  return apiGet<ApiContentPillar[]>(`/pillars${query}`, sessionToken);
}

/** GET /jobs/{id}/creatives — a job's creative versions, oldest first. */
export function listJobCreatives(jobId: string, sessionToken?: string): Promise<ApiCreativeDoc[]> {
  return apiGet<ApiCreativeDoc[]>(`/jobs/${encodeURIComponent(jobId)}/creatives`, sessionToken);
}

/** GET /creatives — the tenant's creatives (latest version per job) for the gallery. */
export function listCreatives(sessionToken?: string): Promise<ApiCreativeDoc[]> {
  return apiGet<ApiCreativeDoc[]>("/creatives", sessionToken);
}

export interface GenerateCreativeBody {
  topic: string;
  pillar?: string;
  format_key?: string;
}

/** POST /clients/{id}/creatives:generate — run the real engine and persist its artifacts. */
export function generateCreative(
  clientId: string,
  body: GenerateCreativeBody,
  sessionToken?: string,
): Promise<ApiGeneratedCreative> {
  return apiPost<ApiGeneratedCreative>(
    `/clients/${encodeURIComponent(clientId)}/creatives:generate`,
    body,
    sessionToken,
    CREATIVE_TIMEOUT_MS,
  );
}



/**
 * POST /creatives/{id}/revise body — a BACKWARD-COMPATIBLE SUPERSET: the typed canvas
 * revision fields (`text_edits` / `layer_ops` / `params` / `ask`, via ApiCanvasRevision)
 * PLUS the legacy v1-editor optionals the backend still accepts.
 */
export interface ReviseCreativeBody extends Partial<ApiCanvasRevision> {
  // Legacy fields kept until B-10/B-12 remove their callers (ReviewPanel v1).
  edits?: {
    headline?: string;
    sub?: string;
    cta?: string;
  };
  instruction?: string;
}

export function reviseCreative(
  creativeId: string,
  body: ReviseCreativeBody,
  sessionToken?: string,
): Promise<ApiGeneratedCreative> {
  return apiPost<ApiGeneratedCreative>(
    `/creatives/${encodeURIComponent(creativeId)}/revise`,
    body,
    sessionToken,
    CREATIVE_TIMEOUT_MS,
  );
}

/** GET /creatives/{id}/versions — the persisted version history of the creative's job. */
export function listCreativeVersions(
  creativeId: string,
  sessionToken?: string,
): Promise<ApiVersionHistory> {
  return apiGet<ApiVersionHistory>(
    `/creatives/${encodeURIComponent(creativeId)}/versions`,
    sessionToken,
  );
}

/** POST /creatives/{id}/revert — re-head the job at an older version (minted as a NEW version). */
export function revertCreative(
  creativeId: string,
  toCreativeId: string,
  sessionToken?: string,
): Promise<ApiGeneratedCreative> {
  return apiPost<ApiGeneratedCreative>(
    `/creatives/${encodeURIComponent(creativeId)}/revert`,
    { to_creative_id: toCreativeId },
    sessionToken,
    CREATIVE_TIMEOUT_MS,
  );
}

export type CreativeArtifactKind = "preview" | "svg" | "psd";

/** Authenticated raw artifact fetch used only by the same-origin Next route proxy. */
export async function fetchCreativeArtifact(
  creativeId: string,
  artifact: CreativeArtifactKind,
  sessionToken?: string,
): Promise<Response> {
  const path =
    artifact === "svg"
      ? `/exports/svg?creative_id=${encodeURIComponent(creativeId)}`
      : artifact === "psd"
        ? `/creatives/${encodeURIComponent(creativeId)}/export.psd`
        : `/creatives/${encodeURIComponent(creativeId)}/preview`;
  const headers: Record<string, string> = { Accept: "*/*" };
  const token = resolveBearer(sessionToken);
  if (token !== undefined) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    headers,
    cache: "no-store",
    signal: AbortSignal.timeout(CREATIVE_TIMEOUT_MS),
  });
  if (!response.ok) {
    throw await apiError(response, `GET ${path} -> ${response.status}`);
  }
  return response;
}

/** Raw SVG master text for the in-product canvas editor. */
export async function fetchCreativeSvg(
  creativeId: string,
  sessionToken?: string,
): Promise<string> {
  const response = await fetchCreativeArtifact(creativeId, "svg", sessionToken);
  return response.text();
}

/** POST /jobs/{id}/creatives body — mint a new creative version (the copy edit → new version path). */
export interface CreateCreativeBody {
  template_key: string;
  copy_block: {
    headline: string;
    subhead: string | null;
    cta: string | null;
    language: string;
    status: "draft" | "approved" | "edited";
  };
  /** Cached image ref to reuse; null → placeholder brand ground. Rejected if an external URL. */
  image_artifact: string | null;
  /** Per-creative layout override; omit to inherit the brand default. */
  layout?: ApiBrandLayout;
}

/** POST /jobs/{id}/creatives — mint a new CreativeDoc version (team-gated at the API). */
export function createCreativeVersion(
  jobId: string,
  body: CreateCreativeBody,
  sessionToken?: string,
): Promise<ApiCreativeDoc> {
  return apiPost<ApiCreativeDoc>(
    `/jobs/${encodeURIComponent(jobId)}/creatives`,
    body,
    sessionToken,
  );
}

/** GET /ops/board — jobs grouped by status with computed at-risk flags. */
export function fetchBoard(sessionToken?: string): Promise<ApiBoardResponse> {
  return apiGet<ApiBoardResponse>("/ops/board", sessionToken);
}

/**
 * POST /ops/jobs/{id}/transition — move a board card to another pipeline column.
 * Team roles only (403 for a client principal). An illegal move 409s with the API's
 * `detail`; a →approved move runs the shared approval/auto-archive path server-side,
 * so the returned job may land in APPROVED or ARCHIVED — re-fetch the board after.
 */
export function transitionJob(
  jobId: string,
  toStatus: ApiJobStatus,
  note?: string,
  sessionToken?: string,
): Promise<{ job: ApiJob }> {
  return apiPost<{ job: ApiJob }>(
    `/ops/jobs/${encodeURIComponent(jobId)}/transition`,
    { to_status: toStatus, ...(note !== undefined && note !== "" ? { note } : {}) },
    sessionToken,
  );
}

/* ---------------------------------------------------------------------------
   Command Center — the generation queue (the "generate" entry of the ops loop).
--------------------------------------------------------------------------- */

/** mimik_contracts.enums.TaskStatus — the queue item's lifecycle. */
export type ApiTaskStatus = "open" | "in_progress" | "done";

/** mimik_contracts.ops.GenerationQueueItem — one queued generation request. */
export interface ApiGenerationQueueItem {
  id: string;
  job_id: string;
  client_id: string;
  topic: string;
  pillar: string | null;
  format_key: string;
  status: ApiTaskStatus;
  requested_by: ApiActor;
  created_at: string;
  error: string | null;
}

/** mimik_contracts.ops.QueueStats — the queue's aggregate counters. */
export interface ApiQueueStats {
  pending: number;
  in_progress: number;
  done_today: number;
  failed_today: number;
}

/** POST /ops/queue body (api.routers.ops.EnqueueGenerationRequest). `pillar` is the pillar
 *  NAME (free text, not an id); `format_key` must be a known preset or the API 422s. */
export interface EnqueueGenerationBody {
  client_id: string;
  topic: string;
  pillar?: string;
  format_key?: string;
}

/** GET /ops/queue — the tenant's generation queue, newest-relevant first. Team-gated (403 for a
 *  client principal). */
export function fetchGenerationQueue(sessionToken?: string): Promise<ApiGenerationQueueItem[]> {
  return apiGet<ApiGenerationQueueItem[]>("/ops/queue", sessionToken);
}

/** GET /ops/queue/stats — pending / in-progress / done-today / failed-today counters. Team-gated. */
export function fetchQueueStats(sessionToken?: string): Promise<ApiQueueStats> {
  return apiGet<ApiQueueStats>("/ops/queue/stats", sessionToken);
}

/** POST /ops/queue — enqueue a generation request. Team-gated (403 for a client principal); an
 *  unknown format_key or blank topic 422s; a foreign/unknown client 404s. */
export function enqueueGeneration(
  body: EnqueueGenerationBody,
  sessionToken?: string,
): Promise<ApiGenerationQueueItem> {
  return apiPost<ApiGenerationQueueItem>("/ops/queue", body, sessionToken);
}

/**
 * POST /approvals — record an approve / request-change / comment action on a creative.
 * `targets` are only valid with `action: "request_change"` (the API 422s otherwise).
 * Throws `ApiError` on non-2xx; network/timeout failures reject with the fetch error.
 */
export function submitApproval(
  body: ApprovalSubmission,
  sessionToken?: string,
): Promise<ApprovalResponse> {
  return apiPost<ApprovalResponse>("/approvals", body, sessionToken);
}

/** GET /jobs/{id}/approvals — the append-only audit trail (comment threads + decisions + deliveries). */
export function getJobAuditTrail(jobId: string, sessionToken?: string): Promise<JobAuditTrail> {
  return apiGet<JobAuditTrail>(`/jobs/${encodeURIComponent(jobId)}/approvals`, sessionToken);
}

/** GET /me — the caller's own identity (role lives in UserAccount, not the provider token). */
export interface ApiMe {
  tenant_id: string;
  /** The caller's OWN tenant slug/name — stable white-label branding key (never cross-tenant). */
  tenant_slug: string | null;
  tenant_name: string | null;
  role: string;
  client_id: string | null;
  user_id: string | null;
}

/** GET /me — resolve the verified principal (for role-based route steering). */
export function getMe(sessionToken?: string): Promise<ApiMe> {
  return apiGet<ApiMe>("/me", sessionToken);
}

/* ---------------------------------------------------------------------------
   Magic-link portal — no-login, single-job capability (token in the body).
--------------------------------------------------------------------------- */

/** POST /portal/session response — one job's review bundle, resolved from a magic-link grant. */
export interface PortalBundle {
  job: ApiJob;
  brand: ApiBrand | null;
  creatives: ApiCreativeDoc[];
  approvals: ApiApproval[];
  deliveries: ApiDelivery[];
}

/** POST /portal/session — resolve a magic-link token to its job's review bundle (no login). */
export function getPortalSession(token: string): Promise<PortalBundle> {
  return apiPost<PortalBundle>("/portal/session", { token });
}

/** POST /jobs/{id}/magic-link — a team member mints a shareable, single-job review grant. */
export function mintMagicLink(
  jobId: string,
  ttlHours: number,
  sessionToken?: string,
): Promise<{ token: string; job_id: string }> {
  return apiPost<{ token: string; job_id: string }>(
    `/jobs/${encodeURIComponent(jobId)}/magic-link`,
    { ttl_hours: ttlHours },
    sessionToken,
  );
}

/** POST /approvals/magic body — a no-login approve/request-change/comment via a magic-link grant. */
export interface MagicApprovalSubmission {
  token: string;
  action: ApprovalActionKind;
  creative_doc_id?: string;
  note?: string;
  reason_tag?: string;
  targets?: ApprovalTarget[];
}

/** POST /approvals/magic — submit a decision with a magic-link token instead of a session. */
export function submitMagicApproval(body: MagicApprovalSubmission): Promise<ApprovalResponse> {
  return apiPost<ApprovalResponse>("/approvals/magic", body);
}

/* ---------------------------------------------------------------------------
   Tasks — the shared ops/portal work table.
--------------------------------------------------------------------------- */

/** GET /tasks — the tenant's tasks (a client principal is auto-confined to its own client).
 *  Optional filters: client, job, status. */
export function listTasks(
  filters: { clientId?: string; jobId?: string; status?: string },
  sessionToken?: string,
): Promise<ApiTask[]> {
  const q = new URLSearchParams();
  if (filters.clientId !== undefined) q.set("client_id", filters.clientId);
  if (filters.jobId !== undefined) q.set("job_id", filters.jobId);
  if (filters.status !== undefined) q.set("status", filters.status);
  const query = q.toString();
  return apiGet<ApiTask[]>(`/tasks${query !== "" ? `?${query}` : ""}`, sessionToken);
}

/** GET /deliveries — one archived-to-Drive record (the join view: delivery + its job title). */
export interface ApiDeliveryRecord {
  id: string;
  job_id: string;
  job_title: string;
  client_id: string;
  creative_doc_id: string;
  drive_path: string;
  delivered_at: string | null;
  created_at: string;
}

/** GET /deliveries — the tenant's archive records (client principals auto-confined to their own). */
export function listDeliveries(sessionToken?: string): Promise<ApiDeliveryRecord[]> {
  return apiGet<ApiDeliveryRecord[]>("/deliveries", sessionToken);
}

/** POST /tasks/{id}/status — advance a task open -> in_progress -> done (team roles only). */
export function advanceTaskStatus(
  taskId: string,
  status: string,
  sessionToken?: string,
): Promise<ApiTask> {
  return apiPost<ApiTask>(
    `/tasks/${encodeURIComponent(taskId)}/status`,
    { status },
    sessionToken,
  );
}

/* ---------------------------------------------------------------------------
   Billing — subscriptions + checkout ("quote") links.
--------------------------------------------------------------------------- */

/** mimik_contracts.enums.SubscriptionStatus. trialing/active grant access; the rest gate it off. */
export type ApiSubscriptionStatus =
  | "trialing"
  | "active"
  | "past_due"
  | "canceled"
  | "incomplete";

/** mimik_contracts.billing.Subscription. */
export interface ApiSubscription {
  id: string;
  created_at: string;
  tenant_id: string;
  client_id: string;
  status: ApiSubscriptionStatus;
  stripe_customer_id: string | null;
  stripe_subscription_id: string | null;
  price_id: string | null;
  current_period_end: string | null;
}

/** GET /clients/{id}/subscription — the client's subscription (404 if none). Client-confined. */
export function getClientSubscription(
  clientId: string,
  sessionToken?: string,
): Promise<ApiSubscription> {
  return apiGet<ApiSubscription>(
    `/clients/${encodeURIComponent(clientId)}/subscription`,
    sessionToken,
  );
}

/** POST /billing/checkout — mint a Stripe checkout ("quote"/payment) link for a client. */
export function startCheckout(
  clientId: string,
  sessionToken?: string,
): Promise<{ checkout_url: string; session_id: string }> {
  return apiPost<{ checkout_url: string; session_id: string }>(
    "/billing/checkout",
    { client_id: clientId },
    sessionToken,
  );
}

/* ---------------------------------------------------------------------------
   Preferences — the per-client learned taste profile (the learning loop).
--------------------------------------------------------------------------- */

/** mimik_contracts.workflow.PreferenceSignal (subset the profile view renders). */
export interface ApiPreferenceSignal {
  source: string;
  reason_tag: string | null;
  weight: number;
  attributes: Record<string, string>;
  creative_doc_id: string | null;
  created_at: string;
}

/** GET /clients/{id}/preferences/profile response. */
export interface ApiPreferenceProfile {
  profile: {
    summary: string;
    signals: ApiPreferenceSignal[];
    client_id: string;
  };
  ranker_active: boolean;
  signal_count: number;
}

/** GET /clients/{id}/preferences/profile — the client's learned preference profile. Client-confined. */
export function getPreferenceProfile(
  clientId: string,
  sessionToken?: string,
): Promise<ApiPreferenceProfile> {
  return apiGet<ApiPreferenceProfile>(
    `/clients/${encodeURIComponent(clientId)}/preferences/profile`,
    sessionToken,
  );
}

/** mimik_contracts.enums.PreferenceSource — where a learning-loop signal came from. */
export type ApiPreferenceSource = "pick" | "edit" | "rejection" | "approval";

/**
 * POST /clients/{id}/preferences body (api.routers.preferences.RecordSignal). `detail` is a note
 * ABOUT the signal (data, not an instruction); `attributes` are salient creative facts the ranker
 * scores on. NOTE: approve / reject / canvas-revise already emit their own signals server-side
 * (api/services/approval_flow.py + creative_generation.py) — call this ONLY from actions that do
 * NOT, or the profile double-counts.
 */
export interface RecordPreferenceBody {
  source: ApiPreferenceSource;
  creative_doc_id?: string;
  job_id?: string;
  detail?: string;
  reason_tag?: string;
  weight?: number;
  attributes?: Record<string, string>;
}

/** POST /clients/{id}/preferences — record one learning-loop signal for the client's taste profile.
 *  Any authed principal (client-confined at the data layer); returns the persisted signal (201). */
export function recordPreferenceSignal(
  clientId: string,
  body: RecordPreferenceBody,
  sessionToken?: string,
): Promise<ApiPreferenceSignal> {
  return apiPost<ApiPreferenceSignal>(
    `/clients/${encodeURIComponent(clientId)}/preferences`,
    body,
    sessionToken,
  );
}

/* ---------------------------------------------------------------------------
   Briefs — the versioned, sign-off-able brand-brief document.
--------------------------------------------------------------------------- */

/** mimik_contracts.enums.BriefStatus. In practice signoff jumps draft->frozen directly. */
export type ApiBriefStatus = "draft" | "in_review" | "signed_off" | "frozen";

/** mimik_contracts.brief.BriefSections — the 9 designer sections (1-5 auto-draft, 6-9 human). */
export interface ApiBriefSections {
  snapshot: string | null;
  logo_notes: string | null;
  tokens: ApiBrandTokens;
  voice_tone: string | null;
  imagery_style: string | null;
  guardrails_dos: string[];
  guardrails_donts: string[];
  references: ApiReference[];
  deliverable_formats: string[];
}

/** mimik_contracts.brief.Brief — versioned; FROZEN = signed-off + locked (edits become new versions). */
export interface ApiBrief {
  id: string;
  created_at: string;
  tenant_id: string;
  client_id: string;
  brand_id: string;
  version: number;
  status: ApiBriefStatus;
  sections: ApiBriefSections;
  signed_off_by: string | null;
  frozen_at: string | null;
}

/** GET /briefs — the tenant's briefs, optionally filtered to one client. */
export function listBriefs(clientId?: string, sessionToken?: string): Promise<ApiBrief[]> {
  const query = clientId !== undefined ? `?client_id=${encodeURIComponent(clientId)}` : "";
  return apiGet<ApiBrief[]>(`/briefs${query}`, sessionToken);
}

/** GET /briefs/{id}. */
export function getBrief(briefId: string, sessionToken?: string): Promise<ApiBrief> {
  return apiGet<ApiBrief>(`/briefs/${encodeURIComponent(briefId)}`, sessionToken);
}

/** PATCH /briefs/{id} — full-replace the 9 sections of a DRAFT brief (409 if frozen). */
export function updateBriefSections(
  briefId: string,
  sections: ApiBriefSections,
  sessionToken?: string,
): Promise<ApiBrief> {
  return apiPatch<ApiBrief>(`/briefs/${encodeURIComponent(briefId)}`, sections, sessionToken);
}

/** POST /briefs/{id}/signoff — freeze the brief; locks it (a later change becomes a new version). */
export function signoffBrief(
  briefId: string,
  signedOffBy: string,
  sessionToken?: string,
): Promise<ApiBrief> {
  return apiPost<ApiBrief>(
    `/briefs/${encodeURIComponent(briefId)}/signoff`,
    { signed_off_by: signedOffBy },
    sessionToken,
  );
}

/** POST /briefs/{id}/revise — mint version N+1 as a fresh draft seeded from this brief's sections. */
export function reviseBrief(briefId: string, sessionToken?: string): Promise<ApiBrief> {
  return apiPost<ApiBrief>(`/briefs/${encodeURIComponent(briefId)}/revise`, {}, sessionToken);
}

/* ---------------------------------------------------------------------------
   Onboarding — create client / brand / pillars, presets, reference uploads.
--------------------------------------------------------------------------- */

/** mimik_contracts.pillars.PillarPreset — a starter content pillar (static template). */
export interface ApiPillarPreset {
  key: string;
  name: string;
  description: string;
}

/** GET /pillars/presets — the static starter pillars (no auth/tenant needed, but token is fine). */
export function listPillarPresets(sessionToken?: string): Promise<ApiPillarPreset[]> {
  return apiGet<ApiPillarPreset[]>("/pillars/presets", sessionToken);
}

export interface CreateClientBody {
  name: string;
  contact_email?: string | null;
  phone?: string | null;
  industry?: string | null;
  website_url?: string | null;
  instagram?: string | null;
  notes?: string | null;
}

/** POST /clients — create a client in the caller's tenant. */
export function createClient(body: CreateClientBody, sessionToken?: string): Promise<ApiClient> {
  return apiPost<ApiClient>("/clients", body, sessionToken);
}

/** A client-shared reference at onboarding (fit_score is assigned later by ingest). */
export interface ReferenceInput {
  url: string;
  source?: string | null;
  note?: string | null;
}

export interface CreateBrandBody {
  client_id: string;
  name: string;
  slug: string;
  niche?: string | null;
  services?: string[];
  target_audience?: string | null;
  brand_voice?: string | null;
  tone_keywords?: string[];
  dos?: string[];
  donts?: string[];
  handles?: Record<string, string>;
  imagery_style?: string | null;
  tokens?: ApiBrandTokens;
  references?: ReferenceInput[];
}

/** POST /brands — create a brand (with tokens + client-shared references) in one call. */
export function createBrand(body: CreateBrandBody, sessionToken?: string): Promise<ApiBrand> {
  return apiPost<ApiBrand>("/brands", body, sessionToken);
}

/** PATCH /brands/{id} — full-replace the brand's design tokens (the brand-kit editor). */
export function updateBrandTokens(
  brandId: string,
  tokens: ApiBrandTokens,
  sessionToken?: string,
): Promise<ApiBrand> {
  return apiPatch<ApiBrand>(`/brands/${encodeURIComponent(brandId)}`, tokens, sessionToken);
}

export interface CreatePillarBody {
  client_id: string;
  /** Adopt a preset by key OR define a custom pillar by name (exactly one). */
  preset_key?: string;
  name?: string;
  description?: string | null;
}

/** POST /pillars — adopt a preset or define a custom content pillar. */
export function createPillar(
  body: CreatePillarBody,
  sessionToken?: string,
): Promise<ApiContentPillar> {
  return apiPost<ApiContentPillar>("/pillars", body, sessionToken);
}

/** POST /briefs — mint a draft brief for a brand (the onboarding auto-draft). */
export function createBrief(brandId: string, sessionToken?: string): Promise<ApiBrief> {
  return apiPost<ApiBrief>("/briefs", { brand_id: brandId }, sessionToken);
}

/** mimik_contracts.enums.AssetKind — what a stored brand asset IS. */
export type AssetKind = "logo" | "font" | "imagery" | "reference_creative";

/**
 * mimik_contracts.assets.AssetStudy — what the vision pass observed in a reference creative.
 * Null until the reference is ingested (`POST /assets/{id}/ingest`); evidence-bound, so every
 * field is describing what is VISIBLE in the file, never an invention.
 */
export interface ApiAssetStudy {
  mood: string | null;
  /** Observed hexes, dominant first. */
  palette: string[];
  composition: string | null;
  lighting: string | null;
  complexity: "minimal" | "moderate" | "busy" | null;
  copy_text: string | null;
  logo_assessment: string | null;
  notes: string | null;
}

/** mimik_contracts.assets.BrandAsset — one stored brand-library asset (the full wire shape). */
export interface ApiBrandAsset {
  id: string;
  created_at: string;
  tenant_id: string;
  client_id: string;
  brand_id: string;
  kind: AssetKind;
  filename: string;
  mime: string;
  /** Server-side storage ref; the bytes are not served to the browser (no public asset URL). */
  local_path: string | null;
  drive_file_id: string | null;
  /** Human gate: an approved LOGO is wired into the brand's logo token for the compositor. */
  approved: boolean;
  license: string | null;
  notes: string | null;
  /** Filled by reference-creative ingestion; null until then. */
  study: ApiAssetStudy | null;
}

/** creative.references.fit_critic.FitVerdict — the fit-critic's call on an ingested reference. */
export interface ApiFitVerdict {
  fit_score: number;
  fits: boolean;
  reasoning: string;
}

/** brand_memory.IngestResult — the outcome of ingesting a reference creative into brand memory. */
export interface ApiIngestResult {
  asset_id: string;
  study: ApiAssetStudy;
  verdict: ApiFitVerdict;
  attached: boolean;
  signals_recorded: number;
}

/**
 * GET /brands/{id}/assets — the brand's curated asset library (team-gated). Optionally filtered
 * to one `kind`. Returns the full BrandAsset rows (approval state, mime, and any ingest study).
 */
export function fetchBrandAssets(
  brandId: string,
  kind?: AssetKind,
  sessionToken?: string,
): Promise<ApiBrandAsset[]> {
  const query = kind !== undefined ? `?kind=${encodeURIComponent(kind)}` : "";
  return apiGet<ApiBrandAsset[]>(
    `/brands/${encodeURIComponent(brandId)}/assets${query}`,
    sessionToken,
  );
}

/**
 * POST /brands/{id}/assets — upload a brand asset of the given kind. Multipart: `kind` is a Form
 * field, `file` is the upload. The browser sets the multipart boundary itself (no manual
 * Content-Type). The backend SNIFFS the real mime from the bytes and 415s a disallowed type — the
 * caller surfaces that error inline. Team-gated at the API (403 for a client principal).
 */
export function uploadBrandAsset(
  brandId: string,
  kind: AssetKind,
  file: File,
  sessionToken?: string,
): Promise<ApiBrandAsset> {
  const form = new FormData();
  // `kind` first so the multipart part order matches the FastAPI Form(...) signature.
  form.append("kind", kind);
  form.append("file", file);
  return apiPostForm<ApiBrandAsset>(
    `/brands/${encodeURIComponent(brandId)}/assets`,
    form,
    sessionToken,
  );
}

/** POST /brands/{id}/assets — upload a client-shared reference image as a reference_creative asset. */
export function uploadReferenceAsset(
  brandId: string,
  file: File,
  sessionToken?: string,
): Promise<ApiBrandAsset> {
  return uploadBrandAsset(brandId, "reference_creative", file, sessionToken);
}

/**
 * POST /assets/{id}/approve — human-approve an asset (owner/ops only). Approving a LOGO wires it
 * into the brand's logo token so the compositor renders the real mark.
 */
export function approveAsset(assetId: string, sessionToken?: string): Promise<ApiBrandAsset> {
  return apiPost<ApiBrandAsset>(`/assets/${encodeURIComponent(assetId)}/approve`, {}, sessionToken);
}

/**
 * POST /assets/{id}/knockout — derive the white-knockout variant of a stored LOGO (a new,
 * unapproved asset). Team-gated; 422 for a non-logo asset, 409 if the logo has no stored bytes.
 */
export function knockoutLogo(assetId: string, sessionToken?: string): Promise<ApiBrandAsset> {
  return apiPost<ApiBrandAsset>(
    `/assets/${encodeURIComponent(assetId)}/knockout`,
    {},
    sessionToken,
    CREATIVE_TIMEOUT_MS,
  );
}

/**
 * POST /assets/{id}/ingest — study a REFERENCE_CREATIVE into brand memory (vision pass + fit
 * critic). Team-gated; 422 for a non-reference asset, 502 when the vision backend is unconfigured.
 * Runs a model pass, so it gets the longer creative ceiling.
 */
export function ingestReference(assetId: string, sessionToken?: string): Promise<ApiIngestResult> {
  return apiPost<ApiIngestResult>(
    `/assets/${encodeURIComponent(assetId)}/ingest`,
    {},
    sessionToken,
    CREATIVE_TIMEOUT_MS,
  );
}

/**
 * Authenticated raw asset-bytes fetch used ONLY by the same-origin Next route proxy
 * (`/api/assets/{id}/raw`). Mirrors `fetchCreativeArtifact`: the bearer never reaches the
 * browser — the proxy attaches it server-side and streams the bytes back same-origin.
 */
export async function fetchAssetRaw(assetId: string, sessionToken?: string): Promise<Response> {
  const path = `/assets/${encodeURIComponent(assetId)}/raw`;
  const headers: Record<string, string> = { Accept: "*/*" };
  const token = resolveBearer(sessionToken);
  if (token !== undefined) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    headers,
    cache: "no-store",
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });
  if (!response.ok) {
    throw await apiError(response, `GET ${path} -> ${response.status}`);
  }
  return response;
}

/** Same-origin proxy URL for an asset's raw bytes — the `<img src>` the browser loads. Auth is
 *  attached server-side by the `/api/assets/[id]/raw` route; no token is ever exposed client-side. */
export function assetRawUrl(assetId: string): string {
  return `/api/assets/${encodeURIComponent(assetId)}/raw`;
}

/** GET /fonts/library entry — one built-in font available to materialize into a brand. */
export interface ApiFontLibraryEntry {
  key: string;
  family: string;
  category: string;
  preview_text: string;
}

/** GET /fonts/library — the built-in font catalog (team-gated). */
export function fetchFontLibrary(sessionToken?: string): Promise<ApiFontLibraryEntry[]> {
  return apiGet<ApiFontLibraryEntry[]>("/fonts/library", sessionToken);
}

/**
 * POST /brands/{brand_id}/fonts/{font_key} — materialize a built-in font as an approved FONT
 * BrandAsset for the brand; returns the created asset (201). Team-gated (403 for a client
 * principal); an unknown font_key 404s and a foreign brand 404s cross-tenant.
 */
export function materializeBuiltinFont(
  brandId: string,
  fontKey: string,
  sessionToken?: string,
): Promise<ApiBrandAsset> {
  return apiPost<ApiBrandAsset>(
    `/brands/${encodeURIComponent(brandId)}/fonts/${encodeURIComponent(fontKey)}`,
    {},
    sessionToken,
  );
}

/* ---------------------------------------------------------------------------
   Members / roles / invitations (the admin panel).
--------------------------------------------------------------------------- */

/** A provisioned team/client account (GET /admin/accounts). `client_scopes` is empty = all
 *  clients in the tenant; non-empty restricts an internal user to those client ids. */
export interface ApiUserAccount {
  id: string;
  tenant_id: string;
  auth_subject: string;
  email: string | null;
  role: string;
  client_id: string | null;
  client_scopes?: string[];
  name: string | null;
  active: boolean;
  created_at: string;
}

export type ApiInvitationStatus = "pending" | "accepted" | "revoked" | "expired";

/** A pending/consumed invite (GET /invitations). */
export interface ApiInvitation {
  id: string;
  tenant_id: string;
  email: string;
  role: string;
  client_scopes: string[];
  status: ApiInvitationStatus;
  invited_by: string | null;
  expires_at: string | null;
  accepted_at: string | null;
  created_at: string;
}

/** POST /invitations response — the invite row plus the copyable accept link. */
export interface ApiInvitationCreated {
  invitation: ApiInvitation;
  accept_url: string;
}

/** GET /admin/capabilities — role -> the capabilities that role holds. */
export type ApiCapabilityMatrix = Record<string, string[]>;

/** GET /admin/accounts — every account in the caller's tenant. */
export function listAccounts(sessionToken?: string): Promise<ApiUserAccount[]> {
  return apiGet<ApiUserAccount[]>("/admin/accounts", sessionToken);
}

/** PATCH /admin/accounts/{id} body — both fields optional; only provided fields update.
 *  `client_scopes: []` = all clients; a non-empty list restricts to those client ids. */
export interface UpdateAccountBody {
  role?: string;
  client_scopes?: string[];
}

/** PATCH /admin/accounts/{id} — owner-only role / per-client access update.
 *  Non-owner → 403; cross-tenant target → 404; unknown role or foreign client id → 422. */
export function updateAccount(
  accountId: string,
  body: UpdateAccountBody,
  sessionToken?: string,
): Promise<ApiUserAccount> {
  return apiPatch<ApiUserAccount>(
    `/admin/accounts/${encodeURIComponent(accountId)}`,
    body,
    sessionToken,
  );
}

/** GET /invitations — the tenant's invitations (any status). */
export function listInvitations(sessionToken?: string): Promise<ApiInvitation[]> {
  return apiGet<ApiInvitation[]>("/invitations", sessionToken);
}

/** GET /admin/capabilities — the role -> capability matrix (for the "what each role can do" panel). */
export function getCapabilityMatrix(sessionToken?: string): Promise<ApiCapabilityMatrix> {
  return apiGet<ApiCapabilityMatrix>("/admin/capabilities", sessionToken);
}

/** POST /invitations — invite by email; returns the copyable accept link. */
export function createInvitation(
  body: { email: string; role: string; client_scopes?: string[] },
  sessionToken?: string,
): Promise<ApiInvitationCreated> {
  return apiPost<ApiInvitationCreated>("/invitations", body, sessionToken);
}

/** POST /invitations/{id}/revoke — revoke a pending invite. */
export function revokeInvitation(
  invitationId: string,
  sessionToken?: string,
): Promise<ApiInvitation> {
  return apiPost<ApiInvitation>(
    `/invitations/${encodeURIComponent(invitationId)}/revoke`,
    {},
    sessionToken,
  );
}

/**
 * POST /invitations/accept — redeem a signed invite token as the INVITED Supabase identity and get
 * back the provisioned `UserAccount` (201). The backend re-checks every guard against the DB row:
 * the invite must still be PENDING and unexpired, and the caller's Supabase-verified email must match
 * the invited email. `sessionToken` MUST be a real Supabase session bearer — the dev bootstrap token
 * is refused server-side (it carries no provider identity to bind). Throws `ApiError` on non-2xx:
 * 400 invalid/expired token · 404 not found · 403 email mismatch · 410 expired · 409 already-accepted
 * / revoked / identity already has an account · 401 invalid session.
 */
export function acceptInvitation(
  token: string,
  sessionToken?: string,
): Promise<ApiUserAccount> {
  return apiPost<ApiUserAccount>("/invitations/accept", { token }, sessionToken);
}
