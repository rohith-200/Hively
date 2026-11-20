"""OWNER: Suman. SingleStore catalog + run storage.
Bodies below are in-memory MOCKS; keep signatures, add the SingleStore path behind USE_SINGLESTORE."""
from app.config import USE_SINGLESTORE  # noqa: F401
from app.contracts import Product, Run, SearchIntent, Store
from app.data.mock_catalog import CATALOG, DESCRIPTIONS

_RUNS: dict[str, Run] = {}


def _score(p: Product, intent: SearchIntent) -> float:
    words = set(intent.query.lower().split())
    text = f"{p.name} {p.style} {p.material} {' '.join(p.colors)} {DESCRIPTIONS.get(p.id, '')}".lower()
    s = sum(1 for w in words if w in text) / max(len(words), 1)
    if any(a in text for a in intent.avoid):
        s -= 0.5
    return round(s, 3)


def search(intent: SearchIntent, room_type: str, stores: list[Store], k: int = 4) -> list[Product]:
    rows = [p for p in CATALOG if p.category == intent.category and p.store in stores and p.in_stock
            and (intent.max_price is None or p.price_usd <= intent.max_price)]
    scored = [p.model_copy(update={"score": _score(p, intent)}) for p in rows]
    return sorted(scored, key=lambda p: -(p.score or 0))[:k]


def get_products(ids: list[str]) -> list[Product]:
    by_id = {p.id: p for p in CATALOG}
    return [by_id[i] for i in ids if i in by_id]


def save_run(run: Run) -> None:
    _RUNS[run.id] = run.model_copy(deep=True)


def load_run(run_id: str) -> Run | None:
    r = _RUNS.get(run_id)
    return r.model_copy(deep=True) if r else None
