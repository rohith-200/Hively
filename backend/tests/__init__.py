import os

# Tests pin the built-in catalog; a locally synced Shopify snapshot must not change results.
os.environ["CATALOG_SNAPSHOT"] = "off"
