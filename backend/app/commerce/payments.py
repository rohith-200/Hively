"""OWNER: Rohit. Stripe test mode: hold on plan, capture (maybe partial) on approve, cancel on reject.
Real when USE_STRIPE=1 and STRIPE_SECRET_KEY is set; otherwise a mock with the same shapes."""
import uuid

from app.config import STRIPE_SECRET_KEY, STRIPE_TEST_PAYMENT_METHOD, USE_STRIPE
from app.contracts import PaymentInfo

LIVE = USE_STRIPE and bool(STRIPE_SECRET_KEY)
if LIVE:
    import stripe
    stripe.api_key = STRIPE_SECRET_KEY


class PaymentError(Exception):
    pass


def _cents(usd: float) -> int:
    return int(round(usd * 100))


def hold(run_id: str, amount_usd: float, description: str = "") -> PaymentInfo:
    if amount_usd <= 0:
        return PaymentInfo(mode="stripe" if LIVE else "mock", status="none")
    if not LIVE:
        return PaymentInfo(mode="mock", payment_intent_id=f"pi_mock_{uuid.uuid4().hex[:12]}", status="held")
    try:
        pi = stripe.PaymentIntent.create(
            amount=_cents(amount_usd), currency="usd", capture_method="manual",
            payment_method=STRIPE_TEST_PAYMENT_METHOD, payment_method_types=["card"], confirm=True,
            description=(description or f"Roomie run {run_id}")[:500],
            metadata={"run_id": run_id, "placed_by": "roomie-agent"},
            idempotency_key=f"hold-{run_id}")
    except Exception as e:  # stripe.error.StripeError and network errors
        raise PaymentError(str(e)) from e
    if pi.status != "requires_capture":
        raise PaymentError(f"unexpected PaymentIntent status {pi.status}")
    return PaymentInfo(mode="stripe", payment_intent_id=pi.id, status="held")


def capture(payment_intent_id: str, amount_usd: float, held_usd: float) -> PaymentInfo:
    partial = _cents(amount_usd) < _cents(held_usd)
    status = "partially_captured" if partial else "captured"
    if not LIVE:
        return PaymentInfo(mode="mock", payment_intent_id=payment_intent_id, status=status)
    try:
        stripe.PaymentIntent.capture(payment_intent_id, amount_to_capture=_cents(amount_usd),
                                     idempotency_key=f"capture-{payment_intent_id}")
    except Exception as e:
        raise PaymentError(str(e)) from e
    return PaymentInfo(mode="stripe", payment_intent_id=payment_intent_id, status=status)


def cancel(payment_intent_id: str) -> PaymentInfo:
    if not LIVE:
        return PaymentInfo(mode="mock", payment_intent_id=payment_intent_id, status="canceled")
    try:
        stripe.PaymentIntent.cancel(payment_intent_id, idempotency_key=f"cancel-{payment_intent_id}")
    except Exception as e:
        raise PaymentError(str(e)) from e
    return PaymentInfo(mode="stripe", payment_intent_id=payment_intent_id, status="canceled")
