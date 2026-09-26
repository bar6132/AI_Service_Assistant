"""Pydantic contracts. Source: AI_Service_Assistant_Design.md section 10."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

Intent = Literal["order_status", "delivery_delay", "cancel", "return", "damaged_item", "other"]

PolicyId = Literal["POL-01", "POL-02", "POL-03", "POL-04", "POL-05", "POL-06", "POL-07"]

ORDER_ID_PATTERN = r"^ORD-\d{4}$"


class AgentInput(BaseModel):
    customer_id: str = Field(pattern=r"^C-\d{3}$")
    message: str = Field(min_length=1, max_length=2000)
    context: str | None = None


class Extraction(BaseModel):
    intent: Intent
    order_ids: list[str]
    product_state: Literal["opened", "unopened", "unknown"]
    asks_compensation: bool
    language: Literal["he", "en"]

    @model_validator(mode="after")
    def drop_malformed_order_ids(self) -> "Extraction":
        import re

        self.order_ids = [oid for oid in self.order_ids if re.match(ORDER_ID_PATTERN, oid)]
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
