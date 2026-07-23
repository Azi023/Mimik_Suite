import type { ApiValidationDetail } from "@/lib/api";

export interface OnboardingValidationFailure {
  message: string;
  stepIndex: number;
  field: string;
}

interface FieldLocation {
  label: string;
  stepName: string;
  stepIndex: number;
}

const FIELD_LOCATIONS: Readonly<Record<string, FieldLocation>> = {
  contact_email: { label: "Contact email", stepName: "Client", stepIndex: 0 },
  name: { label: "Client name", stepName: "Client", stepIndex: 0 },
  industry: { label: "Industry", stepName: "Client", stepIndex: 0 },
  slug: { label: "Brand slug", stepName: "Brand", stepIndex: 0 },
  niche: { label: "Niche", stepName: "Brand", stepIndex: 0 },
  target_audience: { label: "Target audience", stepName: "Brand", stepIndex: 0 },
  brand_voice: { label: "Brand voice", stepName: "Brand", stepIndex: 0 },
  imagery_style: { label: "Imagery style", stepName: "Brand", stepIndex: 0 },
  tone_keywords: { label: "Tone keywords", stepName: "Brand", stepIndex: 0 },
  handles: { label: "Social handles", stepName: "Brand", stepIndex: 0 },
  dos: { label: "Do's", stepName: "Brand", stepIndex: 0 },
  donts: { label: "Don'ts", stepName: "Brand", stepIndex: 0 },
  tokens: { label: "Brand tokens", stepName: "Brand kit", stepIndex: 1 },
  colors: { label: "Palette colors", stepName: "Brand kit", stepIndex: 1 },
  hex: { label: "Color hex", stepName: "Brand kit", stepIndex: 1 },
  typography: { label: "Typography", stepName: "Brand kit", stepIndex: 1 },
  heading_font: { label: "Heading font", stepName: "Brand kit", stepIndex: 1 },
  body_font: { label: "Body font", stepName: "Brand kit", stepIndex: 1 },
  hierarchy: { label: "Typography hierarchy", stepName: "Brand kit", stepIndex: 1 },
  logo: { label: "Logo details", stepName: "Brand kit", stepIndex: 1 },
  ref: { label: "Logo reference", stepName: "Brand kit", stepIndex: 1 },
  clear_space: { label: "Logo clear space", stepName: "Brand kit", stepIndex: 1 },
  min_size_px: { label: "Minimum logo size", stepName: "Brand kit", stepIndex: 1 },
  assessment: { label: "Logo notes", stepName: "Brand kit", stepIndex: 1 },
  references: { label: "References", stepName: "Style reference", stepIndex: 3 },
  url: { label: "Reference URL", stepName: "Style reference", stepIndex: 3 },
  source: { label: "Reference type", stepName: "Style reference", stepIndex: 3 },
  note: { label: "Reference note", stepName: "Style reference", stepIndex: 3 },
};

/** Convert the first recognizable FastAPI validation item into operator-facing recovery data. */
export function formatOnboardingValidationError(
  detail: readonly ApiValidationDetail[] | undefined,
): OnboardingValidationFailure | null {
  if (detail === undefined) return null;

  for (const item of detail) {
    const field = item.loc.at(-1);
    if (field === undefined) continue;
    const location = FIELD_LOCATIONS[field];
    if (location === undefined || item.msg.trim() === "") continue;
    const message = item.msg.trim();
    const punctuation = /[.!?]$/.test(message) ? "" : ".";
    return {
      message: `Couldn’t save — the ${location.label} (${location.stepName}) is invalid: ${message}${punctuation}`,
      stepIndex: location.stepIndex,
      field,
    };
  }
  return null;
}
