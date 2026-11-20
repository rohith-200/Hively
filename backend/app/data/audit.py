"""OWNER: Suman. Hash-chained audit log, mirrored to Amplitude.
The chain is kept in memory and, with USE_SINGLESTORE=1, written through to audit_events and
reloaded from there after a restart. A SingleStore error never blocks a run."""
import hashlib
import json
import sys
import threading

from app.config import USE_SINGLESTORE
from app.contracts import AuditEvent, now
from app.data import analytics, s2

_EVENTS: dict[str, list[AuditEvent]] = {}
_lock = threading.RLock()
GENESIS = "0" * 64

# audit action -> Amplitude event name (the list in the design doc). Others: "." -> "_".
EVENT_NAMES = {
    "run.started": "run_started",
    "llm.vision": "room_analyzed",
    "memory.recalled": "memory_recalled",
    "llm.stylist": "llm_stylist_done",
    "catalog.searched": "catalog_searched",
    "llm.curator": "llm_curator_done",
    "llm.critic": "llm_critic_done",
    "guardrails.passed": "guardrails_passed",
    "guardrails.blocked": "guardrails_blocked",
    "payment.held": "payment_held",
    "run.approved": "run_approved",
    "merchant.executed": "merchant_executed",
    "payment.captured": "payment_captured",
    "run.rejected": "run_rejected",
    "run.failed": "run_failed",
}


def _warn(what: str, err: Exception) -> None:
    print(f"[audit] SingleStore {what} failed, keeping events in memory: {err!r}", file=sys.stderr)


def _hash(prev: str, run_id: str, e: AuditEvent) -> str:
    raw = f"{prev}{run_id}{e.seq}{e.ts.isoformat()}{e.actor}{e.action}{json.dumps(e.data, sort_keys=True, default=str)}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _chain(run_id: str) -> list[AuditEvent]:
    """The run's events, loading them from SingleStore the first time we see this run."""
    if run_id not in _EVENTS:
        events: list[AuditEvent] = []
        if USE_SINGLESTORE:
            try:
                rows = s2.query("SELECT seq, ts, actor, action, summary, data, prev_hash, hash "
                                "FROM audit_events WHERE run_id = %s ORDER BY seq", (run_id,))
                events = [AuditEvent(seq=r["seq"], ts=s2.from_db_time(r["ts"]), actor=r["actor"],
                                     action=r["action"], summary=r["summary"] or "",
                                     data=s2.as_json(r["data"]) or {}, prev_hash=r["prev_hash"],
                                     hash=r["hash"]) for r in rows]
            except Exception as e:
                _warn("load", e)
        _EVENTS[run_id] = events
    return _EVENTS[run_id]


def append(run_id: str, actor: str, action: str, summary: str, data: dict | None = None,
           user_id: str = "", extra_props: dict | None = None) -> AuditEvent:
    with _lock:
        events = _chain(run_id)
        prev = events[-1].hash if events else GENESIS
        # round-trip data through JSON so the stored copy hashes the same as the in-memory one
        clean = json.loads(json.dumps(data or {}, default=str))
        e = AuditEvent(seq=len(events), ts=now(), actor=actor, action=action, summary=summary,
                       data=clean, prev_hash=prev)
        e.hash = _hash(prev, run_id, e)
        events.append(e)
    if USE_SINGLESTORE:
        try:
            s2.query("INSERT INTO audit_events (run_id, seq, ts, actor, action, summary, data, prev_hash, hash) "
                     "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                     (run_id, e.seq, s2.to_db_time(e.ts), actor, action, summary,
                      json.dumps(clean), prev, e.hash))
        except Exception as err:
            _warn("insert", err)
    analytics.track(user_id, EVENT_NAMES.get(action, action.replace(".", "_")),
                    {"run_id": run_id, "user_id": user_id, "actor": actor, "action": action,
                     "seq": e.seq, **(extra_props or {})})
    return e


def list_events(run_id: str) -> list[AuditEvent]:
    with _lock:
        return list(_chain(run_id))


def verify_chain(run_id: str) -> bool:
    prev = GENESIS
    for i, e in enumerate(list_events(run_id)):
        if e.seq != i or e.prev_hash != prev or e.hash != _hash(prev, run_id, e):
            return False
        prev = e.hash
    return True
