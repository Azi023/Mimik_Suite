export const DRAFT_STORAGE_KEY = "mimik:onboarding-draft";

/** Keep repair-flow drafts isolated from the ordinary new-client onboarding draft. */
export function onboardingDraftStorageKey(clientId?: string): string {
  return clientId === undefined ? DRAFT_STORAGE_KEY : `${DRAFT_STORAGE_KEY}:${clientId}`;
}

export const IMAGERY_MEDIA = ["flat illustration", "photography", "product", "mixed"] as const;

export type ImageryMedium = (typeof IMAGERY_MEDIA)[number];

export interface ColorRow {
  name: string;
  hex: string;
  usage: string;
}

export interface CustomPillar {
  name: string;
  description: string;
}

export interface RefLink {
  url: string;
  source: string;
  note: string;
}

export interface OnboardingDraft {
  /** API client already created by a partial submit; reuse it on retry. */
  clientId?: string;
  step: number;
  clientName: string;
  industry: string;
  contactEmail: string;
  brandName: string;
  niche: string;
  targetAudience: string;
  brandVoice: string;
  imageryMedium: ImageryMedium;
  imageryStyleNotes: string;
  toneKeywords: string[];
  dos: string[];
  donts: string[];
  handles: Record<string, string>;
  colors: ColorRow[];
  headingFont: string;
  bodyFont: string;
  logoNotes: string;
  logoMinSize: string;
  selectedPresets: string[];
  customPillars: CustomPillar[];
  refLinks: RefLink[];
}

interface DraftEnvelope {
  version: 1;
  draft: OnboardingDraft;
}

export function createInitialOnboardingDraft(): OnboardingDraft {
  return {
    step: 0,
    clientName: "",
    industry: "",
    contactEmail: "",
    brandName: "",
    niche: "",
    targetAudience: "",
    brandVoice: "",
    imageryMedium: "mixed",
    imageryStyleNotes: "",
    toneKeywords: [],
    dos: [],
    donts: [],
    handles: {},
    colors: [{ name: "", hex: "#4b5563", usage: "" }],
    headingFont: "",
    bodyFont: "",
    logoNotes: "",
    logoMinSize: "",
    selectedPresets: [],
    customPillars: [],
    refLinks: [],
  };
}

export function composeImageryStyle(medium: ImageryMedium, notes: string): string {
  const cleanNotes = notes.trim();
  const prefix = `MEDIUM: ${medium}.`;
  return cleanNotes === "" ? prefix : `${prefix} ${cleanNotes}`;
}

export function serializeOnboardingDraft(draft: OnboardingDraft): string {
  const envelope: DraftEnvelope = { version: 1, draft };
  return JSON.stringify(envelope);
}

export function saveOnboardingDraft(
  storage: Pick<Storage, "setItem">,
  draft: OnboardingDraft,
  storageKey: string = DRAFT_STORAGE_KEY,
): void {
  storage.setItem(storageKey, serializeOnboardingDraft(draft));
}

export function clearOnboardingDraft(
  storage: Pick<Storage, "removeItem">,
  storageKey: string = DRAFT_STORAGE_KEY,
): void {
  storage.removeItem(storageKey);
}

export function parseOnboardingDraft(raw: string | null): OnboardingDraft | null {
  if (raw === null) return null;

  try {
    const parsed: unknown = JSON.parse(raw);
    if (!isRecord(parsed) || parsed.version !== 1 || !isOnboardingDraft(parsed.draft)) {
      return null;
    }
    return parsed.draft;
  } catch {
    return null;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isStringRecord(value: unknown): value is Record<string, string> {
  return isRecord(value) && Object.values(value).every((item) => typeof item === "string");
}

function isImageryMedium(value: unknown): value is ImageryMedium {
  return typeof value === "string" && IMAGERY_MEDIA.some((medium) => medium === value);
}

function isColorRow(value: unknown): value is ColorRow {
  return (
    isRecord(value) &&
    typeof value.name === "string" &&
    typeof value.hex === "string" &&
    typeof value.usage === "string"
  );
}

function isCustomPillar(value: unknown): value is CustomPillar {
  return isRecord(value) && typeof value.name === "string" && typeof value.description === "string";
}

function isRefLink(value: unknown): value is RefLink {
  return (
    isRecord(value) &&
    typeof value.url === "string" &&
    typeof value.source === "string" &&
    typeof value.note === "string"
  );
}

function isOnboardingDraft(value: unknown): value is OnboardingDraft {
  if (!isRecord(value)) return false;

  return (
    (value.clientId === undefined || typeof value.clientId === "string") &&
    typeof value.step === "number" &&
    Number.isInteger(value.step) &&
    value.step >= 0 &&
    value.step <= 4 &&
    typeof value.clientName === "string" &&
    typeof value.industry === "string" &&
    typeof value.contactEmail === "string" &&
    typeof value.brandName === "string" &&
    typeof value.niche === "string" &&
    typeof value.targetAudience === "string" &&
    typeof value.brandVoice === "string" &&
    isImageryMedium(value.imageryMedium) &&
    typeof value.imageryStyleNotes === "string" &&
    isStringArray(value.toneKeywords) &&
    isStringArray(value.dos) &&
    isStringArray(value.donts) &&
    isStringRecord(value.handles) &&
    Array.isArray(value.colors) &&
    value.colors.every(isColorRow) &&
    typeof value.headingFont === "string" &&
    typeof value.bodyFont === "string" &&
    typeof value.logoNotes === "string" &&
    typeof value.logoMinSize === "string" &&
    isStringArray(value.selectedPresets) &&
    Array.isArray(value.customPillars) &&
    value.customPillars.every(isCustomPillar) &&
    Array.isArray(value.refLinks) &&
    value.refLinks.every(isRefLink)
  );
}
