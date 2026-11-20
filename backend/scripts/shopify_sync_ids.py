"""After importing hivly_shopify_products.csv: map each SKU (= catalog id, e.g. shp-4471)
to its real Shopify variant id, and optionally write it into mock_catalog.py.
Needs read_products granted. Run from backend/:
    python3 -m scripts.shopify_sync_ids            # print the mapping
    python3 -m scripts.shopify_sync_ids --write    # also update app/data/mock_catalog.py
Then Suman reseeds: python3 -m scripts.seed_data
"""
import re
import sys
from pathlib import Path

import httpx

from app.commerce.merchants import _shopify_token, shopify_ready
from app.config import SHOPIFY_API_VERSION, SHOPIFY_STORE_DOMAIN

Q = """{ productVariants(first: 100, query: "sku:shp-*") { edges { node { id sku price product { title } } } } }"""
CATALOG_FILE = Path(__file__).resolve().parents[1] / "app" / "data" / "mock_catalog.py"


def main():
    if not shopify_ready():
        print("Not configured: USE_SHOPIFY=1, SHOPIFY_STORE_DOMAIN, SHOPIFY_CLIENT_ID/SECRET in .env")
        return
    r = httpx.post(f"https://{SHOPIFY_STORE_DOMAIN}/admin/api/{SHOPIFY_API_VERSION}/graphql.json",
                   json={"query": Q}, headers={"X-Shopify-Access-Token": _shopify_token()}, timeout=20)
    body = r.json()
    if body.get("errors"):
        print("errors:", body["errors"])
        return
    mapping = {}
    for e in body["data"]["productVariants"]["edges"]:
        n = e["node"]
        if (n.get("sku") or "").startswith("shp-"):
            mapping[n["sku"]] = n["id"].rsplit("/", 1)[-1]
            print(f"{n['sku']:<10} -> {mapping[n['sku']]:<16} ${n['price']:<8} {n['product']['title']}")
    print(f"\n{len(mapping)} variants found")
    if "--write" in sys.argv and mapping:
        src = CATALOG_FILE.read_text()
        changed = 0
        for sku, vid in mapping.items():
            # catalog rows look like: ("shp-4471", "4471", ...
            new, n = re.subn(rf'\("{re.escape(sku)}",\s*"[^"]*"', f'("{sku}", "{vid}"', src)
            src, changed = new, changed + n
        CATALOG_FILE.write_text(src)
        print(f"updated {changed} rows in {CATALOG_FILE.name}; now run: python3 -m scripts.seed_data")


if __name__ == "__main__":
    main()
