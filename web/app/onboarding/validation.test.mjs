import assert from "node:assert/strict";
import { test } from "node:test";

import { formatOnboardingValidationError } from "./validation.ts";

test("names the invalid email and Client step", () => {
  assert.deepEqual(
    formatOnboardingValidationError([
      {
        loc: ["body", "contact_email"],
        msg: "value is not a valid email address",
      },
    ]),
    {
      message:
        "Couldn’t save — the Contact email (Client) is invalid: value is not a valid email address.",
      stepIndex: 0,
      field: "contact_email",
    },
  );
});

test("maps a nested token colour error back to Brand kit", () => {
  assert.deepEqual(
    formatOnboardingValidationError([
      {
        loc: ["body", "tokens", "colors", "0", "hex"],
        msg: "Value error, invalid hex colour",
      },
    ]),
    {
      message:
        "Couldn’t save — the Color hex (Brand kit) is invalid: Value error, invalid hex colour.",
      stepIndex: 1,
      field: "hex",
    },
  );
});

test("returns null when validation detail cannot identify an onboarding field", () => {
  assert.equal(
    formatOnboardingValidationError([
      {
        loc: ["query", "unknown"],
        msg: "Invalid",
      },
    ]),
    null,
  );
});
