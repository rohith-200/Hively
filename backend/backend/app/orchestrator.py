"""OWNER: Rohit. Run state machine:
created -> analyzing -> awaiting_approval -> executing -> completed | partial | rejected | failed
Every step: one audit event (SingleStore + Amplitude) and one SSE event to the app."""
import asyncio
import json
import uuid

from app import llm
from app.commerce import payments
from app.commerce.merchants import ADAPTERS, EXECUTION_MODE
from app.config import DEMO_SHIP_TO, MAX_ITEM_USD, MOCK_STEP_DELAY, USE_NEBIUS
from app.contracts import ApiError, Product, Run, RunItem, Skip, Totals, UserMemory
from app.data import audit, memory, store
from app.events import bus

PHOTOS: dict[str, tuple[bytes, str]] = {}


def r2(x: float) -> float:
    return round(x + 1e-9, 2)


def new_run_id() -> str:
    return "r_" + uuid.uuid4().hex[:6]


def _jsonable(run: Run) -> dict:
    return json.loads(run.model_dump_json())


def _set_state(run: Run, state: str):
    run.state = state
    store.save_run(run)
    bus(run.id).publish("state", {"state": state})


def _step(run: Run, actor: str, action: str, summary: str, data: dict | None = None):
    props = {"room_type": run.room.room_type if run.room else "", "style": run.room.style if run.room else ""}
    e = audit.append(run.id, actor, action, summary, data or {}, user_id=run.user_id, extra_props=props)
    bus(run.id).publish("step", json.loads(e.model_dump_json()))


def compute_totals(run: Run, captured: float = 0.0) -> Totals:
    sel = [i for i in run.items if i.selected]
    auto = [i for i in sel if i.execution_mode == "auto_buy"]
    return Totals(items_usd=r2(sum(i.product.price_usd for i in sel)),
                  auto_buy_usd=r2(sum(i.product.price_usd for i in auto)),
                  cart_link_usd=r2(sum(i.product.price_usd for i in sel if i.execution_mode != "auto_buy")),
                  held_usd=run.totals.held_usd, captured_usd=captured)


async def _pause():
    if not USE_NEBIUS and MOCK_STEP_DELAY:
        await asyncio.sleep(MOCK_STEP_DELAY)


async def _call(fn, *args):
    """Run blocking teammate code (HTTP to Nebius/SingleStore) off the event loop."""
    return await asyncio.to_thread(fn, *args)


# ------------------------------------------------------------------ plan
async def plan(run: Run, image: bytes | None, media_type: str):
    try:
        _set_state(run, "analyzing")
        _step(run, "user", "run.started",
              f"{'Photo' if image else 'Text only'}, budget ${run.budget_usd:.0f}"
              + (f", note: {run.note}" if run.note else ""), {"stores": run.stores})
        await _pause()

        # 1. perceive
        run.room = await _call(llm.analyze_room, image, media_type, run.note)
        if image:
            run.room.photo_url = f"/api/runs/{run.id}/photo"
        _step(run, "vision", "llm.vision",
              f"{run.room.room_type}, {run.room.style} ({run.room.style_confidence:.0%}). {run.room.evidence}",
              {"missing": run.room.missing_categories})
        await _pause()

        # 2. recall
        try:
            mem = await asyncio.wait_for(memory.recall(run.user_id, run.room.room_type), timeout=20)
        except Exception:
            mem = UserMemory(source="local", summary="", facts=[])
        _step(run, "memory", "memory.recalled", mem.summary[:300] or "No history yet for this user",
              {"source": mem.source, "facts": len(mem.facts)})
        await _pause()

        # 3. stylist
        intents = await _call(llm.stylist, run.room, mem, run.budget_usd)
        _step(run, "stylist", "llm.stylist", f"{len(intents)} search intents written",
              {"intents": [i.model_dump() for i in intents]})
        await _pause()

        # 4. retrieve
        candidates: dict[str, list[Product]] = {}
        for it in intents:
            candidates[it.category] = await _call(store.search, it, run.room.room_type, run.stores, 4)
        n = sum(len(v) for v in candidates.values())
        _step(run, "catalog", "catalog.searched", f"{n} candidates across {', '.join(run.stores)}",
              {c: [p.id for p in v] for c, v in candidates.items()})
        await _pause()

        # 5. curate
        cplan = await _call(llm.curator, run.room, mem, candidates, run.budget_usd, MAX_ITEM_USD)
        _step(run, "curator", "llm.curator",
              f"Picked {len(cplan.picks)} items, skipped {len(cplan.skipped)}. {cplan.summary}",
              {"meta": cplan.meta.model_dump() if cplan.meta else None})
        await _pause()

        # 6. critique
        verdict = await _call(llm.critic, cplan, candidates, run.room, mem, run.budget_usd)
        by_id = {p.id: p for v in candidates.values() for p in v}
        picks = {p.category: p for p in cplan.picks}
        notes: dict[str, str] = {}
        for ch in verdict.changes:
            if ch.category in picks and ch.replace_with in by_id:     # never accept invented ids
                picks[ch.category].product_id = ch.replace_with
                notes[ch.category] = ch.reason
        _step(run, "critic", "llm.critic",
              f"{len(verdict.changes)} swap(s). {verdict.notes} Style score {verdict.style_score:.2f}",
              {"changes": [c.model_dump() for c in verdict.changes]})

        # build items (drop anything not in candidates)
        items, skipped = [], list(cplan.skipped)
        for n_, pk in enumerate(picks.values(), start=1):
            prod = by_id.get(pk.product_id)
            if not prod:
                skipped.append(Skip(category=pk.category, reason="Model chose an unknown product; dropped"))
                continue
            items.append(RunItem(id=f"ri_{n_}", category=pk.category, execution_mode=EXECUTION_MODE[prod.store],
                                 reason=pk.reason, critic_note=notes.get(pk.category), score=prod.score, product=prod))

        # 7. guardrails (plain code)
        dropped = []
        for i in list(items):
            if i.product.price_usd > MAX_ITEM_USD or not i.product.in_stock:
                items.remove(i); dropped.append(i)
        while items and sum(i.product.price_usd for i in items) > run.budget_usd:
            worst = max(items, key=lambda i: i.product.price_usd)
            items.remove(worst); dropped.append(worst)
        skipped += [Skip(category=d.category, reason=f"Removed by guardrails (${d.product.price_usd:.2f})") for d in dropped]
        run.items, run.skipped = items, skipped
        run.totals = compute_totals(run)
        if not items:
            _step(run, "policy", "guardrails.blocked", "Nothing fits the budget and rules")
            run.error = ApiError(code="BAD_INPUT", message="No items fit your budget")
            _set_state(run, "failed")
            return
        _step(run, "policy", "guardrails.passed",
              f"${run.totals.items_usd:.2f} <= ${run.budget_usd:.2f} budget; every item <= ${MAX_ITEM_USD:.0f}; all in stock",
              {"dropped": [d.product.id for d in dropped]})

        # 8. hold (auto-buy items only)
        auto = run.totals.auto_buy_usd
        run.payment = payments.hold(run.id, auto, "Roomie: " + "; ".join(
            i.product.name for i in items if i.execution_mode == "auto_buy"))
        run.totals.held_usd = auto if run.payment.status == "held" else 0
        if run.payment.status == "held":
            _step(run, "payments", "payment.held",
                  f"Held ${auto:.2f} on card for auto-buy items, {run.payment.payment_intent_id}. Nothing charged yet",
                  {"payment_intent_id": run.payment.payment_intent_id, "mode": run.payment.mode})

        store.save_run(run)
        bus(run.id).publish("run", _jsonable(run))
        _set_state(run, "awaiting_approval")
    except payments.PaymentError as e:
        _fail(run, "PAYMENT_FAILED", f"Card hold failed: {e}")
    except Exception as e:  # keep the demo alive and visible
        _fail(run, "INTERNAL", repr(e)[:300])


def _fail(run: Run, code: str, msg: str):
    run.error = ApiError(code=code, message=msg)
    _step(run, "system", "run.failed", msg)
    bus(run.id).publish("error", run.error.model_dump())
    _set_state(run, "failed")


# ------------------------------------------------------------------ approve / reject
async def approve(run: Run, selected_ids: list[str]) -> Run:
    for i in run.items:
        i.selected = i.id in selected_ids
    kept = [i for i in run.items if i.selected]
    removed = [i for i in run.items if not i.selected]
    if not kept:
        return await reject(run, "Deselected every item")

    _set_state(run, "executing")
    _step(run, "user", "run.approved", f"Approved {len(kept)} items" +
          (f", removed {', '.join(i.product.name for i in removed)}" if removed else ""),
          {"kept": [i.id for i in kept], "removed": [i.id for i in removed]})

    results = []
    for st in ["shopify", "amazon", "walmart"]:
        st_items = [i for i in kept if i.product.store == st]
        if st_items:
            res = await _call(ADAPTERS[st], run.id, st_items, DEMO_SHIP_TO)
            results.append(res)
            _step(run, "merchant", "merchant.executed",
                  f"{st}: {res.status}" + (f" {res.order_id}" if res.order_id else "") +
                  (f" ({res.error})" if res.error else ""), res.model_dump())
    run.merchant_results = results

    # payment: capture only what was actually ordered at Shopify
    captured = 0.0
    shop = next((r for r in results if r.store == "shopify"), None)
    if run.payment.status == "held":
        try:
            if shop and shop.status == "ordered":
                run.payment = payments.capture(run.payment.payment_intent_id, shop.amount_usd, run.totals.held_usd)
                captured = shop.amount_usd
                _step(run, "payments", "payment.captured", f"Captured ${captured:.2f} of ${run.totals.held_usd:.2f} held")
            else:
                run.payment = payments.cancel(run.payment.payment_intent_id)
                _step(run, "payments", "payment.canceled", "Hold released; no Shopify order placed")
        except payments.PaymentError as e:
            run.error = ApiError(code="PAYMENT_FAILED", message=str(e)[:300])
            _step(run, "payments", "payment.failed", str(e)[:300])

    run.totals = compute_totals(run, captured)
    await memory.remember(run.user_id, f"Bought for {run.room.room_type} ({run.room.style}): "
                          + ", ".join(i.product.name for i in kept), "purchase")
    if removed:
        await memory.remember(run.user_id, "Removed from cart: " + ", ".join(i.product.name for i in removed), "removed")
    failed = any(r.status == "failed" for r in results) or run.payment.status == "failed"
    store.save_run(run)
    _set_state(run, "partial" if failed else "completed")
    return run


async def reject(run: Run, reason: str) -> Run:
    if run.payment.status == "held":
        try:
            run.payment = payments.cancel(run.payment.payment_intent_id)
        except payments.PaymentError as e:
            run.error = ApiError(code="PAYMENT_FAILED", message=str(e)[:300])
    _step(run, "user", "run.rejected", reason or "No reason given")
    await memory.remember(run.user_id, f"Rejected a {run.room.style if run.room else ''} cart: {reason or 'no reason'}",
                          "rejected")
    store.save_run(run)
    _set_state(run, "rejected")
    return run
