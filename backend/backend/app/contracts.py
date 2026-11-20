"""Shared contracts. FROZEN — any change needs a team-chat message + the other owner's OK.
Source of truth: "Roomie — Tech Design & Team Plan" doc.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

Store = Literal["shopify", "amazon", "walmart"]
RunState = Literal["created", "analyzing", "awaiting_approval", "executing",
                   "completed", "partial", "rejected", "failed"]
ExecutionMode = Literal["auto_buy", "cart_link", "product_link"]
Actor = Literal["user", "vision", "memory", "stylist", "catalog", "curator",
                "critic", "policy", "payments", "merchant", "system"]


def now() -> datetime:
    return datetime.now(timezone.utc)


# ---------- catalog / profile / memory ----------
class Product(BaseModel):
    id: str                      # "shp-4471", "amz-B0XXXX", "wmt-123456"
    store: Store
    store_product_id: str        # Shopify variant id | ASIN | Walmart item id
    name: str
    room: str
    category: str
    style: str
    colors: list[str] = []
    material: str = ""
    price_usd: float
    image_url: str = ""
    url: str = ""
    in_stock: bool = True
    score: Optional[float] = None


class PaletteColor(BaseModel):
    name: str
    hex: str


class RoomProfile(BaseModel):
    room_type: str
    style: str
    style_confidence: float
    palette: list[PaletteColor] = []
    materials: list[str] = []
    observed_items: list[str] = []
    missing_categories: list[str] = []
    evidence: str = ""
    photo_url: Optional[str] = None


class UserMemory(BaseModel):
    source: Literal["cognee", "local"]
    summary: str = ""
    facts: list[str] = []


# ---------- LLM outputs (Jaideep) ----------
class LLMMeta(BaseModel):
    model: str
    latency_ms: int = 0
    fallback_used: bool = False


class SearchIntent(BaseModel):
    category: str
    query: str
    must_have: list[str] = []
    avoid: list[str] = []
    max_price: Optional[float] = None


class Pick(BaseModel):
    category: str
    product_id: str
    reason: str


class Skip(BaseModel):
    category: str
    reason: str


class CuratorPlan(BaseModel):
    picks: list[Pick] = []
    skipped: list[Skip] = []
    summary: str = ""
    meta: Optional[LLMMeta] = None


class CriticChange(BaseModel):
    category: str
    replace_with: str
    reason: str


class CriticVerdict(BaseModel):
    approved: bool
    changes: list[CriticChange] = []
    notes: str = ""
    style_score: float = 0.0
    meta: Optional[LLMMeta] = None


# ---------- run (API contract with Naman) ----------
class RunItem(BaseModel):
    id: str                      # "ri_1"
    category: str
    selected: bool = True
    execution_mode: ExecutionMode
    reason: str
    critic_note: Optional[str] = None
    score: Optional[float] = None
    product: Product


class Totals(BaseModel):
    items_usd: float = 0
    auto_buy_usd: float = 0
    cart_link_usd: float = 0
    held_usd: float = 0
    captured_usd: float = 0


class PaymentInfo(BaseModel):
    mode: Literal["stripe", "mock"] = "mock"
    payment_intent_id: Optional[str] = None
    status: Literal["none", "held", "captured", "partially_captured", "canceled", "failed"] = "none"


class MerchantResult(BaseModel):
    store: Store
    mode: ExecutionMode
    status: Literal["ordered", "cart_ready", "link_ready", "failed"]
    url: Optional[str] = None
    order_id: Optional[str] = None
    item_ids: list[str] = []
    amount_usd: float = 0
    error: Optional[str] = None


class ApiError(BaseModel):
    code: Literal["RUN_NOT_FOUND", "INVALID_STATE", "BAD_INPUT", "PAYMENT_FAILED",
                  "LLM_TIMEOUT", "INTERNAL"]
    message: str


class AuditEvent(BaseModel):
    seq: int
    ts: datetime = Field(default_factory=now)
    actor: Actor
    action: str
    summary: str
    data: dict = {}
    hash: str = ""
    prev_hash: str = ""


class Run(BaseModel):
    id: str
    user_id: str
    state: RunState
    created_at: datetime = Field(default_factory=now)
    budget_usd: float
    stores: list[Store] = ["shopify", "amazon", "walmart"]
    note: str = ""
    room: Optional[RoomProfile] = None
    items: list[RunItem] = []
    skipped: list[Skip] = []
    totals: Totals = Totals()
    payment: PaymentInfo = PaymentInfo()
    merchant_results: list[MerchantResult] = []
    error: Optional[ApiError] = None


# ---------- request bodies ----------
class ApproveBody(BaseModel):
    selected_item_ids: list[str]


class RejectBody(BaseModel):
    reason: str = ""


class CreateRunResponse(BaseModel):
    run_id: str
    state: RunState


class AuditResponse(BaseModel):
    events: list[AuditEvent]
    chain_valid: bool
