"""Per-run event bus for SSE. Keeps history so a client that connects late gets a full replay."""
import asyncio
import json

TERMINAL = {"awaiting_approval", "completed", "partial", "rejected", "failed"}


class RunBus:
    def __init__(self):
        self.history: list[tuple[str, dict]] = []
        self.subscribers: list[asyncio.Queue] = []

    def publish(self, event: str, data: dict):
        self.history.append((event, data))
        for q in self.subscribers:
            q.put_nowait((event, data))

    async def stream(self):
        q: asyncio.Queue = asyncio.Queue()
        for item in self.history:
            q.put_nowait(item)
        self.subscribers.append(q)
        try:
            while True:
                try:
                    event, data = await asyncio.wait_for(q.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"
                if event == "state" and data.get("state") in TERMINAL:
                    return
        finally:
            self.subscribers.remove(q)


BUSES: dict[str, RunBus] = {}


def bus(run_id: str) -> RunBus:
    return BUSES.setdefault(run_id, RunBus())
