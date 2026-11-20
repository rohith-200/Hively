"""OWNER: Suman. Cognee taste memory. Local-JSON MOCK below; add Cognee behind USE_COGNEE
with a 20 s timeout and keep this as the fallback."""
import json
from pathlib import Path
from typing import Literal

from app.contracts import UserMemory

_FILE = Path(__file__).resolve().parents[2] / "memory.json"


def _load() -> dict:
    try:
        return json.loads(_FILE.read_text())
    except Exception:
        return {}


async def recall(user_id: str, room_type: str) -> UserMemory:
    facts = _load().get(user_id, [])[-10:]
    return UserMemory(source="local", summary=" ".join(facts), facts=facts)


async def remember(user_id: str, fact: str,
                   kind: Literal["purchase", "removed", "rejected", "preference"]) -> None:
    d = _load()
    d.setdefault(user_id, []).append(f"[{kind}] {fact}")
    _FILE.write_text(json.dumps(d, indent=2))
