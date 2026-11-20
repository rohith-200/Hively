import type { AuditEvent, ExecutionMode, RoomProfile, RunState } from "./types";

export const AGENTS = [
  {
    id: "vision",
    name: "Room reader",
    service: "Claude vision",
    task: "Reading the room, colors, and materials",
    short: "Read",
  },
  {
    id: "memory",
    name: "Taste memory",
    service: "Cognee",
    task: "Recalling your preferences",
    short: "Recall",
  },
  {
    id: "stylist",
    name: "Stylist",
    service: "Arcee · Trinity Mini",
    task: "Turning your room into a shopping direction",
    short: "Style",
  },
  {
    id: "catalog",
    name: "Store search",
    service: "SingleStore",
    task: "Finding in-stock candidates across your stores",
    short: "Search",
  },
  {
    id: "curator",
    name: "Curator",
    service: "Arcee · Trinity Large Thinking",
    task: "Choosing one considered pick per category",
    short: "Curate",
  },
  {
    id: "critic",
    name: "Critic",
    service: "Arcee · Trinity Large Preview",
    task: "Checking style, duplicates, and better alternatives",
    short: "Check",
  },
  {
    id: "policy",
    name: "Budget & availability",
    service: "Code guardrails",
    task: "Checking the budget, item limits, and availability",
    short: "Validate",
  },
  {
    id: "payments",
    name: "Ready for you",
    service: "Stripe",
    task: "Preparing the studio payment hold",
    short: "Prepare",
  },
] as const;
export type AgentId = (typeof AGENTS)[number]["id"];
export function actorForEvent(event: AuditEvent): string {
  if (AGENTS.some((a) => a.id === event.actor)) return event.actor;
  const action = event.action.toLowerCase();
  if (/room_analy|vision|perceive/.test(action)) return "vision";
  if (/memory_recall|recall/.test(action)) return "memory";
  if (/stylist/.test(action)) return "stylist";
  if (/catalog|retriev|search/.test(action)) return "catalog";
  if (/curator/.test(action)) return "curator";
  if (/critic/.test(action)) return "critic";
  if (/guardrail|policy/.test(action)) return "policy";
  if (/payment|hold/.test(action)) return "payments";
  return event.actor;
}
export function agentTimeline(events: AuditEvent[], state: RunState) {
  const last = new Map<string, AuditEvent>();
  for (const event of events)
    if (!/learn|remember|capture|canceled|merchant/.test(event.action))
      last.set(actorForEvent(event), event);
  const lastIndex = Math.max(
    -1,
    ...AGENTS.map((a, i) => (last.has(a.id) ? i : -1)),
  );
  const blockedStep = [...last.values()].some((e) =>
    /blocked|failed/.test(e.action),
  );
  const active =
    !blockedStep && (state === "created" || state === "analyzing")
      ? lastIndex + 1
      : -1;
  return AGENTS.map((agent, index) => {
    const event = last.get(agent.id);
    const blocked = !!event && /blocked|failed/.test(event.action);
    return {
      ...agent,
      event,
      status: blocked
        ? ("blocked" as const)
        : event
          ? ("done" as const)
          : index === active
            ? ("working" as const)
            : ("waiting" as const),
    };
  });
}
export function actorName(actor: string) {
  if (actor === "payments") return "Payments";
  return (
    AGENTS.find((a) => a.id === actor)?.name ||
    { user: "You", merchant: "Store handoff", system: "Hivly" }[actor] ||
    actor.replaceAll("_", " ")
  );
}
export function roomLabel(type?: string | null) {
  if (
    !type ||
    ["room", "unknown", "other", "generic"].includes(type.toLowerCase())
  )
    return "Your room";
  return type
    .replaceAll("_", " ")
    .replaceAll("-", " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
export function roomKind(
  type?: string | null,
): "kitchen" | "living" | "bedroom" | "office" {
  const value = (type || "").toLowerCase();
  if (value.includes("kitchen")) return "kitchen";
  if (value.includes("bed")) return "bedroom";
  if (/office|study|workspace/.test(value)) return "office";
  return "living";
}
export const executionLabel = (mode: ExecutionMode) =>
  ({
    auto_buy: "Order on approval",
    cart_link: "Finish in store cart",
    product_link: "Open product page",
  })[mode];
export function safeExternalUrl(value?: string | null) {
  try {
    const url = new URL(value || "");
    return ["https:", "http:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}
export function isFallback(event?: AuditEvent) {
  if (!event) return false;
  const meta = event.data.meta;
  return (
    event.data.fallback_used === true ||
    !!(
      meta &&
      typeof meta === "object" &&
      "fallback_used" in meta &&
      meta.fallback_used === true
    )
  );
}
export function eventFacts(
  event: AuditEvent,
): { label: string; value: string }[] {
  const facts: { label: string; value: string }[] = [];
  const data = event.data;
  if (
    data.meta &&
    typeof data.meta === "object" &&
    "model" in data.meta &&
    typeof data.meta.model === "string"
  )
    facts.push({ label: "Model", value: data.meta.model });
  for (const [key, label] of [
    ["query", "Search direction"],
    ["summary", "Result"],
    ["notes", "Critic notes"],
    ["source", "Memory source"],
    ["evidence", "Room evidence"],
  ] as const) {
    if (typeof data[key] === "string")
      facts.push({ label, value: data[key] as string });
  }
  for (const [key, label] of [
    ["facts", "Preferences"],
    ["categories", "Categories"],
    ["must_have", "Look for"],
    ["avoid", "Avoid"],
  ] as const) {
    if (Array.isArray(data[key]))
      facts.push({
        label,
        value: (data[key] as unknown[])
          .filter((v) => typeof v === "string")
          .join(", "),
      });
  }
  const intents = Array.isArray(data.intents) ? data.intents : [];
  for (const intent of intents.slice(0, 4))
    if (
      intent &&
      typeof intent === "object" &&
      typeof intent.query === "string"
    )
      facts.push({
        label: String(intent.category || "Search query"),
        value: intent.query,
      });
  if (typeof data.candidates === "number")
    facts.push({
      label: "Candidates compared",
      value: String(data.candidates),
    });
  if (Array.isArray(data.changes))
    for (const change of data.changes.slice(0, 3))
      if (change && typeof change.reason === "string")
        facts.push({ label: "Thoughtful swap", value: change.reason });
  return facts.filter((f) => f.value).slice(0, 6);
}
export function profileFromEvent(event: AuditEvent): RoomProfile | null {
  const candidate =
    event.data.room_profile || event.data.room || event.data.profile;
  if (
    candidate &&
    typeof candidate === "object" &&
    "room_type" in candidate &&
    "style" in candidate
  )
    return candidate as RoomProfile;
  return null;
}
