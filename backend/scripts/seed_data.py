"""OWNER: Suman. One-time setup for the data layer. Run from backend/:

    python -m scripts.seed_data            # tables + catalog + demo user
    python -m scripts.seed_data --check    # only time a sample search and count rows

Needs SINGLESTORE_URL in .env for the SingleStore part; the demo user is seeded either way.
Safe to re-run: products are replaced by id, the demo user is only seeded once.
"""
import asyncio
import sys
import time

from app import config  # noqa: F401  (loads .env)
from app.contracts import SearchIntent
from app.data import memory, s2, store
from app.data.mock_catalog import CATALOG, DESCRIPTIONS

DEMO_USER = "priya"
DEMO_FACTS = [
    ("preference", "Prefers matte finishes and avoids glossy surfaces"),
    ("removed", "Removed a glossy kettle from the last kitchen plan"),
    ("preference", "Likes warm wood tones such as walnut with brass accents"),
]


def seed_products() -> int:
    return s2.upsert_products([(p, DESCRIPTIONS.get(p.id, "")) for p in CATALOG])


def check() -> None:
    n = s2.query("SELECT COUNT(*) AS n FROM products")[0]["n"]
    intent = SearchIntent(category="knife block", query="walnut knife block")
    s2.embed(["warm up"])                                # don't time the model load
    store._s2_search(intent, "kitchen", ["shopify", "amazon", "walmart"], 4)   # nor the connect
    t = time.perf_counter()
    hits = store._s2_search(intent, "kitchen", ["shopify", "amazon", "walmart"], 4)
    ms = (time.perf_counter() - t) * 1000
    print(f"products: {n} rows | 'walnut knife block' -> {[(h.id, h.score) for h in hits]} in {ms:.0f} ms")


async def seed_demo_user() -> str:
    """Seed the local file once; then make sure Cognee has the same facts (if it is switched on)."""
    seeded = not memory._load().get(DEMO_USER)
    if seeded:
        for kind, fact in DEMO_FACTS:
            await memory.remember(DEMO_USER, fact, kind)
        await memory.wait_for_pending()
    elif memory._cognee_ready() and not await memory._cognee_search(DEMO_USER, "kitchen"):
        await memory._cognee_add(DEMO_USER, "\n".join(memory._load()[DEMO_USER]))
        return "demo user pushed to Cognee (graph builds in the background, allow about a minute)"
    return "demo user seeded" if seeded else "demo user already has memory; left as is"


def main() -> None:
    if s2.url():
        if "--check" not in sys.argv:
            print(f"seeded {seed_products()} products")
        check()
    else:
        print("SINGLESTORE_URL is not set: skipped tables and catalog")
    if "--check" not in sys.argv:
        print(asyncio.run(seed_demo_user()))


if __name__ == "__main__":
    main()
