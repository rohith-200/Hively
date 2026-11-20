"""Mock catalog used until Suman's SingleStore catalog is live. IDs are placeholders."""
from app.contracts import Product


def _p(id_, store, spid, name, cat, price, colors, desc, in_stock=True, room="kitchen"):
    return Product(id=id_, store=store, store_product_id=spid, name=name, room=room, category=cat,
                   style="mid-century modern", colors=colors, material=desc, price_usd=price,
                   image_url=f"https://placehold.co/400x400?text={cat.replace(' ', '+')}",
                   url=f"https://example.com/{id_}", in_stock=in_stock)


CATALOG: list[Product] = [
    _p("shp-4471", "shopify", "4471", "Walnut knife block set, 8 pc", "knife block", 160.99, ["walnut", "steel"], "walnut handle knife block brass"),
    _p("amz-B0PLACEHOLD5", "amazon", "B0PLACEHOLD5", "Glossy black knife block, 6 pc", "knife block", 89.99, ["black"], "glossy black modern knife block"),
    _p("shp-4502", "shopify", "4502", "Brushed brass flatware, 20 pc", "cutlery set", 73.99, ["brass"], "brushed brass matte flatware mid century"),
    _p("wmt-PLACEHOLD6", "walmart", "PLACEHOLD6", "Stainless flatware, 20 pc", "cutlery set", 29.99, ["steel"], "stainless steel flatware"),
    _p("amz-B0PLACEHOLD1", "amazon", "B0PLACEHOLD1", "Ceramic canisters with walnut lids, set of 3", "canisters", 56.99, ["white", "walnut"], "matte white ceramic walnut lid canisters"),
    _p("amz-B0PLACEHOLD7", "amazon", "B0PLACEHOLD7", "Glossy red canisters, set of 3", "canisters", 39.99, ["red"], "glossy red canisters"),
    _p("amz-B0PLACEHOLD2", "amazon", "B0PLACEHOLD2", "Teal glazed utensil crock", "utensil holder", 29.99, ["teal"], "teal ceramic utensil crock"),
    _p("wmt-PLACEHOLD3", "walmart", "PLACEHOLD3", "End-grain walnut cutting board", "cutting board", 43.99, ["walnut"], "matte walnut end grain cutting board"),
    _p("wmt-PLACEHOLD4", "walmart", "PLACEHOLD4", "Teal and cream dish towels, set of 4", "dish towels", 23.99, ["teal", "cream"], "teal cream cotton dish towels"),
    _p("shp-4610", "shopify", "4610", "Walnut counter stools, set of 2", "bar stools", 329.00, ["walnut"], "walnut mid century counter stools"),
]
