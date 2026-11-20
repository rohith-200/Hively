
"""Hively personalized shopping Stylist.

Generates search intents from:
- Room analysis
- User preferences and memory
- Total shopping budget

No hardcoded category prices.
Compatible with Rohit's frozen SearchIntent contract.
"""

import re

from app.contracts import SearchIntent
from .nebius_client import ask, enabled, compact


MAX_CATEGORIES = 6


def _categories(profile):
    """Preserve requested categories without duplicates."""
    return list(dict.fromkeys(
        category.strip()
        for category in profile.missing_categories
        if category.strip()
    ))[:MAX_CATEGORIES]


def _fallback(profile, memory, budget):
    """Safe deterministic fallback without an API call."""

    categories = _categories(profile)

    return [
        SearchIntent(
            category=category,
            query=(
                f"{profile.style} {category} "
                f"{' '.join(profile.materials[:2])}"
            ).strip(),
            must_have=[],
            avoid=[],
            max_price=max(0.0, float(budget)),
        )
        for category in categories
    ]


def _normalize_intent(intent, budget):
    """Validate search parameters without arbitrary price caps."""

    intent.query = intent.query.strip()

    if not intent.query:
        raise ValueError("Empty search query")

    # A broad retrieval ceiling prevents the model from
    # excluding good products before the Curator sees them.
    #
    # This is NOT the final spending allocation.
    # The Curator and backend guardrails enforce the budget.
    intent.max_price = max(0.0, float(budget))

    intent.must_have = list(dict.fromkeys(
        value.strip()
        for value in intent.must_have
        if value.strip()
    ))

    intent.avoid = list(dict.fromkeys(
        value.strip()
        for value in intent.avoid
        if value.strip()
    ))

    return intent


def stylist(profile, memory, budget_usd: float) -> list[SearchIntent]:
    """Generate personalized shopping search intents."""

    budget_usd = max(0.0, float(budget_usd))
    fallback = _fallback(profile, memory, budget_usd)

    if not enabled():
        return fallback

    categories = _categories(profile)

    payload = {
        "role": "Hively Personal Shopping Stylist",
        "task": (
            "Generate exactly one personalized shopping search "
            "intent for each requested category. "
            "Return a JSON array with category, query, "
            "must_have, avoid, and max_price. "
            "Use the room style, palette, materials, "
            "observed objects, and user memory. "
            "Preserve category names exactly. "
            "Do not invent additional categories. "
            "Use specific product search queries rather than "
            "generic descriptions. "
            "Prioritize explicit user instructions over "
            "inferred preferences. "
            "Treat colors, materials, and styles as preferences "
            "unless the user explicitly makes them mandatory. "
            "Do not invent restrictions or dislikes. "
            "Do not require product features merely because "
            "they appear elsewhere in the room. "
            "Do not divide the total budget equally between "
            "categories. "
            "max_price is a broad product search ceiling, "
            "not a spending commitment. "
            "The final product combination must be selected "
            "by the Curator within the total budget. "
            "Return valid JSON only."
        ),
        "room_profile": profile.model_dump(
            exclude={"photo_url"}
        ),
        "user_memory": memory.model_dump(),
        "budget_usd": budget_usd,
        "categories": categories,
        "search_price_ceiling_usd": budget_usd,
    }

    allowed = set(categories)

    def validate(data):
        """Validate the model output against frozen contracts."""

        if isinstance(data, dict):
            data = data.get("intents", [])

        if not isinstance(data, list):
            raise ValueError("Expected an array of intents")

        result = [
            SearchIntent.model_validate(item)
            for item in data
        ]

        returned = [item.category for item in result]

        if (
            len(result) != len(categories)
            or len(set(returned)) != len(returned)
            or set(returned) != allowed
        ):
            raise ValueError(
                "Missing, duplicated, or invented categories"
            )

        return [
            _normalize_intent(item, budget_usd)
            for item in result
        ]

    try:
        result, _ = ask(
            "STYLIST",
            compact(payload),
            max_tokens=1100,
            no_thinking=True,
            validator=validate,
        )
        return result

    except Exception as exc:
        print(
            f"Stylist inference failed: {type(exc).__name__}"
        )
        return fallback
