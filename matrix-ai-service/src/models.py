"""Pydantic contracts. Source: AI_Service_Assistant_Design.md section 10."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from src.order_ids import normalize

Intent = Literal["order_status", "delivery_delay", "cancel", "return", "damaged_item", "other"]

PolicyId = Literal["POL-01", "POL-02", "POL-03", "POL-04", "POL-05", "POL-06", "POL-07"]

ORDER_ID_PATTERN = r"^ORD-\d{4}$"

# A clarification follow-up names what was asked and about which order, e.g.
# "return:ORD-1003" (A8). Structured on purpose: it is not a second free-text
# channel into the model.
CONTEXT_PATTERN = r"^(order_status|delivery_delay|cancel|return|damaged_item|other):ORD-\d{4}$"


class AgentInput(BaseModel):
    customer_id: str = Field(pattern=r"^C-\d{3}$")
    message: str = Field(min_length=1, max_length=2000)
    context: str | None = Field(default=None, max_length=40, pattern=CONTEXT_PATTERN)


class Extraction(BaseModel):
    intent: Intent
    order_ids: list[str]
    product_state: Literal["opened", "unopened", "unknown"]
    asks_compensation: bool
    language: Literal["he", "en"]

    @model_validator(mode="after")
    def normalize_order_ids(self) -> "Extraction":
        # "ord-1001" / "ORD 1001" -> "ORD-1001"; malformed dropped; duplicates
        # collapsed so "ORD-1001 ... ORD-1001" is one order, not two.
        normalized: list[str] = []
        for raw in self.order_ids:
            oid = normalize(raw)
            if oid and oid not in normalized:
                normalized.append(oid)
        self.order_ids = normalized
        return self


class Order(BaseModel):
    """Shape an order record must have before the policy engine may use it.
    A record that fails this is treated as a data-quality failure (escalate),
    never guessed around."""

    order_id: str = Field(pattern=ORDER_ID_PATTERN)
    customer_id: str
    status: str
    estimated_delivery: date
    delivered_at: date | None

    @model_validator(mode="after")
    def delivered_needs_date(self) -> "Order":
        if self.status == "delivered" and self.delivered_at is None:
            raise ValueError("status=delivered requires delivered_at")
        return self


class ServiceRequestRef(BaseModel):
    type: Literal["cancellation", "return", "shipping_inquiry", "agent_handoff"]
    id: str


class AgentResponse(BaseModel):
    intent: Intent
    action: Literal["reply", "clarify", "escalate"]
    reply: str = Field(min_length=1)
    order_id: str | None = Field(default=None, pattern=ORDER_ID_PATTERN)
    source_ids: list[PolicyId] = Field(min_length=1)
    service_request: ServiceRequestRef | None = None
    reason: str

    @model_validator(mode="after")
    def consistency(self) -> "AgentResponse":
        if self.service_request is not None and self.order_id is None:
            raise ValueError("service_request requires order_id")
        if self.action == "clarify" and self.service_request is not None:
            raise ValueError("clarify must not open a service_request")
        return self
