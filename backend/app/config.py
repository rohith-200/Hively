"""Env flags. Every real integration is behind its own USE_* flag so it can be
switched to mock on stage. MOCK=1 forces everything to mock."""
import os

from dotenv import load_dotenv

load_dotenv()


def _flag(name: str) -> bool:
    return os.getenv("MOCK", "0") != "1" and os.getenv(name, "0") == "1"


USE_NEBIUS = _flag("USE_NEBIUS")
USE_SINGLESTORE = _flag("USE_SINGLESTORE")
USE_COGNEE = _flag("USE_COGNEE")
USE_AMPLITUDE = _flag("USE_AMPLITUDE")
USE_STRIPE = _flag("USE_STRIPE")
USE_SHOPIFY = _flag("USE_SHOPIFY")

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_TEST_PAYMENT_METHOD = os.getenv("STRIPE_TEST_PAYMENT_METHOD", "pm_card_visa")

SHOPIFY_STORE_DOMAIN = os.getenv("SHOPIFY_STORE_DOMAIN", "")      # roomie-demo.myshopify.com
SHOPIFY_ADMIN_TOKEN = os.getenv("SHOPIFY_ADMIN_TOKEN", "")        # legacy shpat_... (optional)
SHOPIFY_CLIENT_ID = os.getenv("SHOPIFY_CLIENT_ID", "")            # Dev Dashboard app
SHOPIFY_CLIENT_SECRET = os.getenv("SHOPIFY_CLIENT_SECRET", "")
SHOPIFY_API_VERSION = os.getenv("SHOPIFY_API_VERSION", "2026-07")

AMAZON_ASSOCIATE_TAG = os.getenv("AMAZON_ASSOCIATE_TAG", "")

MAX_ITEM_USD = float(os.getenv("MAX_ITEM_USD", "300"))
MAX_BUDGET_USD = float(os.getenv("MAX_BUDGET_USD", "2000"))
MOCK_STEP_DELAY = float(os.getenv("MOCK_STEP_DELAY", "0.6"))    # seconds between mock steps so the UI looks live
DEMO_SHIP_TO = {"name": "Demo User", "address1": "1 Market St", "city": "San Francisco",
                "province": "CA", "zip": "94105", "country": "US", "email": "demo@roomie.dev"}


def modes() -> dict:
    m = lambda on, name: name if on else "mock"
    return {"vision": m(USE_NEBIUS, "nebius"), "llm": m(USE_NEBIUS, "nebius"),
            "db": m(USE_SINGLESTORE, "singlestore"), "memory": m(USE_COGNEE, "cognee"),
            "analytics": m(USE_AMPLITUDE, "amplitude"),
            "payments": m(USE_STRIPE and bool(STRIPE_SECRET_KEY), "stripe"),
            "shopify": m(USE_SHOPIFY and bool(SHOPIFY_STORE_DOMAIN) and bool(SHOPIFY_ADMIN_TOKEN or (SHOPIFY_CLIENT_ID and SHOPIFY_CLIENT_SECRET)), "shopify")}
