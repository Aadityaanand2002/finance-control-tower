"""Demo simulation — inject live financial events."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import ActivityEvent, BankTransaction, Expense, Invoice, Payment, Refund, Settlement
from app.exceptions.engine import upsert_exceptions_from_matches
from app.exceptions.demo_overrides import apply_demo_narrative_overrides
from app.reconciliation.engine import run_reconciliation
from app.schemas import ActivityEventOut, SimulationResult


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _event(db: Session, event_type: str, message: str, entity_id: str | None = None) -> ActivityEvent:
    ev = ActivityEvent(
        id=f"act_{uuid.uuid4().hex[:10]}",
        event_type=event_type,
        message=message,
        entity_id=entity_id,
        created_at=_now(),
    )
    db.add(ev)
    return ev


def run_simulation(db: Session) -> SimulationResult:
    suffix = uuid.uuid4().hex[:6]
    settlement_id = f"set_sim_{suffix}"
    payment_id = f"pay_sim_{suffix}"
    bank_id = f"bank_sim_{suffix}"
    utr = f"UTRSIM{suffix.upper()}"

    gross = 22_000_00
    fee = 396_00
    tax = 71_28
    expected = gross - fee - tax
    # Intentional discrepancy ~₹480
    actual = expected - 480_00

    events: list[ActivityEvent] = []

    payment = Payment(
        id=payment_id,
        order_id=f"order_sim_{suffix}",
        customer_id="cust_sim",
        amount=gross,
        currency="INR",
        payment_method="upi",
        status="captured",
        fee=fee,
        tax=tax,
        created_at=_now(),
        captured_at=_now(),
        settlement_id=None,
    )
    db.add(payment)
    events.append(_event(db, "payment", f"Payment received {payment_id} ₹{gross/100:,.2f}", payment_id))
    db.flush()

    settlement = Settlement(
        id=settlement_id,
        gross_amount=gross,
        fee=fee,
        tax=tax,
        expected_amount=expected,
        settlement_date=_now(),
        utr=utr,
        status="pending",
    )
    db.add(settlement)
    payment.settlement_id = settlement_id
    events.append(_event(db, "settlement", f"Settlement processed {settlement_id}", settlement_id))
    db.flush()

    bank = BankTransaction(
        id=bank_id,
        date=_now(),
        description=f"NEFT RAZORPAY {settlement_id}",
        reference=settlement_id,
        amount=actual,
        type="credit",
        utr=utr,
        bank="HDFC",
    )
    db.add(bank)
    events.append(_event(db, "bank", f"Bank transaction detected {bank_id}", bank_id))

    # Bonus: small refund + invoice noise
    refund = Refund(
        id=f"ref_sim_{suffix}",
        payment_id=payment_id,
        amount=500_00,
        reason="Simulated partial refund",
        status="pending",
        created_at=_now(),
    )
    db.add(refund)
    events.append(_event(db, "refund", f"Refund created ref_sim_{suffix}", refund.id))

    invoice = Invoice(
        id=f"inv_sim_{suffix}",
        customer="Sim Customer",
        amount=22_000_00,
        due_date=_now(),
        paid_amount=22_000_00,
        status="paid",
    )
    db.add(invoice)
    events.append(_event(db, "invoice", f"Invoice recorded {invoice.id}", invoice.id))

    expense = Expense(
        id=f"exp_sim_{suffix}",
        category="Ops",
        vendor="Sim Vendor",
        amount=3_500_00,
        date=_now(),
        payment_status="pending",
    )
    db.add(expense)
    events.append(_event(db, "expense", f"Expense recorded {expense.id}", expense.id))

    db.commit()

    events.append(_event(db, "reconciliation", "Reconciliation completed", settlement_id))
    db.commit()

    matches = run_reconciliation(db)
    created, _ = upsert_exceptions_from_matches(db, matches)
    apply_demo_narrative_overrides(db)
    events.append(_event(db, "exception", f"Exception detected for {settlement_id}", settlement_id))
    events.append(_event(db, "ai", "AI root-cause analysis completed", settlement_id))
    db.commit()

    new_exc_ids = [
        e.id
        for e in db.query(__import__("app.models", fromlist=["FinancialException"]).FinancialException)
        .filter_by(entity_id=settlement_id)
        .all()
    ]

    return SimulationResult(
        events=[ActivityEventOut.model_validate(e) for e in events],
        exceptions_created=new_exc_ids,
        message=f"Simulation injected payment/settlement/bank with ₹480 discrepancy. {created} exception(s) created.",
    )


def generate_new_exception(db: Session) -> SimulationResult:
    suffix = uuid.uuid4().hex[:6]
    settlement_id = f"set_gen_{suffix}"
    payment_id = f"pay_gen_{suffix}"
    bank_id = f"bank_gen_{suffix}"
    utr = f"UTRGEN{suffix.upper()}"

    expected = 75_000_00
    actual = 60_000_00  # ₹15,000 gap — high

    db.add(
        Payment(
            id=payment_id,
            order_id=f"order_gen_{suffix}",
            customer_id="cust_gen",
            amount=expected,
            currency="INR",
            payment_method="card",
            status="captured",
            fee=0,
            tax=0,
            created_at=_now(),
            captured_at=_now(),
            settlement_id=settlement_id,
        )
    )
    db.add(
        Settlement(
            id=settlement_id,
            gross_amount=expected,
            fee=0,
            tax=0,
            expected_amount=expected,
            settlement_date=_now(),
            utr=utr,
            status="pending",
        )
    )
    db.add(
        BankTransaction(
            id=bank_id,
            date=_now(),
            description=f"NEFT {settlement_id}",
            reference=settlement_id,
            amount=actual,
            type="credit",
            utr=utr,
            bank="ICICI",
        )
    )
    events = [
        _event(db, "payment", f"Generated payment {payment_id}", payment_id),
        _event(db, "settlement", f"Generated settlement {settlement_id}", settlement_id),
        _event(db, "bank", f"Generated bank credit {bank_id}", bank_id),
    ]
    db.commit()
    matches = run_reconciliation(db)
    upsert_exceptions_from_matches(db, matches)
    apply_demo_narrative_overrides(db)
    events.append(_event(db, "exception", f"New exception generated for {settlement_id}", settlement_id))
    events.append(_event(db, "ai", "AI analysis ready", settlement_id))
    db.commit()

    from app.models import FinancialException

    exc_ids = [e.id for e in db.query(FinancialException).filter_by(entity_id=settlement_id).all()]
    return SimulationResult(
        events=[ActivityEventOut.model_validate(e) for e in events],
        exceptions_created=exc_ids,
        message=f"Generated high-value exception on {settlement_id} (₹15,000 gap).",
    )
