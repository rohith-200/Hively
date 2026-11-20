"""Mock catalog used until the SingleStore catalog is live: 32 products, 3 stores,
kitchen + living room, 3 styles.

Store ids containing "PLACEHOLD" are not real listings; cart links built from them will not
work. Ids, names and prices of the original 10 rows (and the 6 used in fixtures/) are unchanged.
"""
from app.contracts import Product

MCM, SCANDI, IND = "mid-century modern", "scandinavian", "industrial"
K, L = "kitchen", "living room"
_STORE = {"shp": "shopify", "amz": "amazon", "wmt": "walmart"}

# (id, store_product_id, name, room, category, style, colors, material, price, description)
_ROWS = [
    # ---- kitchen ----
    ("shp-4471", "4471", "Walnut knife block set, 8 pc", K, "knife block", MCM, ["walnut", "steel"], "walnut, stainless steel", 160.99,
     "walnut handle knife block with brass rivets, matte oiled finish"),
    ("amz-B0PLACEHOLD5", "B0PLACEHOLD5", "Glossy black knife block, 6 pc", K, "knife block", MCM, ["black"], "lacquered wood", 89.99,
     "glossy black modern knife block"),
    ("amz-B0PLACEHOLD21", "B0PLACEHOLD21", "Bamboo knife block with 6 knives", K, "knife block", SCANDI, ["natural", "steel"], "bamboo, stainless steel", 49.99,
     "light bamboo slotted knife block, minimal design"),
    ("wmt-PLACEHOLD22", "PLACEHOLD22", "Magnetic black steel knife block", K, "knife block", IND, ["black", "steel"], "powder-coated steel", 64.00,
     "black magnetic knife stand with raw steel base"),
    ("shp-4502", "4502", "Brushed brass flatware, 20 pc", K, "cutlery set", MCM, ["brass"], "brass-plated steel", 73.99,
     "brushed brass matte flatware cutlery set, service for four"),
    ("wmt-PLACEHOLD6", "PLACEHOLD6", "Stainless flatware, 20 pc", K, "cutlery set", SCANDI, ["steel"], "stainless steel", 29.99,
     "stainless steel flatware with slim clean lines"),
    ("wmt-PLACEHOLD7", "PLACEHOLD7", "Matte black flatware, 20 pc", K, "cutlery set", IND, ["black"], "stainless steel", 38.97,
     "matte black stainless flatware, loft look"),
    ("amz-B0PLACEHOLD1", "B0PLACEHOLD1", "Ceramic canisters with walnut lids, set of 3", K, "canisters", MCM, ["white", "walnut"], "ceramic, walnut", 56.99,
     "matte white ceramic canisters with airtight walnut lids"),
    ("amz-B0PLACEHOLD7", "B0PLACEHOLD7", "Glossy red canisters, set of 3", K, "canisters", MCM, ["red"], "enamel steel", 39.99,
     "glossy red enamel canisters with chrome lids, retro diner look"),
    ("shp-4510", "4510", "Stoneware canisters with oak lids, set of 3", K, "canisters", SCANDI, ["grey", "oak"], "stoneware, oak", 62.00,
     "speckled grey matte stoneware canisters with pale oak lids"),
    ("amz-B0PLACEHOLD2", "B0PLACEHOLD2", "Teal glazed utensil crock", K, "utensil holder", MCM, ["teal"], "stoneware", 29.99,
     "teal ceramic utensil holder crock, matte satin glaze"),
    ("shp-4515", "4515", "Marble utensil holder with brass band", K, "utensil holder", SCANDI, ["white", "brass"], "marble, brass", 44.00,
     "white marble utensil holder with a brushed brass band"),
    ("wmt-PLACEHOLD10", "PLACEHOLD10", "Galvanized steel utensil caddy", K, "utensil holder", IND, ["grey"], "galvanized steel", 18.88,
     "raw galvanized steel utensil caddy with riveted handle"),
    ("wmt-PLACEHOLD3", "PLACEHOLD3", "End-grain walnut cutting board", K, "cutting board", MCM, ["walnut"], "walnut", 43.99,
     "matte walnut end grain cutting board with juice groove"),
    ("shp-4520", "4520", "Pale oak serving and cutting board", K, "cutting board", SCANDI, ["oak"], "oak", 58.00,
     "pale oak cutting board with leather loop"),
    ("amz-B0PLACEHOLD11", "B0PLACEHOLD11", "Acacia cutting board with handle", K, "cutting board", SCANDI, ["acacia"], "acacia wood", 32.99,
     "acacia paddle cutting board"),
    ("wmt-PLACEHOLD4", "PLACEHOLD4", "Teal and cream dish towels, set of 4", K, "dish towels", MCM, ["teal", "cream"], "cotton", 23.99,
     "teal cream cotton waffle weave dish towels"),
    ("shp-4525", "4525", "Natural linen dish towels, set of 2", K, "dish towels", SCANDI, ["natural"], "linen", 28.00,
     "stonewashed natural linen dish towels"),
    ("amz-B0PLACEHOLD12", "B0PLACEHOLD12", "Charcoal stripe dish towels, set of 6", K, "dish towels", IND, ["charcoal"], "cotton", 15.99,
     "heavy cotton dish towels with charcoal ticking stripe"),
    ("shp-4610", "4610", "Walnut counter stools, set of 2", K, "bar stools", MCM, ["walnut"], "walnut", 329.00,
     "walnut mid century counter stools"),
    ("amz-B0PLACEHOLD13", "B0PLACEHOLD13", "Walnut and leather bar stools, set of 2", K, "bar stools", MCM, ["walnut", "tan"], "walnut, leather", 349.00,
     "counter height walnut bar stools with tan leather seats and brass footrest"),
    ("wmt-PLACEHOLD14", "PLACEHOLD14", "Industrial metal bar stools, set of 2", K, "bar stools", IND, ["black", "wood"], "steel, reclaimed wood", 329.00,
     "black steel bar stools with reclaimed wood seats"),
    # ---- living room ----
    ("shp-4530", "4530", "Mustard velvet throw pillow", L, "throw pillows", MCM, ["mustard"], "velvet", 36.00,
     "mustard velvet pillow with walnut button"),
    ("amz-B0PLACEHOLD15", "B0PLACEHOLD15", "Grey wool throw pillows, set of 2", L, "throw pillows", SCANDI, ["grey"], "wool blend", 27.99,
     "soft grey wool blend pillows, minimal"),
    ("amz-B0PLACEHOLD16", "B0PLACEHOLD16", "Brass arc floor lamp", L, "floor lamp", MCM, ["brass", "white"], "brushed brass, marble", 129.99,
     "brushed brass arc lamp with marble base and white globe"),
    ("wmt-PLACEHOLD17", "PLACEHOLD17", "Black tripod floor lamp", L, "floor lamp", IND, ["black"], "steel", 89.00,
     "matte black steel tripod lamp with cage shade"),
    ("wmt-PLACEHOLD18", "PLACEHOLD18", "Walnut oval coffee table", L, "coffee table", MCM, ["walnut"], "walnut veneer", 189.00,
     "oval walnut coffee table with tapered legs"),
    ("shp-4535", "4535", "Birch round coffee table", L, "coffee table", SCANDI, ["birch", "white"], "birch", 210.00,
     "round pale birch coffee table with white lower shelf"),
    ("amz-B0PLACEHOLD19", "B0PLACEHOLD19", "Geometric teal and mustard rug, 5x7", L, "area rug", MCM, ["teal", "mustard", "cream"], "polypropylene", 139.99,
     "low pile geometric rug in teal, mustard and cream"),
    ("wmt-PLACEHOLD20", "PLACEHOLD20", "Natural jute area rug, 5x7", L, "area rug", SCANDI, ["natural"], "jute", 98.00,
     "hand woven natural jute rug"),
    ("shp-4540", "4540", "Abstract print in walnut frame", L, "wall art", MCM, ["teal", "mustard", "walnut"], "paper, walnut", 78.00,
     "abstract print in teal and mustard with a walnut frame"),
    ("shp-4545", "4545", "Chunky knit cream throw blanket", L, "throw blanket", SCANDI, ["cream"], "cotton", 54.00,
     "chunky knit cotton throw in cream"),
]

OUT_OF_STOCK = {"wmt-PLACEHOLD20"}

CATALOG: list[Product] = [
    Product(id=i, store=_STORE[i[:3]], store_product_id=spid, name=name, room=room, category=cat,
            style=style, colors=colors, material=mat, price_usd=price,
            image_url=f"https://placehold.co/400x400?text={cat.replace(' ', '+')}",
            url=f"https://example.com/{i}", in_stock=i not in OUT_OF_STOCK)
    for i, spid, name, room, cat, style, colors, mat, price, _ in _ROWS
]
# Search text only (Product has no description field; the SingleStore table does).
DESCRIPTIONS: dict[str, str] = {r[0]: r[-1] for r in _ROWS}
