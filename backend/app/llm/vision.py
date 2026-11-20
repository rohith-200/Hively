
"""Room perception using Nebius Vision.

Returns the frozen RoomProfile contract.
Supports image + note, text-only input, and mock mode.
"""

import base64
import re

from app.contracts import RoomProfile
from .nebius_client import ask, enabled


SCHEMA = """
You are the Vision Agent for Hively, an AI interior shopping assistant.

Your task is to understand the room and identify useful products
that complement its existing design.

Return ONLY a valid JSON object with these exact fields:

{
  "room_type": "kitchen",
  "style": "transitional",
  "style_confidence": 0.85,
  "palette": [
    {"name": "charcoal", "hex": "#4A4A4A"},
    {"name": "white", "hex": "#FFFFFF"}
  ],
  "materials": ["painted wood", "ceramic tile"],
  "observed_items": ["cabinets", "sink"],
  "missing_categories": ["cutting board", "knife block"],
  "evidence": "Short description of visible design evidence."
}

RULES:

1. ROOM IDENTIFICATION
- Identify the room type accurately.
- Use the user's description when no image is supplied.
- Never invent visual observations.

2. STYLE ANALYSIS
- Identify the dominant interior design style.
- Consider modern, Scandinavian, mid-century modern,
  transitional, industrial, farmhouse, and minimalist.
- Base the style on visible design evidence.
- Lower confidence when the image is unclear.

3. COLOR ANALYSIS
- Identify 3 to 6 dominant colors.
- Return each color as {"name": "...", "hex": "#RRGGBB"}.
- Hex codes are approximate visual estimates.
- Do not invent accent colors.

4. MATERIAL ANALYSIS
- Identify only materials that are reasonably visible.
- Distinguish likely materials from certain observations.
- Do not claim a metallic finish is brass merely because
  it looks gold or silver.

5. EXISTING OBJECTS
- List clearly identifiable objects.
- Avoid duplicates and overly specific object names.
- Do not infer hidden appliances or furniture.

6. SHOPPING RECOMMENDATIONS
- Suggest 4 to 6 practical product categories.
- Prioritize affordable decorative and functional accessories.
- Recommend items that complement existing colors and style.
- Do not suggest replacing cabinets, flooring, or appliances
  unless the user explicitly requests renovations.
- Do not suggest items already clearly present.
- Do not assume space exists for bar stools, islands,
  large furniture, or additional appliances.
- Prefer accessories that require no installation.
- Missing_categories means useful shopping opportunities,
  not proof that the room lacks those items.

7. USER PREFERENCES
- Respect the user's note and explicit restrictions.
- Avoid recommending prohibited styles, materials, or finishes.
- The user's note can specify the desired design direction.

8. OUTPUT
- Return only valid JSON.
- No markdown or explanatory text outside JSON.
- Keep evidence factual and concise.
"""


def _mock(note: str) -> RoomProfile:
    """Return a room-appropriate fixture without API calls."""

    note = note or ""
    lower = note.lower()

    if re.search(r"\bkitchen\b", lower):
        return RoomProfile(
            room_type="kitchen",
            style=(
                "Scandinavian"
                if "scandinavian" in lower
                else "mid-century modern"
            ),
            style_confidence=0.82,
            palette=[
                {"name": "walnut", "hex": "#6B4A2F"},
                {"name": "cream", "hex": "#F2E8D5"},
            ],
            materials=["wood", "ceramic"],
            observed_items=["cabinets", "countertop"],
            missing_categories=[
                "knife block",
                "cutlery set",
                "canisters",
                "cutting board",
            ],
            evidence=(
                "Mock kitchen profile based on user description: "
                + note[:150]
            ),
        )

    return RoomProfile(
        room_type="living room",
        style=(
            "Scandinavian"
            if "scandinavian" in lower
            else "mid-century modern"
        ),
        style_confidence=0.82,
        palette=[
            {"name": "walnut", "hex": "#6B4A2F"},
            {"name": "cream", "hex": "#F2E8D5"},
        ],
        materials=["wood", "fabric"],
        observed_items=["sofa", "coffee table"],
        missing_categories=[
            "floor lamp",
            "throw pillows",
            "wall art",
            "area rug",
        ],
        evidence=(
            "Mock living room profile based on user description: "
            + note[:150]
        ),
    )


def analyze_room(
    image: bytes | None,
    media_type: str,
    note: str,
) -> RoomProfile:
    """Analyze a room using Nebius or a local mock."""

    note = note or ""

    if not enabled():
        return _mock(note)

    if not image and not note.strip():
        return _mock("")

    if image:
        if media_type not in ("image/jpeg", "image/png"):
            raise ValueError(
                "Only JPEG and PNG images are supported"
            )

        if len(image) > 8 * 1024 * 1024:
            raise ValueError("Image exceeds 8MB limit")

    parts = [
        {
            "type": "text",
            "text": (
                SCHEMA
                + "\nUSER INSTRUCTIONS:\n"
                + note[:1000]
            ),
        }
    ]

    if image:
        encoded = base64.b64encode(image).decode("ascii")

        parts.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": (
                        f"data:{media_type};base64,{encoded}"
                    )
                },
            }
        )

    try:
        profile, _ = ask(
            "VISION",
            parts,
            max_tokens=850,
            no_thinking=True,
            validator=lambda data: RoomProfile.model_validate(data),
        )

        # Basic normalization and safety checks.
        profile.style_confidence = max(
            0.0,
            min(1.0, profile.style_confidence),
        )

        profile.missing_categories = list(
            dict.fromkeys(
                category.strip().lower()
                for category in profile.missing_categories
                if category.strip()
            )
        )[:6]

        return profile

    except Exception as exc:
        print(
            f"Vision inference failed: {type(exc).__name__}"
        )

        # Preserve demo availability without pretending that
        # a failed image was successfully analyzed.
        profile = _mock(note)
        profile.style_confidence = 0.0
        profile.evidence = (
            "Vision unavailable. Generic fallback suggestions; "
            "image contents have not been verified."
        )
        return profile
