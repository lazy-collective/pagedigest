import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

// Load the deployment module without changing the site's package boundaries.
const source = await readFile(new URL("../site/_worker.js", import.meta.url), "utf8");
const { default: worker } = await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);

test("HTML bytes, status and headers survive the no-transform response policy", async () => {
  for (const status of [200, 404]) {
    const body = "<!doctype html>\n<p>exact bytes \u00e9</p>\n";
    const response = await worker.fetch(new Request("https://example.com/page"), {
      ASSETS: { fetch: async () => new Response(body, { status, headers: {
        "content-type": "text/html; charset=utf-8", "cache-control": "public, max-age=300, must-revalidate",
        etag: '"build"', link: '</.well-known/pagedigest.json>; rel="https://pagedigest.org/rel"',
      } }) },
    });
    assert.equal(await response.text(), body);
    assert.equal(response.status, status);
    assert.equal(response.headers.get("cache-control"), "public, max-age=300, must-revalidate, no-transform");
    assert.equal(response.headers.get("etag"), '"build"');
    assert.match(response.headers.get("link"), /pagedigest/);
  }
});

test("preserves existing no-transform and non-HTML responses", async () => {
  for (const type of ["text/html", "application/json"]) {
    const response = await worker.fetch(new Request("https://example.com/"), {
      ASSETS: { fetch: async () => new Response("body", { headers: {
        "content-type": type, "cache-control": "private, No-Transform",
      } }) },
    });
    assert.equal(response.headers.get("cache-control"), "private, No-Transform");
    assert.equal(await response.text(), "body");
  }
  const asset = new Response("{}", { headers: { "content-type": "application/json" } });
  const response = await worker.fetch(new Request("https://example.com/.well-known/pagedigest.json"), {
    ASSETS: { fetch: async () => asset },
  });
  assert.equal(response, asset);
  assert.equal(response.headers.get("cache-control"), null);
});

test("cooperation endpoint keeps its observation behavior", async () => {
  const values = new Map([["manifest_requests", "9"], ["state_valid", "2"]]);
  const pending = [];
  const response = await worker.fetch(new Request("https://example.com/__pagedigest/cooperation.json", {
    headers: { "PageDigest-State": "site_rev=13" },
  }), { PAGEDIGEST_OBSERVATIONS: {
    get: async (key) => values.get(key), put: async (key, value) => values.set(key, value),
  } }, { waitUntil: (promise) => pending.push(promise) });
  await Promise.all(pending);
  assert.equal(response.headers.get("cache-control"), "no-cache");
  assert.equal((await response.json()).manifestRequests, 9);
  assert.equal(values.get("manifest_requests"), "9");
  assert.equal(values.get("state_valid"), "3");
});
