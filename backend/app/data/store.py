"""OWNER: Suman. Catalog search + run storage.
USE_SINGLESTORE=1: vector search over the products table; runs written through to the runs table.
Otherwise, or whenever SingleStore errors: the in-memory mock below. Signatures are frozen."""
import json
import sys

from app.config import USE_SINGLESTORE
from app.contracts import Product, Run, SearchIntent, Store, now
from app.data import s2
from app.data.mock_catalog import CATALOG, DESCRIPTIONS

_RUNS: dict[str, Run] = {}
_ROOMS = sorted({p.room for p in CATALOG})
_COLS = "id, store, store_product_id, name, room, category, style, colors, material, price_usd, image_url, url, in_stock"


def _warn(what: str, err: Exception) -> None:
    print(f"[store] SingleStore {what} failed, using in-memory fallback: {err!r}", file=sys.stderr)


def _product(row: dict) -> Product:
    return Product(id=row["id"], store=row["store"], store_product_id=row["store_product_id"],
                   name=row["name"], room=row["room"], category=row["category"], style=row["style"],
                   colors=s2.as_json(row["colors"]) or [], material=row["material"] or "",
                   price_usd=float(row["price_usd"]), image_url=row["image_url"] or "",
                   url=row["url"] or "", in_stock=bool(row["in_stock"]))


def _room(room_type: str) -> str | None:
    """Map a free-text room type from the vision model onto a catalog room, if it names one."""
    r = room_type.lower().replace("_", " ").replace("-", " ")
    return next((room for room in _ROOMS if room.split()[0] in r), None)


# ------------------------------------------------------------------ search
def _mock_score(p: Product, intent: SearchIntent) -> float:
    words = set(intent.query.lower().split())
    text = f"{p.name} {p.style} {p.material} {' '.join(p.colors)} {DESCRIPTIONS.get(p.id, '')}".lower()
    s = sum(1 for w in words if w in text) / max(len(words), 1)
    if any(a.lower() in text for a in intent.avoid):
        s -= 0.5
    return round(s, 3)


def _mock_search(intent: SearchIntent, room_type: str, stores: list[Store], k: int) -> list[Product]:
    rows = [p for p in CATALOG if p.category == intent.category and p.store in stores and p.in_stock
            and (intent.max_price is None or p.price_usd <= intent.max_price)]
    scored = [p.model_copy(update={"score": _mock_score(p, intent)}) for p in rows]
    return sorted(scored, key=lambda p: -(p.score or 0))[:k]


def _s2_search(intent: SearchIntent, room_type: str, stores: list[Store], k: int) -> list[Product]:
    if not stores:
        return []
    text = " ".join([intent.query or intent.category, *intent.must_have])
    where = ["in_stock = 1", "LOWER(category) = %s", f"store IN ({', '.join(['%s'] * len(stores))})"]
    params: list = [s2.vec_param(s2.embed([text])[0]), intent.category.lower().strip(), *stores]
    room = _room(room_type)
    if room:
        where.append("room = %s")
        params.append(room)
    if intent.max_price is not None:
        where.append("price_usd <= %s")
        params.append(float(intent.max_price))
    params.append(k * 2 if intent.avoid else k)          # over-fetch so "avoid" can reorder
    rows = s2.query(
        f"SELECT {_COLS}, description, vec <*> (%s :> VECTOR({s2.VECTOR_DIM})) AS score "
        f"FROM products WHERE {' AND '.join(where)} ORDER BY score DESC LIMIT %s", tuple(params))
    out = []
    for row in rows:
        score = float(row["score"])
        text = f"{row['name']} {row['material']} {row['description']}".lower()
        if any(a.lower() in text for a in intent.avoid):
            score -= 0.3
        out.append(_product(row).model_copy(update={"score": round(min(max(score, 0.0), 1.0), 3)}))
    return sorted(out, key=lambda p: -(p.score or 0))[:k]


def search(intent: SearchIntent, room_type: str, stores: list[Store], k: int = 4) -> list[Product]:
    """Top-k in-stock products for one category, best first, each with a score."""
    if USE_SINGLESTORE:
        try:
            return _s2_search(intent, room_type, stores, k)
        except Exception as e:
            _warn("search", e)
    return _mock_search(intent, room_type, stores, k)


def get_products(ids: list[str]) -> list[Product]:
    """Products in the order asked for; unknown ids are dropped."""
    if USE_SINGLESTORE and ids:
        try:
            rows = s2.query(f"SELECT {_COLS} FROM products WHERE id IN ({', '.join(['%s'] * len(ids))})", tuple(ids))
            by_id = {r["id"]: _product(r) for r in rows}
            return [by_id[i] for i in ids if i in by_id]
        except Exception as e:
            _warn("get_products", e)
    by_id = {p.id: p for p in CATALOG}
    return [by_id[i] for i in ids if i in by_id]


# ------------------------------------------------------------------ runs
def save_run(run: Run) -> None:
    """Memory first (so a SingleStore outage never loses a live run), then the runs table."""
    _RUNS[run.id] = run.model_copy(deep=True)
    if not USE_SINGLESTORE:
        return
    try:
        s2.query("REPLACE INTO runs (id, user_id, state, budget_usd, run_json, created_at, updated_at) "
                 "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                 (run.id, run.user_id, run.state, run.budget_usd, run.model_dump_json(),
                  s2.to_db_time(run.created_at), s2.to_db_time(now())))
        for m in run.merchant_results:
            s2.query("REPLACE INTO merchant_orders (run_id, store, mode, status, order_id, url, amount_usd, item_ids, error) "
                     "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                     (run.id, m.store, m.mode, m.status, m.order_id, m.url, m.amount_usd,
                      json.dumps(m.item_ids), m.error))
    except Exception as e:
        _warn("save_run", e)


def load_run(run_id: str) -> Run | None:
    r = _RUNS.get(run_id)
    if r:
        return r.model_copy(deep=True)
    if USE_SINGLESTORE:                                  # e.g. after a server restart
        try:
            rows = s2.query("SELECT run_json FROM runs WHERE id = %s", (run_id,))
            if rows:
                raw = rows[0]["run_json"]
                run = Run.model_validate(s2.as_json(raw))
                _RUNS[run_id] = run
                return run.model_copy(deep=True)
        except Exception as e:
            _warn("load_run", e)
    return None


def _warm() -> None:
    """Load the embedding model and open the connection before the first run needs them."""
    try:
        s2.embed(["warm up"])
        s2.query("SELECT 1")
    except Exception as e:
        _warn("warm-up", e)


if USE_SINGLESTORE:
    import threading
    threading.Thread(target=_warm, daemon=True).start()
