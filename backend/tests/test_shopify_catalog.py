"""Tests for the Shopify catalog sync (no network, no database). Run from backend/:
    python -m pytest tests -q        or        python -m tests.test_shopify_catalog
"""
import json
import os
import tempfile
from pathlib import Path

from app.data import mock_catalog, s2, shopify_catalog
from scripts import sync_shopify_catalog as sync


def _node(pid, title, price="49.00", ptype="", tags=(), collections=(), variants=None, **extra):
    variants = variants or [{"id": f"gid://shopify/ProductVariant/{pid}01", "title": "Default Title", "price": price,
                             "availableForSale": True, "selectedOptions": [{"name": "Title", "value": "Default Title"}]}]
    return {"id": f"gid://shopify/Product/{pid}", "title": title, "handle": title.lower().replace(" ", "-"),
            "description": extra.pop("description", ""), "productType": ptype, "tags": list(tags),
            "onlineStoreUrl": None, "collections": {"nodes": [{"title": c} for c in collections]},
            "variants": {"nodes": variants}, **extra}


NODES = [
    _node(1, "Walnut Knife Block Set", "160.99", tags=["mid-century", "kitchen"],
          description="Solid walnut block with  brass rivets.\nMatte finish.",
          featuredMedia={"preview": {"image": {"url": "https://cdn.example/knife.jpg"}}}),
    _node(2, "Brushed Brass Flatware", "73.99", ptype="Cutlery", featuredImage={"url": "https://cdn.example/flat.jpg"}),
    _node(3, "Linen Throw Pillow", "36.00", ptype="Home decor", tags=["living room"]),
    _node(4, "Copper Whisk", "18.00", collections=["Kitchen essentials"]),
    _node(5, "Oak Cutting Board", variants=[
        {"id": "gid://shopify/ProductVariant/501", "title": "Small", "price": "30.00", "availableForSale": False,
         "selectedOptions": [{"name": "Size", "value": "Small"}, {"name": "Color", "value": "Natural / Oak"}]},
        {"id": "gid://shopify/ProductVariant/502", "title": "Large", "price": "58.00", "availableForSale": True,
         "selectedOptions": [{"name": "Size", "value": "Large"}, {"name": "Material", "value": "Solid Oak"}]}]),
    _node(6, "Stoneware Canisters", "62.00", tags=["scandi"], variants=[
        {"id": "gid://shopify/ProductVariant/601", "title": "Default Title", "price": "62.00",
         "availableForSale": False, "selectedOptions": []}]),
    _node(7, "Gift Card", "25.00"),
]


def test_classify():
    cats = [shopify_catalog.classify(n) for n in NODES]
    assert cats == ["knife block", "cutlery set", None, "kitchen accessory", "cutting board", "canisters", None]


def test_transform():
    os.environ["SHOPIFY_STORE_DOMAIN"] = "roomie-demo.myshopify.com"
    rows = shopify_catalog.to_catalog_rows(NODES)
    by_id = {p.id: (p, d) for p, d in rows}
    assert list(by_id) == ["shp-101", "shp-201", "shp-401", "shp-502", "shp-601"]

    knife, desc = by_id["shp-101"]
    assert (knife.store, knife.store_product_id, knife.room, knife.category) == ("shopify", "101", "kitchen", "knife block")
    assert knife.price_usd == 160.99 and knife.in_stock and knife.style == "mid-century modern"
    assert "walnut" in knife.colors and "brass" in knife.colors and "walnut" in knife.material
    assert knife.image_url == "https://cdn.example/knife.jpg"
    assert knife.url == "https://roomie-demo.myshopify.com/products/walnut-knife-block-set"
    assert desc == "Solid walnut block with brass rivets. Matte finish."

    assert by_id["shp-201"][0].image_url == "https://cdn.example/flat.jpg"       # older image field
    board = by_id["shp-502"][0]                                                   # first sellable variant
    assert board.name == "Oak Cutting Board, Large" and board.price_usd == 58.0 and board.material == "solid oak"
    canisters = by_id["shp-601"][0]
    assert not canisters.in_stock and canisters.style == "scandinavian"


def test_not_configured_is_a_clear_error():
    saved = {k: os.environ.pop(k, None) for k in ("SHOPIFY_STORE_DOMAIN", "SHOPIFY_ADMIN_TOKEN",
                                                   "SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_SECRET")}
    try:
        shopify_catalog.fetch_products()
        raise AssertionError("expected ShopifyError")
    except shopify_catalog.ShopifyError as e:
        assert "not configured" in str(e)
    finally:
        os.environ.update({k: v for k, v in saved.items() if v is not None})


def test_snapshot_replaces_placeholder_shopify_rows():
    rows = shopify_catalog.to_catalog_rows(NODES)
    saved_catalog, saved_desc, saved_path = list(mock_catalog.CATALOG), dict(mock_catalog.DESCRIPTIONS), mock_catalog.SNAPSHOT
    with tempfile.TemporaryDirectory() as tmp:
        sync.SNAPSHOT = mock_catalog.SNAPSHOT = Path(tmp) / "catalog_shopify.json"
        os.environ["CATALOG_SNAPSHOT"] = "on"
        try:
            sync.write_snapshot(rows)
            assert json.loads(mock_catalog.SNAPSHOT.read_text())["products"][0]["id"] == "shp-101"
            assert mock_catalog._apply_snapshot() == 5
            shopify_kitchen = [p.id for p in mock_catalog.CATALOG if p.store == "shopify" and p.room == "kitchen"]
            assert shopify_kitchen == ["shp-101", "shp-201", "shp-401", "shp-502", "shp-601"]
            assert any(p.id == "shp-4530" for p in mock_catalog.CATALOG)          # living room untouched
            assert any(p.id == "amz-B0PLACEHOLD1" for p in mock_catalog.CATALOG)  # other stores untouched
            assert mock_catalog.DESCRIPTIONS["shp-101"].startswith("Solid walnut")
        finally:
            os.environ["CATALOG_SNAPSHOT"] = "off"
            mock_catalog.CATALOG[:] = saved_catalog
            mock_catalog.DESCRIPTIONS.clear(); mock_catalog.DESCRIPTIONS.update(saved_desc)
            sync.SNAPSHOT = mock_catalog.SNAPSHOT = saved_path


def test_singlestore_load_marks_stale_rows():
    rows = shopify_catalog.to_catalog_rows(NODES)
    calls = []

    def fake_query(sql, params=()):
        assert sql.count("%s") == len(params), (sql, params)
        calls.append((sql, params))
        return [{"id": "shp-4471"}, {"id": "shp-4502"}] if sql.startswith("SELECT id FROM products") else []

    real_query, real_embed = s2.query, s2.embed
    s2.query, s2.embed = fake_query, lambda texts: [[0.0] * s2.VECTOR_DIM for _ in texts]
    try:
        assert sync.load_singlestore(rows) == (5, 2)
    finally:
        s2.query, s2.embed = real_query, real_embed
    replaces = [c for c in calls if c[0].startswith("REPLACE INTO products")]
    assert len(replaces) == 5 and replaces[0][1][0] == "shp-101"
    update = calls[-1]
    assert update[0].startswith("UPDATE products SET in_stock = 0") and update[1] == ("shp-4471", "shp-4502")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
