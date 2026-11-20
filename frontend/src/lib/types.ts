export type Store = "shopify" | "amazon" | "walmart";
export type RunState =
  | "created"
  | "analyzing"
  | "awaiting_approval"
  | "executing"
  | "completed"
  | "partial"
  | "rejected"
  | "failed";
export type ExecutionMode = "auto_buy" | "cart_link" | "product_link";
export interface Product {
  id: string;
  store: Store;
  name: string;
  price_usd: number;
  image_url: string;
  url: string;
  colors: string[];
  in_stock?: boolean;
}
export interface RunItem {
  id: string;
  category: string;
  selected: boolean;
  execution_mode: ExecutionMode;
  reason: string;
  critic_note: string | null;
  score: number;
  product: Product;
}
export interface RoomProfile {
  room_type: string;
  style: string;
  style_confidence: number;
  palette: { name: string; hex: string }[];
  materials: string[];
  evidence: string;
  photo_url: string;
  observed_items?: string[];
  missing_categories?: string[];
}
export interface MerchantResult {
  store: Store;
  mode: ExecutionMode;
  status: "ordered" | "cart_ready" | "link_ready" | "failed";
  url: string | null;
  item_ids: string[];
  amount_usd: number;
  order_id: string | null;
  error: string | null;
}
export interface Run {
  id: string;
  user_id: string;
  state: RunState;
  created_at: string;
  budget_usd: number;
  room: RoomProfile | null;
  items: RunItem[];
  skipped: { category: string; reason: string }[];
  totals: {
    items_usd: number;
    auto_buy_usd: number;
    cart_link_usd: number;
    held_usd: number;
    captured_usd: number;
  };
  payment: {
    mode: string;
    payment_intent_id: string | null;
    status:
      | "none"
      | "held"
      | "captured"
      | "partially_captured"
      | "canceled"
      | "failed";
  };
  merchant_results: MerchantResult[];
  error: { code: string; message: string } | null;
}
export interface AuditEvent {
  seq: number;
  ts: string;
  actor: string;
  action: string;
  summary: string;
  data: Record<string, unknown>;
  hash: string;
  prev_hash: string;
}
export interface Health {
  ok: boolean;
  modes: Record<string, string>;
}
export interface CreateRunInput {
  photo: File;
  user_id: string;
  budget_usd: number;
  stores: Store[];
  note: string;
}
export const STORE_NAMES: Record<Store, string> = {
  shopify: "Shopify",
  amazon: "Amazon",
  walmart: "Walmart",
};
export const isTerminal = (state: RunState) =>
  ["completed", "partial", "rejected", "failed"].includes(state);
export const money = (value: number) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(value);
export const cents = (value: number) => Math.round(value * 100);
export function selectedTotals(items: RunItem[], ids: string[]) {
  const selected = items.filter((item) => ids.includes(item.id));
  const sum = (list: RunItem[]) =>
    list.reduce((total, item) => total + cents(item.product.price_usd), 0) /
    100;
  return {
    count: selected.length,
    total: sum(selected),
    auto: sum(selected.filter((i) => i.execution_mode === "auto_buy")),
    carts: sum(selected.filter((i) => i.execution_mode !== "auto_buy")),
  };
}
export function validatePhoto(
  file: File | { size: number; type: string },
): string | null {
  if (!["image/jpeg", "image/png"].includes(file.type))
    return "Choose a JPG or PNG photo.";
  if (file.size > 8 * 1024 * 1024)
    return "This photo is a little large. Choose one under 8 MB.";
  if (!file.size) return "This photo is empty. Please choose another one.";
  return null;
}
