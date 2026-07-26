import assert from "node:assert/strict";
import { test } from "node:test";

import { ApiError, createClient, generateBrandKit } from "./api.ts";

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

test("generateBrandKit posts an explicit overwrite choice with bearer auth", async () => {
  const originalFetch = globalThis.fetch;
  let request;
  globalThis.fetch = async (input, init) => {
    request = { input, init };
    return new Response(JSON.stringify({ id: "brand-1" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    await generateBrandKit("brand-1", { overwrite: true }, "server-token");
    assert.match(String(request.input), /\/brands\/brand-1\/kit\/generate$/);
    assert.equal(request.init.method, "POST");
    assert.equal(request.init.headers.Authorization, "Bearer server-token");
    assert.equal(request.init.body, JSON.stringify({ overwrite: true }));
  } finally {
    globalThis.fetch = originalFetch;
  }
});
