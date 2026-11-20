"""Generates contract-valid fixtures for Naman's mock server.
Run from backend/:  python -m scripts.make_fixtures
Product IDs/URLs are placeholders until Suman's real catalog lands.
"""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.contracts import (AuditEvent, AuditResponse, MerchantResult, PaletteColor, PaymentInfo,
                           Product, RoomProfile, Run, RunItem, Skip, Totals)

OUT = Path(__file__).resolve().parent.parent / "fixtures"
T0 = datetime(2026, 11, 20, 21, 5, 12, tzinfo=timezone.utc)
RID = "r_8f2c1a"


def p(id_, store, spid, name, cat, price, colors, mode):
    return Product(id=id_, store=store, store_product_id=spid, name=name, room="kitchen",
                   category=cat, style="mid-century modern", colors=colors, material="",
                   price_usd=price, image_url=f"https://placehold.co/400x400?text={cat.replace(' ', '+')}",
                   url=f"https://example.com/{id_}", in_stock=True), mode


ROWS = [
    ("ri_1", *p("shp-4471", "shopify", "4471", "Walnut knife block set, 8 pc", "knife block", 160.99, ["walnut", "steel"], "auto_buy"),
     "Walnut handles match the cabinet fronts", None, 0.91),
    ("ri_2", *p("shp-4502", "shopify", "4502", "Brushed brass flatware, 20 pc", "cutlery set", 73.99, ["brass"], "auto_buy"),
     "Echoes the brass drawer pulls", None, 0.88),
    ("ri_3", *p("amz-B0PLACEHOLD1", "amazon", "B0PLACEHOLD1", "Ceramic canisters with walnut lids, set of 3", "canisters", 56.99, ["white", "walnut"], "cart_link"),
     "White body, walnut lid: your palette", "Swapped in for a glossy set; you avoid gloss", 0.84),
    ("ri_4", *p("amz-B0PLACEHOLD2", "amazon", "B0PLACEHOLD2", "Teal glazed utensil crock", "utensil holder", 29.99, ["teal"], "cart_link"),
     "Teal accent from your backsplash", None, 0.8),
    ("ri_5", *p("wmt-PLACEHOLD3", "walmart", "PLACEHOLD3", "End-grain walnut cutting board", "cutting board", 43.99, ["walnut"], "cart_link"),
     "Matte finish, as you prefer", None, 0.79),
    ("ri_6", *p("wmt-PLACEHOLD4", "walmart", "PLACEHOLD4", "Teal and cream dish towels, set of 4", "dish towels", 23.99, ["teal", "cream"], "cart_link"),
     "Soft pop of the teal accent", None, 0.77),
]

ITEMS = [RunItem(id=rid, category=prod.category, execution_mode=mode, reason=why,
                 critic_note=note, score=sc, product=prod)
         for rid, prod, mode, why, note, sc in ROWS]

ROOM = RoomProfile(room_type="kitchen", style="mid-century modern", style_confidence=0.86,
                   palette=[PaletteColor(name="walnut", hex="#6B4A2F"), PaletteColor(name="warm white", hex="#F3EFE6"),
                            PaletteColor(name="brass", hex="#C9A14A"), PaletteColor(name="teal", hex="#2A7C7C")],
                   materials=["walnut cabinets", "brass pulls", "white quartz"],
                   observed_items=["range", "refrigerator"],
                   missing_categories=["knife block", "cutlery set", "canisters", "utensil holder",
                                       "cutting board", "dish towels", "bar stools"],
                   evidence="Walnut slab cabinets, brass pulls and a white quartz counter",
                   photo_url=f"/api/runs/{RID}/photo")


def r2(x):
    return round(x + 1e-9, 2)


def totals(items, captured=0.0):
    sel = [i for i in items if i.selected]
    auto = r2(sum(i.product.price_usd for i in items if i.execution_mode == "auto_buy"))
    return Totals(items_usd=r2(sum(i.product.price_usd for i in sel)),
                  auto_buy_usd=r2(sum(i.product.price_usd for i in sel if i.execution_mode == "auto_buy")),
                  cart_link_usd=r2(sum(i.product.price_usd for i in sel if i.execution_mode != "auto_buy")),
                  held_usd=auto, captured_usd=captured)


STEPS = [
    ("user", "run.started", "Photo uploaded, budget $400, note: we cook a lot"),
    ("vision", "llm.vision", "Kitchen, mid-century modern (86%). Walnut cabinets, brass pulls"),
    ("memory", "memory.recalled", "Prefers matte finishes; removed a glossy kettle last time"),
    ("stylist", "llm.stylist", "7 search intents written, avoiding glossy"),
    ("catalog", "catalog.searched", "28 candidates across Shopify, Amazon, Walmart"),
    ("curator", "llm.curator", "Picked 6 items, skipped bar stools (no match under $300)"),
    ("critic", "llm.critic", "1 swap: glossy canisters -> walnut-lid canisters. Style score 0.86"),
    ("policy", "guardrails.passed", "$389.94 <= $400 budget; every item <= $300; all in stock"),
    ("payments", "payment.held", "Held $234.98 on card for Shopify items, pi_test_123"),
]


def chain(steps):
    out, prev = [], "0" * 64
    for i, (actor, action, summary) in enumerate(steps):
        ts = T0 + timedelta(seconds=2 * i)
        h = hashlib.sha256(f"{prev}{RID}{i}{ts.isoformat()}{actor}{action}{json.dumps({}, sort_keys=True)}".encode()).hexdigest()
        out.append(AuditEvent(seq=i, ts=ts, actor=actor, action=action, summary=summary, data={}, hash=h, prev_hash=prev))
        prev = h
    return out


def main():
    OUT.mkdir(exist_ok=True)
    awaiting = Run(id=RID, user_id="priya", state="awaiting_approval", created_at=T0, budget_usd=400,
                   note="we cook a lot", room=ROOM, items=ITEMS,
                   skipped=[Skip(category="bar stools", reason="No match under $300")],
                   totals=totals(ITEMS),
                   payment=PaymentInfo(mode="stripe", payment_intent_id="pi_test_123", status="held"))

    done_items = [i.model_copy(update={"selected": i.id != "ri_6"}) for i in ITEMS]
    completed = awaiting.model_copy(update={
        "state": "completed", "items": done_items,
        "totals": totals(done_items, captured=234.98),
        "payment": PaymentInfo(mode="stripe", payment_intent_id="pi_test_123", status="captured"),
        "merchant_results": [
            MerchantResult(store="shopify", mode="auto_buy", status="ordered", order_id="#1042",
                           url="https://roomie-demo.myshopify.com/admin/orders/1042",
                           item_ids=["ri_1", "ri_2"], amount_usd=234.98),
            MerchantResult(store="amazon", mode="cart_link", status="cart_ready",
                           url="https://www.amazon.com/gp/aws/cart/add.html?ASIN.1=B0PLACEHOLD1&Quantity.1=1&ASIN.2=B0PLACEHOLD2&Quantity.2=1",
                           item_ids=["ri_3", "ri_4"], amount_usd=86.98),
            MerchantResult(store="walmart", mode="cart_link", status="cart_ready",
                           url="https://affil.walmart.com/cart/addToCart?items=PLACEHOLD3",
                           item_ids=["ri_5"], amount_usd=43.99),
        ]})

    events = chain(STEPS + [("user", "run.approved", "Approved 5 items, removed dish towels"),
                            ("merchant", "merchant.executed", "Shopify order #1042; Amazon + Walmart carts ready"),
                            ("payments", "payment.captured", "Captured $234.98")])

    sse = [{"event": "state", "data": {"state": "analyzing"}}]
    sse += [{"event": "step", "data": json.loads(e.model_dump_json())} for e in events[:len(STEPS)]]
    sse += [{"event": "run", "data": json.loads(awaiting.model_dump_json())},
            {"event": "state", "data": {"state": "awaiting_approval"}}]

    files = {
        "run_awaiting_approval.json": json.loads(awaiting.model_dump_json()),
        "run_completed.json": json.loads(completed.model_dump_json()),
        "audit.json": json.loads(AuditResponse(events=events, chain_valid=True).model_dump_json()),
        "sse_replay.json": sse,
        "health.json": {"ok": True, "modes": {"vision": "mock", "llm": "mock", "db": "mock",
                                              "memory": "mock", "analytics": "mock", "payments": "mock"}},
        "error_invalid_state.json": {"error": {"code": "INVALID_STATE", "message": "Run is not awaiting approval"}},
    }
    for name, obj in files.items():
        (OUT / name).write_text(json.dumps(obj, indent=2))
        print("wrote", name)


if __name__ == "__main__":
    main()
