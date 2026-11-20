"""1) Prints the scopes Shopify actually granted. 2) Places ONE real test order.
Run from backend/:  python3 -m scripts.shopify_order_test <variant_id> [price]
Get <variant_id> from the admin URL: Products -> product -> variant -> .../variants/<id>
"""
import sys

import httpx

from app.commerce.merchants import _shopify_token, shopify_execute, shopify_ready
from app.config import DEMO_SHIP_TO, SHOPIFY_API_VERSION, SHOPIFY_STORE_DOMAIN
from app.contracts import Product, RunItem


def main():
    if not shopify_ready():
        print("Not configured (USE_SHOPIFY / domain / client id+secret)")
        return
    token = _shopify_token()
    r = httpx.post(f"https://{SHOPIFY_STORE_DOMAIN}/admin/api/{SHOPIFY_API_VERSION}/graphql.json",
                   json={"query": "{ currentAppInstallation { accessScopes { handle } } }"},
                   headers={"X-Shopify-Access-Token": token}, timeout=20)
    body = r.json()
    scopes = [s["handle"] for s in ((body.get("data") or {}).get("currentAppInstallation") or {}).get("accessScopes", [])]
    print("granted scopes:", scopes or body)
    if "write_orders" not in scopes:
        print("\nwrite_orders is NOT granted -> add it to a released app version and approve it in the store admin.")
        return
    if len(sys.argv) < 2:
        print("\nScopes OK. Now run with a variant id: python3 -m scripts.shopify_order_test <variant_id> [price]")
        return
    vid = sys.argv[1]
    price = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    item = RunItem(id="ri_test", category="test", execution_mode="auto_buy", reason="order test",
                   product=Product(id=f"shp-{vid}", store="shopify", store_product_id=vid, name="test item",
                                   room="kitchen", category="test", style="test", price_usd=price))
    res = shopify_execute("r_ordertest", [item], DEMO_SHIP_TO)
    print("\nresult:", res.model_dump())


if __name__ == "__main__":
    main()
