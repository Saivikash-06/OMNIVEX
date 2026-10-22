/**
 * OMNIVEX API Client Unit Tests
 * Uses Node's built-in test runner (node --test) with mocked global.fetch.
 * No external test frameworks or dependencies required.
 */

import test from "node:test";
import assert from "node:assert/strict";
import { OmnivexClient } from "../js/api/client.js";

// Helper to mock global fetch
function withMockFetch(mockFn, testFn) {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = mockFn;
  return Promise.resolve()
    .then(testFn)
    .finally(() => {
      globalThis.fetch = originalFetch;
    });
}

test("OmnivexClient - Success path (200 OK with JSON)", async () => {
  await withMockFetch(
    async (url, opts) => {
      return new Response(JSON.stringify({ status: "ok", version: "2.0.0" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
    async () => {
      const client = new OmnivexClient({ baseUrl: "http://test-server" });
      const res = await client.health();

      assert.equal(res.ok, true);
      assert.equal(res.status, 200);
      assert.equal(res.data.status, "ok");
      assert.equal(res.error, null);
      assert.ok(typeof res.elapsedMs === "number");
    }
  );
});

test("OmnivexClient - 422 Validation Error with field details", async () => {
  await withMockFetch(
    async (url, opts) => {
      const body = {
        detail: [
          { loc: ["body", "target_column"], msg: "field required", type: "value_error.missing" },
        ],
      };
      return new Response(JSON.stringify(body), {
        status: 422,
        headers: { "Content-Type": "application/json" },
      });
    },
    async () => {
      const client = new OmnivexClient({ baseUrl: "http://test-server" });
      const res = await client.trainModel({ name: "m", dataset_id: "d", target_column: "t" });

      assert.equal(res.ok, false);
      assert.equal(res.status, 422);
      assert.equal(res.error.code, "VALIDATION_ERROR");
      assert.ok(res.error.details.length > 0);
      assert.match(res.error.details[0], /target_column/);
    }
  );
});

test("OmnivexClient - 404 Not Found mapping", async () => {
  await withMockFetch(
    async () => {
      return new Response(JSON.stringify({ error: { code: "NOT_FOUND", message: "Dataset not found" } }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      });
    },
    async () => {
      const client = new OmnivexClient({ baseUrl: "http://test-server" });
      const res = await client.getDataset("non-existent-id");

      assert.equal(res.ok, false);
      assert.equal(res.status, 404);
      assert.equal(res.error.code, "NOT_FOUND");
    }
  );
});

test("OmnivexClient - 413 Payload Too Large mapping", async () => {
  await withMockFetch(
    async () => {
      return new Response(JSON.stringify({ error: { code: "PAYLOAD_TOO_LARGE", message: "File exceeds 10MB limit" } }), {
        status: 413,
        headers: { "Content-Type": "application/json" },
      });
    },
    async () => {
      const client = new OmnivexClient({ baseUrl: "http://test-server" });
      const fakeFile = new Blob(["big content"]);
      const res = await client.uploadDataset(fakeFile);

      assert.equal(res.ok, false);
      assert.equal(res.status, 413);
      assert.equal(res.error.code, "PAYLOAD_TOO_LARGE");
    }
  );
});

test("OmnivexClient - 429 Rate Limited with retry info surfaced", async () => {
  await withMockFetch(
    async () => {
      return new Response(JSON.stringify({ detail: "Rate limit exceeded" }), {
        status: 429,
        headers: { "Content-Type": "application/json", "Retry-After": "15" },
      });
    },
    async () => {
      const client = new OmnivexClient({ baseUrl: "http://test-server" });
      const res = await client.health();

      assert.equal(res.ok, false);
      assert.equal(res.status, 429);
      assert.equal(res.error.code, "RATE_LIMITED");
      assert.match(res.error.message, /15 seconds/);
    }
  );
});

test("OmnivexClient - 5xx Internal Server Error mapping", async () => {
  await withMockFetch(
    async () => {
      return new Response("Internal Server Error", {
        status: 500,
        headers: { "Content-Type": "text/plain" },
      });
    },
    async () => {
      const client = new OmnivexClient({ baseUrl: "http://test-server" });
      const res = await client.health();

      assert.equal(res.ok, false);
      assert.equal(res.status, 500);
      assert.equal(res.error.code, "SERVER_ERROR");
    }
  );
});

test("OmnivexClient - Network connection refused", async () => {
  await withMockFetch(
    async () => {
      throw new Error("fetch failed: ECONNREFUSED");
    },
    async () => {
      const client = new OmnivexClient({ baseUrl: "http://down-server" });
      const res = await client.health();

      assert.equal(res.ok, false);
      assert.equal(res.status, 0);
      assert.equal(res.error.code, "NETWORK_ERROR");
    }
  );
});

test("OmnivexClient - Request timeout via AbortController", async () => {
  await withMockFetch(
    async () => {
      const err = new Error("The operation was aborted");
      err.name = "AbortError";
      throw err;
    },
    async () => {
      const client = new OmnivexClient({ baseUrl: "http://slow-server", timeoutMs: 50 });
      const res = await client.health();

      assert.equal(res.ok, false);
      assert.equal(res.error.code, "TIMEOUT");
    }
  );
});

test("OmnivexClient - Invalid JSON in 200 response handled safely", async () => {
  await withMockFetch(
    async () => {
      return new Response("Invalid {JSON syntax", {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
    async () => {
      const client = new OmnivexClient({ baseUrl: "http://bad-json" });
      const res = await client.health();

      assert.equal(res.ok, true);
      assert.equal(res.data, null);
    }
  );
});

test("OmnivexClient - API Key header attached only when configured and redacted from errors", async () => {
  let capturedHeaders = null;
  await withMockFetch(
    async (url, opts) => {
      capturedHeaders = opts.headers;
      return new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
    async () => {
      const SECRET_KEY = "super-secret-key-12345";
      const client = new OmnivexClient({ baseUrl: "http://auth-server", apiKey: SECRET_KEY });
      await client.health();

      assert.equal(capturedHeaders["X-API-Key"], SECRET_KEY);

      // Verify that if a network error occurs, key is not in error text
      globalThis.fetch = async () => { throw new Error("Connection failed"); };
      const errRes = await client.health();
      assert.ok(!JSON.stringify(errRes).includes(SECRET_KEY));
    }
  );
});

test("OmnivexClient - GET retried at most twice; POST is NEVER retried", async () => {
  let getCallCount = 0;
  let postCallCount = 0;

  await withMockFetch(
    async (url, opts) => {
      if (opts.method === "GET") {
        getCallCount++;
        throw new Error("Network transient failure");
      } else {
        postCallCount++;
        throw new Error("POST failure");
      }
    },
    async () => {
      const client = new OmnivexClient({ baseUrl: "http://test-server" });

      // GET request should attempt 1 initial + 2 retries = 3 calls total
      await client.health();
      assert.equal(getCallCount, 3);

      // POST request must only be called once
      await client.trainModel({ name: "m", dataset_id: "d", target_column: "t" });
      assert.equal(postCallCount, 1);
    }
  );
});

test("OmnivexClient - Malicious IDs rejected before sending any network request", async () => {
  let fetchCalled = false;
  await withMockFetch(
    async () => {
      fetchCalled = true;
      return new Response("{}", { status: 200 });
    },
    async () => {
      const client = new OmnivexClient({ baseUrl: "http://test-server" });

      const traversalRes = await client.getDataset("../etc/passwd");
      assert.equal(traversalRes.ok, false);
      assert.equal(traversalRes.error.code, "INVALID_INPUT");
      assert.equal(fetchCalled, false);

      const encodedTraversalRes = await client.getModel("mod%2e%2e/sub");
      assert.equal(encodedTraversalRes.ok, false);
      assert.equal(encodedTraversalRes.error.code, "INVALID_INPUT");
      assert.equal(fetchCalled, false);

      const giantId = "a".repeat(500);
      const giantRes = await client.getExperiment(giantId);
      assert.equal(giantRes.ok, false);
      assert.equal(giantRes.error.code, "INVALID_INPUT");
      assert.equal(fetchCalled, false);
    }
  );
});
