"""OWNER: Suman. Hash-chained audit log (SingleStore) mirrored to Amplitude.
The hash chain below is the real algorithm from the design doc; only storage is in-memory.
Swap _EVENTS for the audit_events table behind USE_SINGLESTORE."""
import hashlib
import json

from app.contracts import AuditEvent, now
from app.data import analytics

_EVENTS: dict[str, list[AuditEvent]] = {}
GENESIS = "0" * 64


def _hash(prev: str, run_id: str, e: AuditEvent) -> str:
    raw = f"{prev}{run_id}{e.seq}{e.ts.isoformat()}{e.actor}{e.action}{json.dumps(e.data, sort_keys=True, default=str)}"
    return hashlib.sha256(raw.encode()).hexdigest()


def append(run_id: str, actor: str, action: str, summary: str, data: dict | None = None,
           user_id: str = "", extra_props: dict | None = None) -> AuditEvent:
    events = _EVENTS.setdefault(run_id, [])
    prev = events[-1].hash if events else GENESIS
    e = AuditEvent(seq=len(events), ts=now(), actor=actor, action=action, summary=summary,
                   data=data or {}, prev_hash=prev)
    e.hash = _hash(prev, run_id, e)
    events.append(e)
    analytics.track(user_id, action.replace(".", "_"), {"run_id": run_id, "actor": actor, **(extra_props or {})})
    return e


def list_events(run_id: str) -> list[AuditEvent]:
    return list(_EVENTS.get(run_id, []))


def verify_chain(run_id: str) -> bool:
    prev = GENESIS
    for e in _EVENTS.get(run_id, []):
        if e.prev_hash != prev or e.hash != _hash(prev, run_id, e):
            return False
        prev = e.hash
    return True
