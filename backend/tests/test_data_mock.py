"""Smoke tests for the data layer (app/data). Run from backend/:
    python -m pytest tests -q        or        python -m tests.test_data_mock
These must keep passing when the real backends land behind the USE_* flags.
"""
import asyncio
import tempfile
from pathlib import Path

from app.contracts import AuditResponse, Run, SearchIntent
from app.data import analytics, audit, memory, store
from app.data.mock_catalog import CATALOG

FIX = Path(__file__).resolve().parent.parent / "fixtures"
ALL = ["shopify", "amazon", "walmart"]


def _fixture_run() -> Run:
    return Run.model_validate_json((FIX / "run_awaiting_approval.json").read_text())


def test_catalog_shape():
    ids = [p.id for p in CATALOG]
    assert len(ids) == len(set(ids)) >= 30
    assert {p.store for p in CATALOG} == set(ALL)
    assert {p.room for p in CATALOG} == {"kitchen", "living room"}
    assert all(p.id.startswith({"shopify": "shp-", "amazon": "amz-", "walmart": "wmt-"}[p.store]) for p in CATALOG)
    for item in _fixture_run().items:                            # fixtures and catalog agree
        got = store.get_products([item.product.id])
        assert got and got[0].name == item.product.name and got[0].price_usd == item.product.price_usd


def test_mock_flow_picks_match_fixture():
    """Stylist-style queries for the fixture kitchen must rank the fixture's products first, under $400.
    The intents are built here, not taken from app.llm, so this test only depends on the data layer."""
    palette = "walnut warm white brass teal"
    categories = ["knife block", "cutlery set", "canisters", "utensil holder", "cutting board", "dish towels", "bar stools"]
    intents = [SearchIntent(category=c, query=f"mid-century modern {c} {palette} matte", avoid=["glossy"])
               for c in categories]
    top = {}
    for it in intents:
        hits = store.search(it, "kitchen", ALL, 4)
        assert hits, it.category
        assert [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)
        top[it.category] = hits[0]
    want = {i.category: i.product.id for i in _fixture_run().items}
    assert {c: p.id for c, p in top.items() if c in want} == want
    assert sum(p.price_usd for c, p in top.items() if c in want) <= 400
    assert top["bar stools"].price_usd > 300                     # over the per-item cap


def test_search_filters():
    kb = SearchIntent(category="knife block", query="walnut knife block")
    assert {h.store for h in store.search(kb, "kitchen", ["amazon"])} == {"amazon"}
    assert len(store.search(kb, "kitchen", ALL, k=2)) == 2
    assert store.search(SearchIntent(category="bar stools", query="stools", max_price=300), "kitchen", ALL) == []
    assert store.search(SearchIntent(category="hot tub", query="hot tub"), "kitchen", ALL) == []

    can = store.search(SearchIntent(category="canisters", query="canisters", avoid=["glossy"]), "kitchen", ALL)
    assert can[-1].id == "amz-B0PLACEHOLD7"                      # glossy one sinks to the bottom

    rugs = store.search(SearchIntent(category="area rug", query="rug"), "living room", ALL)
    assert [r.id for r in rugs] == ["amz-B0PLACEHOLD19"]         # jute rug is out of stock


def test_category_resolution():
    r = store.resolve_category
    assert r("Knife Blocks", "kitchen") == "knife block"            # case and plural
    assert r("kitchen towels", "kitchen") == "dish towels"          # same head noun
    assert r("flatware", "kitchen") == "cutlery set"                # alias
    assert r("counter stools", "Kitchen") == "bar stools"
    assert r("bar cart", "kitchen") is None                         # shares "bar" only, not the noun
    assert r("appliance polish", "kitchen") is None and r("cabinet hardware", "kitchen") is None
    assert r("rug", "living room") == "area rug"
    assert "knife block" in store.categories("kitchen") and "area rug" not in store.categories("kitchen")
    hits = store.search(SearchIntent(category="kitchen towels", query="white cotton towels"), "kitchen", ALL)
    assert hits and all(h.category == "dish towels" for h in hits)


def test_get_products():
    got = store.get_products(["wmt-PLACEHOLD3", "nope", "shp-4471"])
    assert [p.id for p in got] == ["wmt-PLACEHOLD3", "shp-4471"]


def test_run_roundtrip():
    run = _fixture_run()
    store.save_run(run)
    run.state = "completed"                                     # must not leak into the store
    loaded = store.load_run(run.id)
    assert loaded.state == "awaiting_approval" and len(loaded.items) == 6
    assert store.load_run("r_missing") is None


def test_audit_chain():
    rid = "r_test_chain"
    audit._EVENTS.pop(rid, None)
    e0 = audit.append(rid, "user", "run.started", "Photo uploaded", {"budget_usd": 400}, user_id="priya")
    e1 = audit.append(rid, "curator", "llm.curator", "Picked 6", {"b": 1, "a": [1, 2]})
    assert (e0.seq, e1.seq) == (0, 1) and e0.prev_hash == "0" * 64 and e1.prev_hash == e0.hash
    assert audit.verify_chain(rid) and audit.verify_chain("r_empty")
    assert [e.seq for e in audit.list_events(rid)] == [0, 1]
    audit._EVENTS[rid][0].data["budget_usd"] = 9999             # tampering is detected
    assert not audit.verify_chain(rid)
    audit._EVENTS.pop(rid)


def test_fixture_chain_verifies():
    """fixtures/audit.json was hashed by scripts/make_fixtures.py; audit.py must agree with it."""
    fx = AuditResponse.model_validate_json((FIX / "audit.json").read_text())
    audit._EVENTS["r_8f2c1a"] = fx.events
    try:
        assert fx.chain_valid and audit.verify_chain("r_8f2c1a")
    finally:
        audit._EVENTS.pop("r_8f2c1a")


def test_memory():
    real, real_flag = memory._FILE, memory.USE_COGNEE
    with tempfile.TemporaryDirectory() as tmp:
        memory._FILE = Path(tmp) / "memory.json"                # don't touch the real memory file
        memory.USE_COGNEE = False                               # nor the real Cognee account
        try:
            assert asyncio.run(memory.recall("priya", "kitchen")).facts == []
            asyncio.run(memory.remember("priya", "dish towels", "removed"))
            mem = asyncio.run(memory.recall("priya", "kitchen"))
            assert mem.source == "local" and len(mem.facts) == 1 and "dish towels" in mem.facts[0]
            assert asyncio.run(memory.recall("someone_else", "kitchen")).facts == []
        finally:
            memory._FILE, memory.USE_COGNEE = real, real_flag


def test_track_never_raises():
    analytics.track("priya", "run_started", {"run_id": "r_1"})
    analytics.track(None, None, None)


# ---- SingleStore code paths, exercised against a fake s2.query (no database needed) ----
class _FakeS2:
    """Stands in for s2.query: checks placeholders match params and keeps rows per table."""
    def __init__(self):
        self.audit, self.runs, self.calls = [], {}, []

    def __call__(self, sql, params=()):
        assert sql.count("%s") == len(params), (sql, params)
        self.calls.append((sql, params))
        if sql.startswith("INSERT INTO audit_events"):
            self.audit.append(params)
        elif sql.startswith("SELECT seq"):
            return [dict(zip(["run_id", "seq", "ts", "actor", "action", "summary", "data", "prev_hash", "hash"], r))
                    for r in self.audit if r[0] == params[0]]
        elif sql.startswith("REPLACE INTO runs"):
            self.runs[params[0]] = params[4]
        elif sql.startswith("SELECT run_json"):
            return [{"run_json": self.runs[params[0]]}] if params[0] in self.runs else []
        elif "FROM products" in sql:
            p = CATALOG[0]
            row = {**p.model_dump(), "colors": '["walnut", "steel"]', "in_stock": 1,
                   "description": "matte walnut", "score": 0.91}
            return [row]
        return []


def _with_fake_s2(fn):
    from app.data import s2
    fake, real_query, real_embed = _FakeS2(), s2.query, s2.embed
    s2.query, s2.embed = fake, lambda texts: [[0.0] * s2.VECTOR_DIM for _ in texts]
    store.USE_SINGLESTORE = audit.USE_SINGLESTORE = True
    try:
        fn(fake)
    finally:
        s2.query, s2.embed = real_query, real_embed
        store.USE_SINGLESTORE = audit.USE_SINGLESTORE = False


def test_s2_search_and_products():
    def body(fake):
        hits = store.search(SearchIntent(category="Knife Block", query="walnut", avoid=["glossy"], max_price=200),
                            "open kitchen", ALL, 4)
        sql, params = fake.calls[-1]
        assert hits[0].id == "shp-4471" and hits[0].score == 0.91 and hits[0].colors == ["walnut", "steel"]
        assert "room = %s" in sql and "price_usd <= %s" in sql and "kitchen" in params and "knife block" in params
        assert params[-1] == 8                                    # over-fetch when avoid is set
        assert [p.id for p in store.get_products(["shp-4471"])] == ["shp-4471"]
    _with_fake_s2(body)


def test_s2_run_and_audit_survive_restart():
    def body(fake):
        run = _fixture_run().model_copy(update={"id": "r_s2"})
        store.save_run(run)
        store._RUNS.pop("r_s2")                                   # simulate a server restart
        assert store.load_run("r_s2").items[0].product.id == "shp-4471"

        audit._EVENTS.pop("r_s2", None)
        audit.append("r_s2", "user", "run.started", "hi", {"z": 1.5, "a": {"k": [1, 2]}}, user_id="priya")
        audit.append("r_s2", "curator", "llm.curator", "picked", {})
        audit._EVENTS.pop("r_s2")                                 # restart: reload from the table
        assert [e.seq for e in audit.list_events("r_s2")] == [0, 1] and audit.verify_chain("r_s2")
        audit._EVENTS.pop("r_s2"); store._RUNS.pop("r_s2", None)
    _with_fake_s2(body)


def test_s2_outage_falls_back_to_mock():
    from app.data import s2
    real = s2.query
    def boom(sql, params=()):
        raise ConnectionError("down")
    s2.query = boom
    store.USE_SINGLESTORE = audit.USE_SINGLESTORE = True
    try:
        hits = store.search(SearchIntent(category="knife block", query="walnut knife block"), "kitchen", ALL)
        assert hits and hits[0].id == "shp-4471"
        assert store.get_products(["shp-4502"])[0].id == "shp-4502"
        run = _fixture_run().model_copy(update={"id": "r_out"})
        store.save_run(run)
        assert store.load_run("r_out").id == "r_out"
        audit.append("r_out", "user", "run.started", "hi", {})
        assert audit.verify_chain("r_out")
        audit._EVENTS.pop("r_out"); store._RUNS.pop("r_out")
    finally:
        s2.query = real
        store.USE_SINGLESTORE = audit.USE_SINGLESTORE = False


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
