from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(64), index=True)
    customer_id: Mapped[str] = mapped_column(String(64), index=True)
    amount: Mapped[int] = mapped_column(Integer)  # paise
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    payment_method: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), index=True)
    fee: Mapped[int] = mapped_column(Integer, default=0)
    tax: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    settlement_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("settlements.id"), nullable=True, index=True)
    invoice_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("invoices.id"), nullable=True)

    settlement = relationship("Settlement", back_populates="payments", foreign_keys=[settlement_id])
    refunds = relationship("Refund", back_populates="payment")


class Settlement(Base):
    __tablename__ = "settlements"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    gross_amount: Mapped[int] = mapped_column(Integer)
    fee: Mapped[int] = mapped_column(Integer, default=0)
    tax: Mapped[int] = mapped_column(Integer, default=0)
    expected_amount: Mapped[int] = mapped_column(Integer)
    settled_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    settlement_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    utr: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)  # pending, processed, mismatched, etc.
    reconciliation_status: Mapped[str | None] = mapped_column(String(48), nullable=True, index=True)
    match_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    payments = relationship("Payment", back_populates="settlement", foreign_keys="Payment.settlement_id")
    bank_transactions = relationship("BankTransaction", back_populates="settlement")


class BankTransaction(Base):
    __tablename__ = "bank_transactions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    description: Mapped[str] = mapped_column(String(512))
    reference: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    amount: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(16))  # credit / debit
    utr: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    bank: Mapped[str] = mapped_column(String(64), default="HDFC")
    settlement_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("settlements.id"), nullable=True, index=True)
    reconciliation_status: Mapped[str | None] = mapped_column(String(48), nullable=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)

    settlement = relationship("Settlement", back_populates="bank_transactions")


class Refund(Base):
    __tablename__ = "refunds"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    payment_id: Mapped[str] = mapped_column(String(64), ForeignKey("payments.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    payment = relationship("Payment", back_populates="refunds")


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer: Mapped[str] = mapped_column(String(128))
    amount: Mapped[int] = mapped_column(Integer)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    paid_amount: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), index=True)


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    vendor: Mapped[str] = mapped_column(String(128), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    payment_status: Mapped[str] = mapped_column(String(32))


class FinancialException(Base):
    __tablename__ = "exceptions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(32), index=True)
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(32), default="settlement")
    amount_affected: Mapped[int] = mapped_column(Integer)
    expected_value: Mapped[int] = mapped_column(Integer)
    actual_value: Mapped[int] = mapped_column(Integer)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_cause: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(48), index=True, default="open")
    priority_score: Mapped[float] = mapped_column(Float, default=0.0)
    priority_reasons: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    pattern_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evidence: Mapped[list | None] = mapped_column(JSON, nullable=True)
    reasoning: Mapped[list | None] = mapped_column(JSON, nullable=True)
    requires_human_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    related_payment_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    related_bank_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    exception_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("exceptions.id"), nullable=True, index=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(128))
    performed_by: Mapped[str] = mapped_column(String(128))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    old_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    new_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_decision: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ActivityEvent(Base):
    __tablename__ = "activity_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(String(512))
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
