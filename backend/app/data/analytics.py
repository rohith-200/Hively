"""OWNER: Suman. Amplitude. Must never raise.
USE_AMPLITUDE=1 + AMPLITUDE_API_KEY: events go to Amplitude (batched, sent in the background).
Otherwise: printed to the console. Pipeline code calls audit.append, not track."""
import os
import sys

from app.config import USE_AMPLITUDE

_client = None


def _amplitude():
    global _client
    if _client is None:
        from amplitude import Amplitude
        _client = Amplitude(os.getenv("AMPLITUDE_API_KEY", ""))
        _client.configuration.min_id_length = 1          # demo user ids can be short
        _client.configuration.flush_interval_millis = 2000
        _client.configuration.callback = _on_result
    return _client


results = {"ok": 0, "failed": 0}                         # delivery counts, for debugging


def _on_result(event, code, message=None) -> None:
    """Called by the SDK's background thread once Amplitude has answered for an event."""
    if code == 200:
        results["ok"] += 1
    else:
        results["failed"] += 1
        print(f"[analytics] Amplitude rejected {getattr(event, 'event_type', '?')}: {code} {message}", file=sys.stderr)


def track(user_id: str, event: str, props: dict) -> None:
    try:
        props = dict(props or {})
        if USE_AMPLITUDE and os.getenv("AMPLITUDE_API_KEY"):
            from amplitude import BaseEvent
            _amplitude().track(BaseEvent(event_type=str(event), user_id=str(user_id or "anonymous"),
                                         event_properties=props))
            return
        print(f"[analytics] {user_id or '-'} {event} {props.get('run_id', '')}")
    except Exception:
        pass


def flush() -> None:
    """Send anything still queued (call before the process exits or before showing the chart)."""
    try:
        if _client is not None:
            _client.flush()
    except Exception:
        pass
