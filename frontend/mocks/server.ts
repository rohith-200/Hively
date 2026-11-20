import { createHash, randomUUID } from "node:crypto";
import type { IncomingMessage, ServerResponse } from "node:http";
import type { Connect, Plugin } from "vite";
import { createFixture, demoSteps, demoScenarioForFile } from "./fixtures";
import type { AuditEvent, Run, Store } from "../src/lib/types";
import { selectedTotals } from "../src/lib/types";

type Session = {
  run: Run;
  events: AuditEvent[];
  photo: Buffer;
  mediaType: string;
  started: number;
  timer?: ReturnType<typeof setInterval>;
  listeners: Set<ServerResponse>;
  plan: Run;
};
const sessions = new Map<string, Session>();
const taste = new Map<string, { facts: string[]; avoid: string[] }>();
const MAX_BODY = 9 * 1024 * 1024;
export function hashEvent(runId: string, event: Omit<AuditEvent, "hash">) {
  // Canonical JSON for the local demo. The live backend owns its audit canonicalization and verification.
  const stable = (value: unknown): string => {
    if (Array.isArray(value)) return `[${value.map(stable).join(",")}]`;
    if (value && typeof value === "object")
      return `{${Object.entries(value)
        .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
        .map(([k, v]) => `${JSON.stringify(k)}:${stable(v)}`)
        .join(",")}}`;
    return JSON.stringify(value);
  };
  return createHash("sha256")
    .update(
      event.prev_hash +
        runId +
        event.seq +
        event.ts +
        event.actor +
        event.action +
        stable(event.data),
    )
    .digest("hex");
}
export function verifyEvents(runId: string, events: AuditEvent[]) {
  return events.every(
    (event, index) =>
      event.seq === index &&
      event.prev_hash === (events[index - 1]?.hash ?? "0".repeat(64)) &&
      event.hash === hashEvent(runId, event),
  );
}
function emit(session: Session, name: string, data: unknown) {
  const body = `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;
  session.listeners.forEach((response) => response.write(body));
}
function append(
  session: Session,
  actor: string,
  action: string,
  summary: string,
  data: Record<string, unknown> = {},
) {
  const event = {
    seq: session.events.length,
    ts: new Date().toISOString(),
    actor,
    action,
    summary,
    data,
    prev_hash: session.events.at(-1)?.hash ?? "0".repeat(64),
  };
  const complete = { ...event, hash: hashEvent(session.run.id, event) };
  session.events.push(complete);
  emit(session, "step", complete);
}
function finishStream(session: Session) {
  emit(session, "run", session.run);
  emit(session, "state", { state: session.run.state });
  session.listeners.forEach((res) => res.end());
  session.listeners.clear();
}
function reply(res: ServerResponse, status: number, data: unknown) {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(data));
}
function fail(
  res: ServerResponse,
  status: number,
  code: string,
  message: string,
) {
  reply(res, status, { error: { code, message } });
}
async function body(req: IncomingMessage) {
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > MAX_BODY) throw new Error("BODY_TOO_LARGE");
    chunks.push(Buffer.from(chunk));
  }
  return Buffer.concat(chunks);
}
const handler: Connect.NextHandleFunction = async (req, res, next) => {
  const path = (req.url || "").split("?")[0];
  if (!path.startsWith("/api/")) return next();
  try {
    if (path === "/api/health" && req.method === "GET")
      return reply(res, 200, {
        ok: true,
        modes: {
          vision: "mock",
          llm: "mock",
          db: "mock",
          memory: "mock",
          analytics: "mock",
          payments: "mock",
        },
      });
    if (path === "/api/runs" && req.method === "POST") {
      const bytes = await body(req);
      const request = new Request("http://localhost/api/runs", {
        method: "POST",
        headers: { "Content-Type": req.headers["content-type"] || "" },
        body: new Uint8Array(bytes),
      });
      const form = await request.formData();
      const photo = form.get("photo");
      const budget = Number(form.get("budget_usd"));
      const userId = String(form.get("user_id") || "").trim();
      const stores = String(form.get("stores") || "").split(",") as Store[];
      if (
        !(photo instanceof File) ||
        !["image/jpeg", "image/png"].includes(photo.type) ||
        !photo.size ||
        photo.size > 8 * 1024 * 1024 ||
        !userId ||
        !Number.isFinite(budget) ||
        budget < 1 ||
        !stores.length ||
        stores.some((s) => !["shopify", "amazon", "walmart"].includes(s))
      )
        return fail(
          res,
          400,
          "BAD_INPUT",
          "Provide a JPG/PNG under 8 MB, a budget above $0, and at least one store.",
        );
      const id = `r_${randomUUID().slice(0, 8)}`;
      const memory = taste.get(userId) || { facts: [], avoid: [] };
      const note = String(form.get("note") || "");
      const plan = createFixture(
        id,
        userId,
        budget,
        stores,
        demoScenarioForFile(photo.name),
        memory.avoid,
      );
      const run: Run = {
        ...structuredClone(plan),
        room: null,
        items: [],
        skipped: [],
        totals: {
          items_usd: 0,
          auto_buy_usd: 0,
          cart_link_usd: 0,
          held_usd: 0,
          captured_usd: 0,
        },
        payment: { mode: "mock", payment_intent_id: null, status: "none" },
      };
      const steps = demoSteps(plan, note, memory.facts);
      const session: Session = {
        run,
        events: [],
        photo: Buffer.from(await photo.arrayBuffer()),
        mediaType: photo.type,
        started: Date.now(),
        listeners: new Set(),
        plan,
      };
      sessions.set(id, session);
      append(
        session,
        "user",
        "run_started",
        "A new room, a fresh possibility.",
        { budget_usd: budget, stores, demo: true },
      );
      let step = 0;
      session.timer = setInterval(() => {
        const { actor, action, summary, data } = steps[step];
        if (actor === "vision") session.run.room = plan.room;
        if (actor === "curator") {
          session.run.items = plan.items;
          session.run.skipped = plan.skipped;
        }
        if (actor === "payments") {
          session.run.totals = plan.totals;
          session.run.payment = plan.payment;
        }
        append(session, actor, action, summary, data);
        step++;
        if (step === steps.length) {
          clearInterval(session.timer);
          session.run.state = "awaiting_approval";
          finishStream(session);
        }
      }, 600);
      return reply(res, 201, { run_id: id, state: "analyzing" });
    }
    const match = path.match(
      /^\/api\/runs\/([^/]+)(?:\/(events|approve|reject|audit|photo))?$/,
    );
    if (!match)
      return fail(
        res,
        404,
        "RUN_NOT_FOUND",
        "This endpoint could not be found.",
      );
    const session = sessions.get(match[1]);
    if (!session)
      return fail(
        res,
        404,
        "RUN_NOT_FOUND",
        "This room session has expired. Start a new room.",
      );
    const endpoint = match[2];
    if (!endpoint && req.method === "GET") return reply(res, 200, session.run);
    if (endpoint === "photo" && req.method === "GET") {
      res.writeHead(200, {
        "Content-Type": session.mediaType,
        "Cache-Control": "private, max-age=3600",
      });
      return res.end(session.photo);
    }
    if (endpoint === "audit" && req.method === "GET")
      return reply(res, 200, {
        events: session.events,
        chain_valid: verifyEvents(session.run.id, session.events),
      });
    if (endpoint === "events" && req.method === "GET") {
      res.writeHead(200, {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
        "X-Accel-Buffering": "no",
      });
      res.flushHeaders();
      session.events.forEach((event) =>
        res.write(`event: step\ndata: ${JSON.stringify(event)}\n\n`),
      );
      if (
        session.run.state !== "analyzing" &&
        session.run.state !== "executing"
      ) {
        res.write(`event: run\ndata: ${JSON.stringify(session.run)}\n\n`);
        return res.end();
      }
      session.listeners.add(res);
      req.on("close", () => session.listeners.delete(res));
      return;
    }
    if (endpoint === "approve" && req.method === "POST") {
      if (session.run.state !== "awaiting_approval")
        return fail(
          res,
          409,
          "INVALID_STATE",
          "This room is no longer awaiting approval.",
        );
      const input = JSON.parse((await body(req)).toString());
      const ids = input.selected_item_ids;
      if (
        !Array.isArray(ids) ||
        !ids.length ||
        new Set(ids).size !== ids.length ||
        ids.some(
          (id) =>
            typeof id !== "string" ||
            !session.run.items.some((item) => item.id === id),
        )
      )
        return fail(res, 400, "BAD_INPUT", "Select at least one valid item.");
      const totals = selectedTotals(session.run.items, ids);
      if (totals.total > session.run.budget_usd)
        return fail(
          res,
          400,
          "BAD_INPUT",
          "The selected items exceed the room budget.",
        );
      session.run.state = "executing";
      append(session, "user", "run_approved", "You approved your collection.", {
        selected_item_ids: ids,
      });
      session.run.items.forEach((item) => {
        item.selected = ids.includes(item.id);
      });
      session.run.totals = {
        items_usd: totals.total,
        auto_buy_usd: totals.auto,
        cart_link_usd: totals.carts,
        held_usd: totals.auto,
        captured_usd: totals.auto,
      };
      session.run.payment.status = totals.auto > 0 ? "captured" : "none";
      session.run.merchant_results = (
        ["shopify", "amazon", "walmart"] as Store[]
      ).flatMap((store) => {
        const items = session.run.items.filter(
          (i) => i.selected && i.product.store === store,
        );
        if (!items.length) return [];
        return [
          {
            store,
            mode:
              store === "shopify"
                ? ("auto_buy" as const)
                : ("cart_link" as const),
            status:
              store === "shopify"
                ? ("ordered" as const)
                : ("cart_ready" as const),
            url:
              store === "shopify"
                ? null
                : `/demo-cart/${session.run.id}/${store}`,
            item_ids: items.map((i) => i.id),
            amount_usd: selectedTotals(items, ids).total,
            order_id:
              store === "shopify"
                ? `DEMO-${session.run.id.slice(2).toUpperCase()}`
                : null,
            error: null,
          },
        ];
      });
      append(
        session,
        "merchant",
        "merchant_executed",
        "Your demo order and preview carts are ready.",
        { demo: true },
      );
      append(
        session,
        "payments",
        "payment_captured",
        `Simulated studio payment: $${totals.auto.toFixed(2)}. No money moved.`,
        { demo: true, amount_usd: totals.auto },
      );
      session.run.state = "completed";
      const removed = session.run.items
        .filter((i) => !i.selected)
        .map((i) => i.category);
      const memory = taste.get(session.run.user_id) || { facts: [], avoid: [] };
      taste.set(session.run.user_id, {
        facts: [
          ...new Set([
            ...memory.facts,
            ...removed.map((c) => `Previously removed ${c}`),
            `Approved ${ids.length} items in your last collection`,
          ]),
        ].slice(-8),
        avoid: [...new Set([...memory.avoid, ...removed])],
      });
      append(
        session,
        "memory",
        "preferences_learned",
        "Saved your approvals and removals in this local demo session.",
        {
          removed_categories: removed,
          selected_item_ids: ids,
          source: "local demo memory",
          demo: true,
        },
      );
      finishStream(session);
      return reply(res, 200, session.run);
    }
    if (endpoint === "reject" && req.method === "POST") {
      if (session.run.state !== "awaiting_approval")
        return fail(
          res,
          409,
          "INVALID_STATE",
          "This room is no longer awaiting approval.",
        );
      const input = JSON.parse((await body(req)).toString());
      session.run.state = "rejected";
      session.run.payment.status = "canceled";
      session.run.totals.held_usd = 0;
      append(
        session,
        "user",
        "run_rejected",
        "Collection declined. The payment hold was released.",
        { reason: String(input.reason || "") },
      );
      finishStream(session);
      return reply(res, 200, session.run);
    }
    return fail(res, 405, "BAD_INPUT", "This action is not available.");
  } catch (error) {
    if (error instanceof SyntaxError || error instanceof TypeError)
      return fail(
        res,
        400,
        "BAD_INPUT",
        "The request could not be read. Please check your inputs.",
      );
    if (error instanceof Error && error.message === "BODY_TOO_LARGE")
      return fail(res, 400, "BAD_INPUT", "Choose a photo under 8 MB.");
    return fail(
      res,
      500,
      "INTERNAL",
      "The local demo hit a snag. Please try again.",
    );
  }
};
export function mockApiPlugin(): Plugin {
  const dispose = () => {
    sessions.forEach((s) => {
      clearInterval(s.timer);
      s.listeners.forEach((r) => r.end());
    });
    sessions.clear();
    taste.clear();
  };
  return {
    name: "roomie-mock-api",
    configureServer(server) {
      server.middlewares.use(handler);
      server.httpServer?.once("close", dispose);
    },
    configurePreviewServer(server) {
      server.middlewares.use(handler);
      server.httpServer.once("close", dispose);
    },
  };
}
