"""OWNER: Rohit. One adapter per store. Each turns approved items into a MerchantResult.
- shopify: real order on our dev store via Admin GraphQL (USE_SHOPIFY=1), else mock order id
- amazon:  official Add-to-Cart form URL with every ASIN (no API key needed)
- walmart: affiliate add-to-cart URL (verify with one real item ID at 3:00; fallback = product page)
"""
import time
import uuid
from urllib.parse import urlencode

import httpx

from app.config import (AMAZON_ASSOCIATE_TAG, SHOPIFY_ADMIN_TOKEN, SHOPIFY_API_VERSION,
                        SHOPIFY_CLIENT_ID, SHOPIFY_CLIENT_SECRET, SHOPIFY_STORE_DOMAIN, USE_SHOPIFY)
from app.contracts import ExecutionMode, MerchantResult, RunItem, Store

EXECUTION_MODE: dict[Store, ExecutionMode] = {"shopify": "auto_buy", "amazon": "cart_link", "walmart": "cart_link"}


def _amount(items: list[RunItem]) -> float:
    return round(sum(i.product.price_usd for i in items) + 1e-9, 2)


# ---------------- Shopify ----------------
_ORDER_CREATE = """
mutation orderCreate($order: OrderCreateOrderInput!) {
  orderCreate(order: $order) {
    order { id name }
    userErrors { field message }
  }
}"""


_TOKEN = {"value": "", "expires": 0.0}


def _shopify_token() -> str:
    """Legacy admin token if given; else Dev Dashboard client-credentials grant (token cached)."""
    if SHOPIFY_ADMIN_TOKEN:
        return SHOPIFY_ADMIN_TOKEN
    if _TOKEN["value"] and time.time() < _TOKEN["expires"] - 60:
        return _TOKEN["value"]
    r = httpx.post(f"https://{SHOPIFY_STORE_DOMAIN}/admin/oauth/access_token",
                   data={"grant_type": "client_credentials", "client_id": SHOPIFY_CLIENT_ID,
                         "client_secret": SHOPIFY_CLIENT_SECRET}, timeout=20)
    r.raise_for_status()
    body = r.json()
    _TOKEN["value"] = body["access_token"]
    _TOKEN["expires"] = time.time() + float(body.get("expires_in", 3600))
    return _TOKEN["value"]


def shopify_ready() -> bool:
    return USE_SHOPIFY and bool(SHOPIFY_STORE_DOMAIN) and bool(
        SHOPIFY_ADMIN_TOKEN or (SHOPIFY_CLIENT_ID and SHOPIFY_CLIENT_SECRET))


def shopify_execute(run_id: str, items: list[RunItem], ship_to: dict) -> MerchantResult:
    ids = [i.id for i in items]
    if not shopify_ready():
        return MerchantResult(store="shopify", mode="auto_buy", status="ordered",
                              order_id=f"#MOCK-{uuid.uuid4().hex[:4].upper()}", item_ids=ids, amount_usd=_amount(items))
    order = {
        "lineItems": [{"variantId": f"gid://shopify/ProductVariant/{i.product.store_product_id}", "quantity": 1}
                      for i in items],
        "email": ship_to.get("email"),
        "financialStatus": "PAID",
        "shippingAddress": {k: ship_to.get(k) for k in ("address1", "city", "zip")} |
                           {"firstName": ship_to.get("name", "Demo"), "provinceCode": ship_to.get("province"),
                            "countryCode": ship_to.get("country", "US")},
        "note": f"Placed by Roomie agent, run {run_id}",
        "tags": ["roomie", run_id],
    }
    url = f"https://{SHOPIFY_STORE_DOMAIN}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
    try:
        r = httpx.post(url, json={"query": _ORDER_CREATE, "variables": {"order": order}},
                       headers={"X-Shopify-Access-Token": _shopify_token()}, timeout=20)
        r.raise_for_status()
        body = r.json()
        res = (body.get("data") or {}).get("orderCreate") or {}
        errs = res.get("userErrors") or body.get("errors")
        if errs or not res.get("order"):
            raise RuntimeError(str(errs))
        o = res["order"]
        numeric = o["id"].rsplit("/", 1)[-1]
        return MerchantResult(store="shopify", mode="auto_buy", status="ordered", order_id=o["name"],
                              url=f"https://{SHOPIFY_STORE_DOMAIN}/admin/orders/{numeric}",
                              item_ids=ids, amount_usd=_amount(items))
    except Exception as e:
        return MerchantResult(store="shopify", mode="auto_buy", status="failed", item_ids=ids,
                              amount_usd=_amount(items), error=str(e)[:300])


# ---------------- Amazon ----------------
def amazon_execute(run_id: str, items: list[RunItem], ship_to: dict) -> MerchantResult:
    params = {}
    if AMAZON_ASSOCIATE_TAG:
        params["AssociateTag"] = AMAZON_ASSOCIATE_TAG
    for n, i in enumerate(items, start=1):
        params[f"ASIN.{n}"] = i.product.store_product_id
        params[f"Quantity.{n}"] = 1
    return MerchantResult(store="amazon", mode="cart_link", status="cart_ready",
                          url="https://www.amazon.com/gp/aws/cart/add.html?" + urlencode(params),
                          item_ids=[i.id for i in items], amount_usd=_amount(items))


# ---------------- Walmart ----------------
def walmart_execute(run_id: str, items: list[RunItem], ship_to: dict) -> MerchantResult:
    item_ids = ",".join(i.product.store_product_id for i in items)
    return MerchantResult(store="walmart", mode="cart_link", status="cart_ready",
                          url=f"https://affil.walmart.com/cart/addToCart?items={item_ids}",
                          item_ids=[i.id for i in items], amount_usd=_amount(items))


ADAPTERS = {"shopify": shopify_execute, "amazon": amazon_execute, "walmart": walmart_execute}
