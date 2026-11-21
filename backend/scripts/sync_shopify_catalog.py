"""OWNER: Suman. Nightly catalog sync: Shopify -> Roomie catalog. Run from backend/:

    python -m scripts.sync_shopify_catalog              # pull kitchen products and load them
    python -m scripts.sync_shopify_catalog --dry-run    # pull and print, change nothing

What it does:
  1. Extract   every active product from the Shopify store (Admin GraphQL, paginated).
  2. Transform keep the kitchen ones and map them to catalog rows (one row per product).
  3. Load      a) backend/catalog_shopify.json, which the in-memory catalog reads at startup;
               b) the SingleStore products table, with embeddings, if SINGLESTORE_URL is set.
               Shopify kitchen rows that are no longer in the store are marked out of stock.

Safe to re-run. If Shopify returns no kitchen products the job fails without touching the
catalog, so an outage or a bad filter cannot empty it.

Needs SHOPIFY_STORE_DOMAIN and either SHOPIFY_ADMIN_TOKEN or SHOPIFY_CLIENT_ID + SHOPIFY_CLIENT_SECRET.
Scheduled by .github/workflows/catalog-sync.yml.
"""
import json
import sys
from datetime import datetime, timezone

from app import config  # noqa: F401  (loads .env)
from app.data import s2, shopify_catalog
from app.data.mock_catalog import SNAPSHOT

ROOM = "kitchen"


def write_snapshot(rows: list[tuple]) -> None:
    payload = {"synced_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "room": ROOM,
               "products": [{**p.model_dump(exclude={"score"}), "description": desc} for p, desc in rows]}
    SNAPSHOT.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_singlestore(rows: list[tuple]) -> tuple[int, int]:
    """Upsert the rows, then mark Shopify rows for this room that were not in the pull as out of stock."""
    n = s2.upsert_products(rows)
    ids = [p.id for p, _ in rows]
    stale = s2.query(
        f"SELECT id FROM products WHERE store = 'shopify' AND room = %s AND in_stock = 1 "
        f"AND id NOT IN ({', '.join(['%s'] * len(ids))})", (ROOM, *ids))
    if stale:
        gone = [r["id"] for r in stale]
        s2.query(f"UPDATE products SET in_stock = 0 WHERE id IN ({', '.join(['%s'] * len(gone))})", tuple(gone))
    return n, len(stale)


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    try:
        nodes = shopify_catalog.fetch_products()
    except Exception as e:
        print(f"FAILED to read Shopify: {e}")
        return 1
    rows = shopify_catalog.to_catalog_rows(nodes, ROOM)
    print(f"Shopify: {len(nodes)} active products, {len(rows)} for the {ROOM}")
    for p, _ in rows:
        stock = "in stock" if p.in_stock else "OUT"
        print(f"  {p.id:<22} ${p.price_usd:>8.2f}  {stock:<8}  {p.category:<16} {p.style or '-':<20} {p.name}")
    skipped = len(nodes) - len(rows)
    if skipped:
        print(f"  ({skipped} products skipped: not recognised as {ROOM} items)")
    if not rows:
        print(f"FAILED: no {ROOM} products found; catalog left unchanged")
        return 1
    if dry_run:
        print("dry run: nothing written")
        return 0

    write_snapshot(rows)
    print(f"wrote {SNAPSHOT.name} ({len(rows)} products)")
    if s2.url():
        try:
            n, stale = load_singlestore(rows)
            print(f"SingleStore: upserted {n} products, marked {stale} stale rows out of stock")
        except Exception as e:
            print(f"FAILED to load SingleStore: {e!r}")
            return 1
    else:
        print("SINGLESTORE_URL is not set: skipped the SingleStore load")
    return 0


if __name__ == "__main__":
    sys.exit(main())
