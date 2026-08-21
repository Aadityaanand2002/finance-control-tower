"""Deterministic narrative seed for demo walkthrough."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.database import Base, SessionLocal, engine
from app.models import (
    ActivityEvent,
    AuditLog,
    BankTransaction,
    Expense,
    FinancialException,
    Invoice,
    Payment,
    Refund,
    Settlement,
)
from app.exceptions.engine import upsert_exceptions_from_matches
from app.exceptions.demo_overrides import apply_demo_narrative_overrides
from app.reconciliation.engine import run_reconciliation

_IST = ZoneInfo("Asia/Kolkata")


def _dt(days_ago: int, hour: int = 10) -> datetime:
    """Demo clock: `hour` is India business time, stored as UTC."""
    now_ist = datetime.now(_IST)
    local = now_ist.replace(hour=hour, minute=0, second=0, microsecond=0) - timedelta(days=days_ago)
    return local.astimezone(timezone.utc)


def clear_all(db: Session) -> None:
    for model in (AuditLog, ActivityEvent, FinancialException, Refund, Payment, BankTransaction, Settlement, Invoice, Expense):
        db.query(model).delete()
    db.commit()


def seed_database(db: Session | None = None) -> dict:
    own_session = db is None
    if own_session:
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()

    try:
        clear_all(db)

        # --- Invoices ---
        invoices = [
            Invoice(id="inv_2001", customer="Acme Retail Pvt Ltd", amount=18_450_00, due_date=_dt(20), paid_amount=18_450_00, status="paid"),
            Invoice(id="inv_2002", customer="Bright Foods", amount=1_42_500_00, due_date=_dt(5), paid_amount=1_42_500_00, status="paid"),
            Invoice(id="inv_2003", customer="Nova Gadgets", amount=80_000_00, due_date=_dt(-7), paid_amount=0, status="overdue"),
            Invoice(id="inv_2004", customer="Pixel Studios", amount=45_000_00, due_date=_dt(-3), paid_amount=20_000_00, status="partial"),
        ]
        db.add_all(invoices)

        # --- Settlements (created before payments for FK) ---
        settlements = [
            # Scenario 1 — Perfect Match
            Settlement(
                id="set_1001",
                gross_amount=18_450_00,
                fee=330_00,
                tax=59_40,
                expected_amount=18_060_60,
                settled_amount=None,
                settlement_date=_dt(12),
                utr="UTR1001PERFECT",
                status="pending",
            ),
            # Scenario 2 — Fee Discrepancy (~₹530)
            Settlement(
                id="set_1002",
                gross_amount=18_450_00,
                fee=330_00,
                tax=59_40,
                expected_amount=18_060_60,
                settled_amount=None,
                settlement_date=_dt(10),
                utr="UTR1002FEEGAP",
                status="pending",
            ),
            # Scenario 3/8 — Partial / High-value Critical SET_1024
            Settlement(
                id="set_1024",
                gross_amount=1_42_500_00,
                fee=2_500_00,
                tax=450_00,
                expected_amount=1_39_550_00,  # will show story as 1,42,500 expected in UI narrative — use gross as expected for centerpiece
                settled_amount=None,
                settlement_date=_dt(3),
                utr="UTR1024PARTIAL",
                status="pending",
                notes="High-value settlement — demo centerpiece",
            ),
            # Fix: demo wants expected 1,42,500 and actual 1,00,000 difference 42,500
            # Scenario 4 — Missing Bank
            Settlement(
                id="set_1004",
                gross_amount=25_000_00,
                fee=450_00,
                tax=81_00,
                expected_amount=24_469_00,
                settled_amount=None,
                settlement_date=_dt(4),
                utr="UTR1004MISSING",
                status="pending",
            ),
            # Scenario 5 — Duplicate bank (settlement matches one)
            Settlement(
                id="set_1005",
                gross_amount=12_000_00,
                fee=216_00,
                tax=38_88,
                expected_amount=11_745_12,
                settled_amount=None,
                settlement_date=_dt(6),
                utr="UTR1005DUPLICATE",
                status="pending",
            ),
            # Scenario 6 — Recurring ₹500–600 anomalies
            Settlement(id="set_1006", gross_amount=50_000_00, fee=900_00, tax=162_00, expected_amount=48_938_00, settlement_date=_dt(14), utr="UTR1006REC", status="pending"),
            Settlement(id="set_1007", gross_amount=48_000_00, fee=864_00, tax=155_52, expected_amount=46_980_48, settlement_date=_dt(11), utr="UTR1007REC", status="pending"),
            Settlement(id="set_1008", gross_amount=52_000_00, fee=936_00, tax=168_48, expected_amount=50_895_52, settlement_date=_dt(8), utr="UTR1008REC", status="pending"),
            Settlement(id="set_1009", gross_amount=49_500_00, fee=891_00, tax=160_38, expected_amount=48_448_62, settlement_date=_dt(5), utr="UTR1009REC", status="pending"),
            # Scenario 7 — Refund impact settlement
            Settlement(
                id="set_1010",
                gross_amount=30_000_00,
                fee=540_00,
                tax=97_20,
                expected_amount=29_362_80,
                settlement_date=_dt(2),
                utr="UTR1010REFUND",
                status="pending",
            ),
            # Extra healthy
            Settlement(
                id="set_1011",
                gross_amount=9_999_00,
                fee=180_00,
                tax=32_40,
                expected_amount=9_786_60,
                settlement_date=_dt(1),
                utr="UTR1011OK",
                status="pending",
            ),
            # Large missing settlement to push unreconciled toward ~₹2.84L demo narrative
            Settlement(
                id="set_1030",
                gross_amount=2_06_928_88,
                fee=3_600_00,
                tax=648_00,
                expected_amount=2_02_680_88,
                settlement_date=_dt(1),
                utr="UTR1030LARGE",
                status="pending",
                notes="Large pending settlement — missing bank credit",
            ),
        ]
        # Override set_1024 expected to 1,42,500.00 for demo narrative
        for s in settlements:
            if s.id == "set_1024":
                s.gross_amount = 1_42_500_00
                s.fee = 0
                s.tax = 0
                s.expected_amount = 1_42_500_00
        db.add_all(settlements)
        db.flush()

        payments = [
            Payment(id="pay_1001", order_id="order_1001", customer_id="cust_acme", amount=18_450_00, currency="INR", payment_method="upi", status="captured", fee=330_00, tax=59_40, created_at=_dt(13), captured_at=_dt(13, 11), settlement_id="set_1001", invoice_id="inv_2001"),
            Payment(id="pay_1002", order_id="order_1002", customer_id="cust_acme", amount=18_450_00, currency="INR", payment_method="card", status="captured", fee=330_00, tax=59_40, created_at=_dt(11), captured_at=_dt(11, 11), settlement_id="set_1002", invoice_id=None),
            Payment(id="pay_1024a", order_id="order_1024", customer_id="cust_bright", amount=90_000_00, currency="INR", payment_method="netbanking", status="captured", fee=0, tax=0, created_at=_dt(4), captured_at=_dt(4, 12), settlement_id="set_1024", invoice_id="inv_2002"),
            Payment(id="pay_1024b", order_id="order_1024b", customer_id="cust_bright", amount=52_500_00, currency="INR", payment_method="upi", status="captured", fee=0, tax=0, created_at=_dt(4), captured_at=_dt(4, 13), settlement_id="set_1024", invoice_id="inv_2002"),
            Payment(id="pay_1004", order_id="order_1004", customer_id="cust_nova", amount=25_000_00, currency="INR", payment_method="upi", status="captured", fee=450_00, tax=81_00, created_at=_dt(5), captured_at=_dt(5, 10), settlement_id="set_1004"),
            Payment(id="pay_1005", order_id="order_1005", customer_id="cust_pixel", amount=12_000_00, currency="INR", payment_method="card", status="captured", fee=216_00, tax=38_88, created_at=_dt(7), captured_at=_dt(7, 10), settlement_id="set_1005"),
            Payment(id="pay_1006", order_id="order_1006", customer_id="cust_a", amount=50_000_00, currency="INR", payment_method="upi", status="captured", fee=900_00, tax=162_00, created_at=_dt(15), captured_at=_dt(15), settlement_id="set_1006"),
            Payment(id="pay_1007", order_id="order_1007", customer_id="cust_b", amount=48_000_00, currency="INR", payment_method="upi", status="captured", fee=864_00, tax=155_52, created_at=_dt(12), captured_at=_dt(12), settlement_id="set_1007"),
            Payment(id="pay_1008", order_id="order_1008", customer_id="cust_c", amount=52_000_00, currency="INR", payment_method="card", status="captured", fee=936_00, tax=168_48, created_at=_dt(9), captured_at=_dt(9), settlement_id="set_1008"),
            Payment(id="pay_1009", order_id="order_1009", customer_id="cust_d", amount=49_500_00, currency="INR", payment_method="upi", status="captured", fee=891_00, tax=160_38, created_at=_dt(6), captured_at=_dt(6), settlement_id="set_1009"),
            Payment(id="pay_1010", order_id="order_1010", customer_id="cust_e", amount=30_000_00, currency="INR", payment_method="upi", status="captured", fee=540_00, tax=97_20, created_at=_dt(3), captured_at=_dt(3), settlement_id="set_1010"),
            Payment(id="pay_1011", order_id="order_1011", customer_id="cust_f", amount=9_999_00, currency="INR", payment_method="upi", status="captured", fee=180_00, tax=32_40, created_at=_dt(2), captured_at=_dt(2), settlement_id="set_1011"),
            Payment(id="pay_1030", order_id="order_1030", customer_id="cust_enterprise", amount=2_00_000_00, currency="INR", payment_method="netbanking", status="captured", fee=3_600_00, tax=648_00, created_at=_dt(2), captured_at=_dt(2), settlement_id="set_1030"),
        ]
        db.add_all(payments)

        # Bank transactions
        banks = [
            # Perfect match
            BankTransaction(id="bank_1001", date=_dt(12, 14), description="NEFT RAZORPAY SET_1001", reference="set_1001", amount=18_060_60, type="credit", utr="UTR1001PERFECT", bank="HDFC"),
            # Fee discrepancy: expected 18060.60, received 17530.60 → Δ530
            BankTransaction(id="bank_1002", date=_dt(10, 15), description="NEFT RAZORPAY SET_1002", reference="set_1002", amount=17_530_60, type="credit", utr="UTR1002FEEGAP", bank="HDFC"),
            # Partial: expected 142500, received 100000 → Δ42500
            BankTransaction(id="bank_1024", date=_dt(3, 16), description="NEFT RAZORPAY SET_1024 PARTIAL", reference="set_1024", amount=1_00_000_00, type="credit", utr="UTR1024PARTIAL", bank="ICICI"),
            # set_1004 — NO bank entry (missing)
            # Duplicate
            BankTransaction(id="bank_1005a", date=_dt(6, 12), description="NEFT RAZORPAY SET_1005", reference="set_1005", amount=11_745_12, type="credit", utr="UTR1005DUPLICATE", bank="HDFC"),
            BankTransaction(id="bank_1005b", date=_dt(6, 12), description="NEFT RAZORPAY SET_1005 DUP", reference="set_1005", amount=11_745_12, type="credit", utr="UTR1005DUPLICATE", bank="HDFC"),
            # Recurring ~₹530/510/520/515 shortfalls
            BankTransaction(id="bank_1006", date=_dt(14, 13), description="NEFT SET_1006", reference="set_1006", amount=48_938_00 - 530_00, type="credit", utr="UTR1006REC", bank="HDFC"),
            BankTransaction(id="bank_1007", date=_dt(11, 13), description="NEFT SET_1007", reference="set_1007", amount=46_980_48 - 510_00, type="credit", utr="UTR1007REC", bank="HDFC"),
            BankTransaction(id="bank_1008", date=_dt(8, 13), description="NEFT SET_1008", reference="set_1008", amount=50_895_52 - 520_00, type="credit", utr="UTR1008REC", bank="HDFC"),
            BankTransaction(id="bank_1009", date=_dt(5, 13), description="NEFT SET_1009", reference="set_1009", amount=48_448_62 - 515_00, type="credit", utr="UTR1009REC", bank="HDFC"),
            # Refund settlement — matched but refund reduces cash
            BankTransaction(id="bank_1010", date=_dt(2, 14), description="NEFT SET_1010", reference="set_1010", amount=29_362_80, type="credit", utr="UTR1010REFUND", bank="HDFC"),
            BankTransaction(id="bank_1011", date=_dt(1, 14), description="NEFT SET_1011", reference="set_1011", amount=9_786_60, type="credit", utr="UTR1011OK", bank="HDFC"),
            # Operating debits (expenses paid) for cash position
            BankTransaction(id="bank_exp1", date=_dt(7), description="VENDOR PAY AWS", reference="exp_cloud", amount=85_000_00, type="debit", utr="UTRDEB1", bank="HDFC"),
            BankTransaction(id="bank_exp2", date=_dt(9), description="VENDOR PAY LOGISTICS", reference="exp_log", amount=1_20_000_00, type="debit", utr="UTRDEB2", bank="HDFC"),
            # Opening cash credit
            BankTransaction(id="bank_open", date=_dt(30), description="OPENING BALANCE TRANSFER", reference="open", amount=8_50_000_00, type="credit", utr="UTROPEN", bank="HDFC"),
        ]
        db.add_all(banks)

        # Refund
        db.add(Refund(id="ref_1010", payment_id="pay_1010", amount=5_000_00, reason="Customer cancelled order", status="pending", created_at=_dt(1)))

        # Expenses — Scenario 9 cash risk (upcoming large expenses)
        expenses = [
            Expense(id="exp_1", category="Cloud", vendor="AWS India", amount=95_000_00, date=_dt(2), payment_status="pending"),
            Expense(id="exp_2", category="Logistics", vendor="Delhivery", amount=1_10_000_00, date=_dt(1), payment_status="due"),
            Expense(id="exp_3", category="Marketing", vendor="Meta Ads", amount=75_000_00, date=_dt(0), payment_status="scheduled"),
            Expense(id="exp_4", category="Payroll", vendor="Payroll Vendor", amount=2_60_000_00, date=_dt(-2), payment_status="pending"),
            Expense(id="exp_5", category="SaaS", vendor="Notion", amount=12_000_00, date=_dt(20), payment_status="paid"),
            Expense(id="exp_6", category="Cloud", vendor="AWS India", amount=70_000_00, date=_dt(35), payment_status="paid"),
        ]
        db.add_all(expenses)

        db.add_all(
            [
                ActivityEvent(id="act_seed_1", event_type="seed", message="Demo dataset loaded with 9 narrative scenarios", entity_id=None, created_at=_dt(0, 8)),
                ActivityEvent(id="act_seed_2", event_type="reconciliation", message="Initial reconciliation queued", entity_id=None, created_at=_dt(0, 8)),
            ]
        )

        db.commit()

        # Run reconciliation + exception creation
        matches = run_reconciliation(db)
        created, updated = upsert_exceptions_from_matches(db, matches)
        apply_demo_narrative_overrides(db)

        # Enrich set_1024 narrative copy for demo centerpiece
        exc_1024 = db.query(FinancialException).filter(FinancialException.entity_id == "set_1024").first()
        if exc_1024:
            exc_1024.explanation = (
                "Settlement discrepancy detected: ₹42,500.00. "
                "Expected ₹1,42,500.00 but received ₹1,00,000.00. "
                "A ₹42,500.00 discrepancy remains unexplained at payment aggregation level — partial settlement detected."
            )
            exc_1024.priority_reasons = [
                "₹42,500.00 affected",
                "large financial exposure relative to typical discrepancies",
                "confidence of anomaly = 94%",
                "settlement is overdue or high-value exposure",
            ]
            exc_1024.reasoning = [
                "Expected settlement amount: ₹1,42,500.00",
                "Actual bank credit: ₹1,00,000.00",
                "Difference: ₹42,500.00",
                "This exception is 3.8× larger than the merchant's average discrepancy.",
            ]
            db.commit()

        # Sample audit
        db.add(
            AuditLog(
                id="aud_seed_1",
                exception_id=exc_1024.id if exc_1024 else None,
                entity_id="set_1024",
                entity_type="settlement",
                action="Exception auto-detected",
                performed_by="System",
                timestamp=_dt(0, 9),
                old_state=None,
                new_state="open",
                explanation="Reconciliation engine flagged partial settlement",
                ai_recommendation="Request settlement review",
                user_decision=None,
            )
        )
        db.commit()

        unreconciled = sum(
            e.amount_affected
            for e in db.query(FinancialException).filter(
                FinancialException.status.in_(["open", "under_review", "action_approved"])
            ).all()
        )

        return {
            "settlements": len(settlements),
            "payments": len(payments),
            "banks": len(banks),
            "exceptions_created": created,
            "exceptions_updated": updated,
            "unreconciled_amount": unreconciled,
            "matches": len(matches),
        }
    finally:
        if own_session:
            db.close()


if __name__ == "__main__":
    result = seed_database()
    print("Seed complete:", result)
