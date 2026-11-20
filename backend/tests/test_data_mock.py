"""Smoke tests for the data layer (app/data). Run from backend/:
    python -m pytest tests -q        or        python -m tests.test_data_mock
These must keep passing when the real backends land behind the USE_* flags.
"""
import asyncio
import tempfile
from pathlib import Path

from app import llm
from app.contracts import AuditResponse, Run, SearchIntent, UserMemory
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
    """The mock stylist's queries must rank the fixture's products first and stay under $400."""
    profile = llm.analyze_room(None, "", "")
    intents = llm.stylist(profile, UserMemory(source="local"), 400)
    top = {}
    for it in intents:
        hits = store.search(it, profile.room_type, ALL, 4)
        assert hits, it.category
        assert [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)
        top[it.category] = hits[0]
    want = {i.category: i.product.id for i in _fixture_run().items}
    assert {c: p.id for c, p in top.items() if c in want} == want
    assert sum(p.price_usd for c, p in top.items() if c in want) <= 400
    assert top["bar stools"].price_usd > 300                     # so the curator skips it


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
    real = memory._FILE
    with tempfile.TemporaryDirectory() as tmp:
        memory._FILE = Path(tmp) / "memory.json"                # don't touch the real memory file
        try:
            assert asyncio.run(memory.recall("priya", "kitchen")).facts == []
            asyncio.run(memory.remember("priya", "dish towels", "removed"))
            mem = asyncio.run(memory.recall("priya", "kitchen"))
            assert mem.source == "local" and len(mem.facts) == 1 and "dish towels" in mem.facts[0]
            assert asyncio.run(memory.recall("someone_else", "kitchen")).facts == []
        finally:
            memory._FILE = real


def test_track_never_raises():
    analytics.track("priya", "run_started", {"run_id": "r_1"})
    analytics.track(None, None, None)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
