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
 *   production credential. Real user auth is the Supabase-issued path (the API already
 *   accepts it, discriminated by `iss`) and lands with the auth phase — at which point
 *   this env var goes away in favor of a per-user session token.
 */

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

/** mimik_contracts.brand.BrandTokens */
export interface ApiBrandTokens {
  colors: ApiColorRole[];
  typography: ApiTypography;
  logo: ApiLogoSpec;
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
 * True when BOTH `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_DEV_TOKEN` are set —
 * the gate `lib/data.ts` uses before attempting live fetches. Without both,
 * the app renders from mocks and never touches the network.
 */
export function isApiConfigured(): boolean {
  const url = process.env.NEXT_PUBLIC_API_URL;
  return url !== undefined && url !== "" && getDevToken() !== undefined;
}

/** Raised for non-2xx responses so callers can distinguish API errors from network errors. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function apiGet<T>(path: string): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const token = getDevToken();
  if (token !== undefined) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    headers,
    cache: "no-store",
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });
  if (!response.ok) {
    throw new ApiError(response.status, `GET ${path} -> ${response.status}`);
  }
  return (await response.json()) as T;
}

async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json",
  };
  const token = getDevToken();
  if (token !== undefined) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    cache: "no-store",
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });
  if (!response.ok) {
    throw new ApiError(response.status, `POST ${path} -> ${response.status}`);
  }
  return (await response.json()) as T;
}

/** GET /clients — the caller-tenant's clients. */
export function listClients(): Promise<ApiClient[]> {
  return apiGet<ApiClient[]>("/clients");
}

/** GET /brands/{id}. */
export function getBrand(brandId: string): Promise<ApiBrand> {
  return apiGet<ApiBrand>(`/brands/${encodeURIComponent(brandId)}`);
}

/** GET /jobs — optionally filtered to one client. */
export function listJobs(clientId?: string): Promise<ApiJob[]> {
  const query = clientId !== undefined ? `?client_id=${encodeURIComponent(clientId)}` : "";
  return apiGet<ApiJob[]>(`/jobs${query}`);
}

/** GET /pillars — optionally filtered to one client. */
export function listPillars(clientId?: string): Promise<ApiContentPillar[]> {
  const query = clientId !== undefined ? `?client_id=${encodeURIComponent(clientId)}` : "";
  return apiGet<ApiContentPillar[]>(`/pillars${query}`);
}

/** GET /jobs/{id}/creatives — a job's creative versions, oldest first. */
export function listCreatives(jobId: string): Promise<ApiCreativeDoc[]> {
  return apiGet<ApiCreativeDoc[]>(`/jobs/${encodeURIComponent(jobId)}/creatives`);
}

/** GET /ops/board — jobs grouped by status with computed at-risk flags. */
export function fetchBoard(): Promise<ApiBoardResponse> {
  return apiGet<ApiBoardResponse>("/ops/board");
}

/**
 * POST /approvals — record an approve / request-change / comment action on a creative.
 * `targets` are only valid with `action: "request_change"` (the API 422s otherwise).
 * Throws `ApiError` on non-2xx; network/timeout failures reject with the fetch error.
 */
export function submitApproval(body: ApprovalSubmission): Promise<ApprovalResponse> {
  return apiPost<ApprovalResponse>("/approvals", body);
}
