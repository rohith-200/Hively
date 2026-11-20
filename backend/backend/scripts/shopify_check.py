"""Checks the Shopify connection and prints variant IDs for Suman's catalog.
Run from backend/:  python3 -m scripts.shopify_check
"""
import httpx

from app.commerce.merchants import _shopify_token, shopify_ready
from app.config import SHOPIFY_API_VERSION, SHOPIFY_STORE_DOMAIN

Q = """{ products(first: 25) { edges { node { title variants(first: 5) { edges { node { id title price } } } } } } }"""


def main():
    if not shopify_ready():
        print("Not configured: set USE_SHOPIFY=1, SHOPIFY_STORE_DOMAIN and SHOPIFY_CLIENT_ID/SECRET in .env")
        return
    token = _shopify_token()
    print("token OK:", token[:8] + "…")
    r = httpx.post(f"https://{SHOPIFY_STORE_DOMAIN}/admin/api/{SHOPIFY_API_VERSION}/graphql.json",
                   json={"query": Q}, headers={"X-Shopify-Access-Token": token}, timeout=20)
    print("HTTP", r.status_code)
    body = r.json()
    if body.get("errors"):
        print("errors:", body["errors"])
        return
    print("\nstore_product_id (variant id) | price | product")
    for e in body["data"]["products"]["edges"]:
        p = e["node"]
        for v in p["variants"]["edges"]:
            vid = v["node"]["id"].rsplit("/", 1)[-1]
            print(f"{vid} | {v['node']['price']} | {p['title']}")


if __name__ == "__main__":
    main()
