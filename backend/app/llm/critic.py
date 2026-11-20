
"""Hively independent recommendation Critic.

Reviews style, preferences, duplicates, stock and budget.
Only proposes genuine same-category product replacements.
"""

from app.contracts import CriticVerdict, LLMMeta
from .nebius_client import ask, enabled, compact, model


def _fallback():
    return CriticVerdict(
        approved=True,
        changes=[],
        notes=(
            "AI review unavailable; no model-based changes made. "
            "Deterministic guardrails must still run."
        ),
        style_score=0.5,
    )


def critic(
    plan,
    candidates,
    profile,
    memory,
    budget_usd: float,
) -> CriticVerdict:

    fallback = _fallback()

    if not enabled():
        fallback.meta = LLMMeta(
            model="mock",
            fallback_used=True,
        )
        return fallback

    allowed = {
        category: {product.id: product for product in products}
        for category, products in candidates.items()
    }

    current = {
        pick.category: pick.product_id
        for pick in plan.picks
    }

    payload = {
        "task": (
            "You are Hively's independent shopping Critic. "
            "Review the Curator's selections for style consistency, "
            "user preferences, duplicate products, stock and budget. "

            "Return valid JSON containing: "
            "approved (boolean), changes (array), "
            "notes (string), style_score (number from 0 to 1). "

            "Each change must contain category, replace_with and reason. "

            "IMPORTANT RULES: "
            "Only propose a replacement if a DIFFERENT and clearly "
            "BETTER product exists in the SAME category. "

            "Never replace a product with itself. "

            "If the selected product is acceptable but its explanation "
            "could be improved, describe that in notes instead of "
            "creating a replacement. "

            "A difference between the product's catalog style label "
            "and the room style does not automatically make the "
            "product unsuitable. Consider actual colors, materials "
            "and visual compatibility. "

            "Respect explicit user preferences over inferred ones. "

            "Never invent product IDs. "
            "Only use IDs from the supplied candidate list. "

            "Never recommend out-of-stock products. "
            "Never exceed the total budget. "
            "Do not create duplicate selections. "

            "If no genuine replacements are needed, "
            "return approved=true and changes=[]. "

            "If one or more genuine replacements are proposed, "
            "return approved=false. "

            "Use notes for observations that do not require swaps. "
            "Return JSON only."
        ),
        "profile": profile.model_dump(
            exclude={"photo_url"}
        ),
        "memory": memory.model_dump(),
        "budget": budget_usd,
        "plan": plan.model_dump(exclude={"meta"}),
        "candidates": {
            category: [
                {
                    "id": product.id,
                    "price": product.price_usd,
                    "name": product.name,
                    "style": product.style,
                    "colors": product.colors,
                    "material": product.material,
                    "in_stock": product.in_stock,
                }
                for product in products[:4]
            ]
            for category, products in candidates.items()
        },
    }

    def validate(data):
        verdict = CriticVerdict.model_validate(data)

        seen = set()
        valid_changes = []

        for change in verdict.changes:

            if change.category not in current:
                raise ValueError(
                    "Critic referenced an unselected category"
                )

            if change.category in seen:
                raise ValueError(
                    "Duplicate Critic category"
                )

            seen.add(change.category)

            category_products = allowed.get(
                change.category, {}
            )

            if change.replace_with not in category_products:
                raise ValueError(
                    "Replacement is not a same-category candidate"
                )

            # A replacement with the current product is not a swap.
            # Keep the observation in notes instead.
            if change.replace_with == current[change.category]:
                if change.reason:
                    verdict.notes = (
                        verdict.notes + " " + change.reason
                    ).strip()
                continue

            replacement = category_products[change.replace_with]

            if not replacement.in_stock:
                raise ValueError(
                    "Critic selected an out-of-stock replacement"
                )

            valid_changes.append(change)

        verdict.changes = valid_changes

        proposed = dict(current)

        for change in valid_changes:
            proposed[change.category] = change.replace_with

        if len(set(proposed.values())) != len(proposed):
            raise ValueError(
                "Duplicate product IDs after Critic changes"
            )

        total = 0.0

        for category, product_id in proposed.items():

            product = allowed.get(category, {}).get(product_id)

            if product is None:
                raise ValueError(
                    "Selected product missing from candidate catalog"
                )

            if not product.in_stock:
                raise ValueError(
                    "Selected product is out of stock"
                )

            total += product.price_usd

        if total > budget_usd + 0.001:
            raise ValueError(
                "Critic changes exceed the total budget"
            )

        verdict.approved = len(valid_changes) == 0

        verdict.style_score = max(
            0.0,
            min(1.0, verdict.style_score),
        )

        return verdict

    try:
        verdict, latency = ask(
            "CRITIC",
            compact(payload),
            max_tokens=1100,
            no_thinking=True,
            validator=validate,
        )

        verdict.meta = LLMMeta(
            model=model("CRITIC"),
            latency_ms=latency,
            fallback_used=False,
        )

        return verdict

    except Exception as exc:
        print(
            f"Critic inference failed: {type(exc).__name__}"
        )

        fallback.meta = LLMMeta(
            model=model("CRITIC"),
            fallback_used=True,
        )

        return fallback
