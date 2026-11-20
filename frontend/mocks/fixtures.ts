import type { AuditEvent, Run, RunItem, Store } from "../src/lib/types";
import { selectedTotals } from "../src/lib/types";

export type DemoScenario =
  | "kitchen"
  | "living-room"
  | "bedroom"
  | "office"
  | "generic";
function item(
  id: string,
  category: string,
  name: string,
  store: Store,
  price: number,
  art: string,
  reason: string,
  critic: string | null = null,
): RunItem {
  return {
    id,
    category,
    selected: true,
    execution_mode: store === "shopify" ? "auto_buy" : "cart_link",
    score: 0.94,
    critic_note: critic,
    reason,
    product: {
      id: `${store}-demo-${id}`,
      store,
      name,
      price_usd: price,
      image_url: `/products/${art}.svg`,
      url: "",
      colors: ["natural", "sage"],
      in_stock: true,
    },
  };
}
export const PRODUCTS = [
  item(
    "ri_1",
    "knife block",
    "Walnut knife block set",
    "shopify",
    89,
    "knife",
    "Walnut handles echo the cabinet fronts and keep the counter visually calm.",
  ),
  item(
    "ri_2",
    "ceramic canisters",
    "Everyday ceramic canisters",
    "amazon",
    48.99,
    "canisters",
    "Matte ivory softens the straight cabinet lines.",
    "Swapped glossy ceramics for a matte finish that suits this sample palette.",
  ),
  item(
    "ri_3",
    "pendant light",
    "Solstice brass pendant",
    "shopify",
    119,
    "pendant",
    "Brushed brass connects the lighting with the existing cabinet hardware.",
  ),
  item(
    "ri_4",
    "counter stool",
    "Form oak counter stool",
    "walmart",
    74.95,
    "stool",
    "Oak and slim charcoal legs balance the sample kitchen’s warm materials.",
  ),
  item(
    "ri_5",
    "vase",
    "Sage stoneware vase",
    "amazon",
    29.99,
    "vase",
    "A muted sage accent adds softness to the warm neutral palette.",
  ),
];
const living = [
  item(
    "lr_1",
    "side table",
    "Arc oak side table",
    "shopify",
    119,
    "table",
    "Rounded oak complements the sofa’s soft silhouette and warm timber floor.",
  ),
  item(
    "lr_2",
    "floor lamp",
    "Cove linen floor lamp",
    "amazon",
    89,
    "lamp",
    "A linen shade adds gentle, layered light beside the seating area.",
  ),
  item(
    "lr_3",
    "throw",
    "Moss woven throw",
    "walmart",
    39,
    "throw",
    "A tactile sage layer connects the cream sofa with the room’s greenery.",
  ),
  item(
    "lr_4",
    "wall art",
    "Quiet forms framed print",
    "shopify",
    49,
    "art",
    "Soft abstract shapes balance the open wall without overpowering the seating.",
    "Chose a quieter print to avoid competing patterns.",
  ),
  item(
    "lr_5",
    "vase",
    "Sage stoneware vase",
    "amazon",
    29.99,
    "vase",
    "A small ceramic accent repeats the palette on the coffee table.",
  ),
];
const bedroom = [
  item(
    "br_1",
    "bedside table",
    "Nook oak bedside table",
    "shopify",
    79,
    "table",
    "A compact oak surface adds practical storage beside the sample bed.",
  ),
  item(
    "br_2",
    "bed linen",
    "Cloud linen bedding",
    "amazon",
    69,
    "throw",
    "Warm ivory linen keeps the sleeping area soft and visually restful.",
  ),
  item(
    "br_3",
    "bedside light",
    "Dune linen table lamp",
    "walmart",
    69,
    "lamp",
    "A shaded bedside light creates a gentle evening layer.",
  ),
  item(
    "br_4",
    "wall art",
    "Still morning framed print",
    "shopify",
    49,
    "art",
    "Low-contrast artwork supports the room’s quiet natural palette.",
  ),
  item(
    "br_5",
    "vase",
    "Sage stoneware vase",
    "amazon",
    29.99,
    "vase",
    "A small ceramic piece brings a little color to the bedside.",
  ),
];
const office = [
  item(
    "of_1",
    "desk",
    "Field oak writing desk",
    "shopify",
    129,
    "table",
    "A clear oak work surface fits the sample office’s simple layout.",
  ),
  item(
    "of_2",
    "task light",
    "Cove adjustable desk lamp",
    "amazon",
    89,
    "lamp",
    "Focused light supports the work area without adding visual weight.",
  ),
  item(
    "of_3",
    "organizer",
    "Walnut desktop organizer",
    "walmart",
    39,
    "organizer",
    "A natural wood organizer keeps everyday essentials together.",
  ),
  item(
    "of_4",
    "wall art",
    "Quiet forms framed print",
    "shopify",
    49,
    "art",
    "A calm print introduces a soft focal point above the desk.",
  ),
  item(
    "of_5",
    "plant",
    "Little leaf planter",
    "amazon",
    29,
    "plant",
    "A small green accent softens the practical workspace.",
  ),
];
const generic = [living[1], living[2], living[4], living[3], office[4]].map(
  (i, n) => ({
    ...i,
    id: `gn_${n + 1}`,
    score: 0,
    critic_note: null,
    reason: "An example product for exploring the shopping workflow.",
  }),
);
const scenarios = {
  kitchen: {
    type: "kitchen",
    style: "mid-century modern",
    materials: ["walnut cabinetry", "brushed brass", "natural stone"],
    evidence:
      "The sample kitchen pairs walnut cabinetry, brass hardware, and light stone.",
    products: PRODUCTS,
  },
  "living-room": {
    type: "living room",
    style: "warm Scandinavian",
    materials: ["oak", "linen upholstery", "woven wool"],
    evidence:
      "The sample living room combines a cream sofa, oak furniture, and soft green accents.",
    products: living,
  },
  bedroom: {
    type: "bedroom",
    style: "soft contemporary",
    materials: ["oak", "natural linen", "matte ceramics"],
    evidence:
      "The sample bedroom uses layered linen, pale wood, and a calm neutral palette.",
    products: bedroom,
  },
  office: {
    type: "home office",
    style: "natural minimal",
    materials: ["oak", "linen", "matte metal"],
    evidence:
      "The sample office has a simple wood desk, focused lighting, and room for greenery.",
    products: office,
  },
  generic: {
    type: "room",
    style: "Sample style preview",
    materials: [],
    evidence:
      "This upload has not been analyzed in demo mode. Live vision will identify its room type, colors, and materials.",
    products: generic,
  },
};
/** Exact built-in sample identifiers select fixtures; arbitrary filenames are never classified. */
export function demoScenarioForFile(name: string): DemoScenario {
  const match = name.match(
    /^hivly-sample-(kitchen|living-room|bedroom|office)\.png$/,
  );
  return match ? (match[1] as DemoScenario) : "generic";
}
export function createFixture(
  id: string,
  userId: string,
  budget: number,
  stores: Store[],
  scenario: DemoScenario = "generic",
  avoid: string[] = [],
): Run {
  const fixture = scenarios[scenario];
  let used = 0;
  const available = fixture.products.filter((i) =>
    stores.includes(i.product.store),
  );
  const items = available
    .filter((i) => {
      if (
        avoid.includes(i.category) ||
        Math.round((used + i.product.price_usd) * 100) >
          Math.round(budget * 100)
      )
        return false;
      used = Math.round((used + i.product.price_usd) * 100) / 100;
      return true;
    })
    .map((i) => structuredClone(i));
  const total = selectedTotals(
    items,
    items.map((i) => i.id),
  );
  return {
    id,
    user_id: userId,
    state: "analyzing",
    created_at: new Date().toISOString(),
    budget_usd: budget,
    room: {
      room_type: fixture.type,
      style: fixture.style,
      style_confidence: scenario === "generic" ? 0 : 0.94,
      palette:
        scenario === "generic"
          ? []
          : [
              { name: "Oak", hex: "#9A7855" },
              { name: "Ivory", hex: "#EAE5D7" },
              { name: "Sage", hex: "#929F83" },
              { name: "Brass", hex: "#C6A262" },
            ],
      materials: fixture.materials,
      evidence: fixture.evidence,
      photo_url: `/api/runs/${id}/photo`,
      observed_items:
        scenario === "generic"
          ? []
          : [
              fixture.type === "living room"
                ? "sofa"
                : fixture.type === "bedroom"
                  ? "bed"
                  : fixture.type === "kitchen"
                    ? "cabinets"
                    : "desk",
            ],
      missing_categories: items.map((i) => i.category),
    },
    items,
    skipped: available
      .filter((p) => !items.some((i) => i.id === p.id))
      .map((p) => ({
        category: p.category,
        reason: avoid.includes(p.category)
          ? "Left out based on your previous removal in this demo."
          : "No sample match within the remaining budget.",
      })),
    totals: {
      items_usd: total.total,
      auto_buy_usd: total.auto,
      cart_link_usd: total.carts,
      held_usd: total.auto,
      captured_usd: 0,
    },
    payment: {
      mode: "mock",
      payment_intent_id: total.auto ? `pi_demo_${id}` : null,
      status: total.auto ? "held" : "none",
    },
    merchant_results: [],
    error: null,
  };
}
export function demoSteps(
  plan: Run,
  note: string,
  facts: string[],
): Pick<AuditEvent, "actor" | "action" | "summary" | "data">[] {
  const known = plan.room?.room_type !== "room";
  const changes = plan.items
    .filter((i) => i.critic_note)
    .map((i) => ({
      category: i.category,
      replace_with: i.product.id,
      reason: i.critic_note,
    }));
  return [
    {
      actor: "vision",
      action: "room_analyzed",
      summary: known
        ? `Loaded the ${plan.room?.room_type} sample profile and its material palette.`
        : "Your photo is received. Photo-specific analysis needs the live backend.",
      data: {
        room_profile: plan.room,
        evidence: plan.room?.evidence,
        demo: true,
      },
    },
    {
      actor: "memory",
      action: "memory_recalled",
      summary: facts.length
        ? "Recalled your previous choices from this demo session."
        : note
          ? "Carried your style note into this room."
          : "No saved preferences yet. Starting with a fresh room.",
      data: {
        source: "local demo memory",
        facts: [...facts, ...(note ? [note] : [])],
        demo: true,
      },
    },
    {
      actor: "stylist",
      action: "llm.stylist",
      summary: `The sample stylist planned ${plan.items.length} finishing categories.`,
      data: {
        intents: plan.items.map((i) => ({
          category: i.category,
          query: `${plan.room?.style} ${i.category}`,
          max_price: plan.budget_usd,
          must_have: [],
          avoid: [],
        })),
        meta: { model: "Trinity Mini", fallback_used: false },
        demo: true,
      },
    },
    {
      actor: "catalog",
      action: "catalog_searched",
      summary: `Found ${plan.items.length} sample matches in your selected stores.`,
      data: {
        candidates: plan.items.length,
        product_ids: plan.items.map((i) => i.product.id),
        demo: true,
      },
    },
    {
      actor: "curator",
      action: "llm.curator",
      summary: `Curated ${plan.items.length} pieces with a reason for each choice.`,
      data: {
        picks: plan.items.map((i) => ({
          category: i.category,
          product_id: i.product.id,
          reason: i.reason,
        })),
        meta: { model: "Trinity Large Thinking", fallback_used: false },
        demo: true,
      },
    },
    {
      actor: "critic",
      action: "llm.critic",
      summary: changes.length
        ? `Checked the collection and made ${changes.length} thoughtful swap${changes.length === 1 ? "" : "s"}.`
        : "Checked the sample collection for clashes and duplicates.",
      data: {
        changes,
        notes: "Sample picks are consistent with the selected demo scenario.",
        meta: { model: "Trinity Large Preview", fallback_used: false },
        demo: true,
      },
    },
    {
      actor: "policy",
      action: "guardrails_passed",
      summary: `The sample collection is within your $${plan.budget_usd.toFixed(2)} budget.`,
      data: {
        items_usd: plan.totals.items_usd,
        budget_usd: plan.budget_usd,
        in_stock: true,
        demo: true,
      },
    },
    {
      actor: "payments",
      action: "payment_held",
      summary: plan.totals.auto_buy_usd
        ? `Prepared a simulated $${plan.totals.auto_buy_usd.toFixed(2)} hold for approval.`
        : "No automatic-purchase items selected. No payment hold needed.",
      data: { amount_usd: plan.totals.auto_buy_usd, mode: "mock", demo: true },
    },
  ];
}
