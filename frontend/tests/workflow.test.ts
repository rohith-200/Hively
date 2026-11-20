import assert from "node:assert/strict";
import { test } from "node:test";
import { watchRun } from "../src/lib/api";
import {
  agentTimeline,
  actorForEvent,
  roomLabel,
  executionLabel,
} from "../src/lib/workflow";
import { createFixture, demoScenarioForFile } from "../mocks/fixtures";
import type { AuditEvent, Run } from "../src/lib/types";

const event = (actor: string, action: string, seq = 0): AuditEvent => ({
  seq,
  actor,
  action,
  ts: new Date().toISOString(),
  summary: action,
  data: {},
  hash: "test",
  prev_hash: "test",
});
test("room type comes from backend data, not arbitrary upload filenames", () => {
  assert.equal(demoScenarioForFile("my-living-room-photo.png"), "generic");
  assert.equal(demoScenarioForFile("kitchen-vacation-photo.jpg"), "generic");
  assert.equal(
    demoScenarioForFile("hivly-sample-living-room.png"),
    "living-room",
  );
  const living = createFixture(
    "living",
    "test",
    400,
    ["shopify", "amazon", "walmart"],
    "living-room",
  );
  const bedroom = createFixture(
    "bed",
    "test",
    400,
    ["shopify", "amazon", "walmart"],
    "bedroom",
  );
  const generic = createFixture("any", "test", 400, [
    "shopify",
    "amazon",
    "walmart",
  ]);
  assert.equal(living.room?.room_type, "living room");
  assert.ok(living.items.every((i) => i.category !== "knife block"));
  assert.equal(bedroom.room?.room_type, "bedroom");
  assert.ok(bedroom.items.some((i) => i.category === "bed linen"));
  assert.equal(generic.room?.room_type, "room");
  assert.equal(generic.room?.style_confidence, 0);
  assert.deepEqual(generic.room?.palette, []);
  assert.ok(
    generic.items.every(
      (item) => item.score === 0 && item.critic_note === null,
    ),
  );
  assert.equal(roomLabel("home_office"), "Home Office");
});
test("only received step events complete agent tasks, and blocked guardrails stop progress", () => {
  const timeline = agentTimeline(
    [event("vision", "room_analyzed")],
    "analyzing",
  );
  assert.equal(timeline[0].status, "done");
  assert.equal(timeline[1].status, "working");
  assert.equal(timeline[2].status, "waiting");
  const stopped = agentTimeline(
    [event("policy", "guardrails_blocked")],
    "analyzing",
  );
  assert.equal(stopped[6].status, "blocked");
  assert.ok(stopped.every((a) => a.status !== "working"));
  const missing = agentTimeline(
    [event("critic", "llm.critic")],
    "awaiting_approval",
  );
  assert.equal(missing[0].status, "waiting");
  assert.equal(missing[5].status, "done");
  assert.equal(actorForEvent(event("system", "llm_curator_done")), "curator");
  assert.equal(executionLabel("product_link"), "Open product page");
});
test("SSE failure falls back to polling and advances even when the audit endpoint fails", async () => {
  const target = new EventTarget();
  let closed = 0;
  let fallback = 0;
  let calls = 0;
  const run: Run = {
    ...createFixture("poll-test", "test", 400, ["amazon"], "living-room"),
    state: "awaiting_approval",
  };
  const completed = new Promise<Run>((resolve, reject) => {
    watchRun(
      run.id,
      {
        onStep: () => {},
        onRun: resolve,
        onError: reject,
        onFallback: () => fallback++,
      },
      {
        stream: () =>
          ({
            addEventListener: target.addEventListener.bind(target),
            close: () => {
              closed++;
            },
          }) as Pick<EventSource, "addEventListener" | "close">,
        run: async () => {
          calls++;
          return run;
        },
        audit: async () => {
          throw new Error("Audit temporarily unavailable");
        },
        interval: 5,
      },
    );
  });
  target.dispatchEvent(new Event("error"));
  assert.equal((await completed).state, "awaiting_approval");
  assert.equal(fallback, 1);
  assert.equal(calls, 1);
  assert.ok(closed >= 1);
});
test("subscription cleanup cancels polling and ignores late events", async () => {
  const target = new EventTarget();
  let updates = 0;
  let closed = 0;
  const run = createFixture("stopped", "test", 100, ["amazon"]);
  const stop = watchRun(
    run.id,
    {
      onStep: () => updates++,
      onRun: () => updates++,
      onError: () => {},
      onFallback: () => {},
    },
    {
      stream: () =>
        ({
          addEventListener: target.addEventListener.bind(target),
          close: () => {
            closed++;
          },
        }) as Pick<EventSource, "addEventListener" | "close">,
      run: async () => run,
      audit: async () => ({ events: [], chain_valid: true }),
      interval: 5,
    },
  );
  stop();
  const late = new Event("step");
  Object.defineProperty(late, "data", {
    value: JSON.stringify(event("vision", "room_analyzed")),
  });
  target.dispatchEvent(late);
  target.dispatchEvent(new Event("error"));
  assert.equal(updates, 0);
  assert.equal(closed, 1);
});
test("a stalled audit request does not hold up terminal run status", async () => {
  const target = new EventTarget();
  const run: Run = {
    ...createFixture("slow-audit", "test", 400, ["amazon"]),
    state: "awaiting_approval",
  };
  const terminal = new Promise<Run>((resolve, reject) => {
    watchRun(
      run.id,
      {
        onStep: () => {},
        onRun: resolve,
        onError: reject,
        onFallback: () => {},
      },
      {
        stream: () =>
          ({
            addEventListener: target.addEventListener.bind(target),
            close: () => {},
          }) as Pick<EventSource, "addEventListener" | "close">,
        run: async () => run,
        audit: () => new Promise(() => {}),
        interval: 5,
      },
    );
  });
  target.dispatchEvent(new Event("error"));
  assert.equal((await terminal).state, "awaiting_approval");
});
