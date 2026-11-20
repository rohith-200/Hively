"""OWNER: Suman. Per-user taste memory.
Every fact is always written to a local JSON file. With USE_COGNEE=1 (and COGNEE_API_URL,
COGNEE_API_KEY, COGNEE_TENANT_ID set) facts are also sent to a per-user dataset on Cognee Cloud
(in the background, so approve is never slowed down) and recall asks Cognee first, falling back
to the local file on any error or after COGNEE_TIMEOUT seconds."""
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Literal

import httpx

from app.config import USE_COGNEE
from app.contracts import UserMemory

_FILE = Path(__file__).resolve().parents[2] / "memory.json"
COGNEE_TIMEOUT = float(os.getenv("COGNEE_TIMEOUT", "12"))    # under the orchestrator's 20 s limit
_tasks: set = set()


def _load() -> dict:
    try:
        return json.loads(_FILE.read_text())
    except Exception:
        return {}


def _warn(what: str, err: Exception) -> None:
    print(f"[memory] Cognee {what} failed, using local memory: {err!r}", file=sys.stderr)


def _dataset(user_id: str) -> str:
    return "roomie_" + re.sub(r"[^a-zA-Z0-9]+", "_", user_id or "anonymous")


def _cognee_ready() -> bool:
    return bool(USE_COGNEE and os.getenv("COGNEE_API_URL") and os.getenv("COGNEE_API_KEY"))


def _client(timeout: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=os.environ["COGNEE_API_URL"].rstrip("/"), timeout=timeout,
        headers={"X-Api-Key": os.environ["COGNEE_API_KEY"], "X-Tenant-Id": os.getenv("COGNEE_TENANT_ID", "")})


async def _cognee_add(user_id: str, text: str) -> None:
    """POST /api/v1/remember: add + build the graph. Cognee does the graph build server-side."""
    try:
        async with _client(30) as c:
            r = await c.post("/api/v1/remember", files=[("raw_data", (None, text)),
                                                        ("datasetName", (None, _dataset(user_id)))])
            r.raise_for_status()
    except Exception as e:
        _warn("remember", e)


async def _cognee_search(user_id: str, room_type: str) -> list[str]:
    """POST /api/v1/recall on the user's dataset. 404 = nothing searchable yet."""
    async with _client(COGNEE_TIMEOUT) as c:
        r = await c.post("/api/v1/recall", json={
            "query": f"What does this user like, dislike or avoid when furnishing a {room_type}? "
                     "Include anything they removed or rejected before.",
            "datasets": [_dataset(user_id)], "searchType": "GRAPH_COMPLETION",
            "systemPrompt": "Answer in one or two short sentences using only the provided context."})
        if r.status_code == 404:
            return []
        r.raise_for_status()
    out = []
    for item in r.json() or []:
        text = item if isinstance(item, str) else (item.get("text") or item.get("answer") or "")
        if isinstance(text, str) and text.strip():
            out.append(text.strip())
    return out


async def recall(user_id: str, room_type: str) -> UserMemory:
    facts = _load().get(user_id, [])[-10:]
    if _cognee_ready() and facts:                             # nothing stored yet -> nothing to ask
        try:
            answers = await asyncio.wait_for(_cognee_search(user_id, room_type), COGNEE_TIMEOUT)
            if answers:
                return UserMemory(source="cognee", summary=" ".join(answers)[:600], facts=facts)
        except Exception as e:
            _warn("search", e)
    return UserMemory(source="local", summary=" ".join(facts), facts=facts)


async def remember(user_id: str, fact: str,
                   kind: Literal["purchase", "removed", "rejected", "preference"]) -> None:
    d = _load()
    entry = f"[{kind}] {fact}"
    d.setdefault(user_id, []).append(entry)
    _FILE.write_text(json.dumps(d, indent=2))
    if _cognee_ready():
        task = asyncio.create_task(_cognee_add(user_id, entry))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)


async def wait_for_pending() -> None:
    """Let background Cognee writes finish (seed script, tests)."""
    if _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)
