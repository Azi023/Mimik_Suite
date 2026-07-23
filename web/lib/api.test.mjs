import assert from "node:assert/strict";
import { test } from "node:test";

import { ApiError, createClient } from "./api.ts";

test("ApiError carries parsed FastAPI validation detail", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () =>
    new Response(
      JSON.stringify({
        detail: [
          {
            type: "value_error",
            loc: ["body", "tokens", "colors", 0, "hex"],
            msg: "Value error, invalid hex colour",
            input: "not-a-colour",
          },
        ],
      }),
      {
        status: 422,
        headers: { "Content-Type": "application/json" },
      },
    );

  try {
    await assert.rejects(
      createClient({ name: "Broken" }, "test-token"),
      (error) => {
        assert.ok(error instanceof ApiError);
        assert.equal(error.status, 422);
        assert.deepEqual(error.detail, [
          {
            loc: ["body", "tokens", "colors", "0", "hex"],
            msg: "Value error, invalid hex colour",
          },
        ]);
        return true;
      },
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});
