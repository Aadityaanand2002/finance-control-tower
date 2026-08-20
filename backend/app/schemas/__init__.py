from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class PaymentOut(BaseModel):
    id: str
    order_id: str
    customer_id: str
    amount: int
    currency: str
    payment_method: str
    status: str
    fee: int
    tax: int
    created_at: datetime
    captured_at: Optional[datetime] = None
    settlement_id: Optional[str] = None
    invoice_id: Optional[str] = None

    model_config = {"from_attributes": True}


class SettlementOut(BaseModel):
    id: str
    gross_amount: int
    fee: int
    tax: int
    expected_amount: int
    settled_amount: Optional[int] = None
    settlement_date: datetime
    utr: Optional[str] = None
    status: str
    reconciliation_status: Optional[str] = None
    match_confidence: Optional[float] = None
    notes: Optional[str] = None
    payment_ids: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class BankTransactionOut(BaseModel):
    id: str
    date: datetime
    description: str
    reference: Optional[str] = None
    amount: int
    type: str
    utr: Optional[str] = None
    bank: str
    settlement_id: Optional[str] = None
    reconciliation_status: Optional[str] = None
    is_duplicate: bool = False

    model_config = {"from_attributes": True}


class RefundOut(BaseModel):
    id: str
    payment_id: str
    amount: int
    reason: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class InvoiceOut(BaseModel):
    id: str
    customer: str
    amount: int
    due_date: datetime
    paid_amount: int
    status: str

    model_config = {"from_attributes": True}


class ExpenseOut(BaseModel):
    id: str
    category: str
    vendor: str
    amount: int
    date: datetime
    payment_status: str

    model_config = {"from_attributes": True}


class ExceptionOut(BaseModel):
    id: str
    type: str
    severity: str
    entity_id: str
    entity_type: str
    amount_affected: int
    expected_value: int
    actual_value: int
    explanation: Optional[str] = None
    root_cause: Optional[str] = None
    confidence: float
    recommended_action: Optional[str] = None
    status: str
    priority_score: float
    priority_reasons: Optional[list[str] | dict[str, Any]] = None
    pattern_info: Optional[dict[str, Any]] = None
    evidence: Optional[list[Any]] = None
    reasoning: Optional[list[Any]] = None
    requires_human_approval: bool = True
    created_at: datetime
    resolved_at: Optional[datetime] = None
    related_payment_ids: Optional[list[str]] = None
    related_bank_ids: Optional[list[str]] = None

    model_config = {"from_attributes": True}


class AuditLogOut(BaseModel):
    id: str
    exception_id: Optional[str] = None
    entity_id: Optional[str] = None
    entity_type: Optional[str] = None
    action: str
    performed_by: str
    timestamp: datetime
    old_state: Optional[str] = None
    new_state: Optional[str] = None
    explanation: Optional[str] = None
    ai_recommendation: Optional[str] = None
    user_decision: Optional[str] = None

    model_config = {"from_attributes": True}


class ActivityEventOut(BaseModel):
    id: str
    event_type: str
    message: str
    entity_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AIAnalysisResult(BaseModel):
    summary: str
    severity: str
    amount_affected: int
    root_cause: str
    confidence: float
    evidence: list[str] = Field(default_factory=list)
    recommended_action: str
    reasoning: list[str] = Field(default_factory=list)
    requires_human_approval: bool = True
    fallback_used: bool = False
    fallback_message: Optional[str] = None


class AIQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)


class AIQueryResponse(BaseModel):
    answer: str
    supporting_records: list[dict[str, Any]] = Field(default_factory=list)
    calculations: list[str] = Field(default_factory=list)
    reasoning: list[str] = Field(default_factory=list)
    recommended_action: Optional[str] = None
    fallback_used: bool = False


class ActionRequest(BaseModel):
    note: Optional[str] = None
    performed_by: Optional[str] = None


class DashboardOut(BaseModel):
    total_payments: int
    total_settled: int
    pending_settlement: int
    unreconciled_amount: int
    active_exceptions: int
    high_risk_exceptions: int
    expected_cash_position: int
    recoverable_at_risk: int
    reconciliation_percentage: float
    settlement_status_distribution: dict[str, int]
    exception_severity_distribution: dict[str, int]
    cash_position_trend: list[dict[str, Any]]
    recent_high_priority_exceptions: list[ExceptionOut]
    activity_stream: list[ActivityEventOut]


class CashPositionOut(BaseModel):
    available_cash: int
    expected_settlements: int
    pending_receivables: int
    upcoming_expenses: int
    outstanding_refunds: int
    at_risk_unreconciled: int
    projected_net_cash: int
    calculation_steps: list[str]
    control_adjusted_label: str = "Current Control-Adjusted Cash Position"


class ReconciliationMatchOut(BaseModel):
    settlement_id: str
    payment_ids: list[str]
    bank_ids: list[str]
    status: str
    expected_amount: int
    actual_amount: int
    difference: int
    confidence: float
    signals: list[str]
    explanation: str


class ReconciliationRunResult(BaseModel):
    matches: list[ReconciliationMatchOut]
    exceptions_created: int
    exceptions_updated: int
    message: str


class SimulationResult(BaseModel):
    events: list[ActivityEventOut]
    exceptions_created: list[str]
    message: str


class HealthOut(BaseModel):
    status: str
    demo_mode: bool
    ai_provider: str
    data_provider: str
    database: str


class ExceptionDetailOut(BaseModel):
    exception: ExceptionOut
    payments: list[PaymentOut] = Field(default_factory=list)
    settlement: Optional[SettlementOut] = None
    bank_transactions: list[BankTransactionOut] = Field(default_factory=list)
    audit_trail: list[AuditLogOut] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)
