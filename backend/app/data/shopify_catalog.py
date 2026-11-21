"""OWNER: Suman. Extract + transform for the Shopify catalog sync.

fetch_products() pages through the store's active products with the Admin GraphQL API.
to_catalog_rows() keeps the ones that belong to a room and maps them to contract Products.
Loading (SingleStore + local snapshot) lives in scripts/sync_shopify_catalog.py.

Auth is read straight from the environment so the sync does not depend on USE_SHOPIFY:
SHOPIFY_STORE_DOMAIN plus either SHOPIFY_ADMIN_TOKEN or SHOPIFY_CLIENT_ID + SHOPIFY_CLIENT_SECRET.
"""
import os
import re

import httpx

from app.contracts import Product

PAGE_SIZE = 50
MAX_PAGES = 40                      # 2000 products; a safety stop, not a target

# Category keywords, checked in order against the product title, then type and tags.
# Category names match what the vision model is asked to return, because search filters on them.
KITCHEN_CATEGORIES: list[tuple[str, list[str]]] = [
    ("knife block", ["knife block", "knife set", "knife stand", "knives"]),
    ("cutlery set", ["cutlery", "flatware", "silverware"]),
    ("canisters", ["canister", "canisters", "storage jar", "storage jars"]),
    ("utensil holder", ["utensil holder", "utensil crock", "utensil caddy", "crock"]),
    ("cutting board", ["cutting board", "chopping board", "serving board"]),
    ("dish towels", ["dish towel", "dish towels", "tea towel", "tea towels", "kitchen towel", "kitchen towels"]),
    ("bar stools", ["bar stool", "bar stools", "counter stool", "counter stools"]),
    ("cookware", ["skillet", "frying pan", "saucepan", "dutch oven", "cookware", "stockpot"]),
    ("dinnerware", ["dinnerware", "dinner plate", "plates", "bowls", "bowl set"]),
    ("drinkware", ["mug", "mugs", "glassware", "tumbler", "tumblers"]),
    ("kettle", ["kettle"]),
    ("spice rack", ["spice rack", "spice jars"]),
    ("fruit bowl", ["fruit bowl"]),
    ("pendant light", ["pendant light", "pendant lamp"]),
]
ROOM_WORDS = {"kitchen": ["kitchen", "kitchenware", "cookware", "tableware", "dining"]}
ROOM_CATEGORIES = {"kitchen": KITCHEN_CATEGORIES}

STYLES: list[tuple[str, list[str]]] = [
    ("mid-century modern", ["mid-century", "mid century", "midcentury", "mcm", "retro"]),
    ("scandinavian", ["scandinavian", "scandi", "nordic"]),
    ("industrial", ["industrial", "loft"]),
    ("farmhouse", ["farmhouse", "rustic"]),
    ("modern", ["modern", "minimalist", "minimal"]),
]
COLORS = ["walnut", "oak", "birch", "acacia", "brass", "copper", "gold", "silver", "steel", "black",
          "white", "cream", "beige", "grey", "gray", "charcoal", "teal", "blue", "green", "red",
          "mustard", "natural", "tan"]
MATERIALS = ["stainless steel", "cast iron", "walnut", "oak", "birch", "acacia", "bamboo", "ceramic",
             "stoneware", "porcelain", "marble", "glass", "brass", "copper", "steel", "leather",
             "cotton", "linen", "wood"]

# Image field names differ between Admin API versions; try the newest first.
_IMAGE_SELECTIONS = ["featuredMedia { preview { image { url } } }", "featuredImage { url }", ""]

_QUERY = """
query Products($first: Int!, $after: String) {
  products(first: $first, after: $after, query: "status:active") {
    nodes {
      id title handle description productType tags onlineStoreUrl
      %s
      collections(first: 10) { nodes { title } }
      variants(first: 25) { nodes { id title price availableForSale selectedOptions { name value } } }
    }
    pageInfo { hasNextPage endCursor }
  }
}"""


class ShopifyError(RuntimeError):
    pass


# ------------------------------------------------------------------ extract
def _admin_token() -> str:
    token = os.getenv("SHOPIFY_ADMIN_TOKEN", "").strip()
    return "" if token.endswith("...") else token        # ".env.example" placeholder is not a token


def configured() -> bool:
    return bool(os.getenv("SHOPIFY_STORE_DOMAIN") and (
        _admin_token() or (os.getenv("SHOPIFY_CLIENT_ID") and os.getenv("SHOPIFY_CLIENT_SECRET"))))


def _token(client: httpx.Client, domain: str) -> str:
    if _admin_token():
        return _admin_token()
    r = client.post(f"https://{domain}/admin/oauth/access_token",
                    data={"grant_type": "client_credentials", "client_id": os.getenv("SHOPIFY_CLIENT_ID", ""),
                          "client_secret": os.getenv("SHOPIFY_CLIENT_SECRET", "")})
    if r.status_code != 200:
        raise ShopifyError(f"token request failed: HTTP {r.status_code} {' '.join(r.text.split())[:120]}")
    return r.json()["access_token"]


def fetch_products() -> list[dict]:
    """Every active product in the store, as raw GraphQL nodes."""
    if not configured():
        raise ShopifyError("Shopify is not configured: set SHOPIFY_STORE_DOMAIN and either "
                           "SHOPIFY_ADMIN_TOKEN or SHOPIFY_CLIENT_ID + SHOPIFY_CLIENT_SECRET")
    domain = os.environ["SHOPIFY_STORE_DOMAIN"].strip()
    version = os.getenv("SHOPIFY_API_VERSION", "2026-07")
    url = f"https://{domain}/admin/api/{version}/graphql.json"
    with httpx.Client(timeout=30) as client:
        headers = {"X-Shopify-Access-Token": _token(client, domain)}
        last_error = None
        for image_selection in _IMAGE_SELECTIONS:
            try:
                return _fetch_all(client, url, headers, _QUERY % image_selection)
            except ShopifyError as e:
                # only a schema complaint about the image field is worth retrying
                if not image_selection or image_selection.split()[0] not in str(e):
                    raise
                last_error = e
        raise last_error or ShopifyError("no query variant worked")


def _fetch_all(client: httpx.Client, url: str, headers: dict, query: str) -> list[dict]:
    nodes, after = [], None
    for _ in range(MAX_PAGES):
        r = client.post(url, headers=headers, json={"query": query, "variables": {"first": PAGE_SIZE, "after": after}})
        if r.status_code != 200:
            raise ShopifyError(f"HTTP {r.status_code} {' '.join(r.text.split())[:200]}")
        body = r.json()
        if body.get("errors"):
            raise ShopifyError(f"GraphQL errors: {body['errors']}")
        page = body["data"]["products"]
        nodes.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    return nodes


# ------------------------------------------------------------------ transform
def _has(text: str, phrase: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text) is not None


def _first_match(text: str, table: list[tuple[str, list[str]]]) -> str:
    return next((name for name, words in table if any(_has(text, w) for w in words)), "")


def _image(node: dict) -> str:
    media = node.get("featuredMedia") or {}
    url = (((media.get("preview") or {}).get("image")) or {}).get("url")
    return url or (node.get("featuredImage") or {}).get("url") or ""


def classify(node: dict, room: str = "kitchen") -> str | None:
    """The catalog category if this product belongs to the room, else None."""
    title = (node.get("title") or "").lower()
    labels = " ".join([node.get("productType") or "", *(node.get("tags") or []),
                       *[c.get("title") or "" for c in ((node.get("collections") or {}).get("nodes") or [])]]).lower()
    table = ROOM_CATEGORIES[room]
    category = _first_match(title, table) or _first_match(labels, table)
    if category:
        return category
    if any(_has(labels, w) or _has(title, w) for w in ROOM_WORDS[room]):
        return (node.get("productType") or "").strip().lower() or f"{room} accessory"
    return None


def to_product(node: dict, room: str = "kitchen") -> tuple[Product, str] | None:
    """Map one Shopify product to (Product, description), or None if it is not for this room.
    One row per product: the first variant that can be sold, else the first variant."""
    category = classify(node, room)
    variants = ((node.get("variants") or {}).get("nodes")) or []
    if not category or not variants:
        return None
    variant = next((v for v in variants if v.get("availableForSale")), variants[0])
    variant_id = variant["id"].rsplit("/", 1)[-1]
    options = {o["name"].lower(): o["value"] for o in (variant.get("selectedOptions") or [])}
    description = " ".join((node.get("description") or "").split())[:500]
    text = " ".join([node.get("title") or "", " ".join(node.get("tags") or []), description,
                     " ".join(options.values())]).lower()

    colors = [c.strip().lower() for c in re.split(r"[/,&]| and ", options.get("color") or options.get("colour") or "")
              if c.strip()]
    colors += [c for c in COLORS if _has(text, c) and c not in colors]
    material = options.get("material") or ", ".join(m for m in MATERIALS if _has(text, m))
    name = node["title"].strip()
    if len(variants) > 1 and variant.get("title") and variant["title"] != "Default Title":
        name = f"{name}, {variant['title']}"
    domain = os.getenv("SHOPIFY_STORE_DOMAIN", "").strip()
    url = node.get("onlineStoreUrl") or (f"https://{domain}/products/{node['handle']}" if domain and node.get("handle") else "")

    product = Product(id=f"shp-{variant_id}", store="shopify", store_product_id=variant_id, name=name,
                      room=room, category=category, style=_first_match(text, STYLES), colors=colors[:4],
                      material=material.lower(), price_usd=round(float(variant["price"]), 2),
                      image_url=_image(node), url=url, in_stock=bool(variant.get("availableForSale")))
    return product, description


def to_catalog_rows(nodes: list[dict], room: str = "kitchen") -> list[tuple[Product, str]]:
    rows, seen = [], set()
    for node in nodes:
        row = to_product(node, room)
        if row and row[0].id not in seen:
            seen.add(row[0].id)
            rows.append(row)
    return rows
