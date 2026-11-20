"""OWNER: Jaideep. Nebius-backed LLM pipeline.
Keep these signatures exactly (see contracts.py). The bodies below are MOCKS so the
orchestrator runs today; replace them behind `if USE_NEBIUS:` and keep the mock as fallback.
"""
from app.config import USE_NEBIUS  # noqa: F401  (Jaideep: branch on this)
from app.contracts import (CriticVerdict, CuratorPlan, LLMMeta, PaletteColor, Pick, Product,
                           RoomProfile, SearchIntent, Skip, UserMemory)

_MOCK = LLMMeta(model="mock", latency_ms=5, fallback_used=False)


def analyze_room(image: bytes | None, media_type: str, note: str) -> RoomProfile:
    return RoomProfile(
        room_type="kitchen", style="mid-century modern", style_confidence=0.86,
        palette=[PaletteColor(name="walnut", hex="#6B4A2F"), PaletteColor(name="warm white", hex="#F3EFE6"),
                 PaletteColor(name="brass", hex="#C9A14A"), PaletteColor(name="teal", hex="#2A7C7C")],
        materials=["walnut cabinets", "brass pulls", "white quartz"], observed_items=["range", "refrigerator"],
        missing_categories=["knife block", "cutlery set", "canisters", "utensil holder",
                            "cutting board", "dish towels", "bar stools"],
        evidence="MOCK: walnut slab cabinets, brass pulls, white quartz counter")


def stylist(profile: RoomProfile, memory: UserMemory, budget_usd: float) -> list[SearchIntent]:
    palette = " ".join(c.name for c in profile.palette)
    return [SearchIntent(category=c, query=f"{profile.style} {c} {palette} matte", avoid=["glossy"],
                         max_price=None) for c in profile.missing_categories]


def curator(profile: RoomProfile, memory: UserMemory, candidates: dict[str, list[Product]],
            budget_usd: float, max_item_usd: float) -> CuratorPlan:
    picks, skipped = [], []
    for cat, cands in candidates.items():
        ok = [p for p in cands if p.price_usd <= max_item_usd]
        if not ok:
            skipped.append(Skip(category=cat, reason=f"No match under ${max_item_usd:.0f}"))
            continue
        best = ok[0]
        picks.append(Pick(category=cat, product_id=best.id,
                          reason=f"MOCK: {', '.join(best.colors)} fits a {profile.style} palette"))
    return CuratorPlan(picks=picks, skipped=skipped, summary="MOCK plan: top match per category", meta=_MOCK)


def critic(plan: CuratorPlan, candidates: dict[str, list[Product]], profile: RoomProfile,
           memory: UserMemory, budget_usd: float) -> CriticVerdict:
    return CriticVerdict(approved=True, changes=[], notes="MOCK: palette consistent", style_score=0.86, meta=_MOCK)
