import assert from "node:assert/strict";
import { test } from "node:test";

import {
  DRAFT_STORAGE_KEY,
  clearOnboardingDraft,
  composeImageryStyle,
  createInitialOnboardingDraft,
  parseOnboardingDraft,
  saveOnboardingDraft,
  serializeOnboardingDraft,
} from "./draft.ts";

test("uses the requested stable onboarding draft key", () => {
  assert.equal(DRAFT_STORAGE_KEY, "mimik:onboarding-draft");
});

test("composes imagery medium and optional notes into imagery_style", () => {
  assert.equal(composeImageryStyle("photography", "Natural light."), "MEDIUM: photography. Natural light.");
  assert.equal(composeImageryStyle("flat illustration", "  "), "MEDIUM: flat illustration.");
});

test("round-trips every serializable onboarding field", () => {
  const draft = {
    ...createInitialOnboardingDraft(),
    step: 3,
    clientName: "Glow Aesthetics",
    brandName: "Glow",
    imageryMedium: "product",
    imageryStyleNotes: "Clean studio shadows",
    dos: ["Keep shoulders covered"],
    donts: ["No real people"],
    refLinks: [{ url: "https://example.com/reference", source: "website", note: "Quiet composition" }],
  };

  assert.deepEqual(parseOnboardingDraft(serializeOnboardingDraft(draft)), draft);
});

test("ignores malformed or incompatible local drafts", () => {
  assert.equal(parseOnboardingDraft(null), null);
  assert.equal(parseOnboardingDraft("not-json"), null);
  assert.equal(parseOnboardingDraft(JSON.stringify({ version: 99, draft: {} })), null);
});

test("saves and clears the draft through the stable localStorage key", () => {
  const writes = new Map();
  const storage = {
    setItem(key, value) {
      writes.set(key, value);
    },
    removeItem(key) {
      writes.delete(key);
    },
  };
  const draft = { ...createInitialOnboardingDraft(), brandName: "Glow" };

  saveOnboardingDraft(storage, draft);
  assert.deepEqual(parseOnboardingDraft(writes.get(DRAFT_STORAGE_KEY)), draft);

  clearOnboardingDraft(storage);
  assert.equal(writes.has(DRAFT_STORAGE_KEY), false);
});
