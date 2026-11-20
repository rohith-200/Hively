import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { createServer, type ViteDevServer } from "vite";
import { verifyEvents } from "../mocks/server";
import {
  selectedTotals,
  validatePhoto,
  type Run,
  type AuditEvent,
} from "../src/lib/types";

let server: ViteDevServer;
let base: string;
before(async () => {
  server = await createServer({
    server: { host: "127.0.0.1", port: 0, strictPort: false },
    logLevel: "silent",
  });
  await server.listen();
  const address = server.httpServer!.address();
  assert.ok(address && typeof address !== "string");
  base = `http://127.0.0.1:${address.port}`;
});
after(async () => {
  await server?.close();
});
const photo = new File(
  [
    Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j6p0AAAAASUVORK5CYII=",
      "base64",
    ),
  ],
  "hivly-sample-kitchen.png",
  { type: "image/png" },
);
async function start(
  budget = 400,
  stores = "shopify,amazon,walmart",
  filename = photo.name,
  userId = "contract-test",
) {
  const form = new FormData();
  form.append("photo", new File([photo], filename, { type: "image/png" }));
  form.append("user_id", userId);
  form.append("budget_usd", String(budget));
  form.append("stores", stores);
  const response = await fetch(`${base}/api/runs`, {
    method: "POST",
    body: form,
  });
  assert.equal(response.status, 201);
  return (await response.json()).run_id as string;
}
async function ready(id: string) {
  const response = await fetch(`${base}/api/runs/${id}/events`);
  assert.match(
    response.headers.get("content-type") || "",
    /text\/event-stream/,
  );
  return response.text();
}
const getRun = async (id: string) =>
  (await (await fetch(`${base}/api/runs/${id}`)).json()) as Run;

test("photo → 600ms SSE steps → review → edited approval → store results → verified audit", async () => {
  const health = await (await fetch(`${base}/api/health`)).json();
  assert.equal(health.ok, true);
  assert.equal(health.modes.payments, "mock");
  const id = await start();
  const stream = await ready(id);
  assert.match(stream, /event: step/);
  assert.match(stream, /event: run/);
  assert.match(stream, /awaiting_approval/);
  const run = await getRun(id);
  assert.equal(run.state, "awaiting_approval");
  assert.equal(run.items.length, 5);
  assert.ok(run.totals.items_usd <= 400);
  const ids = run.items
    .filter((i) => !["ri_2", "ri_3"].includes(i.id))
    .map((i) => i.id);
  const response = await fetch(`${base}/api/runs/${id}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ selected_item_ids: ids }),
  });
  assert.equal(response.status, 200);
  const result: Run = await response.json();
  assert.equal(result.state, "completed");
  assert.equal(result.totals.items_usd, 193.94);
  assert.equal(result.totals.captured_usd, 89);
  assert.equal(result.items.find((i) => i.id === "ri_2")!.selected, false);
  assert.deepEqual(
    result.merchant_results.map((r) => r.status),
    ["ordered", "cart_ready", "cart_ready"],
  );
  assert.ok(
    result.merchant_results
      .filter((r) => r.url)
      .every((r) => r.url!.startsWith("/demo-cart/")),
  );
  const audit: { events: AuditEvent[]; chain_valid: boolean } = await (
    await fetch(`${base}/api/runs/${id}/audit`)
  ).json();
  assert.equal(audit.chain_valid, true);
  assert.equal(verifyEvents(id, audit.events), true);
  const altered = structuredClone(audit.events);
  altered[1].data.confidence = 0;
  assert.equal(verifyEvents(id, altered), false);
  const secondApproval = await fetch(`${base}/api/runs/${id}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ selected_item_ids: ids }),
  });
  assert.equal(secondApproval.status, 409);
  assert.equal((await secondApproval.json()).error.code, "INVALID_STATE");
  const repeatId = await start(
    400,
    "shopify,amazon,walmart",
    photo.name,
    "contract-test",
  );
  const repeatStream = await ready(repeatId);
  const repeated = await getRun(repeatId);
  assert.ok(repeated.items.every((i) => !["ri_2", "ri_3"].includes(i.id)));
  assert.match(repeatStream, /Previously removed/);
});

test("different room samples and arbitrary uploads keep distinct, honest profiles", async () => {
  const livingId = await start(
    400,
    "shopify,amazon,walmart",
    "hivly-sample-living-room.png",
    "multi-room",
  );
  const unknownId = await start(
    400,
    "shopify,amazon,walmart",
    "my-kitchen-or-anything.png",
    "unknown-upload",
  );
  await Promise.all([ready(livingId), ready(unknownId)]);
  const living = await getRun(livingId);
  const unknown = await getRun(unknownId);
  assert.equal(living.room?.room_type, "living room");
  assert.ok(living.items.every((i) => i.category !== "knife block"));
  assert.equal(unknown.room?.room_type, "room");
  assert.equal(unknown.room?.style_confidence, 0);
  assert.match(unknown.room!.evidence, /not been analyzed/);
});

test("a budget with no suitable products produces a reviewable empty result without a hold", async () => {
  const id = await start(
    1,
    "amazon",
    "hivly-sample-bedroom.png",
    "empty-result",
  );
  await ready(id);
  const result = await getRun(id);
  assert.equal(result.state, "awaiting_approval");
  assert.deepEqual(result.items, []);
  assert.equal(result.totals.held_usd, 0);
  assert.equal(result.payment.status, "none");
  const response = await fetch(`${base}/api/runs/${id}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ selected_item_ids: [] }),
  });
  assert.equal(response.status, 400);
});

test("store selection and low budget constrain picks; rejection releases the hold", async () => {
  const id = await start(100, "shopify");
  await ready(id);
  const run = await getRun(id);
  assert.equal(run.items.length, 1);
  assert.equal(run.items[0].product.store, "shopify");
  assert.equal(run.totals.items_usd, 89);
  const response = await fetch(`${base}/api/runs/${id}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason: "Trying a different style" }),
  });
  const result: Run = await response.json();
  assert.equal(result.state, "rejected");
  assert.equal(result.payment.status, "canceled");
  assert.equal(result.totals.held_usd, 0);
  assert.equal(result.totals.captured_usd, 0);
});

test("invalid forms and expired sessions return the frozen error envelope", async () => {
  const missing = await fetch(`${base}/api/runs/r_missing`);
  assert.equal(missing.status, 404);
  assert.equal((await missing.json()).error.code, "RUN_NOT_FOUND");
  const form = new FormData();
  form.append("photo", new File(["bad"], "bad.txt", { type: "text/plain" }));
  form.append("user_id", "test");
  form.append("budget_usd", "400");
  form.append("stores", "amazon");
  const response = await fetch(`${base}/api/runs`, {
    method: "POST",
    body: form,
  });
  assert.equal(response.status, 400);
  assert.equal((await response.json()).error.code, "BAD_INPUT");
  assert.match(
    validatePhoto({ size: 9 * 1024 * 1024, type: "image/png" })!,
    /8 MB/,
  );
  assert.match(
    validatePhoto({ size: 12, type: "image/svg+xml" })!,
    /JPG or PNG/,
  );
});

test("selection totals avoid floating-point cents and keep store payment modes separate", () => {
  const items = [
    { id: "a", execution_mode: "auto_buy", product: { price_usd: 0.1 } },
    { id: "b", execution_mode: "cart_link", product: { price_usd: 0.2 } },
  ] as Run["items"];
  assert.deepEqual(selectedTotals(items, ["a", "b"]), {
    count: 2,
    total: 0.3,
    auto: 0.1,
    carts: 0.2,
  });
  assert.deepEqual(selectedTotals(items, []), {
    count: 0,
    total: 0,
    auto: 0,
    carts: 0,
  });
});
