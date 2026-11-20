"""OWNER: Suman. Amplitude. Must never raise. Console MOCK below; add Amplitude behind USE_AMPLITUDE."""
from app.config import USE_AMPLITUDE  # noqa: F401


def track(user_id: str, event: str, props: dict) -> None:
    try:
        print(f"[analytics] {user_id or '-'} {event} {props.get('run_id', '')}")
    except Exception:
        pass
